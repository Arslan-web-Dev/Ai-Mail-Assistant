"""
Auth-related business logic. The frontend performs the actual Google sign-in
via Supabase Auth (see frontend/utils/supabaseClient.ts) and hands the
backend a verified access token on every request. This service is
responsible for making sure a `profiles` row exists for that user and for
returning profile data — always scoped to the verified user id.
"""
from __future__ import annotations

from database.supabase_client import get_supabase_admin
from models.user import AuthenticatedUser
from services.db_utils import get_or_create_row


def ensure_profile(user: AuthenticatedUser) -> dict:
    """Create the profiles row on first login (race-safe — see db_utils.get_or_create_row)."""
    return get_or_create_row(get_supabase_admin(), "profiles", "id", user.id, {"email": user.email or ""})


def get_profile(user: AuthenticatedUser) -> dict:
    db = get_supabase_admin()
    result = (
        db.table("profiles").select("*").eq("id", user.id).limit(1).execute()
    )
    if result.data:
        return result.data[0]
    # Defensive fallback: provision on the fly if somehow missing.
    return ensure_profile(user)


def update_profile(user_id: str, updates: dict) -> dict:
    db = get_supabase_admin()
    if updates:
        db.table("profiles").update(updates).eq("id", user_id).execute()
    result = db.table("profiles").select("*").eq("id", user_id).limit(1).execute()
    return result.data[0] if result.data else {"id": user_id, **updates}
