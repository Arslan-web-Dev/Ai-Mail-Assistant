"""
email_sync_service.py

Orchestrates syncing Gmail messages into Supabase:
- full_sync(): initial sync, lists recent INBOX messages.
- incremental_sync(): uses Gmail's history.list API to fetch only what
  changed since the last known historyId (used after a push notification).
- Both paths share `_store_message`, which enforces duplicate prevention
  via the (user_id, gmail_message_id) unique constraint, parses/sanitizes
  content (see email_parser.py), and writes a processing log entry.

Nothing in this module trusts or executes email content — it only stores
sanitized text/HTML and attachment *metadata* (never attachment bytes).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from database.supabase_client import get_supabase_admin
from schemas.email import SyncResult
from services import gmail_service
from services.email_parser import ParsedEmail, parse_gmail_message

logger = logging.getLogger("ai_mail_assistant.email_sync")

MAX_FULL_SYNC_MESSAGES = 50  # keep the initial sync bounded/fast; older mail can be backfilled later


def _log(user_id: str, email_id: str | None, stage: str, status: str, message: str = "") -> None:
    from utils.processing_log import log_event

    log_event(user_id, email_id, stage, status, message)


def _upsert_thread(user_id: str, parsed: ParsedEmail) -> str | None:
    db = get_supabase_admin()
    existing = (
        db.table("email_threads")
        .select("id, message_count")
        .eq("user_id", user_id)
        .eq("gmail_thread_id", parsed.gmail_thread_id)
        .limit(1)
        .execute()
    )
    now = datetime.now(timezone.utc).isoformat()
    if existing.data:
        row = existing.data[0]
        db.table("email_threads").update(
            {
                "subject": parsed.subject,
                "last_message_at": parsed.received_at.isoformat() if parsed.received_at else now,
                "message_count": row["message_count"] + 1,
                "updated_at": now,
            }
        ).eq("id", row["id"]).execute()
        return row["id"]

    result = (
        db.table("email_threads")
        .insert(
            {
                "user_id": user_id,
                "gmail_thread_id": parsed.gmail_thread_id,
                "subject": parsed.subject,
                "last_message_at": parsed.received_at.isoformat() if parsed.received_at else now,
                "message_count": 1,
            }
        )
        .execute()
    )
    return result.data[0]["id"] if result.data else None


def _store_message(user_id: str, parsed: ParsedEmail) -> tuple[bool, bool, str | None]:
    """
    Store a parsed message. Returns (stored, was_duplicate, email_id).
    Duplicate prevention relies on the DB unique constraint
    (user_id, gmail_message_id) — we check first for a clean log message,
    but the constraint is the actual source of truth if there's a race.
    """
    db = get_supabase_admin()
    existing = (
        db.table("emails")
        .select("id")
        .eq("user_id", user_id)
        .eq("gmail_message_id", parsed.gmail_message_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        _log(user_id, existing.data[0]["id"], "sync", "success", "Duplicate message skipped")
        return False, True, None

    thread_id = _upsert_thread(user_id, parsed)

    attachment_metadata = [
        {
            "filename": a.filename,
            "mime_type": a.mime_type,
            "size": a.size,
            "attachment_id": a.attachment_id,
        }
        for a in parsed.attachments
    ]

    try:
        result = (
            db.table("emails")
            .insert(
                {
                    "user_id": user_id,
                    "thread_id": thread_id,
                    "gmail_message_id": parsed.gmail_message_id,
                    "gmail_thread_id": parsed.gmail_thread_id,
                    "sender": parsed.sender,
                    "recipient": parsed.recipient,
                    "subject": parsed.subject,
                    "body_text": parsed.body_text,
                    "body_html_sanitized": parsed.body_html_sanitized,
                    "snippet": parsed.snippet,
                    "labels": parsed.labels,
                    "has_attachments": parsed.has_attachments,
                    "attachment_metadata": attachment_metadata,
                    "received_at": parsed.received_at.isoformat() if parsed.received_at else None,
                    "is_read": "UNREAD" not in parsed.labels,
                    "processing_status": "parsed",
                    "rfc_message_id": parsed.rfc_message_id,
                }
            )
            .execute()
        )
        email_id = result.data[0]["id"] if result.data else None
        _log(user_id, email_id, "sync", "success", "Message stored")
        return True, False, email_id
    except Exception as exc:
        # Unique-constraint violation races land here too — treat as duplicate.
        if "duplicate key" in str(exc).lower() or "unique" in str(exc).lower():
            _log(user_id, None, "sync", "success", "Duplicate message (race) skipped")
            return False, True, None
        _log(user_id, None, "sync", "failed", f"Store failed: {exc}")
        raise


def full_sync(user_id: str) -> SyncResult:
    """Fetch the most recent inbox messages and store any not already synced."""
    credentials = gmail_service.get_valid_credentials(user_id)
    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)

    fetched = stored = duplicates = failed = 0
    new_email_ids: list[str] = []

    try:
        list_response = (
            service.users()
            .messages()
            .list(userId="me", labelIds=["INBOX"], maxResults=MAX_FULL_SYNC_MESSAGES)
            .execute()
        )
    except HttpError as exc:
        _log(user_id, None, "sync", "failed", f"Failed to list messages: {exc}")
        raise gmail_service.GmailApiError(f"Failed to list Gmail messages: {exc}") from exc

    for item in list_response.get("messages", []):
        fetched += 1
        try:
            message = service.users().messages().get(userId="me", id=item["id"], format="full").execute()
            parsed = parse_gmail_message(message)
            was_stored, was_dup, email_id = _store_message(user_id, parsed)
            stored += int(was_stored)
            duplicates += int(was_dup)
            if was_stored and email_id:
                new_email_ids.append(email_id)
        except Exception:
            failed += 1
            logger.exception("Failed to sync message %s", item.get("id"))

    # Record current historyId so future syncs can be incremental.
    try:
        profile = service.users().getProfile(userId="me").execute()
        history_id = profile.get("historyId")
        if history_id:
            get_supabase_admin().table("profiles").update(
                {"last_history_id": history_id}
            ).eq("id", user_id).execute()
    except Exception:
        logger.exception("Failed to record historyId after full sync (non-fatal)")

    return SyncResult(fetched=fetched, stored=stored, duplicates=duplicates, failed=failed, new_email_ids=new_email_ids)


def incremental_sync(user_id: str) -> SyncResult:
    """
    Sync only what changed since the last known historyId (from Gmail's
    history.list API). Falls back to a full sync if we have no starting
    point, or if Gmail reports the historyId is too old (expired).
    """
    db = get_supabase_admin()
    profile_row = db.table("profiles").select("last_history_id").eq("id", user_id).limit(1).execute()
    start_history_id = profile_row.data[0]["last_history_id"] if profile_row.data else None

    if not start_history_id:
        return full_sync(user_id)

    credentials = gmail_service.get_valid_credentials(user_id)
    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)

    fetched = stored = duplicates = failed = 0
    new_email_ids: list[str] = []
    new_message_ids: set[str] = set()

    try:
        page_token = None
        while True:
            resp = (
                service.users()
                .history()
                .list(
                    userId="me",
                    startHistoryId=start_history_id,
                    historyTypes=["messageAdded"],
                    pageToken=page_token,
                )
                .execute()
            )
            for record in resp.get("history", []):
                for added in record.get("messagesAdded", []):
                    new_message_ids.add(added["message"]["id"])
            page_token = resp.get("nextPageToken")
            if not page_token:
                latest_history_id = resp.get("historyId", start_history_id)
                break
    except HttpError as exc:
        if getattr(exc, "status_code", None) == 404 or "404" in str(exc):
            # historyId too old / expired — Gmail requires a fresh full sync.
            _log(user_id, None, "sync", "retrying", "historyId expired, falling back to full sync")
            return full_sync(user_id)
        _log(user_id, None, "sync", "failed", f"history.list failed: {exc}")
        raise gmail_service.GmailApiError(f"Gmail history sync failed: {exc}") from exc

    for message_id in new_message_ids:
        fetched += 1
        try:
            message = service.users().messages().get(userId="me", id=message_id, format="full").execute()
            parsed = parse_gmail_message(message)
            was_stored, was_dup, email_id = _store_message(user_id, parsed)
            stored += int(was_stored)
            duplicates += int(was_dup)
            if was_stored and email_id:
                new_email_ids.append(email_id)
        except Exception:
            failed += 1
            logger.exception("Failed to sync message %s", message_id)

    db.table("profiles").update({"last_history_id": latest_history_id}).eq("id", user_id).execute()

    return SyncResult(fetched=fetched, stored=stored, duplicates=duplicates, failed=failed, new_email_ids=new_email_ids)
