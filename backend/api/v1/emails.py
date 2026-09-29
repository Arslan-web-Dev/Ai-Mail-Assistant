"""
Emails API: cursor-paginated inbox listing (search/filter/sort — Module 5)
plus a detail endpoint surfacing the AI analysis and latest draft for one
email (Module 4). All queries are scoped strictly to the caller's own rows.
"""
from fastapi import APIRouter, HTTPException, Query, status

from app.dependencies import CurrentUser
from database.supabase_client import get_supabase_admin
from models.user import AuthenticatedUser
from schemas.email import CursorPage, EmailFilter
from services.email_query_service import list_emails as query_emails

router = APIRouter(prefix="/emails", tags=["emails"])


@router.get("", response_model=CursorPage)
async def list_emails(
    current_user: AuthenticatedUser = CurrentUser,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    search: str | None = Query(default=None, max_length=200),
    filter: EmailFilter = Query(default=EmailFilter.all),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
):
    try:
        items, next_cursor = query_emails(
            current_user.id,
            cursor=cursor,
            limit=limit,
            search=search,
            filter=filter,
            descending=(order == "desc"),
        )
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid pagination cursor")
    return CursorPage(items=items, next_cursor=next_cursor)


@router.get("/{email_id}")
async def get_email_detail(email_id: str, current_user: AuthenticatedUser = CurrentUser):
    """Full email detail, its AI analysis (if any), and its latest draft (if any)."""
    db = get_supabase_admin()
    email_result = (
        db.table("emails").select("*").eq("id", email_id).eq("user_id", current_user.id).limit(1).execute()
    )
    if not email_result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email not found")

    analysis_result = db.table("ai_analyses").select("*").eq("email_id", email_id).limit(1).execute()
    draft_result = (
        db.table("email_drafts")
        .select("*")
        .eq("email_id", email_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )

    return {
        "email": email_result.data[0],
        "analysis": analysis_result.data[0] if analysis_result.data else None,
        "draft": draft_result.data[0] if draft_result.data else None,
    }
