from enum import Enum

from pydantic import BaseModel, Field


class DraftStatus(str, Enum):
    generating = "generating"
    ready = "ready"
    edited = "edited"
    approved = "approved"
    rejected = "rejected"
    sent = "sent"
    failed = "failed"


class DraftUpdate(BaseModel):
    edited_content: str = Field(min_length=1, max_length=20_000)
    subject: str | None = Field(default=None, max_length=300)
