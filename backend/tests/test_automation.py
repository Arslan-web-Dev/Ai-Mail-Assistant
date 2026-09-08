"""
Tests for Module 6: the safety decision engine + automation orchestration.

test_safety_engine_decision_matrix covers every example from the product
spec directly: job/low-risk/high-confidence -> AUTO_SEND; sensitive
categories (legal/financial/medical, represented via sensitivity HIGH) ->
MANUAL_REVIEW; spam -> IGNORE; unknown high-risk sender (sensitivity HIGH)
-> MANUAL_REVIEW; blocked category -> BLOCK.
"""
import pytest

from schemas.ai import AIAnalysisResult
from services import automation_service, draft_service
from services.safety_engine import DecisionContext, SafetyDecision, decide

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _analysis(**overrides) -> AIAnalysisResult:
    base = {
        "category": "job",
        "intent": "Following up",
        "priority": "medium",
        "sentiment": "positive",
        "requires_reply": True,
        "sensitivity_level": "LOW",
        "confidence": 0.95,
    }
    base.update(overrides)
    return AIAnalysisResult(**base)


def _ctx(**overrides) -> DecisionContext:
    base = dict(
        automation_enabled=True,
        paused=False,
        minimum_confidence=0.9,
        allowed_categories=[],
        blocked_categories=["spam"],
        require_approval_for_medium_risk=True,
        daily_limit=20,
        sent_today_count=0,
        within_business_hours=True,
        draft_requires_review=False,
    )
    base.update(overrides)
    return DecisionContext(**base)


# ---------------------------------------------------------------------
# Decision matrix — directly from the product spec's examples
# ---------------------------------------------------------------------


def test_job_low_risk_high_confidence_automation_enabled_auto_sends():
    result = decide(_analysis(category="job", sensitivity_level="LOW", confidence=0.95), _ctx())
    assert result.decision == SafetyDecision.AUTO_SEND


def test_sensitive_category_via_high_sensitivity_forces_manual_review():
    """Legal/financial/medical-class content is captured by sensitivity HIGH/CRITICAL, not a category name."""
    result = decide(_analysis(category="business", sensitivity_level="HIGH", confidence=0.99), _ctx())
    assert result.decision == SafetyDecision.MANUAL_REVIEW
    assert "sensitivity_level=HIGH" in result.reason


def test_critical_sensitivity_forces_manual_review_even_with_perfect_confidence():
    result = decide(_analysis(sensitivity_level="CRITICAL", confidence=1.0), _ctx(automation_enabled=True))
    assert result.decision == SafetyDecision.MANUAL_REVIEW


def test_spam_is_always_ignored():
    result = decide(_analysis(category="spam", confidence=1.0), _ctx())
    assert result.decision == SafetyDecision.IGNORE


def test_unknown_high_risk_sender_via_sensitivity_forces_manual_review():
    # ai_analyzer's prompt explicitly assigns HIGH/CRITICAL sensitivity to
    # unknown/unclear senders, so this case is covered by the sensitivity check.
    result = decide(_analysis(sensitivity_level="HIGH", intent="unclear, unknown sender"), _ctx())
    assert result.decision == SafetyDecision.MANUAL_REVIEW


def test_blocked_category_is_blocked_not_just_reviewed():
    result = decide(_analysis(category="personal"), _ctx(blocked_categories=["personal"]))
    assert result.decision == SafetyDecision.BLOCK


def test_category_not_in_allowlist_requires_manual_review():
    result = decide(_analysis(category="networking"), _ctx(allowed_categories=["job", "business"]))
    assert result.decision == SafetyDecision.MANUAL_REVIEW


def test_category_in_allowlist_can_auto_send():
    result = decide(_analysis(category="job"), _ctx(allowed_categories=["job", "business"]))
    assert result.decision == SafetyDecision.AUTO_SEND


# ---------------------------------------------------------------------
# Hard safety floor cannot be bypassed by settings
# ---------------------------------------------------------------------


