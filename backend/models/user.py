"""
Internal representation of the authenticated user, derived exclusively from
a verified Supabase JWT. This is what `get_current_user` returns — routes
and services must use `current_user.id`, never a client-supplied user id.
"""
from pydantic import BaseModel


class AuthenticatedUser(BaseModel):
    id: str          # Supabase auth.users.id (UUID string), the ONLY trusted user id
    email: str | None = None
