"""
Google OAuth 2.0 flow for connecting Gmail.

This is separate from the user's *sign-in* identity (handled by Supabase
Auth on the frontend). This flow grants the backend permission to read/send
Gmail on the user's behalf, and is always tied to an already-authenticated
Supabase user id via a server-side, single-use `state` token.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from app.config import settings
from database.supabase_client import get_supabase_admin

STATE_TTL_MINUTES = 10


def _client_config() -> dict:
    return {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.google_redirect_uri],
        }
    }


def create_oauth_state(user_id: str) -> str:
    """Generate a CSRF-safe, single-use state token bound to `user_id`."""
    state = secrets.token_urlsafe(32)
    db = get_supabase_admin()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=STATE_TTL_MINUTES)
    db.table("oauth_states").insert(
        {"state": state, "user_id": user_id, "expires_at": expires_at.isoformat()}
    ).execute()
    return state


def consume_oauth_state(state: str) -> str | None:
    """Validate and delete a state token. Returns the bound user_id, or None."""
    db = get_supabase_admin()
    result = db.table("oauth_states").select("*").eq("state", state).limit(1).execute()
    if not result.data:
        return None

    row = result.data[0]
    db.table("oauth_states").delete().eq("state", state).execute()  # single-use

    expires_at = datetime.fromisoformat(row["expires_at"])
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        return None

    return row["user_id"]


def build_authorization_url(user_id: str) -> str:
    flow = Flow.from_client_config(
        _client_config(),
        scopes=settings.google_scopes_list,
        redirect_uri=settings.google_redirect_uri,
    )
    state = create_oauth_state(user_id)
    authorization_url, _ = flow.authorization_url(
        access_type="offline",       # required to receive a refresh token
        include_granted_scopes="true",
        prompt="consent",            # ensures a refresh token even on re-auth
        state=state,
    )
    return authorization_url


def exchange_code_for_credentials(code: str) -> Credentials:
    flow = Flow.from_client_config(
        _client_config(),
        scopes=settings.google_scopes_list,
        redirect_uri=settings.google_redirect_uri,
    )
    flow.fetch_token(code=code)
    return flow.credentials
