"""
dashboard_service.py

Computes dashboard stat-card numbers from real data — no placeholder or
fake statistics. Each count is a lightweight `count="exact", head=True`
query scoped to the caller's own rows.
"""
from __future__ import annotations

from database.supabase_client import get_supabase_admin


def _count(table: str, user_id: str, filters: dict | None = None, in_filters: dict | None = None) -> int:
    db = get_supabase_admin()
    query = db.table(table).select("id", count="exact", head=True).eq("user_id", user_id)
    for key, value in (filters or {}).items():
        query = query.eq(key, value)
    for key, values in (in_filters or {}).items():
        query = query.in_(key, values)
    result = query.execute()
    return result.count or 0


def get_stats(user_id: str) -> dict:
    total_emails = _count("emails", user_id)
    needs_reply = _count("emails", user_id, filters={"requires_reply": True})
    failed_processing = _count("emails", user_id, in_filters={"processing_status": ["failed", "needs_manual_review"]})

    ai_drafts = _count("email_drafts", user_id)
    pending_approval = _count("email_drafts", user_id, in_filters={"status": ["ready", "edited"]})
    failed_drafts = _count("email_drafts", user_id, filters={"status": "failed"})

    sent_replies = _count("sent_emails", user_id)
    auto_replies = _count("sent_emails", user_id, filters={"sent_via": "auto"})

    return {
        "total_emails": total_emails,
        "needs_reply": needs_reply,
        "ai_drafts": ai_drafts,
        "pending_approval": pending_approval,
        "sent_replies": sent_replies,
        "auto_replies": auto_replies,
        "failed_processing": failed_processing + failed_drafts,
    }
