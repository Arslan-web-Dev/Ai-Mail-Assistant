"""
email_query_service.py

Powers the inbox list view: search, filter, sort, and cursor (keyset)
pagination — always scoped to the authenticated caller's own emails.

Filters that depend on another table (category, priority, draft/sent
status) are resolved with a small lookup query first (get matching email
ids from ai_analyses / email_drafts / sent_emails), then applied to the
main `emails` query with `.in_("id", ids)`. This keeps each query simple
and avoids relying on PostgREST embedded-resource filter syntax.
"""
from __future__ import annotations

import re

from database.supabase_client import get_supabase_admin
from schemas.email import EmailFilter
from utils.pagination import apply_keyset_filter, decode_cursor, encode_cursor

DEFAULT_LIMIT = 25
MAX_LIMIT = 100


def _ids_with_category(user_id: str, category: str) -> list[str]:
    db = get_supabase_admin()
    result = (
        db.table("ai_analyses")
        .select("email_id")
        .eq("user_id", user_id)
        .eq("category", category)
        .execute()
    )
    return [row["email_id"] for row in (result.data or [])]


def _ids_with_high_priority(user_id: str) -> list[str]:
    db = get_supabase_admin()
    result = (
        db.table("ai_analyses")
        .select("email_id")
        .eq("user_id", user_id)
        .in_("priority", ["high", "urgent"])
        .execute()
    )
    return [row["email_id"] for row in (result.data or [])]


def _ids_with_active_draft(user_id: str) -> list[str]:
    db = get_supabase_admin()
    result = (
        db.table("email_drafts")
        .select("email_id")
        .eq("user_id", user_id)
        .in_("status", ["ready", "edited"])
        .execute()
    )
    return list({row["email_id"] for row in (result.data or [])})


def _ids_with_sent_reply(user_id: str) -> list[str]:
    db = get_supabase_admin()
    result = (
        db.table("sent_emails")
        .select("email_id")
        .eq("user_id", user_id)
        .execute()
    )
    return [row["email_id"] for row in (result.data or []) if row.get("email_id")]


def list_emails(
    user_id: str,
    *,
    cursor: str | None = None,
    limit: int = DEFAULT_LIMIT,
    search: str | None = None,
    filter: EmailFilter = EmailFilter.all,
    descending: bool = True,
) -> tuple[list[dict], str | None]:
    limit = max(1, min(limit, MAX_LIMIT))

    # Validate untrusted input before touching any resource.
    cursor_value = cursor_id = None
    if cursor:
        cursor_value, cursor_id = decode_cursor(cursor)

    db = get_supabase_admin()

    query = (
        db.table("emails")
        .select(
            "id, gmail_message_id, gmail_thread_id, sender, recipient, subject, "
            "snippet, received_at, is_read, requires_reply, processing_status, has_attachments"
        )
        .eq("user_id", user_id)
    )

    if filter == EmailFilter.unread:
        query = query.eq("is_read", False)
    elif filter == EmailFilter.needs_reply:
        query = query.eq("requires_reply", True)
    elif filter == EmailFilter.drafts:
        ids = _ids_with_active_draft(user_id)
        if not ids:
            return [], None
        query = query.in_("id", ids)
    elif filter == EmailFilter.sent:
        ids = _ids_with_sent_reply(user_id)
        if not ids:
            return [], None
        query = query.in_("id", ids)
    elif filter == EmailFilter.high_priority:
        ids = _ids_with_high_priority(user_id)
        if not ids:
            return [], None
        query = query.in_("id", ids)
    elif filter in (EmailFilter.job, EmailFilter.business, EmailFilter.meeting, EmailFilter.personal):
        ids = _ids_with_category(user_id, filter.value)
        if not ids:
            return [], None
        query = query.in_("id", ids)
    # EmailFilter.all: no extra filter

    if search:
        # Strip characters with special meaning in PostgREST's filter
        # syntax (commas separate clauses, parentheses nest them) before
        # interpolating user input into the .or_() expression — otherwise
        # a crafted search string could inject additional filter clauses.
        escaped = re.sub(r"[,()%]", " ", search).strip()
        if escaped:
            query = query.or_(f"subject.ilike.%{escaped}%,sender.ilike.%{escaped}%,body_text.ilike.%{escaped}%")

    sort_column = "received_at"
    if cursor:
        query = apply_keyset_filter(query, sort_column, cursor_value, cursor_id, descending)

    query = query.order(sort_column, desc=descending).order("id", desc=descending).limit(limit + 1)
    result = query.execute()
    rows = result.data or []

    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        last = rows[-1]
        next_cursor = encode_cursor(last["received_at"] or "", last["id"])

    return rows, next_cursor
