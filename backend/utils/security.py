"""
Security helpers:
- verify_supabase_jwt: verifies a Supabase-issued access token server-side.
- Fernet-based encrypt/decrypt for Gmail OAuth tokens at rest.

Nothing here trusts client-supplied identity. The only trusted identity is
whatever `verify_supabase_jwt` returns after signature + expiry verification.
"""
from __future__ import annotations

import jwt
from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


class InvalidTokenError(Exception):
    pass


def verify_supabase_jwt(token: str) -> dict:
    """
    Verify a Supabase Auth access token (JWT) and return its claims.
    Raises InvalidTokenError on any failure (bad signature, expired, malformed).
    """
    if not settings.supabase_jwt_secret:
        raise RuntimeError("SUPABASE_JWT_SECRET is not configured")
    try:
        claims = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
            options={"require": ["exp", "sub"]},
        )
        return claims
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc


def _fernet() -> Fernet:
    if not settings.token_encryption_key:
        raise RuntimeError("TOKEN_ENCRYPTION_KEY is not configured")
    return Fernet(settings.token_encryption_key.encode())


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise InvalidTokenError("Could not decrypt stored token") from exc
