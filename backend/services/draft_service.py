"""
draft_service.py

Draft management for the review workflow: list, view, edit, regenerate,
reject, and — the safety-critical one — approve_and_send, which performs
the full 10-step send flow from the spec:

 1. Verify authentication         — enforced by the caller (get_current_user)
 2. Verify draft ownership        — _get_owned_draft
 3. Validate recipient            — extract + sanity-check an email address
 4. Validate content              — non-empty reply content
 5. Run safety check              — draft not already sent/rejected; email
                                     not already replied to (duplicate guard)
 6. Verify Gmail connection       — gmail_service.get_valid_credentials
 7. Send through Gmail API        — gmail_send_service.send_reply
 8. Save sent email               — insert into sent_emails
 9. Update draft                  — status -> "sent"
10. Create audit log              — insert into audit_logs

Per product decision, "Approve" in the UI performs steps 1-10 in one call
(there is no separate manual "send" step) — but the underlying Gmail
send/duplicate-prevention logic here is what a future manual "approve
then send" flow would also reuse, if that's ever split apart.

If sending fails at any point, the draft is left as-is (not marked sent)
and the error propagates to the caller so the UI can show it and let the
user retry — never marked "sent" on failure.
"""
from __future__ import annotations

import logging

from database.supabase_client import get_supabase_admin
from schemas.ai import AIAnalysisResult
from services import gmail_send_service, reply_generator
from services.user_preferences_service import get_or_create_preferences
from utils.pagination import apply_keyset_filter, decode_cursor, encode_cursor

logger = logging.getLogger("ai_mail_assistant.draft_service")

DEFAULT_LIMIT = 25
MAX_LIMIT = 100


class DraftError(Exception):
    """Base class for draft-management errors mapped to HTTP responses by the API layer."""


class DraftNotFoundError(DraftError):
    pass


class DraftAlreadySentError(DraftError):
    pass


class InvalidDraftContentError(DraftError):
    pass


def _log(user_id: str, email_id: str | None, stage: str, status: str, message: str = "") -> None:
    from utils.processing_log import log_event

    log_event(user_id, email_id, stage, status, message)


def list_drafts(
    user_id: str,
    *,
    cursor: str | None = None,
    limit: int = DEFAULT_LIMIT,
    status: str | None = None,
) -> tuple[list[dict], str | None]:
    limit = max(1, min(limit, MAX_LIMIT))

    cursor_value = cursor_id = None
    if cursor:
        cursor_value, cursor_id = decode_cursor(cursor)

    db = get_supabase_admin()
    query = db.table("email_drafts").select("*").eq("user_id", user_id)

    if status:
        query = query.eq("status", status)

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


