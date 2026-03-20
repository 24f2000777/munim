"""Pydantic models for file upload requests and responses."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    upload_id: UUID
    file_name: str
    file_type: str
    file_size_bytes: int
    status: str
    data_health_score: Optional[int] = None
    health_report: Optional[dict] = None
    message: str


class UploadStatusResponse(BaseModel):
    upload_id: UUID
    status: str                    # pending | processing | done | error
    data_health_score: Optional[int] = None
    health_report: Optional[dict] = None
    error_message: Optional[str] = None
    created_at: datetime
    processed_at: Optional[datetime] = None
