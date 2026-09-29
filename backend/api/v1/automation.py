"""
Automation settings endpoints (Module 6). Every route is scoped to the
caller's own settings row — the user controls: enable/disable automation,
pause/resume, allowed/blocked categories, confidence threshold, daily
reply limit, business hours, and whether to require approval for
medium-risk emails. None of these settings can weaken the hard safety
floor in services/safety_engine.py (sensitivity HIGH/CRITICAL always
forces manual review; spam is always ignored) — that floor is not
represented as a setting at all, so there's nothing here that could
disable it.
"""
from fastapi import APIRouter

from app.dependencies import CurrentUser
from models.user import AuthenticatedUser
from schemas.automation import AutomationSettings, AutomationSettingsUpdate
from services import automation_service

router = APIRouter(prefix="/automation", tags=["automation"])


@router.get("/settings", response_model=AutomationSettings)
async def get_settings(current_user: AuthenticatedUser = CurrentUser):
    return automation_service.get_or_create_settings(current_user.id)


@router.patch("/settings", response_model=AutomationSettings)
async def patch_settings(payload: AutomationSettingsUpdate, current_user: AuthenticatedUser = CurrentUser):
    return automation_service.update_settings(current_user.id, payload.to_update_dict())


@router.post("/pause", response_model=AutomationSettings)
async def pause_automation(current_user: AuthenticatedUser = CurrentUser):
    return automation_service.set_paused(current_user.id, True)


@router.post("/resume", response_model=AutomationSettings)
async def resume_automation(current_user: AuthenticatedUser = CurrentUser):
    return automation_service.set_paused(current_user.id, False)