def _get_owned_draft(user_id: str, draft_id: str) -> dict:
    result = (
        get_supabase_admin()
        .table("email_drafts")
        .select("*")
        .eq("id", draft_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise DraftNotFoundError("Draft not found")
    return result.data[0]


def _get_owned_email(user_id: str, email_id: str) -> dict:
    result = (
        get_supabase_admin()
        .table("emails")
        .select("*")
        .eq("id", email_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise DraftNotFoundError("Underlying email not found")
    return result.data[0]


def get_draft(user_id: str, draft_id: str) -> dict:
    return _get_owned_draft(user_id, draft_id)


def update_draft(user_id: str, draft_id: str, edited_content: str, subject: str | None) -> dict:
    """User hand-edits a draft. Marks it 'edited' — still requires approval to send."""
    draft = _get_owned_draft(user_id, draft_id)
    if draft["status"] in ("sent",):
        raise DraftAlreadySentError("Cannot edit a draft that has already been sent")

    payload = {"edited_content": edited_content, "status": "edited"}
    if subject:
        payload["subject"] = subject

    db = get_supabase_admin()
    db.table("email_drafts").update(payload).eq("id", draft_id).execute()
    _log(user_id, draft["email_id"], "draft_edit", "success", "User edited draft")
    return {**draft, **payload}


def reject_draft(user_id: str, draft_id: str) -> dict:
    draft = _get_owned_draft(user_id, draft_id)
    if draft["status"] == "sent":
        raise DraftAlreadySentError("Cannot reject a draft that has already been sent")

    db = get_supabase_admin()
    db.table("email_drafts").update({"status": "rejected"}).eq("id", draft_id).execute()
    _log(user_id, draft["email_id"], "draft_reject", "success", "User rejected draft")
    return {**draft, "status": "rejected"}


def regenerate_draft(user_id: str, draft_id: str) -> dict:
    """Re-run AI reply generation for the same email, replacing this draft's content in place."""
    draft = _get_owned_draft(user_id, draft_id)
    if draft["status"] == "sent":
        raise DraftAlreadySentError("Cannot regenerate a draft that has already been sent")

    email_row = _get_owned_email(user_id, draft["email_id"])

    analysis_row = (
        get_supabase_admin().table("ai_analyses").select("*").eq("email_id", draft["email_id"]).limit(1).execute()
    )
    if not analysis_row.data:
        raise InvalidDraftContentError("No AI analysis found for this email; run analysis first")
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

    profile = _fetch_profile(user_id)
    preferences = get_or_create_preferences(user_id)

    # generate_reply always inserts a new row; we regenerate into a fresh
    # row and retire the old one, so history of prior drafts is preserved
    # for audit purposes rather than being overwritten in place.
    new_draft = reply_generator.generate_reply(user_id, email_row, analysis, profile, preferences)
    if new_draft is None:
        raise InvalidDraftContentError("Reply generation failed after retrying")

    get_supabase_admin().table("email_drafts").update({"status": "rejected"}).eq("id", draft_id).execute()
    _log(user_id, draft["email_id"], "draft_regenerate", "success", f"old_draft={draft_id} new_draft={new_draft['id']}")
    return new_draft


def _fetch_profile(user_id: str) -> dict:
    result = get_supabase_admin().table("profiles").select("*").eq("id", user_id).limit(1).execute()
    return result.data[0] if result.data else {"id": user_id}


def approve_and_send_draft(user_id: str, draft_id: str, sent_via: str = "manual") -> dict:
    """
    The full approve-and-send flow (steps 2-10; step 1 is enforced by the
    caller via get_current_user). Raises DraftError subclasses for
    expected failure modes, and lets gmail_service's own exceptions
    (GmailNotConnectedError/GmailAuthError/GmailApiError) propagate for
    the API layer's existing exception handlers to map to HTTP responses.

    `sent_via` is "manual" for the user-initiated Approve button, or
    "auto" when called by the Module 6 automation pipeline
    (services/automation_service.py) after safety_engine.decide() returns
    AUTO_SEND. This function itself does not make that decision — it's the
    automation module's job to only ever call this with sent_via="auto"
    after the safety layer has approved it; automation must never bypass
    that layer.
    """
    # 2. Verify draft ownership
    draft = _get_owned_draft(user_id, draft_id)

    # 5a. Safety check: don't send an already-sent/rejected draft again.
    if draft["status"] == "sent":
        raise DraftAlreadySentError("This draft has already been sent")
    if draft["status"] == "rejected":
        raise InvalidDraftContentError("Cannot send a rejected draft")

    email_row = _get_owned_email(user_id, draft["email_id"])

    # 5b. Duplicate-send guard: has this email already been replied to
    # (e.g. via a different draft, or a race on this same one)?
    existing_sent = (
        get_supabase_admin()
        .table("sent_emails")
        .select("id")
        .eq("email_id", email_row["id"])
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if existing_sent.data:
        raise DraftAlreadySentError("A reply has already been sent for this email")

    # 4. Validate content
    body = draft.get("edited_content") or draft.get("generated_content") or ""
    if not body.strip():
        raise InvalidDraftContentError("Draft has no content to send")

    # 3. Validate recipient
    recipient = gmail_send_service.extract_reply_address(email_row["sender"])
    if not recipient:
        raise InvalidDraftContentError(f"Could not determine a valid recipient from sender: {email_row['sender']!r}")

    subject = draft.get("subject") or f"Re: {email_row.get('subject') or '(no subject)'}"

    # 6 & 7. Verify Gmail connection + send (gmail_send_service handles both;
    # get_valid_credentials raises GmailNotConnectedError/GmailAuthError,
    # which the API layer already maps to 409/401).
    try:
        send_response = gmail_send_service.send_reply(
            user_id=user_id,
            email_row=email_row,
            recipient=recipient,
            subject=subject,
            body=body,
        )
    except Exception as exc:
        # Send failed: keep the draft exactly as-is so the user can retry —
        # never mark it sent on failure.
        _log(user_id, email_row["id"], "send", "failed", str(exc))
        raise

    db = get_supabase_admin()

    # 8. Save sent email
    try:
        db.table("sent_emails").insert(
            {
                "user_id": user_id,
                "draft_id": draft_id,
                "email_id": email_row["id"],
                "gmail_message_id": send_response.get("id"),
                "gmail_thread_id": send_response.get("threadId"),
                "recipient": recipient,
                "subject": subject,
                "body": body,
                "sent_via": sent_via,
            }
        ).execute()
    except Exception as exc:
        # The message reached Gmail (sent successfully) but our own
        # bookkeeping insert failed — this is a serious but different
        # failure mode from a send failure: don't re-raise as if nothing
        # was sent (that would risk a duplicate send on retry). Log loudly
        # and still proceed to mark the draft sent, since the source of
        # truth (Gmail) confirms it went out.
        logger.error("Sent email but failed to record sent_emails row for draft %s: %s", draft_id, exc)

    # 9. Update draft
    db.table("email_drafts").update({"status": "sent"}).eq("id", draft_id).execute()

    # 10. Create audit log
    try:
        db.table("audit_logs").insert(
            {
                "user_id": user_id,
                "action": "email_sent",
                "details": {
                    "draft_id": draft_id,
                    "email_id": email_row["id"],
                    "recipient": recipient,
                    "gmail_message_id": send_response.get("id"),
                    "sent_via": sent_via,
                },
            }
        ).execute()
    except Exception:
        logger.exception("Failed to write audit log for sent draft %s (non-fatal)", draft_id)

    _log(user_id, email_row["id"], "send", "success", f"gmail_message_id={send_response.get('id')}")

    return {**draft, "status": "sent"}
