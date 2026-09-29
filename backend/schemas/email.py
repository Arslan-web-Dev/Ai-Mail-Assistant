from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class EmailSummary(BaseModel):
    id: str
    gmail_message_id: str
    gmail_thread_id: str
    sender: str
    recipient: str | None = None
    subject: str | None = None
    snippet: str | None = None
    received_at: datetime | None = None
    is_read: bool
    requires_reply: bool | None = None
    processing_status: str
    has_attachments: bool


class SyncResult(BaseModel):
    fetched: int
    stored: int
    duplicates: int
    failed: int
    new_email_ids: list[str] = []


class EmailFilter(str, Enum):
    all = "all"
    unread = "unread"
    needs_reply = "needs_reply"
    drafts = "drafts"
    sent = "sent"
    high_priority = "high_priority"
    job = "job"
    business = "business"
    meeting = "meeting"
    personal = "personal"


class CursorPage(BaseModel):
    items: list[dict]
    next_cursor: str | None = None
