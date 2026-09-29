"""
Tests for Module 5: draft management + sending.

The send flow is the safety-critical part here — these tests mock
`gmail_send_service.send_reply` (never hitting real Gmail) and focus on:
duplicate-send prevention, "never mark sent on failure", ownership checks,
recipient extraction, and pagination cursor correctness.
"""
import pytest

from services import draft_service, gmail_send_service
from services.gmail_send_service import extract_reply_address
from utils.pagination import apply_keyset_filter, decode_cursor, encode_cursor


# ---------------------------------------------------------------------
# Recipient extraction
# ---------------------------------------------------------------------


def test_extract_reply_address_from_display_name_format():
    assert extract_reply_address("Jane Recruiter <jane@example.com>") == "jane@example.com"


def test_extract_reply_address_from_bare_address():
    assert extract_reply_address("jane@example.com") == "jane@example.com"


def test_extract_reply_address_returns_none_for_garbage():
    assert extract_reply_address("not an email at all") is None


def test_extract_reply_address_handles_empty_string():
    assert extract_reply_address("") is None


# ---------------------------------------------------------------------
# Pagination cursor
# ---------------------------------------------------------------------


def test_cursor_roundtrip():
    cursor = encode_cursor("2026-01-01T00:00:00+00:00", "email-abc")
    value, id_ = decode_cursor(cursor)
    assert value == "2026-01-01T00:00:00+00:00"
    assert id_ == "email-abc"


def test_decode_cursor_rejects_garbage():
    with pytest.raises(ValueError):
        decode_cursor("not-a-real-cursor")


class _FakeQuery:
    def __init__(self):
        self.or_calls = []

    def or_(self, expr):
        self.or_calls.append(expr)
        return self


def test_apply_keyset_filter_builds_expected_expression():
    query = _FakeQuery()
    apply_keyset_filter(query, "received_at", "2026-01-01T00:00:00+00:00", "email-1", descending=True)
    assert query.or_calls == [
        "received_at.lt.2026-01-01T00:00:00+00:00,and(received_at.eq.2026-01-01T00:00:00+00:00,id.lt.email-1)"
    ]


# ---------------------------------------------------------------------
# Draft send flow (mocked Gmail + Supabase)
# ---------------------------------------------------------------------

DRAFT_ROW = {
    "id": "draft-1",
    "email_id": "email-1",
    "user_id": "user-1",
    "generated_content": "Thanks, I'll follow up shortly.",
    "edited_content": None,
    "subject": "Re: Hello",
    "status": "ready",
}

EMAIL_ROW = {
    "id": "email-1",
    "user_id": "user-1",
    "sender": "Jane Recruiter <jane@example.com>",
    "subject": "Hello",
    "gmail_thread_id": "thread-1",
    "rfc_message_id": "<orig@mail.gmail.com>",
}


class _FakeTable:
    """
    Minimal Supabase query-builder stand-in. Backed by an in-memory dict of
    tables the test configures; supports the handful of chained calls
    draft_service actually uses.
    """

    def __init__(self, data_by_table: dict, name: str):
        self.data_by_table = data_by_table
        self.name = name
        self._filters = {}
        self._payload = None
        self._select = False

    def select(self, *_a, **_k):
        self._select = True
        return self

    def eq(self, key, value):
        self._filters[key] = value
        return self

    def limit(self, _n):
        return self

    def order(self, *_a, **_k):
        return self

    def insert(self, payload):
        self._payload = dict(payload)
        rows = self.data_by_table.setdefault(self.name, [])
        rows.append(self._payload)
        return self

    def update(self, payload):
        self._payload = dict(payload)
        rows = self.data_by_table.get(self.name, [])
        for row in rows:
            if all(row.get(k) == v for k, v in self._filters.items()):
                row.update(payload)
        return self

    def execute(self):
        class _Result:
            def __init__(self, data):
                self.data = data

        if self._payload is not None and not self._select:
            return _Result([self._payload])

        rows = self.data_by_table.get(self.name, [])
        matched = [r for r in rows if all(r.get(k) == v for k, v in self._filters.items())]
        return _Result(matched)


