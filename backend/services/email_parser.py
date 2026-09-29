"""
email_parser.py

Parses a raw Gmail API message resource into a normalized, safe internal
representation.

Security rules enforced here:
- HTML bodies are sanitized with `bleach` before storage — script tags,
  event handlers (onclick, onerror, ...), <iframe>, <object>, <embed>,
  forms, and style/link injection are all stripped. We NEVER render or
  execute raw email HTML.
- We never download or execute attachment content. Only metadata
  (filename, mime type, size, Gmail attachment id) is extracted, so a
  later module can fetch an attachment on-demand and explicitly, with its
  own scanning/consent step — this module does not fetch attachment bytes.
- Email body/subject/sender are treated as untrusted input end-to-end;
  nothing here interprets them as instructions.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import bleach
from bs4 import BeautifulSoup

# Conservative allow-list for sanitized HTML we might render later.
ALLOWED_TAGS = [
    "p", "br", "b", "strong", "i", "em", "u", "ul", "ol", "li",
    "a", "span", "div", "blockquote", "table", "thead", "tbody",
    "tr", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6", "hr",
]
ALLOWED_ATTRS = {"a": ["href", "title"]}  # no `style` — CSS isn't sanitized by bleach without css_sanitizer
ALLOWED_PROTOCOLS = ["http", "https", "mailto"]

MAX_BODY_CHARS = 50_000  # guard against extremely large email bodies


@dataclass
class ParsedAttachment:
    filename: str
    mime_type: str
    size: int
    attachment_id: str


@dataclass
class ParsedEmail:
    gmail_message_id: str
    gmail_thread_id: str
    sender: str
    recipient: str | None
    subject: str | None
    snippet: str | None
    body_text: str
    body_html_sanitized: str | None
    labels: list[str]
    received_at: datetime | None
    has_attachments: bool
    rfc_message_id: str | None = None  # the email's RFC 5322 "Message-ID" header, for In-Reply-To/References threading
    attachments: list[ParsedAttachment] = field(default_factory=list)


def _header(headers: list[dict], name: str) -> str | None:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value")
    return None


def _decode_b64(data: str) -> bytes:
    # Gmail uses URL-safe base64 without padding guarantees.
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded)


DANGEROUS_TAGS = ["script", "style", "iframe", "object", "embed", "form", "noscript"]


def _strip_dangerous_content(html: str) -> str:
    """
    Remove tags whose *content* is unsafe to keep even as text (script/style
    JS or CSS payloads, embedded objects) before running bleach. bleach's
    tag-stripping alone removes markup but preserves inner text, which would
    leak raw JS/CSS into the "sanitized" output — decompose() removes the
    tag and everything inside it.
    """
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(DANGEROUS_TAGS):
        tag.decompose()
    return str(soup)


def _sanitize_html(html: str) -> str:
    pre_cleaned = _strip_dangerous_content(html)
    cleaned = bleach.clean(
        pre_cleaned,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
        strip_comments=True,
    )
    return cleaned[:MAX_BODY_CHARS]


def _html_to_text(html: str) -> str:
    # Strip scripts/styles entirely before text extraction, then get plain text.
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(DANGEROUS_TAGS):
        tag.decompose()
    return soup.get_text(separator="\n").strip()


def _walk_parts(payload: dict) -> list[dict]:
    """Flatten a Gmail MIME payload tree into a list of parts (including the root)."""
    parts = [payload]
    for p in payload.get("parts", []) or []:
        parts.extend(_walk_parts(p))
    return parts


def _extract_body_and_attachments(payload: dict) -> tuple[str, str | None, list[ParsedAttachment]]:
    text_plain = ""
    text_html = ""
    attachments: list[ParsedAttachment] = []

    for part in _walk_parts(payload):
        mime_type = part.get("mimeType", "")
        filename = part.get("filename") or ""
        body = part.get("body", {}) or {}

        if filename and body.get("attachmentId"):
            attachments.append(
                ParsedAttachment(
                    filename=filename,
                    mime_type=mime_type or "application/octet-stream",
                    size=int(body.get("size", 0)),
                    attachment_id=body["attachmentId"],
                )
            )
            continue

        data = body.get("data")
        if not data:
            continue

        try:
            decoded = _decode_b64(data).decode("utf-8", errors="replace")
        except Exception:
            continue

        if mime_type == "text/plain" and not text_plain:
            text_plain = decoded
        elif mime_type == "text/html" and not text_html:
            text_html = decoded

    body_html_sanitized = _sanitize_html(text_html)[:MAX_BODY_CHARS] if text_html else None

    if text_plain:
        body_text = text_plain
    elif text_html:
        body_text = _html_to_text(text_html)
    else:
        body_text = ""

    return body_text[:MAX_BODY_CHARS], body_html_sanitized, attachments


def parse_gmail_message(message: dict[str, Any]) -> ParsedEmail:
    """
    Parse a Gmail API `users.messages.get` response (format="full") into a
    ParsedEmail. Never trust or execute the content — this only extracts
    and sanitizes it for storage.
    """
    payload = message.get("payload", {}) or {}
    headers = payload.get("headers", []) or []

    body_text, body_html_sanitized, attachments = _extract_body_and_attachments(payload)

    received_at = None
    internal_date = message.get("internalDate")
    if internal_date:
        try:
            received_at = datetime.fromtimestamp(int(internal_date) / 1000, tz=timezone.utc)
        except (ValueError, OSError):
            received_at = None

    return ParsedEmail(
        gmail_message_id=message["id"],
        gmail_thread_id=message.get("threadId", message["id"]),
        sender=_header(headers, "From") or "unknown",
        recipient=_header(headers, "To"),
        subject=_header(headers, "Subject"),
        snippet=message.get("snippet"),
        body_text=body_text,
        body_html_sanitized=body_html_sanitized,
        labels=message.get("labelIds", []) or [],
        received_at=received_at,
        has_attachments=len(attachments) > 0,
        rfc_message_id=_header(headers, "Message-ID"),
        attachments=attachments,
    )
