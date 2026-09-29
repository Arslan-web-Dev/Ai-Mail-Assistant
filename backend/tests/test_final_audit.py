"""
Module 8 final audit tests — verifying the specific issues found and
fixed during the security/code audit (see README's audit table):

1. Pagination cursor filter-injection hardening
2. Search-string filter-injection hardening
3. Race condition in get_or_create_row (duplicate-key handling)
4. Global exception handler never leaks internal error details
5. Duplicate-email prevention at the sync layer
6. Malformed email parsing doesn't crash
7. Deep health check endpoint shape
"""
import base64
import json

import jwt
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from services import automation_service
from services.db_utils import get_or_create_row
from services.email_parser import parse_gmail_message
from utils.pagination import apply_keyset_filter, decode_cursor, encode_cursor

client = TestClient(app)


def _valid_token(sub: str = "user-1") -> str:
    import time

    payload = {"sub": sub, "email": "u@example.com", "aud": "authenticated", "exp": int(time.time()) + 3600}
    return jwt.encode(payload, settings.supabase_jwt_secret or "test-secret", algorithm="HS256")


# ---------------------------------------------------------------------
# 1. Cursor injection hardening
# ---------------------------------------------------------------------


def _forged_cursor(v: str, id_: str) -> str:
    payload = json.dumps({"v": v, "id": id_})
    return base64.urlsafe_b64encode(payload.encode()).decode()


def test_legitimate_cursor_still_works():
    cursor = encode_cursor("2026-01-01T00:00:00+00:00", "abc-123")
    value, id_ = decode_cursor(cursor)
    assert value == "2026-01-01T00:00:00+00:00"
    assert id_ == "abc-123"


def test_cursor_with_injected_filter_syntax_is_rejected():
    """
    A cursor whose decoded 'id' field tries to break out of the intended
    PostgREST filter clause (via a comma/parenthesis) must be rejected,
    not silently interpolated into the query.
    """
    forged = _forged_cursor("2026-01-01T00:00:00+00:00", "x),or(user_id.eq.someone-else")
    with pytest.raises(ValueError):
        decode_cursor(forged)


def test_cursor_with_injected_value_field_is_rejected():
    forged = _forged_cursor("2026-01-01),or(is_read.eq.true", "abc-123")
    with pytest.raises(ValueError):
        decode_cursor(forged)


def test_apply_keyset_filter_still_produces_expected_expression_for_safe_input():
    class _FakeQuery:
        def __init__(self):
            self.calls = []

        def or_(self, expr):
            self.calls.append(expr)
            return self

    q = _FakeQuery()
    apply_keyset_filter(q, "received_at", "2026-01-01T00:00:00+00:00", "email-1", descending=True)
    assert q.calls == [
        "received_at.lt.2026-01-01T00:00:00+00:00,and(received_at.eq.2026-01-01T00:00:00+00:00,id.lt.email-1)"
    ]


# ---------------------------------------------------------------------
# 2. Search-string injection hardening
# ---------------------------------------------------------------------


def test_email_search_endpoint_rejects_forged_injecting_cursor(monkeypatch):
    monkeypatch.setattr(settings, "supabase_jwt_secret", "test-secret")
    token = _valid_token()
    forged = _forged_cursor("x", "y),or(user_id.eq.someone-else")
    response = client.get("/api/v1/emails", headers={"Authorization": f"Bearer {token}"}, params={"cursor": forged})
    assert response.status_code == 400


def test_drafts_endpoint_rejects_forged_injecting_cursor(monkeypatch):
    monkeypatch.setattr(settings, "supabase_jwt_secret", "test-secret")
    token = _valid_token()
    forged = _forged_cursor("x", "y),or(user_id.eq.someone-else")
    response = client.get("/api/v1/drafts", headers={"Authorization": f"Bearer {token}"}, params={"cursor": forged})
    assert response.status_code == 400


# ---------------------------------------------------------------------
# 3. Race condition fix in get_or_create_row
# ---------------------------------------------------------------------


