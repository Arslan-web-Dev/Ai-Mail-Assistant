"""
AI analysis + reply generation endpoints (Module 4).

Both endpoints operate on a single email that must belong to the
authenticated caller — ownership is checked explicitly against the
verified user id before any AI call or database write (never trust an
email_id alone; this is the IDOR guard for these routes).

Neither endpoint sends anything via Gmail; they only create/update
`ai_analyses` and `email_drafts` rows for the user to review later.
"""
from fastapi import APIRouter, HTTPException, status

from app.dependencies import CurrentUser
from database.supabase_client import get_supabase_admin
from models.user import AuthenticatedUser
from schemas.ai import AIAnalysisResult
from services import ai_analyzer, reply_generator
from services.auth_service import get_profile
from services.user_preferences_service import get_or_create_preferences

router = APIRouter(prefix="/emails", tags=["ai"])


def _get_owned_email(user_id: str, email_id: str) -> dict:
    result = (
        get_supabase_admin()
        .table("emails")
        .select("*")
        .eq("id", email_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email not found")
    return result.data[0]


@router.post("/{email_id}/analyze", response_model=AIAnalysisResult)
async def analyze_email_endpoint(email_id: str, current_user: AuthenticatedUser = CurrentUser):
    """Run (or re-run) AI classification for one of the caller's own emails."""
    email_row = _get_owned_email(current_user.id, email_id)
    return ai_analyzer.analyze_email(current_user.id, email_row)


@router.post("/{email_id}/generate-reply")
async def generate_reply_endpoint(email_id: str, current_user: AuthenticatedUser = CurrentUser):
    """
    Generate a reply draft. Reuses an existing analysis if one exists;
    otherwise runs analysis first. Always requires the email to belong to
    the caller.
    """
    email_row = _get_owned_email(current_user.id, email_id)

    db = get_supabase_admin()
    existing_analysis = db.table("ai_analyses").select("*").eq("email_id", email_id).limit(1).execute()
    if existing_analysis.data:
        row = existing_analysis.data[0]
        analysis = AIAnalysisResult(
            category=row["category"],
            intent=row["intent"],
            priority=row["priority"],
            sentiment=row["sentiment"],
            requires_reply=row["requires_reply"],
            sensitivity_level=row["sensitivity_level"],
            confidence=row["confidence"] or 0.0,
        )
    else:
        analysis = ai_analyzer.analyze_email(current_user.id, email_row)

    profile = get_profile(current_user)
    preferences = get_or_create_preferences(current_user.id)

    draft = reply_generator.generate_reply(current_user.id, email_row, analysis, profile, preferences)
    if draft is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to generate a reply after retrying; marked for manual review",
        )
    return draft
