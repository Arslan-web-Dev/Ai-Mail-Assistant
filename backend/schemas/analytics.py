from datetime import datetime

from pydantic import BaseModel


class AnalyticsSummary(BaseModel):
    start: datetime
    end: datetime
    total_emails: int
    emails_processed: int
    replies_generated: int
    replies_sent: int
    auto_replies: int
    manual_replies: int
    rejected_drafts: int
    failed_replies: int
    average_processing_time_seconds: float | None
    average_ai_confidence: float | None
    category_breakdown: dict[str, int]
    reply_activity: list[dict]
    automation_activity: dict[str, int]
