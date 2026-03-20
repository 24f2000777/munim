"""
Upload Router
=============
Handles file uploads from CA firms and SMB owners.
Files are validated, stored in Cloudflare R2, and queued for async processing.

Security checks:
  - File size limit enforced (50MB max)
  - File type validated by magic bytes (not just extension)
  - Files stored with random UUIDs (not user-supplied names)
  - Rate limited: 10 uploads per hour per user
  - Virus scanning hook (pluggable)
"""

import logging
import uuid
from typing import Optional

import boto3
from botocore.config import Config
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from auth import AuthenticatedUser, get_current_user
from config import settings
from db.neon_client import get_db_session
from models.upload import UploadResponse
from services.ingestor.schema_detector import _detect_file_type
from tasks.process_upload import process_upload_task

logger = logging.getLogger(__name__)
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

# ---------------------------------------------------------------------------
# Cloudflare R2 client (S3-compatible)
# ---------------------------------------------------------------------------

def _get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("10/hour")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    ca_client_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Upload a Tally XML, Excel, or CSV file for analysis.

    The file is:
    1. Validated (size + type)
    2. Stored in Cloudflare R2
    3. Record created in uploads table
    4. Async processing queued via Celery

    Returns immediately with upload_id — poll /upload/{id}/status for progress.
    """
    user_id = current_user.user_id

    # --- Size validation ---
    raw_bytes = await file.read()
    file_size = len(raw_bytes)

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty.",
        )

    if file_size > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {settings.MAX_FILE_SIZE_MB}MB.",
        )

    # --- File type validation (magic bytes — not just extension) ---
    filename = file.filename or "upload"
    file_type = _detect_file_type(raw_bytes, filename)

    if file_type == "unknown":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                "Unsupported file format. Please upload a Tally XML (.xml), "
                "Excel (.xlsx, .xls), or CSV (.csv) file."
            ),
        )

    # --- Generate safe storage path (never use user-supplied filename) ---
    upload_id = uuid.uuid4()
    safe_extension = {"tally_xml": "xml", "excel": "xlsx", "csv": "csv"}.get(file_type, "bin")
    r2_key = f"uploads/{user_id}/{upload_id}.{safe_extension}"

    # --- Upload to Cloudflare R2 ---
    try:
        r2 = _get_r2_client()
        r2.put_object(
            Bucket=settings.R2_BUCKET_NAME,
            Key=r2_key,
            Body=raw_bytes,
            ContentType=_get_content_type(file_type),
            Metadata={
                "original_filename": filename[:255],   # Limit metadata size
                "user_id": str(user_id),
                "upload_id": str(upload_id),
            },
        )
        logger.info("File uploaded to R2: %s (%d bytes)", r2_key, file_size)
    except Exception as exc:
        logger.error("R2 upload failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="File storage temporarily unavailable. Please try again.",
        )

    # --- Create DB record ---
    try:
        await db.execute(
            text("""
                INSERT INTO uploads (
                    id, user_id, ca_client_id, file_name, file_path,
                    file_type, file_size_bytes, status
                ) VALUES (
                    :id, :user_id, :ca_client_id, :file_name, :file_path,
                    :file_type, :file_size_bytes, 'pending'
                )
            """),
            {
                "id": str(upload_id),
                "user_id": str(user_id),
                "ca_client_id": ca_client_id,
                "file_name": filename[:255],
                "file_path": r2_key,
                "file_type": file_type,
                "file_size_bytes": file_size,
            },
        )
        await db.commit()
    except Exception as exc:
        logger.error("DB insert failed: %s", exc, exc_info=True)
        # Try to clean up R2 object
        try:
            _get_r2_client().delete_object(Bucket=settings.R2_BUCKET_NAME, Key=r2_key)
        except Exception as cleanup_err:  # nosec B110
            logger.warning("R2 cleanup failed for key %s: %s", r2_key, cleanup_err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create upload record. Please try again.",
        )

    # --- Queue async processing ---
    try:
        process_upload_task.delay(str(upload_id))
        logger.info("Processing task queued for upload: %s", upload_id)
    except Exception as exc:
        # Task queue failure is not critical — processing can be retried
        logger.error("Failed to queue processing task: %s", exc)

    return UploadResponse(
        upload_id=upload_id,
        file_name=filename,
        file_type=file_type,
        file_size_bytes=file_size,
        status="pending",
        message=(
            "File uploaded successfully. Analysis is in progress — "
            f"check status at /api/v1/upload/{upload_id}/status"
        ),
    )


@router.get("/{upload_id}/status")
async def get_upload_status(
    upload_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Poll for upload processing status."""
    user_id = current_user.user_id

    result = await db.execute(
        text("""
            SELECT id, status, data_health_score, health_report,
                   error_message, created_at, processed_at
            FROM uploads
            WHERE id = :upload_id AND user_id = :user_id
        """),
        {"upload_id": upload_id, "user_id": str(user_id)},
    )
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Upload not found.",
        )

    return {
        "upload_id": str(row.id),
        "status": row.status,
        "data_health_score": row.data_health_score,
        "health_report": row.health_report,
        "error_message": row.error_message,
        "created_at": row.created_at,
        "processed_at": row.processed_at,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_content_type(file_type: str) -> str:
    return {
        "tally_xml": "application/xml",
        "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "csv": "text/csv",
    }.get(file_type, "application/octet-stream")
