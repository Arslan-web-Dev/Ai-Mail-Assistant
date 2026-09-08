"""
Shared FastAPI dependencies.

`get_current_user` is the ONLY way any route should learn who the caller is.
It extracts the `Authorization: Bearer <token>` header, verifies it as a
genuine Supabase-issued JWT (signature + expiry), and returns an
`AuthenticatedUser`. Routes must never accept a `user_id` from the request
body/query string and treat it as trusted.
"""
from fastapi import Depends, Header, HTTPException, status

from models.user import AuthenticatedUser
from utils.security import InvalidTokenError, verify_supabase_jwt


async def get_current_user(
    authorization: str | None = Header(default=None),
) -> AuthenticatedUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.split(" ", 1)[1].strip()

    try:
        claims = verify_supabase_jwt(token)
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = claims.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject claim",
        )

    return AuthenticatedUser(id=user_id, email=claims.get("email"))


CurrentUser = Depends(get_current_user)
