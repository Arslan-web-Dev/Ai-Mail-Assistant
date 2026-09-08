"""
Background tasks: email sync triggered by Gmail push notifications (Module
3), AI analysis and reply-draft generation for newly synced emails (Module
4), and the automation safety-decision pipeline that may auto-send a
generated draft (Module 6). Also periodic Gmail watch renewal, since
watch() registrations expire after ~7 days.

Run a worker:    celery -A workers.celery_app worker --loglevel=info
Run the beat scheduler: celery -A workers.celery_app beat --loglevel=info
"""
import logging

from workers.celery_app import celery_app

logger = logging.getLogger("ai_mail_assistant.tasks")


@celery_app.task(name="sync_user_email", bind=True, max_retries=3, default_retry_delay=30)
def sync_user_email_task(self, user_id: str):
    """
    Triggered by the Gmail webhook after a verified push notification.
    Safe to retry: incremental_sync is idempotent thanks to the
    (user_id, gmail_message_id) unique constraint on `emails`.

    After a successful sync, enqueues AI analysis + reply-draft generation
    (Module 4) for each newly stored email.
    """
    from services.email_sync_service import incremental_sync
    from services.gmail_service import GmailAuthError, GmailNotConnectedError

    try:
        result = incremental_sync(user_id)
        logger.info("Synced user %s: %s", user_id, result)
        for email_id in result.new_email_ids:
            analyze_and_draft_task.delay(user_id, email_id)
        return result.model_dump()
    except GmailNotConnectedError:
        logger.info("Skipping sync for %s: Gmail not connected", user_id)
    except GmailAuthError:
        # Don't retry auth failures — the user needs to reconnect.
        logger.warning("Sync auth error for %s: user must reconnect Gmail", user_id)
    except Exception as exc:
        logger.exception("Sync failed for %s, retrying", user_id)
        raise self.retry(exc=exc)


@celery_app.task(name="analyze_and_draft", bind=True, max_retries=2, default_retry_delay=15)
def analyze_and_draft_task(self, user_id: str, email_id: str):
    """
    Runs AI classification for one email, and — if it's classified as
    needing a reply and isn't spam — generates a reply draft. Never sends
    anything itself; only writes `ai_analyses` / `email_drafts` rows.

    If a draft was generated, hands off to the Module 6 automation
    pipeline (evaluate_and_maybe_send), which is the only code path
    allowed to auto-send — and only after the safety_engine says AUTO_SEND.
    """
    from database.supabase_client import get_supabase_admin
    from services.ai_analyzer import analyze_email
    from services.automation_service import evaluate_and_maybe_send
    from services.openai_client import AIResponseError
    from services.reply_generator import generate_reply
    from services.user_preferences_service import get_or_create_preferences

    db = get_supabase_admin()
    email_result = db.table("emails").select("*").eq("id", email_id).eq("user_id", user_id).limit(1).execute()
    if not email_result.data:
        logger.warning("analyze_and_draft: email %s not found for user %s", email_id, user_id)
        return
    email_row = email_result.data[0]

    try:
        analysis = analyze_email(user_id, email_row)
    except RuntimeError:
        # OPENAI_API_KEY not configured in this environment — nothing to do.
        logger.warning("Skipping AI analysis for %s: OpenAI not configured", email_id)
        return
    except Exception as exc:
        logger.exception("AI analysis failed for email %s", email_id)
        raise self.retry(exc=exc)

    if not analysis.requires_reply or analysis.category.value == "spam":
        logger.info(
            "Skipping reply generation for email %s (requires_reply=%s, category=%s)",
            email_id,
            analysis.requires_reply,
            analysis.category.value,
        )
        return

    profile = _get_profile_dict(user_id)
    preferences = get_or_create_preferences(user_id)

    draft = None
    try:
        draft = generate_reply(user_id, email_row, analysis, profile, preferences)
    except RuntimeError:
        logger.warning("Skipping reply generation for %s: OpenAI not configured", email_id)
        return
    except AIResponseError:
        logger.warning("Reply generation failed for %s after retry (handled, marked failed)", email_id)
        return

    if draft is None:
        return

    try:
        decision = evaluate_and_maybe_send(user_id, email_id, draft["id"])
        logger.info("Automation decision for email %s: %s", email_id, decision.value)
        _notify_for_decision(user_id, email_id, draft, decision)
    except Exception:
        # Automation evaluation itself should never crash the pipeline —
        # evaluate_and_maybe_send already catches its own expected
        # failures, so anything reaching here is unexpected; log and leave
        # the draft as a normal 'ready' draft for manual review.
        logger.exception("Automation evaluation failed for email %s; leaving draft for manual review", email_id)


def _notify_for_decision(user_id: str, email_id: str, draft: dict, decision) -> None:
    """
    Fire "needs your attention" notifications once the automation decision
    is known. AUTO_SEND's own success/failure notifications are created in
    automation_service.py itself, right where the actual outcome (not just
    the decision) is known — a decision of AUTO_SEND doesn't guarantee the
    send succeeded.
    """
    if decision.value not in ("MANUAL_REVIEW", "BLOCK"):
        return
    from services.notification_service import create_notification

    subject = draft.get("subject") or "(no subject)"
    create_notification(
        user_id, "approval_required", f"New AI draft ready for review: {subject}", {"email_id": email_id}
    )


def _get_profile_dict(user_id: str) -> dict:
    """Fetch the profile row directly (task context has no AuthenticatedUser)."""
    from database.supabase_client import get_supabase_admin

    result = get_supabase_admin().table("profiles").select("*").eq("id", user_id).limit(1).execute()
    return result.data[0] if result.data else {"id": user_id}


@celery_app.task(name="renew_gmail_watches")
def renew_gmail_watches_task():
    """Periodic task (see beat schedule below): renews watches expiring soon."""
    from services.gmail_watch_service import renew_expiring_watches

    renewed = renew_expiring_watches()
    logger.info("Renewed %d Gmail watch registrations", renewed)
    return renewed
