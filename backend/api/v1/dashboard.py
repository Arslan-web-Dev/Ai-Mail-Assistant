from fastapi import APIRouter

from app.dependencies import CurrentUser
from models.user import AuthenticatedUser
from services.dashboard_service import get_stats

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats")
async def dashboard_stats(current_user: AuthenticatedUser = CurrentUser):
    return get_stats(current_user.id)
