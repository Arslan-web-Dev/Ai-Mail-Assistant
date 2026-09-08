"""
Gmail connection endpoints.

GET  /api/v1/gmail/connect     — protected. Returns a Google consent URL
                                  bound to the caller's verified user id.
GET  /api/v1/gmail/callback    — public (Google redirects the browser here).
                                  Identity comes ONLY from the signed,
                                  single-use `state` token created in
                                  /connect — never trusted from the request.
GET  /api/v1/gmail/status      — protected. Connected/disconnected/error.
POST /api/v1/gmail/disconnect  — protected. Revokes + deletes stored tokens.
POST /api/v1/gmail/webhook     — public, but every request's identity comes
                                  from Google's signed OIDC push token
                                  (verified below), never from the payload.
POST /api/v1/gmail/sync        — protected. Manual "sync now" fallback /
                                  dev-testing entry point (Module 3).
"""
import base64
import json
import logging

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.config import settings
from app.dependencies import CurrentUser
from database.supabase_client import get_supabase_admin
from models.user import AuthenticatedUser
from schemas.email import SyncResult
from schemas.gmail import (
    GmailAuthUrlResponse,
    GmailDisconnectResponse,
    GmailStatusResponse,
)
from services import email_sync_service, gmail_service, gmail_watch_service, google_oauth

router = APIRouter(prefix="/gmail", tags=["gmail"])
logger = logging.getLogger("ai_mail_assistant.gmail_webhook")


@router.get("/connect", response_model=GmailAuthUrlResponse)
async def connect_gmail(current_user: AuthenticatedUser = CurrentUser):
    """Return a Google OAuth consent URL. Frontend navigates the browser to it."""
    try:
        url = google_oauth.build_authorization_url(current_user.id)
    except RuntimeError as exc:
        # e.g. Google client id/secret not configured
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
    return GmailAuthUrlResponse(authorization_url=url)


@router.get("/callback")
async def gmail_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
):
    """
    Public redirect target from Google. We never trust who the "user" is
    from the query string directly — we only trust the user id bound to the
    single-use `state` token we generated in /connect.
    """
    settings_page = f"{settings.frontend_url}/settings/gmail"

    if error:
        # e.g. user clicked "Deny" on the consent screen
        return RedirectResponse(f"{settings_page}?gmail_status=denied")

    if not code or not state:
        return RedirectResponse(f"{settings_page}?gmail_status=invalid_request")

    user_id = google_oauth.consume_oauth_state(state)
    if not user_id:
        # Expired, already-used, or forged state — reject.
        return RedirectResponse(f"{settings_page}?gmail_status=invalid_state")

    try:
        credentials = google_oauth.exchange_code_for_credentials(code)
        gmail_service.save_credentials(user_id, credentials)
        try:
            gmail_watch_service.start_watch(user_id)
        except gmail_service.GmailServiceError:
            # Connection itself succeeded; push notifications can be retried
            # later (manual sync / periodic renewal task still cover us).
            pass
    except gmail_service.GmailServiceError:
        return RedirectResponse(f"{settings_page}?gmail_status=error")
    except Exception:
        return RedirectResponse(f"{settings_page}?gmail_status=error")

    return RedirectResponse(f"{settings_page}?gmail_status=connected")


@router.get("/status", response_model=GmailStatusResponse)
async def gmail_status(current_user: AuthenticatedUser = CurrentUser):
    data = gmail_service.get_status(current_user.id)
    return GmailStatusResponse(**data)


@router.post("/disconnect", response_model=GmailDisconnectResponse)
async def gmail_disconnect(current_user: AuthenticatedUser = CurrentUser):
    gmail_watch_service.stop_watch(current_user.id)
    gmail_service.disconnect(current_user.id)
    return GmailDisconnectResponse(status="disconnected")


@router.post("/webhook", include_in_schema=False)
async def gmail_webhook(request: Request):
    """
    Public endpoint that Google Cloud Pub/Sub pushes to when Gmail reports
    a mailbox change. We do NOT trust the request body to identify the
    user — the request body is a base64-encoded `{emailAddress, historyId}`
    payload that anyone could forge if they knew our URL. Instead we
    verify the Google-signed OIDC bearer token Pub/Sub push subscriptions
    attach to every request, and only then use the emailAddress in the
    (now-trusted) payload to look up which user to sync.
    """
    if not settings.google_pubsub_audience or not settings.google_pubsub_service_account:
        # Pub/Sub not configured in this environment — nothing to verify
        # against, so refuse rather than trusting an unverifiable caller.
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Push sync not configured")

    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing push auth token")
    token = auth_header.split(" ", 1)[1]

    try:
        claims = google_id_token.verify_oauth2_token(
            token, google_requests.Request(), audience=settings.google_pubsub_audience
        )
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid push auth token")

    if claims.get("email") != settings.google_pubsub_service_account or not claims.get("email_verified"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unexpected push token issuer")

    body = await request.json()
    message = body.get("message", {})
    data_b64 = message.get("data", "")
    try:
        payload = json.loads(base64.b64decode(data_b64).decode("utf-8"))
    except Exception:
        # Malformed push payload — ack it (200) so Pub/Sub doesn't retry forever,
        # but do nothing further with it.
        return {"status": "ignored"}

    gmail_email = payload.get("emailAddress")
    if not gmail_email:
        return {"status": "ignored"}

    # Look up which of our users this Gmail address belongs to. This is the
    # ONLY place we derive a user identity from push-notification content,
    # and only after the token verification above establishes the request
    # genuinely came from our own Pub/Sub subscription.
    match = (
        get_supabase_admin()
        .table("gmail_connections")
        .select("user_id")
        .eq("gmail_email", gmail_email)
        .eq("status", "connected")
        .limit(1)
        .execute()
    )
    if not match.data:
        return {"status": "ignored"}

    user_id = match.data[0]["user_id"]

    # Kick off the actual sync in the background so we ack Pub/Sub quickly.
    from workers.tasks import sync_user_email_task

    sync_user_email_task.delay(user_id)
    return {"status": "accepted"}


@router.post("/sync", response_model=SyncResult)
async def gmail_manual_sync(current_user: AuthenticatedUser = CurrentUser):
    """
    Manual "sync now" fallback — also useful in local/dev environments
    without Pub/Sub configured. Runs synchronously so the caller gets an
    immediate result; production push-triggered syncs run via Celery
    (see workers/tasks.py) instead.
    """
    try:
        return email_sync_service.incremental_sync(current_user.id)
    except gmail_service.GmailServiceError:
        raise
    except Exception as exc:
        logger.exception("Manual sync failed for user %s", current_user.id)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Sync failed: {exc}")
