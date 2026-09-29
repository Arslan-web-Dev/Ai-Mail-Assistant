"""
gmail_service.py

Handles everything Gmail-API related for a given (already-authenticated)
user:
- persisting OAuth tokens (encrypted at rest)
- checking connection status
- refreshing expired access tokens
- fetching the Gmail profile
- disconnecting (revoking + deleting stored tokens)

Errors are normalized into GmailServiceError subclasses so the API layer can
map them to sensible HTTP responses instead of leaking raw Google errors.
"""
from __future__ import annotations

from datetime import datetime, timezone

import httpx
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import settings
from database.supabase_client import get_supabase_admin
from utils.security import decrypt_secret, encrypt_secret


class GmailServiceError(Exception):
    """Base class for Gmail integration errors."""


class GmailNotConnectedError(GmailServiceError):
    pass


class GmailAuthError(GmailServiceError):
    """Token expired/revoked and could not be refreshed — user must reconnect."""


class GmailRateLimitError(GmailServiceError):
    pass


class GmailApiError(GmailServiceError):
    pass


def _table():
    return get_supabase_admin().table("gmail_connections")


def save_credentials(user_id: str, credentials: Credentials) -> dict:
    """Fetch the Gmail profile and persist encrypted tokens for this user."""
    try:
        service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
        profile = service.users().getProfile(userId="me").execute()
    except HttpError as exc:
        raise GmailApiError(f"Failed to fetch Gmail profile: {exc}") from exc

    expiry = credentials.expiry
    if expiry is None:
        # google-auth may not always set this; default to now (forces refresh on first use)
        expiry = datetime.now(timezone.utc)
    elif expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)

    payload = {
        "user_id": user_id,
        "gmail_email": profile.get("emailAddress", ""),
        "encrypted_access_token": encrypt_secret(credentials.token),
        "encrypted_refresh_token": encrypt_secret(credentials.refresh_token or ""),
        "scopes": " ".join(credentials.scopes or settings.google_scopes_list),
        "token_expiry": expiry.isoformat(),
        "status": "connected",
        "last_error": None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    existing = _table().select("user_id").eq("user_id", user_id).limit(1).execute()
    if existing.data:
        _table().update(payload).eq("user_id", user_id).execute()
    else:
        payload["connected_at"] = datetime.now(timezone.utc).isoformat()
        _table().insert(payload).execute()

    return payload


def get_connection_row(user_id: str) -> dict | None:
    result = _table().select("*").eq("user_id", user_id).limit(1).execute()
    return result.data[0] if result.data else None


def _mark_error(user_id: str, message: str) -> None:
    _table().update(
        {"status": "error", "last_error": message, "updated_at": datetime.now(timezone.utc).isoformat()}
    ).eq("user_id", user_id).execute()
    try:
        from services.notification_service import create_notification

        create_notification(user_id, "gmail_disconnected", f"Gmail connection needs attention: {message}")
    except Exception:
        pass  # notification failures must never break the auth/token-refresh flow


def get_valid_credentials(user_id: str) -> Credentials:
    """
    Return usable Credentials for this user, refreshing the access token if
    it's expired. Raises GmailNotConnectedError / GmailAuthError as needed.
    """
    row = get_connection_row(user_id)
    if not row or row["status"] == "disconnected":
        raise GmailNotConnectedError("Gmail is not connected for this user")

    credentials = Credentials(
        token=decrypt_secret(row["encrypted_access_token"]),
        refresh_token=decrypt_secret(row["encrypted_refresh_token"]) or None,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=row["scopes"].split(" "),
    )

    expiry = datetime.fromisoformat(row["token_expiry"])
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)

    if expiry <= datetime.now(timezone.utc):
        if not credentials.refresh_token:
            _mark_error(user_id, "Access expired and no refresh token is available")
            raise GmailAuthError("Gmail access expired; please reconnect Gmail")
        try:
            credentials.refresh(GoogleRequest())
        except RefreshError as exc:
            _mark_error(user_id, "Google revoked access; reconnection required")
            raise GmailAuthError("Gmail access was revoked; please reconnect Gmail") from exc

        new_expiry = credentials.expiry or datetime.now(timezone.utc)
        if new_expiry.tzinfo is None:
            new_expiry = new_expiry.replace(tzinfo=timezone.utc)
        _table().update(
            {
                "encrypted_access_token": encrypt_secret(credentials.token),
                "token_expiry": new_expiry.isoformat(),
                "status": "connected",
                "last_error": None,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("user_id", user_id).execute()

    return credentials


def get_status(user_id: str) -> dict:
    row = get_connection_row(user_id)
    if not row:
        return {"status": "disconnected", "gmail_email": None, "connected_at": None, "last_error": None}

    # Cheap validity probe: try to get valid credentials. This will attempt a
    # refresh if needed, and flip status to "error" if refresh fails.
    if row["status"] == "connected":
        try:
            get_valid_credentials(user_id)
        except GmailAuthError as exc:
            return {
                "status": "error",
                "gmail_email": row["gmail_email"],
                "connected_at": row.get("connected_at"),
                "last_error": str(exc),
            }

    row = get_connection_row(user_id) or row
    return {
        "status": row["status"],
        "gmail_email": row["gmail_email"],
        "connected_at": row.get("connected_at"),
        "last_error": row.get("last_error"),
    }


def disconnect(user_id: str) -> None:
    row = get_connection_row(user_id)
    if not row:
        return

    # Best-effort revoke with Google; don't fail disconnect if this errors
    # (token may already be invalid/revoked on Google's side).
    try:
        access_token = decrypt_secret(row["encrypted_access_token"])
        httpx.post(
            "https://oauth2.googleapis.com/revoke",
            params={"token": access_token},
            headers={"content-type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
    except Exception:
        pass

    _table().delete().eq("user_id", user_id).execute()


def fetch_gmail_profile(user_id: str) -> dict:
    credentials = get_valid_credentials(user_id)
    try:
        service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
        return service.users().getProfile(userId="me").execute()
    except HttpError as exc:
        status_code = getattr(exc, "status_code", None) or exc.resp.status
        if status_code == 429 or status_code == 403:
            raise GmailRateLimitError("Gmail API rate limit reached, try again shortly") from exc
        raise GmailApiError(f"Gmail API error: {exc}") from exc
    except httpx.RequestError as exc:
        raise GmailApiError(f"Network error contacting Gmail: {exc}") from exc
