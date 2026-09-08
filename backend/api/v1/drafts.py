"""
Draft management endpoints (Module 5). Every route resolves the draft
through the caller's verified user id — a draft_id alone is never enough
(see draft_service._get_owned_draft).

POST /drafts/{id}/approve performs the full approve-and-send flow in one
call (approve = send immediately, per product decision) — there is no
separate manual "send" endpoint.
"""
from fastapi import APIRouter, HTTPException, Query, status

from app.dependencies import CurrentUser
from models.user import AuthenticatedUser
from schemas.draft import DraftUpdate
from schemas.email import CursorPage
from services import draft_service

router = APIRouter(prefix="/drafts", tags=["drafts"])


def _map_draft_error(exc: draft_service.DraftError) -> HTTPException:
    if isinstance(exc, draft_service.DraftNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, draft_service.DraftAlreadySentError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, draft_service.InvalidDraftContentError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get("", response_model=CursorPage)
async def list_drafts(
    current_user: AuthenticatedUser = CurrentUser,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    draft_status: str | None = Query(default=None, alias="status"),
):
    try:
        items, next_cursor = draft_service.list_drafts(
            current_user.id, cursor=cursor, limit=limit, status=draft_status
        )
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid pagination cursor")
    return CursorPage(items=items, next_cursor=next_cursor)


@router.get("/{draft_id}")
async def get_draft(draft_id: str, current_user: AuthenticatedUser = CurrentUser):
    try:
        return draft_service.get_draft(current_user.id, draft_id)
    except draft_service.DraftError as exc:
        raise _map_draft_error(exc)


@router.patch("/{draft_id}")
async def edit_draft(draft_id: str, payload: DraftUpdate, current_user: AuthenticatedUser = CurrentUser):
    try:
        return draft_service.update_draft(current_user.id, draft_id, payload.edited_content, payload.subject)
    except draft_service.DraftError as exc:
        raise _map_draft_error(exc)


@router.post("/{draft_id}/regenerate")
async def regenerate_draft(draft_id: str, current_user: AuthenticatedUser = CurrentUser):
    try:
        return draft_service.regenerate_draft(current_user.id, draft_id)
    except draft_service.DraftError as exc:
        raise _map_draft_error(exc)


@router.post("/{draft_id}/reject")
async def reject_draft(draft_id: str, current_user: AuthenticatedUser = CurrentUser):
    try:
        return draft_service.reject_draft(current_user.id, draft_id)
    except draft_service.DraftError as exc:
        raise _map_draft_error(exc)


@router.post("/{draft_id}/approve")
async def approve_and_send(draft_id: str, current_user: AuthenticatedUser = CurrentUser):
    """Approve = send immediately. Full flow documented in draft_service.approve_and_send_draft."""
    try:
        return draft_service.approve_and_send_draft(current_user.id, draft_id)
    except draft_service.DraftError as exc:
        raise _map_draft_error(exc)
