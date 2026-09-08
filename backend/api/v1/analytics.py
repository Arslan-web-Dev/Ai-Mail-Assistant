"""
Analytics endpoint (Module 7). Supports the spec's date filters: 7/30/90
days, or a custom [start, end) range. All figures are scoped to the
caller's own data (see analytics_service.py).
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, status

from app.dependencies import CurrentUser
from models.user import AuthenticatedUser
from schemas.analytics import AnalyticsSummary
from services.analytics_service import get_summary

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary", response_model=AnalyticsSummary)
async def analytics_summary(
    current_user: AuthenticatedUser = CurrentUser,
    range: str = Query(default="30d", pattern="^(7d|30d|90d|custom)$"),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
):
    now = datetime.now(timezone.utc)

    if range == "custom":
        if not start or not end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start and end are required when range=custom",
            )
        if start >= end:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="start must be before end")
    else:
        days = {"7d": 7, "30d": 30, "90d": 90}[range]
        end = now
        start = now - timedelta(days=days)

    return get_summary(current_user.id, start, end)