def test_sensitivity_floor_cannot_be_bypassed_by_wide_open_settings():
    wide_open_ctx = _ctx(
        automation_enabled=True,
        minimum_confidence=0.0,
        allowed_categories=[],
        blocked_categories=[],
        require_approval_for_medium_risk=False,
        daily_limit=0,
    )
    result = decide(_analysis(sensitivity_level="CRITICAL", confidence=1.0), wide_open_ctx)
    assert result.decision == SafetyDecision.MANUAL_REVIEW


def test_spam_floor_cannot_be_bypassed_even_if_spam_not_in_blocked_list():
    result = decide(_analysis(category="spam", confidence=1.0), _ctx(blocked_categories=[]))
    assert result.decision == SafetyDecision.IGNORE


# ---------------------------------------------------------------------
# User configuration checks
# ---------------------------------------------------------------------


def test_automation_disabled_forces_manual_review():
    result = decide(_analysis(), _ctx(automation_enabled=False))
    assert result.decision == SafetyDecision.MANUAL_REVIEW


def test_paused_forces_manual_review_even_if_enabled():
    result = decide(_analysis(), _ctx(automation_enabled=True, paused=True))
    assert result.decision == SafetyDecision.MANUAL_REVIEW


def test_medium_sensitivity_requires_approval_when_configured():
    result = decide(_analysis(sensitivity_level="MEDIUM"), _ctx(require_approval_for_medium_risk=True))
    assert result.decision == SafetyDecision.MANUAL_REVIEW


def test_medium_sensitivity_can_auto_send_when_not_required():
    result = decide(_analysis(sensitivity_level="MEDIUM", confidence=0.95), _ctx(require_approval_for_medium_risk=False))
    assert result.decision == SafetyDecision.AUTO_SEND


def test_confidence_below_threshold_forces_manual_review():
    result = decide(_analysis(confidence=0.5), _ctx(minimum_confidence=0.9))
    assert result.decision == SafetyDecision.MANUAL_REVIEW


def test_draft_requires_review_flag_forces_manual_review():
    result = decide(_analysis(confidence=0.99), _ctx(draft_requires_review=True))
    assert result.decision == SafetyDecision.MANUAL_REVIEW


def test_daily_limit_reached_forces_manual_review():
    result = decide(_analysis(), _ctx(daily_limit=5, sent_today_count=5))
    assert result.decision == SafetyDecision.MANUAL_REVIEW


def test_daily_limit_not_yet_reached_allows_auto_send():
    result = decide(_analysis(), _ctx(daily_limit=5, sent_today_count=4))
    assert result.decision == SafetyDecision.AUTO_SEND


def test_daily_limit_zero_means_unlimited():
    result = decide(_analysis(), _ctx(daily_limit=0, sent_today_count=10_000))
    assert result.decision == SafetyDecision.AUTO_SEND


def test_outside_business_hours_forces_manual_review():
    result = decide(_analysis(), _ctx(within_business_hours=False))
    assert result.decision == SafetyDecision.MANUAL_REVIEW


# ---------------------------------------------------------------------
# Business-hours helper
# ---------------------------------------------------------------------


def test_business_hours_disabled_always_within_hours():
    assert automation_service._within_business_hours({"business_hours_enabled": False}) is True


def test_business_hours_invalid_timezone_fails_closed():
    settings = {
        "business_hours_enabled": True,
        "business_hours_timezone": "Not/A_Real_Zone",
        "business_hours_start": "09:00",
        "business_hours_end": "18:00",
    }
    assert automation_service._within_business_hours(settings) is False


# ---------------------------------------------------------------------
# Orchestration (evaluate_and_maybe_send) with mocked DB + send
# ---------------------------------------------------------------------


