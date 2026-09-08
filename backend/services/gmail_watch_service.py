"""
gmail_watch_service.py

Registers, renews, and stops Gmail push notifications (Cloud Pub/Sub) for a
user's mailbox. Gmail's watch() registration expires after ~7 days and must
be renewed — see workers/tasks.py for the periodic renewal task.

This requires a Google Cloud Pub/Sub topic that Gmail is allowed to publish
to, and a push subscription pointing at
`{BACKEND_URL}/api/v1/gmail/webhook` (configured with OIDC auth — see
api/v1/gmail.py webhook handler for the corresponding verification). Setting
up the actual GCP topic/subscription is an infrastructure step done once in
the Google Cloud Console / gcloud CLI — see README for the exact commands.
"""
from __future__ import annotations

from datetime import datetime, timezone

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import settings
from database.supabase_client import get_supabase_admin
from services import gmail_service


def start_watch(user_id: str) -> None:
    """Register (or refresh) Gmail push notifications for this user's inbox."""
    if not settings.google_pubsub_topic:
        # Pub/Sub not configured (e.g. local dev without GCP set up) — skip
        # silently. Manual sync (POST /gmail/sync) still works.
        return

    credentials = gmail_service.get_valid_credentials(user_id)
    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)

    try:
        response = (
            service.users()
            .watch(
                userId="me",
                body={"topicName": settings.google_pubsub_topic, "labelIds": ["INBOX"]},
            )
            .execute()
        )
    except HttpError as exc:
        raise gmail_service.GmailApiError(f"Failed to start Gmail watch: {exc}") from exc

    expiration_ms = int(response.get("expiration", 0))
    expiration = (
        datetime.fromtimestamp(expiration_ms / 1000, tz=timezone.utc)
        if expiration_ms
        else None
    )

    get_supabase_admin().table("gmail_connections").update(
        {
            "watch_history_id": response.get("historyId"),
            "watch_expiration": expiration.isoformat() if expiration else None,
        }
    ).eq("user_id", user_id).execute()


def stop_watch(user_id: str) -> None:
    if not settings.google_pubsub_topic:
        return
    try:
        credentials = gmail_service.get_valid_credentials(user_id)
        service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
        service.users().stop(userId="me").execute()
    except Exception:
        # Best-effort — token may already be invalid if the user is
        # disconnecting because access was revoked.
        pass


def renew_expiring_watches() -> int:
    """
    Find gmail_connections whose watch expires soon and renew them.
    Intended to be called by a periodic Celery beat task. Returns the
    number of watches renewed.
    """
    from datetime import timedelta

    threshold = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    db = get_supabase_admin()
    expiring = (
        db.table("gmail_connections")
        .select("user_id")
        .eq("status", "connected")
        .lte("watch_expiration", threshold)
        .execute()
    )

    renewed = 0
    for row in expiring.data or []:
        try:
            start_watch(row["user_id"])
            renewed += 1
        except Exception:
            # Leave it for the next run / surfaces as a stale watch, not a crash.
            continue
    return renewed
