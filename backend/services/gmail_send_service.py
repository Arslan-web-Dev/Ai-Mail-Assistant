"""
gmail_send_service.py

Builds and sends a reply email via the Gmail API, preserving conversation
threading (In-Reply-To / References headers + Gmail's own threadId).
"""
from __future__ import annotations

import base64
import re
from email.mime.text import MIMEText

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from services import gmail_service

# Simple, deliberately conservative email-address extraction — good enough
# to pull an address out of "Display Name <addr@example.com>" or a bare
# address, without trying to be a full RFC 5322 parser.
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


def extract_reply_address(from_header: str) -> str | None:
    """Extract a plausible reply-to email address from a Gmail 'From' header."""
    if not from_header:
        return None
    match = _EMAIL_RE.search(from_header)
    return match.group(0) if match else None


def _build_raw_message(
    *,
    to_address: str,
    subject: str,
    body: str,
    thread_headers: dict,
) -> str:
    message = MIMEText(body, "plain", "utf-8")
    message["To"] = to_address
    message["Subject"] = subject
    if thread_headers.get("in_reply_to"):
        message["In-Reply-To"] = thread_headers["in_reply_to"]
    if thread_headers.get("references"):
        message["References"] = thread_headers["references"]

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return raw


def send_reply(*, user_id: str, email_row: dict, recipient: str, subject: str, body: str) -> dict:
    """
    Send `body` as a reply to `email_row`, preserving Gmail thread
    continuity. Returns the Gmail API response (contains `id`, `threadId`).
    Raises gmail_service.GmailServiceError subclasses on failure — callers
    must not mark anything as sent if this raises.
    """
    credentials = gmail_service.get_valid_credentials(user_id)
    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)

    original_message_id = email_row.get("rfc_message_id")
    raw = _build_raw_message(
        to_address=recipient,
        subject=subject,
        body=body,
        thread_headers={
            "in_reply_to": original_message_id,
            "references": original_message_id,  # single-hop; a full References chain would need thread history
        },
    )

    request_body = {"raw": raw}
    if email_row.get("gmail_thread_id"):
        request_body["threadId"] = email_row["gmail_thread_id"]

    try:
        return service.users().messages().send(userId="me", body=request_body).execute()
    except HttpError as exc:
        status_code = getattr(exc, "status_code", None) or exc.resp.status
        if status_code in (429, 403):
            raise gmail_service.GmailRateLimitError("Gmail API rate limit reached while sending") from exc
        raise gmail_service.GmailApiError(f"Failed to send reply via Gmail: {exc}") from exc
