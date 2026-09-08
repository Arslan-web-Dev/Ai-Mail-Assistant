"""
Auth endpoints.

Actual Google sign-in happens client-side via Supabase Auth (see
frontend/utils/supabaseClient.ts + frontend/services/authService.ts). The
frontend then sends the resulting Supabase access token on every request as
`Authorization: Bearer <token>`. These endpoints just verify that token and
expose/maintain the corresponding backend profile.
"""
from fastapi import APIRouter

from app.dependencies import CurrentUser
from models.user import AuthenticatedUser
from schemas.auth import SessionResponse
from services.auth_service import ensure_profile, get_profile

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/session", response_model=SessionResponse)
async def get_session(current_user: AuthenticatedUser = CurrentUser):
    """Return the current authenticated user's profile. Protected route."""
    profile = ensure_profile(current_user)
    return SessionResponse(
        id=profile["id"],
        email=profile.get("email"),
        full_name=profile.get("full_name"),
        avatar_url=profile.get("avatar_url"),
    )


@router.post("/logout")
async def logout(current_user: AuthenticatedUser = CurrentUser):
    """
    Sign-out is primarily a frontend action (Supabase clears the local
    session). This endpoint exists for symmetry / future server-side
    session invalidation (e.g. revoking refresh tokens) and simply confirms
    the caller was authenticated.
    """
    return {"detail": "Logged out"}
