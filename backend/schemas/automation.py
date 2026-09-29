import re

from pydantic import BaseModel, Field, field_validator

from schemas.ai import EmailCategory

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


class AutomationSettings(BaseModel):
    auto_reply_enabled: bool
    paused: bool
    minimum_ai_confidence: float = Field(ge=0.0, le=1.0)
    allowed_categories: list[str] = Field(default_factory=list)
    blocked_categories: list[str] = Field(default_factory=list)
    require_approval_for_medium_risk: bool
    daily_reply_limit: int = Field(ge=0)
    business_hours_enabled: bool
    business_hours_start: str
    business_hours_end: str
    business_hours_timezone: str
    signature_enabled: bool


class AutomationSettingsUpdate(BaseModel):
    """All fields optional — PATCH semantics; only provided fields are updated."""

    auto_reply_enabled: bool | None = None
    paused: bool | None = None
    minimum_ai_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    allowed_categories: list[EmailCategory] | None = None
    blocked_categories: list[EmailCategory] | None = None
    require_approval_for_medium_risk: bool | None = None
    daily_reply_limit: int | None = Field(default=None, ge=0, le=1000)
    business_hours_enabled: bool | None = None
    business_hours_start: str | None = None
    business_hours_end: str | None = None
    business_hours_timezone: str | None = None
    signature_enabled: bool | None = None

    @field_validator("business_hours_start", "business_hours_end")
    @classmethod
    def _validate_time_format(cls, v: str | None) -> str | None:
        if v is not None and not _TIME_RE.match(v):
            raise ValueError("Time must be in HH:MM 24-hour format")
        return v

    def to_update_dict(self) -> dict:
        data = self.model_dump(exclude_none=True)
        # EmailCategory values need to become plain strings for JSON storage.
        for key in ("allowed_categories", "blocked_categories"):
            if key in data:
                data[key] = [c.value if hasattr(c, "value") else c for c in data[key]]
        return data
