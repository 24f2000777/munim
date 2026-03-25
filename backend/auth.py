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
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

import jwt
from fastapi import Depends, HTTPException, Query, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import get_settings

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=True)
_bearer_optional = HTTPBearer(auto_error=False)

# Algorithm allowlist — must be explicit to prevent confusion attacks
_ALLOWED_ALGORITHMS = ["HS256"]

_UNAUTH = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


class AuthenticatedUser:
    """Minimal representation of a verified JWT principal."""

    def __init__(self, user_id: str, email: str, name: str = ""):
        self.user_id = user_id
        self.email = email
        self.name = name

    def __repr__(self) -> str:
        return f"<AuthenticatedUser user_id={self.user_id!r} email={self.email!r}>"


def _decode_token(raw_token: str) -> AuthenticatedUser:
    """Decode and validate a JWT, returning an AuthenticatedUser. Raises HTTP 401 on failure."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            raw_token,
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


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Security(_bearer)],
) -> AuthenticatedUser:
    """
    FastAPI dependency that validates the Bearer JWT and returns the authenticated user.

    Raises HTTP 401 on any validation failure — never leaks the reason to the client
    (logged server-side only) to prevent oracle attacks.
    """
    return _decode_token(credentials.credentials)


def get_current_user_or_token(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Security(_bearer_optional)] = None,
    token: Optional[str] = Query(None),
) -> AuthenticatedUser:
    """
    FastAPI dependency that accepts either a Bearer JWT (from OAuth session)
    or a `?token=` query param (from WhatsApp analysis share links).

    Priority: query param > Bearer header.
    This is critical because the frontend axios interceptor auto-injects the
    Google session token into the Authorization header — but for share links
    the WhatsApp share token (with the correct user_id) must take precedence.
    """
    # Prefer share token from query param (WhatsApp deep links)
    if token:
        return _decode_token(token)
    # Fall back to Bearer header (normal dashboard sessions)
    raw_token = credentials.credentials if credentials else None
    if not raw_token:
        raise _UNAUTH
    return _decode_token(raw_token)


def generate_analysis_token(upload_id: str, user_id: str) -> str:
    """
    Generate a signed JWT share token for a specific analysis.
    Valid for 7 days. Used in WhatsApp deep links.
    """
    settings = get_settings()
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": user_id,
        "email": "whatsapp@munim.ai",
        "name": "WhatsApp User",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=7)).timestamp()),
        "type": "analysis_share",
        "upload_id": upload_id,
    }
    return jwt.encode(payload, settings.NEXTAUTH_SECRET, algorithm="HS256")
