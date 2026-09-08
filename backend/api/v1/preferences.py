"""
AI writing-preferences endpoints (Module 7): tone, language, signature,
custom instructions, reply length, and a "preview a reply" action so the
user can see what their settings produce before relying on them for real
email. The preview runs against a fixed synthetic sample email — it never
touches the user's real inbox — but through the exact same
reply_generator.py code path (and therefore the exact same safety rules:
user custom_instructions can steer style, never override the system
prompt's safety rules).
"""
from fastapi import APIRouter

from app.dependencies import CurrentUser
from models.user import AuthenticatedUser
from schemas.ai import AIPreferences, AIPreferencesUpdate, ReplyPreviewRequest
from schemas.ai import AIAnalysisResult
from services.auth_service import get_profile
from services.reply_generator import _build_user_prompt, _call_with_retry
from services.user_preferences_service import get_or_create_preferences, update_preferences

router = APIRouter(prefix="/ai", tags=["ai-preferences"])

_SAMPLE_EMAIL = {
    "id": "preview",
    "sender": "Jordan Rivera <jordan.rivera@example.com>",
    "subject": "Quick question about your availability",
    "body_text": (
        "Hi, I hope you're doing well. I wanted to check if you'd be available "
        "for a call sometime next week to discuss a potential opportunity. "
        "Let me know what works for you.\n\nBest,\nJordan"
    ),
}

_SAMPLE_ANALYSIS = AIAnalysisResult(
    category="networking",
    intent="Requesting a call to discuss an opportunity",
    priority="medium",
    sentiment="positive",
    requires_reply=True,
    sensitivity_level="LOW",
    confidence=0.9,
)


@router.get("/preferences", response_model=AIPreferences)
async def get_preferences(current_user: AuthenticatedUser = CurrentUser):
    return get_or_create_preferences(current_user.id)


@router.patch("/preferences", response_model=AIPreferences)
async def patch_preferences(payload: AIPreferencesUpdate, current_user: AuthenticatedUser = CurrentUser):
    return update_preferences(current_user.id, payload.to_update_dict())


@router.post("/preview-reply")
async def preview_reply(payload: ReplyPreviewRequest, current_user: AuthenticatedUser = CurrentUser):
    """
    Generates a sample reply using either the provided (unsaved) preference
    overrides or the user's saved preferences — without writing anything to
    the database. Lets the settings UI show a live preview as the user
    adjusts tone/signature/instructions before saving.
    """
    saved = get_or_create_preferences(current_user.id)
    preferences = {
        "tone": (payload.tone.value if payload.tone else saved.get("tone", "Professional")),
        "language": saved.get("language", "en"),
        "signature": payload.signature if payload.signature is not None else saved.get("signature"),
        "custom_instructions": (
            payload.custom_instructions if payload.custom_instructions is not None else saved.get("custom_instructions")
        ),
    }
    profile = get_profile(current_user)

    prompt = _build_user_prompt(_SAMPLE_EMAIL, _SAMPLE_ANALYSIS, profile, preferences)
    result = _call_with_retry(prompt, current_user.id, "preview")

    if result is None:
        return {"subject": None, "reply": None, "error": "Preview generation failed — please try again."}

    return {"subject": result.subject, "reply": result.reply}
