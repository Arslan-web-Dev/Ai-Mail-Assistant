"""
notification_service.py

In-app notifications (Module 7). `create_notification` is called from
various points in the pipeline (see callers: workers/tasks.py,
automation_service.py, gmail_service.py, ai_analyzer.py) whenever
something happens that the user should know about without having to go
looking for it.

Known simplification: a couple of notification types (e.g. "daily limit
reached") are created once per triggering event rather than deduplicated
per day — fine for a v1, but a production system would want to throttle
these so a busy inbox doesn't spam the notification center.
"""
from __future__ import annotations

import logging

from database.supabase_client import get_supabase_admin
from utils.pagination import apply_keyset_filter, decode_cursor, encode_cursor

logger = logging.getLogger("ai_mail_assistant.notifications")

DEFAULT_LIMIT = 25
MAX_LIMIT = 100

VALID_TYPES = {
    "new_draft",
    "approval_required",
    "email_sent",
    "email_failed",
    "gmail_disconnected",
    "ai_processing_failed",
    "automation_paused",
    "daily_limit_reached",
}


def create_notification(user_id: str, notif_type: str, message: str, metadata: dict | None = None) -> None:
    """Best-effort — a failure here should never break the caller's main flow."""
    try:
        get_supabase_admin().table("notifications").insert(
            {
                "user_id": user_id,
                "type": notif_type,
                "message": message[:1000],
                "metadata": metadata or {},
            }
        ).execute()
    except Exception:
        logger.exception("Failed to create notification (non-fatal): type=%s", notif_type)


def list_notifications(
    user_id: str, *, cursor: str | None = None, limit: int = DEFAULT_LIMIT, unread_only: bool = False
) -> tuple[list[dict], str | None]:
    limit = max(1, min(limit, MAX_LIMIT))

    cursor_value = cursor_id = None
    if cursor:
        cursor_value, cursor_id = decode_cursor(cursor)

    db = get_supabase_admin()
    query = db.table("notifications").select("*").eq("user_id", user_id)

    if unread_only:
        query = query.eq("is_read", False)

    if cursor:
        query = apply_keyset_filter(query, "created_at", cursor_value, cursor_id, descending=True)

    query = query.order("created_at", desc=True).order("id", desc=True).limit(limit + 1)
    result = query.execute()
    rows = result.data or []

    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        last = rows[-1]
        next_cursor = encode_cursor(last["created_at"], last["id"])

    return rows, next_cursor


def count_unread(user_id: str) -> int:
    db = get_supabase_admin()
    result = (
        db.table("notifications")
        .select("id", count="exact", head=True)
        .eq("user_id", user_id)
        .eq("is_read", False)
        .execute()
    )
    return result.count or 0


def mark_read(user_id: str, notification_id: str) -> None:
    get_supabase_admin().table("notifications").update({"is_read": True}).eq("id", notification_id).eq(
        "user_id", user_id
    ).execute()


def mark_all_read(user_id: str) -> None:
    get_supabase_admin().table("notifications").update({"is_read": True}).eq("user_id", user_id).eq(
        "is_read", False
    ).execute()


def delete_notification(user_id: str, notification_id: str) -> None:
    get_supabase_admin().table("notifications").delete().eq("id", notification_id).eq("user_id", user_id).execute()
