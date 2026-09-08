"""
analytics_service.py

Computes the Module 7 analytics summary — all counts scoped strictly to
the caller's own data, over an explicit [start, end) date range. No
placeholder numbers; every figure is a real query against the user's rows.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime

from database.supabase_client import get_supabase_admin


def _count(table: str, user_id: str, start: datetime, end: datetime, filters: dict | None = None, in_filters: dict | None = None) -> int:
    db = get_supabase_admin()
    query = (
        db.table(table)
        .select("id", count="exact", head=True)
        .eq("user_id", user_id)
        .gte("created_at", start.isoformat())
        .lt("created_at", end.isoformat())
    )
    for key, value in (filters or {}).items():
        query = query.eq(key, value)
    for key, values in (in_filters or {}).items():
        query = query.in_(key, values)
    result = query.execute()
    return result.count or 0


def get_summary(user_id: str, start: datetime, end: datetime) -> dict:
    db = get_supabase_admin()

    total_emails = _count("emails", user_id, start, end)
    emails_processed = _count(
        "emails", user_id, start, end, in_filters={"processing_status": ["analyzed", "needs_manual_review"]}
    )
    replies_generated = _count("email_drafts", user_id, start, end)
    replies_sent = _count("sent_emails", user_id, start, end)
    auto_replies = _count("sent_emails", user_id, start, end, filters={"sent_via": "auto"})
    manual_replies = _count("sent_emails", user_id, start, end, filters={"sent_via": "manual"})
    rejected_drafts = _count("email_drafts", user_id, start, end, filters={"status": "rejected"})
    failed_replies = _count("email_drafts", user_id, start, end, filters={"status": "failed"})

    # Average AI confidence
    analyses = (
        db.table("ai_analyses")
        .select("confidence")
        .eq("user_id", user_id)
        .gte("created_at", start.isoformat())
        .lt("created_at", end.isoformat())
        .execute()
    )
    confidences = [row["confidence"] for row in (analyses.data or []) if row.get("confidence") is not None]
    avg_confidence = sum(confidences) / len(confidences) if confidences else None

    # Category breakdown
    category_rows = (
        db.table("ai_analyses")
        .select("category")
        .eq("user_id", user_id)
        .gte("created_at", start.isoformat())
        .lt("created_at", end.isoformat())
        .execute()
    )
    category_breakdown = dict(Counter(row["category"] for row in (category_rows.data or []) if row.get("category")))

    # Reply activity: sent replies per day
    sent_rows = (
        db.table("sent_emails")
        .select("created_at")
        .eq("user_id", user_id)
        .gte("created_at", start.isoformat())
        .lt("created_at", end.isoformat())
        .execute()
    )
    day_counts: Counter = Counter()
    for row in sent_rows.data or []:
        day = (row["created_at"] or "")[:10]  # ISO date prefix
        if day:
            day_counts[day] += 1
    reply_activity = [{"date": day, "count": count} for day, count in sorted(day_counts.items())]

    # Automation activity: decisions logged by automation_service (stage="automation")
    automation_rows = (
        db.table("email_processing_logs")
        .select("status")
        .eq("user_id", user_id)
        .eq("stage", "automation")
        .gte("created_at", start.isoformat())
        .lt("created_at", end.isoformat())
        .in_("status", ["AUTO_SEND", "MANUAL_REVIEW", "BLOCK", "IGNORE"])
        .execute()
    )
    automation_activity = dict(Counter(row["status"] for row in (automation_rows.data or [])))

    # Average processing time: time from email creation to draft creation.
    email_rows = (
        db.table("emails")
        .select("id, created_at")
        .eq("user_id", user_id)
        .gte("created_at", start.isoformat())
        .lt("created_at", end.isoformat())
        .execute()
    )
    draft_rows = (
        db.table("email_drafts")
        .select("email_id, created_at")
        .eq("user_id", user_id)
        .gte("created_at", start.isoformat())
        .lt("created_at", end.isoformat())
        .execute()
    )
    email_created_at = {row["id"]: row["created_at"] for row in (email_rows.data or [])}
    deltas = []
    for draft in draft_rows.data or []:
        email_ts = email_created_at.get(draft["email_id"])
        if not email_ts:
            continue
        try:
            t1 = datetime.fromisoformat(email_ts.replace("Z", "+00:00"))
            t2 = datetime.fromisoformat(draft["created_at"].replace("Z", "+00:00"))
            deltas.append((t2 - t1).total_seconds())
        except Exception:
            continue
    avg_processing_time = sum(deltas) / len(deltas) if deltas else None

    return {
        "start": start,
        "end": end,
        "total_emails": total_emails,
        "emails_processed": emails_processed,
        "replies_generated": replies_generated,
        "replies_sent": replies_sent,
        "auto_replies": auto_replies,
        "manual_replies": manual_replies,
        "rejected_drafts": rejected_drafts,
        "failed_replies": failed_replies,
        "average_processing_time_seconds": avg_processing_time,
        "average_ai_confidence": avg_confidence,
        "category_breakdown": category_breakdown,
        "reply_activity": reply_activity,
        "automation_activity": automation_activity,
    }