class _RaceTable:
    """Simulates: first insert always fails with a unique-violation (as if
    a concurrent request won the race), second select succeeds."""

    def __init__(self, existing_row):
        self.existing_row = existing_row
        self.select_calls = 0

    def select(self, *_a, **_k):
        return self

    def eq(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    def insert(self, _payload):
        raise Exception('duplicate key value violates unique constraint "automation_settings_user_id_key"')

    def execute(self):
        self.select_calls += 1

        class _Result:
            def __init__(self, data):
                self.data = data

        # First select (before insert attempt): nothing exists yet.
        if self.select_calls == 1:
            return _Result([])
        # Second select (after failed insert, race recovery): the row the
        # "other" concurrent request inserted is now there.
        return _Result([self.existing_row])


class _RaceDB:
    def __init__(self, table_obj):
        self.table_obj = table_obj

    def table(self, _name):
        return self.table_obj


def test_get_or_create_row_recovers_from_concurrent_insert_race():
    winner_row = {"user_id": "user-1", "auto_reply_enabled": False}
    db = _RaceDB(_RaceTable(winner_row))

    result = get_or_create_row(db, "automation_settings", "user_id", "user-1", {"auto_reply_enabled": True})

    # Must return the row that "won" the race, not raise, and not silently
    # invent a different value than what's actually stored.
    assert result == winner_row


def test_get_or_create_row_reraises_non_duplicate_errors():
    class _FailTable(_RaceTable):
        def insert(self, _payload):
            raise Exception("connection reset by peer")

    db = _RaceDB(_FailTable({"user_id": "user-1"}))
    with pytest.raises(Exception, match="connection reset"):
        get_or_create_row(db, "automation_settings", "user_id", "user-1", {})


# ---------------------------------------------------------------------
# 4. Global exception handler never leaks internal details
# ---------------------------------------------------------------------


def test_unhandled_exception_returns_generic_message_not_internal_detail(monkeypatch):
    """
    Note: uses a TestClient with raise_server_exceptions=False. Starlette's
    ServerErrorMiddleware calls our registered handler AND sends its
    response, but then deliberately re-raises the original exception too
    (so real ASGI servers can log it) — the default TestClient re-raises
    that in tests, which would make this test fail even though the
    handler worked correctly and the client actually received the right
    response. This setting lets us inspect that response instead.
    """
    monkeypatch.setattr(settings, "supabase_jwt_secret", "test-secret")
    secret_detail = "psycopg2.OperationalError: password authentication failed for user 'super_secret_internal'"

    def boom(_user_id):
        raise RuntimeError(secret_detail)

    monkeypatch.setattr(automation_service, "get_or_create_settings", boom)

    no_raise_client = TestClient(app, raise_server_exceptions=False)
    token = _valid_token()
    response = no_raise_client.get("/api/v1/automation/settings", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    assert secret_detail not in response.text
    assert "super_secret_internal" not in response.text


# ---------------------------------------------------------------------
# 5. Duplicate-email prevention (Module 3 requirement, re-verified here)
# ---------------------------------------------------------------------


class _EmailsFakeTable:
    def __init__(self, rows_by_table: dict, name: str):
        self.rows_by_table = rows_by_table
        self.name = name
        self._filters = {}

    def select(self, *_a, **_k):
        return self

    def eq(self, key, value):
        self._filters[key] = value
        return self

    def limit(self, *_a, **_k):
        return self

    def insert(self, payload):
        rows = self.rows_by_table.setdefault(self.name, [])
        row = dict(payload)
        row.setdefault("id", f"new-{self.name}-{len(rows) + 1}")
        rows.append(row)
        self._inserted = row
        return self

    def update(self, payload):
        self._pending_update = dict(payload)
        return self

    def execute(self):
        class _Result:
            def __init__(self, data):
                self.data = data

        if getattr(self, "_inserted", None) is not None:
            return _Result([self._inserted])

        rows = self.rows_by_table.get(self.name, [])
        matched = [r for r in rows if all(r.get(k) == v for k, v in self._filters.items())]

        if getattr(self, "_pending_update", None) is not None:
            for row in matched:
                row.update(self._pending_update)
            return _Result(matched)

        return _Result(matched)


def test_store_message_skips_duplicate_gmail_message_id(monkeypatch):
    from services import email_sync_service
    from services.email_parser import ParsedEmail

    rows_by_table = {"emails": [{"id": "existing-email-id", "user_id": "user-1", "gmail_message_id": "msg-1"}]}
    insert_calls = {"emails": 0}

    class _FakeDB:
        def table(self, name):
            table = _EmailsFakeTable(rows_by_table, name)
            original_insert = table.insert

            def counting_insert(payload):
                insert_calls[name] = insert_calls.get(name, 0) + 1
                return original_insert(payload)

            table.insert = counting_insert
            return table

    monkeypatch.setattr(email_sync_service, "get_supabase_admin", lambda: _FakeDB())

    parsed = ParsedEmail(
        gmail_message_id="msg-1",
        gmail_thread_id="thread-1",
        sender="a@example.com",
        recipient=None,
        subject="Hi",
        snippet="hi",
        body_text="hi",
        body_html_sanitized=None,
        labels=[],
        received_at=None,
        has_attachments=False,
    )

    stored, was_duplicate, email_id = email_sync_service._store_message("user-1", parsed)

    assert stored is False
    assert was_duplicate is True
    assert insert_calls.get("emails", 0) == 0  # never attempted a second insert into emails


# ---------------------------------------------------------------------
# 6. Malformed email parsing doesn't crash
# ---------------------------------------------------------------------


def test_parser_handles_missing_body_data_gracefully():
    message = {
        "id": "msg-1",
        "threadId": "thread-1",
        "snippet": "",
        "internalDate": "1700000000000",
        "labelIds": [],
        "payload": {
            "headers": [{"name": "From", "value": "a@example.com"}],
            "parts": [{"mimeType": "text/plain", "body": {}}],  # no "data" key at all
        },
    }
    parsed = parse_gmail_message(message)
    assert parsed.body_text == ""
    assert parsed.sender == "a@example.com"


def test_parser_handles_corrupted_base64_gracefully():
    message = {
        "id": "msg-1",
        "threadId": "thread-1",
        "snippet": "",
        "internalDate": "1700000000000",
        "labelIds": [],
        "payload": {
            "headers": [],
            "parts": [{"mimeType": "text/plain", "body": {"data": "!!!not-valid-base64!!!"}}],
        },
    }
    # Must not raise — corrupted data is simply skipped.
    parsed = parse_gmail_message(message)
    assert parsed.sender == "unknown"


def test_parser_handles_missing_payload_entirely():
    message = {"id": "msg-1", "threadId": "thread-1", "internalDate": "1700000000000"}
    parsed = parse_gmail_message(message)
    assert parsed.body_text == ""
    assert parsed.subject is None


# ---------------------------------------------------------------------
# 7. Deep health check
# ---------------------------------------------------------------------


def test_deep_health_check_is_public_and_reports_components():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert "components" in body
    for key in ("supabase", "redis", "openai", "gmail_oauth", "celery"):
        assert key in body["components"]
        assert "status" in body["components"][key]


def test_basic_health_check_still_fast_and_public():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