class _FakeTable:
    def __init__(self, data_by_table: dict, name: str):
        self.data_by_table = data_by_table
        self.name = name
        self._filters = {}
        self._select = False

    def select(self, *_a, **_k):
        self._select = True
        return self

    def eq(self, key, value):
        self._filters[key] = value
        return self

    def gte(self, *_a, **_k):
        return self

    def limit(self, _n):
        return self

    def insert(self, payload):
        rows = self.data_by_table.setdefault(self.name, [])
        rows.append(dict(payload))
        self._inserted = payload
        return self

    def update(self, payload):
        rows = self.data_by_table.get(self.name, [])
        for row in rows:
            if all(row.get(k) == v for k, v in self._filters.items()):
                row.update(payload)
        self._inserted = None
        return self

    def execute(self):
        class _Result:
            def __init__(self, data, count=None):
                self.data = data
                self.count = count

        if getattr(self, "_inserted", None) is not None:
            return _Result([self._inserted])

        rows = self.data_by_table.get(self.name, [])
        matched = [r for r in rows if all(r.get(k) == v for k, v in self._filters.items())]
        return _Result(matched, count=len(matched))


class _FakeDB:
    def __init__(self, data):
        self.data = data

    def table(self, name):
        return _FakeTable(self.data, name)


@pytest.fixture
def automation_fixture(monkeypatch):
    data = {
        "ai_analyses": [
            {
                "email_id": "email-1",
                "category": "job",
                "intent": "test",
                "priority": "medium",
                "sentiment": "positive",
                "requires_reply": True,
                "sensitivity_level": "LOW",
                "confidence": 0.95,
            }
        ],
        "email_drafts": [{"id": "draft-1", "email_id": "email-1", "user_id": "user-1", "requires_review": False, "status": "ready"}],
        "automation_settings": [],
        "sent_emails": [],
        "email_processing_logs": [],
    }
    db = _FakeDB(data)
    monkeypatch.setattr(automation_service, "get_supabase_admin", lambda: db)
    return data


def test_evaluate_and_maybe_send_auto_sends_when_enabled(monkeypatch, automation_fixture):
    automation_fixture["automation_settings"].append(
        {**automation_service.DEFAULT_SETTINGS, "user_id": "user-1", "auto_reply_enabled": True}
    )

    monkeypatch.setattr(
        draft_service, "approve_and_send_draft", lambda user_id, draft_id, sent_via="manual": {"status": "sent"}
    )

    decision = automation_service.evaluate_and_maybe_send("user-1", "email-1", "draft-1")
    assert decision == SafetyDecision.AUTO_SEND


def test_evaluate_and_maybe_send_does_not_send_when_disabled(monkeypatch, automation_fixture):
    called = {"n": 0}

    def fake_send(*_a, **_k):
        called["n"] += 1
        return {"status": "sent"}

    monkeypatch.setattr(draft_service, "approve_and_send_draft", fake_send)

    # No automation_settings row -> defaults -> auto_reply_enabled=False
    decision = automation_service.evaluate_and_maybe_send("user-1", "email-1", "draft-1")

    assert decision == SafetyDecision.MANUAL_REVIEW
    assert called["n"] == 0  # never attempted a send


def test_evaluate_and_maybe_send_handles_already_sent_gracefully(monkeypatch, automation_fixture):
    automation_fixture["automation_settings"].append(
        {**automation_service.DEFAULT_SETTINGS, "user_id": "user-1", "auto_reply_enabled": True}
    )

    def fake_send(*_a, **_k):
        raise draft_service.DraftAlreadySentError("already sent")

    monkeypatch.setattr(draft_service, "approve_and_send_draft", fake_send)

    decision = automation_service.evaluate_and_maybe_send("user-1", "email-1", "draft-1")
    assert decision == SafetyDecision.AUTO_SEND  # decision was correct; the send was just redundant


# ---------------------------------------------------------------------
# Endpoint auth boundaries
# ---------------------------------------------------------------------


def test_automation_endpoints_require_auth():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    assert client.get("/api/v1/automation/settings").status_code == 401
    assert client.patch("/api/v1/automation/settings", json={"auto_reply_enabled": True}).status_code == 401
    assert client.post("/api/v1/automation/pause").status_code == 401
    assert client.post("/api/v1/automation/resume").status_code == 401
