"""
FastAPI application factory / entrypoint.

Run with:
    uvicorn app.main:app --reload --port 8000
"""
import logging

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.v1 import ai as ai_routes
from api.v1 import analytics as analytics_routes
from api.v1 import auth as auth_routes
from api.v1 import automation as automation_routes
from api.v1 import dashboard as dashboard_routes
from api.v1 import drafts as drafts_routes
from api.v1 import emails as emails_routes
from api.v1 import gmail as gmail_routes
from api.v1 import health as health_routes
from api.v1 import notifications as notifications_routes
from api.v1 import preferences as preferences_routes
from api.v1 import profile as profile_routes
from app.config import settings
from middleware.auth_middleware import RequestLoggingMiddleware
from services.gmail_service import (
    GmailApiError,
    GmailAuthError,
    GmailNotConnectedError,
    GmailRateLimitError,
)

logger = logging.getLogger("ai_mail_assistant.main")

app = FastAPI(
    title="AI Mail Assistant API",
    version="0.2.0",
    description="Backend API for AI Mail Assistant",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(GmailNotConnectedError)
async def gmail_not_connected_handler(_: Request, exc: GmailNotConnectedError):
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})


@app.exception_handler(GmailAuthError)
async def gmail_auth_error_handler(_: Request, exc: GmailAuthError):
    return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": str(exc)})


@app.exception_handler(GmailRateLimitError)
async def gmail_rate_limit_handler(_: Request, exc: GmailRateLimitError):
    return JSONResponse(status_code=status.HTTP_429_TOO_MANY_REQUESTS, content={"detail": str(exc)})


@app.exception_handler(GmailApiError)
async def gmail_api_error_handler(_: Request, exc: GmailApiError):
    return JSONResponse(status_code=status.HTTP_502_BAD_GATEWAY, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Module 8 audit fix: catch-all so an unexpected internal error (a bug,
    a third-party library raising something we didn't anticipate) never
    leaks its raw message/stack trace to the client. The real detail is
    logged server-side; the client only ever sees a generic message.
    """
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"detail": "Internal server error"})


@app.get("/health", tags=["health"])
async def health_check():
    """Basic liveness probe for the hosting platform (Render/Railway) — always fast, no dependency checks."""
    return {"status": "ok", "environment": settings.environment}


app.include_router(auth_routes.router, prefix="/api/v1")
app.include_router(gmail_routes.router, prefix="/api/v1")
app.include_router(emails_routes.router, prefix="/api/v1")
app.include_router(ai_routes.router, prefix="/api/v1")
app.include_router(drafts_routes.router, prefix="/api/v1")
app.include_router(dashboard_routes.router, prefix="/api/v1")
app.include_router(automation_routes.router, prefix="/api/v1")
app.include_router(analytics_routes.router, prefix="/api/v1")
app.include_router(notifications_routes.router, prefix="/api/v1")
app.include_router(profile_routes.router, prefix="/api/v1")
app.include_router(preferences_routes.router, prefix="/api/v1")
app.include_router(health_routes.router, prefix="/api/v1")
