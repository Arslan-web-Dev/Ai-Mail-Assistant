"""
Deep health check (Module 8). Unlike the plain `/health` liveness probe
(used by the hosting platform to decide "is this process alive"), this
endpoint actually exercises the chain the spec asks for: Supabase, Redis,
and reports whether OpenAI/Gmail OAuth/Celery are configured. It's public
(no auth) but reveals no secrets — only booleans and short status strings.
"""
import logging

from fastapi import APIRouter

from app.config import settings

router = APIRouter(tags=["health"])
logger = logging.getLogger("ai_mail_assistant.health")


def _check_supabase() -> dict:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return {"status": "not_configured"}
    try:
        from database.supabase_client import get_supabase_admin

        get_supabase_admin().table("profiles").select("id", count="exact", head=True).limit(1).execute()
        return {"status": "ok"}
    except Exception as exc:
        logger.warning("Supabase health check failed: %s", exc)
        return {"status": "error"}


def _check_redis() -> dict:
    if not settings.redis_url:
        return {"status": "not_configured"}
    try:
        import redis

        client = redis.from_url(settings.redis_url, socket_connect_timeout=2)
        client.ping()
        return {"status": "ok"}
    except Exception as exc:
        logger.warning("Redis health check failed: %s", exc)
        return {"status": "error"}


def _check_openai() -> dict:
    return {"status": "configured" if settings.openai_api_key else "not_configured"}


def _check_gmail_oauth() -> dict:
    configured = bool(settings.google_client_id and settings.google_client_secret)
    return {"status": "configured" if configured else "not_configured"}


def _check_celery() -> dict:
    # We don't require a live worker to answer a health check quickly, so
    # this reports whether a broker is configured rather than pinging one
    # (which could hang if no worker/broker is reachable).
    return {"status": "configured" if settings.celery_broker_url else "not_configured"}


@router.get("/health")
async def deep_health_check():
    components = {
        "backend": {"status": "ok"},
        "supabase": _check_supabase(),
        "redis": _check_redis(),
        "openai": _check_openai(),
        "gmail_oauth": _check_gmail_oauth(),
        "celery": _check_celery(),
    }
    overall = "ok" if all(c["status"] in ("ok", "configured") for c in components.values()) else "degraded"
    return {"status": overall, "environment": settings.environment, "components": components}
