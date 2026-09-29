"""
automation_service.py

Orchestrates Module 6: fetches/creates automation settings, computes the
dynamic bits (today's auto-send count, business-hours check), calls the
pure safety_engine.decide(), logs the decision, and — only for AUTO_SEND —
performs the actual send via draft_service.approve_and_send_draft(...,
sent_via="auto"), reusing all of its duplicate-prevention and
never-mark-sent-on-failure guarantees.

This module is the ONLY caller of draft_service with sent_via="auto", and
it always routes through safety_engine.decide() first — automation must
never bypass the safety layer.
"""
from __future__ import annotations

import logging
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from database.supabase_client import get_supabase_admin
from schemas.ai import AIAnalysisResult
from services import draft_service
from services.db_utils import get_or_create_row
from services.safety_engine import DecisionContext, SafetyDecision, decide

logger = logging.getLogger("ai_mail_assistant.automation")

# Safe-by-default settings: automation is OFF until the user opts in, and
# even once enabled, blocked_categories still excludes spam (belt and
# braces alongside safety_engine's hard-coded spam=IGNORE rule) and
# require_approval_for_medium_risk defaults to True.
DEFAULT_SETTINGS = {
    "auto_reply_enabled": False,
    "paused": False,
    "minimum_ai_confidence": 0.9,
    "allowed_categories": [],
    "blocked_categories": ["spam"],
    "require_approval_for_medium_risk": True,
    "daily_reply_limit": 20,
    "business_hours_enabled": False,
    "business_hours_start": "09:00",
    "business_hours_end": "18:00",
    "business_hours_timezone": "UTC",
    "signature_enabled": True,
}


def get_or_create_settings(user_id: str) -> dict:
    return get_or_create_row(get_supabase_admin(), "automation_settings", "user_id", user_id, DEFAULT_SETTINGS)


def update_settings(user_id: str, updates: dict) -> dict:
    get_or_create_settings(user_id)  # ensure a row exists before updating
    if updates:
        get_supabase_admin().table("automation_settings").update(updates).eq("user_id", user_id).execute()
    return get_or_create_settings(user_id)


def set_paused(user_id: str, paused: bool) -> dict:
    result = update_settings(user_id, {"paused": paused})
    if paused:
        try:
            from services.notification_service import create_notification

            create_notification(user_id, "automation_paused", "Automation has been paused.")
        except Exception:
            logger.exception("Failed to create automation_paused notification (non-fatal)")
    return result


def _count_auto_sent_today(user_id: str) -> int:
    db = get_supabase_admin()
    start_of_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    result = (
        db.table("sent_emails")
        .select("id", count="exact", head=True)
        .eq("user_id", user_id)
        .eq("sent_via", "auto")
        .gte("created_at", start_of_day.isoformat())
        .execute()
    )
    return result.count or 0


def _within_business_hours(settings: dict) -> bool:
    if not settings.get("business_hours_enabled"):
        return True
    try:
        tz = ZoneInfo(settings.get("business_hours_timezone") or "UTC")
        now_local = datetime.now(tz).time()
        start = time.fromisoformat(settings.get("business_hours_start") or "09:00")
        end = time.fromisoformat(settings.get("business_hours_end") or "18:00")
        if start <= end:
            return start <= now_local <= end
        return now_local >= start or now_local <= end  # overnight window, e.g. 22:00-06:00
    except Exception:
        # Fail closed: if we can't evaluate business hours, treat it as
        # "outside" so automation falls back to manual review rather than
        # auto-sending on bad config.
        logger.exception("Failed to evaluate business hours for automation settings; failing closed")
        return False


def _log(user_id: str, email_id: str, status: str, message: str) -> None:
    from utils.processing_log import log_event

    log_event(user_id, email_id, "automation", status, message)


def evaluate_and_maybe_send(user_id: str, email_id: str, draft_id: str) -> SafetyDecision:
    """
    Called after a draft is generated (see workers/tasks.py:
    analyze_and_draft_task). Evaluates the safety decision and, if
    AUTO_SEND, sends immediately. Never raises for expected failure modes —
    logs and returns a decision either way, so one problematic email can't
    take down the analysis/automation pipeline for the rest of the user's
    inbox.
    """
    db = get_supabase_admin()

    analysis_row = db.table("ai_analyses").select("*").eq("email_id", email_id).limit(1).execute()
    if not analysis_row.data:
        _log(user_id, email_id, "failed", "No AI analysis found; cannot make automation decision")
        return SafetyDecision.MANUAL_REVIEW

    a = analysis_row.data[0]
    analysis = AIAnalysisResult(
        category=a["category"],
        intent=a["intent"],
        priority=a["priority"],
        sentiment=a["sentiment"],
        requires_reply=a["requires_reply"],
        sensitivity_level=a["sensitivity_level"],
        confidence=a["confidence"] or 0.0,
    )

    draft_row = db.table("email_drafts").select("*").eq("id", draft_id).limit(1).execute()
    draft_requires_review = bool(draft_row.data[0].get("requires_review")) if draft_row.data else True

    settings = get_or_create_settings(user_id)

    ctx = DecisionContext(
        automation_enabled=bool(settings.get("auto_reply_enabled")),
        paused=bool(settings.get("paused")),
        minimum_confidence=float(settings.get("minimum_ai_confidence", 0.9)),
        allowed_categories=settings.get("allowed_categories") or [],
        blocked_categories=settings.get("blocked_categories") or [],
        require_approval_for_medium_risk=bool(settings.get("require_approval_for_medium_risk", True)),
        daily_limit=int(settings.get("daily_reply_limit", 0) or 0),
        sent_today_count=_count_auto_sent_today(user_id),
        within_business_hours=_within_business_hours(settings),
        draft_requires_review=draft_requires_review,
    )

    result = decide(analysis, ctx)
    _log(user_id, email_id, result.decision.value, f"reason={result.reason}")

    if "daily_reply_limit" in result.reason:
        try:
            from services.notification_service import create_notification

            create_notification(
                user_id,
                "daily_limit_reached",
                "Today's automatic reply limit has been reached; further replies need manual approval.",
            )
        except Exception:
            logger.exception("Failed to create daily_limit_reached notification (non-fatal)")

    if result.decision != SafetyDecision.AUTO_SEND:
        return result.decision

    try:
        draft_service.approve_and_send_draft(user_id, draft_id, sent_via="auto")
        _log(user_id, email_id, "auto_send_success", "auto-sent successfully")
        try:
            from services.notification_service import create_notification

            create_notification(user_id, "email_sent", "An email was replied to automatically.", {"email_id": email_id})
        except Exception:
            logger.exception("Failed to create email_sent notification (non-fatal)")
    except draft_service.DraftAlreadySentError:
        # Idempotency: something else already sent a reply for this email
        # (e.g. the user manually approved it in the same window). Not an
        # error — just means there's nothing left for automation to do.
        _log(user_id, email_id, "auto_send_skipped", "skipped auto-send: already sent")
    except Exception as exc:
        # draft_service guarantees the draft is never marked sent on
        # failure, so it's still sitting there as a normal 'ready' draft
        # for the user to review/retry manually.
        logger.exception("Auto-send failed for draft %s", draft_id)
        _log(user_id, email_id, "auto_send_failed", f"auto-send failed, left for manual review: {exc}")
        try:
            from services.notification_service import create_notification

            create_notification(
                user_id,
                "email_failed",
                "An automated reply failed to send and was left for manual review.",
                metadata={"draft_id": draft_id, "email_id": email_id},
            )
        except Exception:
            logger.exception("Failed to create email_failed notification (non-fatal)")

    return result.decision
