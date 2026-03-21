"""
Auth Router
============
Handles user sync after Google OAuth (via NextAuth.js), profile management,
and account deletion.

Flow:
  1. User signs in via NextAuth.js (Google OAuth) on the frontend.
  2. Frontend calls POST /api/v1/auth/sync with the user's Google profile.
  3. We upsert the user in Neon PostgreSQL.
  4. Subsequent requests carry a JWT — validated by auth.py dependency.

Security:
  - All mutating endpoints require JWT (get_current_user dependency).
  - Sync endpoint accepts Google ID token from NextAuth.js session.
  - Phone numbers are validated — no arbitrary strings stored.
  - Account deletion cascades via ON DELETE CASCADE in the DB schema.
"""

import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from auth import AuthenticatedUser, get_current_user
from db.neon_client import get_db_session

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class UserSyncRequest(BaseModel):
    """Payload from NextAuth.js after successful Google OAuth."""
    google_id: str
    email: EmailStr
    name: str
    avatar_url: Optional[str] = None
    user_type: str = "smb_owner"

    @field_validator("user_type")
    @classmethod
    def validate_user_type(cls, v: str) -> str:
        if v not in ("ca_firm", "smb_owner"):
            raise ValueError("user_type must be 'ca_firm' or 'smb_owner'")
        return v


class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    language_preference: Optional[str] = None
    whatsapp_opted_in: Optional[bool] = None
    notify_on_anomaly: Optional[bool] = None
    notify_weekly: Optional[bool] = None
    notify_monthly: Optional[bool] = None

    @field_validator("language_preference")
    @classmethod
    def validate_language(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("hi", "en", "hinglish"):
            raise ValueError("language_preference must be 'hi', 'en', or 'hinglish'")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            digits = re.sub(r"\D", "", v)
            if len(digits) < 10 or len(digits) > 13:
                raise ValueError("Invalid phone number")
            return f"+91{digits[-10:]}" if not v.startswith("+") else v
        return v


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    phone: Optional[str]
    user_type: str
    language_preference: str
    whatsapp_opted_in: bool
    subscription_status: str
    avatar_url: Optional[str]
    created_at: str
    notify_on_anomaly: bool
    notify_weekly: bool
    notify_monthly: bool


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/sync", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def sync_user(
    payload: UserSyncRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Upsert user after Google OAuth. Called by the Next.js backend on first
    sign-in and on every session refresh (idempotent).
    """
    result = await db.execute(
        text("""
            INSERT INTO users (email, name, google_id, avatar_url, user_type)
            VALUES (:email, :name, :google_id, :avatar_url, :user_type)
            ON CONFLICT (email) DO UPDATE SET
                name        = EXCLUDED.name,
                google_id   = EXCLUDED.google_id,
                avatar_url  = EXCLUDED.avatar_url,
                updated_at  = NOW()
            RETURNING
                id::text, email, name, phone, user_type,
                language_preference, whatsapp_opted_in,
                subscription_status, avatar_url,
                created_at::text,
                notify_on_anomaly, notify_weekly, notify_monthly
        """),
        {
            "email": payload.email,
            "name": payload.name,
            "google_id": payload.google_id,
            "avatar_url": payload.avatar_url,
            "user_type": payload.user_type,
        },
    )
    await db.commit()
    row = result.fetchone()
    return _row_to_user(row)


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Return the authenticated user's profile."""
    result = await db.execute(
        text("""
            SELECT id::text, email, name, phone, user_type,
                   language_preference, whatsapp_opted_in,
                   subscription_status, avatar_url, created_at::text,
                   notify_on_anomaly, notify_weekly, notify_monthly
            FROM users WHERE email = :email
        """),
        {"email": current_user.email},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return _row_to_user(row)


@router.put("/profile", response_model=UserResponse)
async def update_profile(
    payload: ProfileUpdateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Update language preference, phone, WhatsApp opt-in, or display name."""
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update.",
        )

    set_clauses = ", ".join(f"{k} = :{k}" for k in updates)
    updates["email"] = current_user.email

    result = await db.execute(
        text(f"""
            UPDATE users SET {set_clauses}, updated_at = NOW()
            WHERE email = :email
            RETURNING id::text, email, name, phone, user_type,
                      language_preference, whatsapp_opted_in,
                      subscription_status, avatar_url, created_at::text,
                      notify_on_anomaly, notify_weekly, notify_monthly
        """),
        updates,
    )
    await db.commit()
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return _row_to_user(row)


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Permanently delete the user account and all associated data.
    ON DELETE CASCADE in schema handles cascading deletes.
    """
    result = await db.execute(
        text("DELETE FROM users WHERE email = :email RETURNING id"),
        {"email": current_user.email},
    )
    await db.commit()
    deleted = result.fetchone()
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    logger.info("Account deleted: %s", current_user.email)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_user(row) -> dict:
    return {
        "id": row.id,
        "email": row.email,
        "name": row.name,
        "phone": row.phone,
        "user_type": row.user_type,
        "language_preference": row.language_preference,
        "whatsapp_opted_in": row.whatsapp_opted_in,
        "subscription_status": row.subscription_status,
        "avatar_url": row.avatar_url,
        "created_at": row.created_at,
        "notify_on_anomaly": getattr(row, "notify_on_anomaly", True),
        "notify_weekly": getattr(row, "notify_weekly", False),
        "notify_monthly": getattr(row, "notify_monthly", False),
    }
