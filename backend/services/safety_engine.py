"""
safety_engine.py

The core Module 6 safety decision engine: given an email's AI analysis and
the user's automation settings (plus a couple of dynamic facts — today's
auto-send count, whether we're in business hours), decides whether a reply
is safe to auto-send, needs manual review, should be blocked from
automation entirely, or should simply be ignored (spam).

`decide()` is intentionally pure (no I/O, no database, no network) so it
can be exhaustively unit-tested — see tests/test_automation.py for the
full decision matrix. All the impure parts (fetching settings, counting
today's auto-sends, checking business hours, and actually sending) live in
automation_service.py, which calls this function and never overrides its
result.

HARD SAFETY FLOOR — these two checks run first and CANNOT be bypassed by
any user setting, including a fully-enabled, wide-open automation
configuration:
  - sensitivity_level HIGH or CRITICAL always forces MANUAL_REVIEW. This is
    where legal, financial, medical, password-reset/account-recovery,
    security, and unknown/suspicious-sender emails get caught — see the
    sensitivity classification rules in ai_analyzer.py's SYSTEM_PROMPT.
  - category "spam" is always IGNORE, never sent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from schemas.ai import AIAnalysisResult


class SafetyDecision(str, Enum):
    AUTO_SEND = "AUTO_SEND"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    BLOCK = "BLOCK"
    IGNORE = "IGNORE"


@dataclass
class DecisionContext:
    """Pre-computed, already-fetched inputs — decide() itself does no I/O."""

    automation_enabled: bool
    paused: bool
    minimum_confidence: float
    require_approval_for_medium_risk: bool
    daily_limit: int
    sent_today_count: int
    within_business_hours: bool
    draft_requires_review: bool
    allowed_categories: list[str] = field(default_factory=list)
    blocked_categories: list[str] = field(default_factory=list)


@dataclass
class Decision:
    decision: SafetyDecision
    reason: str


def decide(analysis: AIAnalysisResult, ctx: DecisionContext) -> Decision:
    # --- Hard safety floor: cannot be overridden by any setting ---
    if analysis.category.value == "spam":
        return Decision(SafetyDecision.IGNORE, "category=spam")

    if analysis.sensitivity_level.value in ("HIGH", "CRITICAL"):
        return Decision(
            SafetyDecision.MANUAL_REVIEW,
            f"sensitivity_level={analysis.sensitivity_level.value} "
            "(legal/financial/medical/security-class content always requires a human)",
        )

    # --- User automation configuration (all overridable, all safe defaults) ---
    if ctx.paused:
        return Decision(SafetyDecision.MANUAL_REVIEW, "automation paused by user")

    if not ctx.automation_enabled:
        return Decision(SafetyDecision.MANUAL_REVIEW, "automation disabled")

    if ctx.blocked_categories and analysis.category.value in ctx.blocked_categories:
        return Decision(SafetyDecision.BLOCK, f"category={analysis.category.value} is in blocked_categories")

    if ctx.allowed_categories and analysis.category.value not in ctx.allowed_categories:
        return Decision(SafetyDecision.MANUAL_REVIEW, f"category={analysis.category.value} not in allowed_categories")

    if ctx.require_approval_for_medium_risk and analysis.sensitivity_level.value == "MEDIUM":
        return Decision(SafetyDecision.MANUAL_REVIEW, "sensitivity_level=MEDIUM requires approval per user setting")

    if analysis.confidence < ctx.minimum_confidence:
        return Decision(
            SafetyDecision.MANUAL_REVIEW,
            f"confidence={analysis.confidence:.2f} below minimum_confidence={ctx.minimum_confidence:.2f}",
        )

    if ctx.draft_requires_review:
        return Decision(SafetyDecision.MANUAL_REVIEW, "draft flagged requires_review")

    if ctx.daily_limit > 0 and ctx.sent_today_count >= ctx.daily_limit:
        return Decision(SafetyDecision.MANUAL_REVIEW, f"daily_reply_limit={ctx.daily_limit} reached")

    if not ctx.within_business_hours:
        return Decision(SafetyDecision.MANUAL_REVIEW, "outside configured business hours")

    return Decision(SafetyDecision.AUTO_SEND, "passed all automation checks")
