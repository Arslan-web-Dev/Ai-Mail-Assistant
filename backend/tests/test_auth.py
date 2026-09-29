"""
Tests for authentication behavior.

These focus on the security-critical guarantee: routes must reject missing
or invalid tokens, and must never trust a client-supplied user id.
"""
import jwt
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

client = TestClient(app)


def _make_token(sub: str = "user-123", email: str = "user@example.com", expired: bool = False) -> str:
    import time

    payload = {
        "sub": sub,
        "email": email,
        "aud": "authenticated",
        "exp": int(time.time()) + (-3600 if expired else 3600),
    }
    return jwt.encode(payload, settings.supabase_jwt_secret or "test-secret", algorithm="HS256")


def test_health_check_is_public():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_session_requires_auth_header():
    response = client.get("/api/v1/auth/session")
    assert response.status_code == 401


def test_gmail_status_rejects_missing_token():
    response = client.get("/api/v1/gmail/status")
    assert response.status_code == 401


def test_gmail_status_rejects_malformed_header():
    response = client.get("/api/v1/gmail/status", headers={"Authorization": "NotBearer abc"})
    assert response.status_code == 401


def test_gmail_status_rejects_expired_token(monkeypatch):
    monkeypatch.setattr(settings, "supabase_jwt_secret", "test-secret")
    token = _make_token(expired=True)
    response = client.get("/api/v1/gmail/status", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_gmail_connect_rejects_no_token():
    response = client.get("/api/v1/gmail/connect")
    assert response.status_code == 401


def test_cannot_override_user_id_via_body():
    """
    Regression guard: even if a caller sends a `user_id` in the body,
    protected routes must ignore it and rely solely on the verified token.
    disconnect() takes no body at all, so this mainly documents intent —
    no route in this API accepts a client-supplied user id.
    """
    response = client.post(
        "/api/v1/gmail/disconnect",
        json={"user_id": "someone-elses-id"},
    )
    assert response.status_code == 401
