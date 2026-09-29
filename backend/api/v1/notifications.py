"""
Notifications endpoints (Module 7). Every route is scoped to the caller's
own notifications — ownership is enforced by the service layer's explicit
.eq("user_id", user_id) filters, defense in depth alongside RLS.
"""
from fastapi import APIRouter, HTTPException, Query

from app.dependencies import CurrentUser
from models.user import AuthenticatedUser
from schemas.email import CursorPage
from services import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=CursorPage)
async def list_notifications(
    current_user: AuthenticatedUser = CurrentUser,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    unread_only: bool = Query(default=False),
):
    try:
        items, next_cursor = notification_service.list_notifications(
            current_user.id, cursor=cursor, limit=limit, unread_only=unread_only
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid pagination cursor")
    return CursorPage(items=items, next_cursor=next_cursor)


@router.get("/unread-count")
async def unread_count(current_user: AuthenticatedUser = CurrentUser):
    return {"count": notification_service.count_unread(current_user.id)}


@router.post("/{notification_id}/read")
async def mark_read(notification_id: str, current_user: AuthenticatedUser = CurrentUser):
    notification_service.mark_read(current_user.id, notification_id)
    return {"status": "ok"}


@router.post("/read-all")
async def mark_all_read(current_user: AuthenticatedUser = CurrentUser):
    notification_service.mark_all_read(current_user.id)
    return {"status": "ok"}


@router.delete("/{notification_id}")
async def delete_notification(notification_id: str, current_user: AuthenticatedUser = CurrentUser):
    notification_service.delete_notification(current_user.id, notification_id)
    return {"status": "ok"}
