from enum import Enum

from pydantic import BaseModel, Field


class EmailCategory(str, Enum):
    job = "job"
    internship = "internship"
    business = "business"
    meeting = "meeting"
    networking = "networking"
    customer_support = "customer_support"
    university = "university"
    personal = "personal"
    newsletter = "newsletter"
    notification = "notification"
    spam = "spam"
    other = "other"


class PriorityLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


class SentimentLevel(str, Enum):
    positive = "positive"
    neutral = "neutral"
    negative = "negative"
    mixed = "mixed"


class SensitivityLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ReplyTone(str, Enum):
    professional = "Professional"
    friendly = "Friendly"
    formal = "Formal"
    concise = "Concise"
    confident = "Confident"


class AIAnalysisResult(BaseModel):
    """Validated shape of the AI analyzer's JSON output (see ai_analyzer.py)."""

    category: EmailCategory
    intent: str = Field(min_length=1, max_length=500)
    priority: PriorityLevel
    sentiment: SentimentLevel
    requires_reply: bool
    sensitivity_level: SensitivityLevel
    confidence: float = Field(ge=0.0, le=1.0)


class ReplyGenerationResult(BaseModel):
    """Validated shape of the reply generator's JSON output (see reply_generator.py)."""

    subject: str = Field(min_length=1, max_length=300)
    reply: str = Field(min_length=1, max_length=20_000)
    confidence: float = Field(ge=0.0, le=1.0)
    requires_review: bool


class ReplyLength(str, Enum):
    short = "short"
    medium = "medium"
    long = "long"


class AIPreferences(BaseModel):
    tone: str
    language: str
    signature: str | None = None
    custom_instructions: str | None = None
    reply_length: ReplyLength = ReplyLength.medium
    auto_reply_enabled: bool = False


class AIPreferencesUpdate(BaseModel):
    tone: ReplyTone | None = None
    language: str | None = Field(default=None, max_length=10)
    signature: str | None = Field(default=None, max_length=2000)
    custom_instructions: str | None = Field(default=None, max_length=5000)
    reply_length: ReplyLength | None = None

    def to_update_dict(self) -> dict:
        data = self.model_dump(exclude_none=True)
        for key in ("tone", "reply_length"):
            if key in data and hasattr(data[key], "value"):
                data[key] = data[key].value
        return data


class ReplyPreviewRequest(BaseModel):
    tone: ReplyTone | None = None
    signature: str | None = Field(default=None, max_length=2000)
    custom_instructions: str | None = Field(default=None, max_length=5000)
