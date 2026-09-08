"""
pagination.py

Opaque cursor helpers for keyset ("cursor-based") pagination. We paginate
on a timestamp column (e.g. `received_at`, `created_at`) with the row `id`
as a tiebreaker, which avoids the classic offset-pagination problems (skew
when new rows arrive, O(n) cost for deep pages) at the cost of only
supporting "next page" traversal in one direction — which is all these
list UIs need.

The cursor itself is just a base64-encoded JSON blob; it's opaque to the
client and MUST NOT be constructed by hand, but it's not a security
boundary — the underlying query is still always scoped to the
authenticated user's own rows.
"""
from __future__ import annotations

import base64
import json
import re

# Cursor values are interpolated directly into a PostgREST `.or_()` filter
# expression (see apply_keyset_filter below), which uses commas and
# parentheses as syntax. A cursor is client-supplied (even though opaque),
# so without validation a hand-crafted cursor could inject extra filter
# clauses. These allow-lists restrict decoded cursor fields to characters
# that can never form filter syntax, closing that off regardless of what
# ends up in the interpolated string.
_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,128}$")
_SAFE_VALUE_RE = re.compile(r"^[A-Za-z0-9:\-+.TZ ]{1,64}$")


def encode_cursor(sort_value: str, id_value: str) -> str:
    payload = json.dumps({"v": sort_value, "id": id_value}, separators=(",", ":"))
    return base64.urlsafe_b64encode(payload.encode()).decode()


def decode_cursor(cursor: str) -> tuple[str, str]:
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
        value, id_ = str(payload["v"]), str(payload["id"])
    except Exception as exc:
        raise ValueError("Invalid pagination cursor") from exc

    if not _SAFE_ID_RE.match(id_) or not _SAFE_VALUE_RE.match(value):
        raise ValueError("Invalid pagination cursor")

    return value, id_


def apply_keyset_filter(query, sort_column: str, cursor_value: str, cursor_id: str, descending: bool = True):
    """
    Apply a keyset ("seek") filter to a Supabase/PostgREST query builder for
    `(sort_column, id) < (cursor_value, cursor_id)` (descending) or
    `>` (ascending) — implemented as the standard
    `col < X OR (col = X AND id < Y)` pattern via PostgREST's `.or_()`.
    """
    op = "lt" if descending else "gt"
    filter_expr = f"{sort_column}.{op}.{cursor_value},and({sort_column}.eq.{cursor_value},id.{op}.{cursor_id})"
    return query.or_(filter_expr)
