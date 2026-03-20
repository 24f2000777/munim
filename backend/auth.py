"""
JWT Authentication Middleware
================================
Validates NextAuth.js JWTs signed with HS256 using the NEXTAUTH_SECRET.
Used as a FastAPI dependency via `Depends(get_current_user)`.

Security notes:
- Enforces algorithm allowlist (HS256 only) — prevents algorithm confusion attacks
- Validates exp, iat, nbf claims automatically
- Never accepts 'none' algorithm
"""

import logging
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import get_settings

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=True)

# Algorithm allowlist — must be explicit to prevent confusion attacks
_ALLOWED_ALGORITHMS = ["HS256"]


class AuthenticatedUser:
    """Minimal representation of a verified JWT principal."""

    def __init__(self, user_id: str, email: str, name: str = ""):
        self.user_id = user_id
        self.email = email
        self.name = name

    def __repr__(self) -> str:
        return f"<AuthenticatedUser user_id={self.user_id!r} email={self.email!r}>"


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Security(_bearer)],
) -> AuthenticatedUser:
    """
    FastAPI dependency that validates the Bearer JWT and returns the authenticated user.

    Raises HTTP 401 on any validation failure — never leaks the reason to the client
    (logged server-side only) to prevent oracle attacks.
    """
    settings = get_settings()
    token = credentials.credentials

    _UNAUTH = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.NEXTAUTH_SECRET,
            algorithms=_ALLOWED_ALGORITHMS,
            options={
                "require": ["exp", "iat", "sub"],
                "verify_exp": True,
                "verify_iat": True,
            },
        )
    except jwt.ExpiredSignatureError:
        logger.warning("JWT expired")
        raise _UNAUTH
    except jwt.InvalidAlgorithmError:
        logger.warning("JWT algorithm not in allowlist")
        raise _UNAUTH
    except jwt.InvalidTokenError as exc:
        logger.warning("JWT validation failed: %s", type(exc).__name__)
        raise _UNAUTH

    user_id = payload.get("sub")
    email = payload.get("email", "")
    name = payload.get("name", "")

    if not user_id or not email:
        logger.warning("JWT missing required claims: sub=%r email=%r", user_id, email)
        raise _UNAUTH

    return AuthenticatedUser(user_id=user_id, email=email, name=name)
