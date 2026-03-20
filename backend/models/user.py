"""Pydantic models for user data."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator


class UserCreate(BaseModel):
    email: EmailStr
    name: str
    phone: Optional[str] = None
    user_type: str
    language_preference: str = "hi"
    google_id: Optional[str] = None

    @field_validator("user_type")
    @classmethod
    def validate_user_type(cls, v: str) -> str:
        if v not in ("ca_firm", "smb_owner"):
            raise ValueError("user_type must be 'ca_firm' or 'smb_owner'")
        return v

    @field_validator("language_preference")
    @classmethod
    def validate_language(cls, v: str) -> str:
        if v not in ("hi", "en", "hinglish"):
            raise ValueError("language_preference must be 'hi', 'en', or 'hinglish'")
        return v


class UserResponse(BaseModel):
    id: UUID
    email: str
    name: str
    phone: Optional[str]
    user_type: str
    language_preference: str
    whatsapp_opted_in: bool
    subscription_status: str
    trial_ends_at: Optional[datetime]
    created_at: datetime


class CAClientCreate(BaseModel):
    client_name: str
    client_phone: Optional[str] = None
    client_email: Optional[str] = None
    white_label_name: Optional[str] = None
    language_preference: str = "hi"


class CAClientResponse(BaseModel):
    id: UUID
    ca_user_id: UUID
    client_name: str
    client_phone: Optional[str]
    client_email: Optional[str]
    whatsapp_opted_in: bool
    white_label_name: Optional[str]
    language_preference: str
    active: bool
    created_at: datetime