class _FakeDB:
    def __init__(self, data_by_table: dict):
        self.data_by_table = data_by_table

    def table(self, name):
        return _FakeTable(self.data_by_table, name)


@pytest.fixture
def fake_db(monkeypatch):
    data = {
        "email_drafts": [dict(DRAFT_ROW)],
        "emails": [dict(EMAIL_ROW)],
        "sent_emails": [],
        "audit_logs": [],
        "email_processing_logs": [],
    }
    db = _FakeDB(data)
    monkeypatch.setattr(draft_service, "get_supabase_admin", lambda: db)
    return data


def test_approve_and_send_success(monkeypatch, fake_db):
    sent = {}

    def fake_send_reply(**kwargs):
        sent.update(kwargs)
        return {"id": "gmail-msg-1", "threadId": "thread-1"}

    monkeypatch.setattr(gmail_send_service, "send_reply", fake_send_reply)
    monkeypatch.setattr(draft_service.gmail_send_service, "send_reply", fake_send_reply)

    result = draft_service.approve_and_send_draft("user-1", "draft-1")

    assert result["status"] == "sent"
    assert sent["recipient"] == "jane@example.com"
    assert len(fake_db["sent_emails"]) == 1
    assert fake_db["sent_emails"][0]["gmail_message_id"] == "gmail-msg-1"
    assert len(fake_db["audit_logs"]) == 1


def test_approve_and_send_rejects_already_sent_draft(monkeypatch, fake_db):
    fake_db["email_drafts"][0]["status"] = "sent"

    with pytest.raises(draft_service.DraftAlreadySentError):
        draft_service.approve_and_send_draft("user-1", "draft-1")


def test_approve_and_send_rejects_duplicate_reply_to_same_email(monkeypatch, fake_db):
    # Simulate an existing sent_emails row for this email (e.g. from a race).
    fake_db["sent_emails"].append({"id": "sent-1", "email_id": "email-1", "user_id": "user-1"})

    with pytest.raises(draft_service.DraftAlreadySentError):
        draft_service.approve_and_send_draft("user-1", "draft-1")


def test_approve_and_send_never_marks_sent_on_gmail_failure(monkeypatch, fake_db):
    def failing_send(**_kwargs):
        raise RuntimeError("simulated Gmail outage")

    monkeypatch.setattr(draft_service.gmail_send_service, "send_reply", failing_send)

    with pytest.raises(RuntimeError):
        draft_service.approve_and_send_draft("user-1", "draft-1")

    # Draft must remain untouched — not marked sent, no sent_emails row.
    assert fake_db["email_drafts"][0]["status"] == "ready"
    assert fake_db["sent_emails"] == []


def test_approve_and_send_rejects_wrong_owner(fake_db):
    with pytest.raises(draft_service.DraftNotFoundError):
        draft_service.approve_and_send_draft("someone-else", "draft-1")


def test_edit_draft_marks_status_edited(fake_db):
    result = draft_service.update_draft("user-1", "draft-1", "Updated reply text", None)
    assert result["status"] == "edited"
    assert fake_db["email_drafts"][0]["status"] == "edited"


def test_edit_draft_rejects_already_sent(fake_db):
    fake_db["email_drafts"][0]["status"] = "sent"
    with pytest.raises(draft_service.DraftAlreadySentError):
        draft_service.update_draft("user-1", "draft-1", "New text", None)


# ---------------------------------------------------------------------
# Endpoint auth boundaries
# ---------------------------------------------------------------------


def test_draft_endpoints_require_auth():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    assert client.get("/api/v1/drafts").status_code == 401
    assert client.get("/api/v1/drafts/some-id").status_code == 401
    assert client.patch("/api/v1/drafts/some-id", json={"edited_content": "x"}).status_code == 401
    assert client.post("/api/v1/drafts/some-id/approve").status_code == 401
    assert client.post("/api/v1/drafts/some-id/reject").status_code == 401
    assert client.post("/api/v1/drafts/some-id/regenerate").status_code == 401


def test_dashboard_stats_requires_auth():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    assert client.get("/api/v1/dashboard/stats").status_code == 401
