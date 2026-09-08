"""
Profile endpoints (Module 7). Returns/updates the caller's own `profiles`
row only. This never includes or accepts Gmail OAuth tokens — those live
exclusively in `gmail_connections` (Module 2) and are never serialized
into any API response.
"""
from fastapi import APIRouter

from app.dependencies import CurrentUser
from models.user import AuthenticatedUser
from schemas.profile import ProfileUpdate
from services.auth_service import get_profile, update_profile

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("")
async def get_my_profile(current_user: AuthenticatedUser = CurrentUser):
    return get_profile(current_user)


@router.patch("")
async def update_my_profile(payload: ProfileUpdate, current_user: AuthenticatedUser = CurrentUser):
    return update_profile(current_user.id, payload.to_update_dict())
