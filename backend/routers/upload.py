"""
Upload Router
=============
Handles file uploads from CA firms and SMB owners.

Storage strategy:
  - Production: Cloudflare R2 (set R2_ACCOUNT_ID / R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY)
  - Development: Local disk at ./uploads/ when R2 credentials are absent

Processing strategy:
  - Production: Celery + Redis async queue
  - Development: FastAPI BackgroundTasks (runs after response is sent, ~instant feedback)
"""

import logging
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from auth import AuthenticatedUser, get_current_user
from config import settings
from db.neon_client import get_db_session
from models.upload import UploadResponse
from services.ingestor.schema_detector import _detect_file_type

logger = logging.getLogger(__name__)
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

# Local uploads directory — used when R2 is not configured
LOCAL_UPLOADS_DIR = Path(__file__).parent.parent / "uploads"
LOCAL_UPLOADS_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

def _r2_configured() -> bool:
    return bool(
        settings.R2_ACCOUNT_ID
        and settings.R2_ACCESS_KEY_ID
        and settings.R2_SECRET_ACCESS_KEY
    )


def _store_file(raw_bytes: bytes, r2_key: str, file_type: str) -> None:
    """Store file either in Cloudflare R2 or local disk."""
    if _r2_configured():
        import boto3
        from botocore.config import Config

        try:
            r2 = boto3.client(
                "s3",
                endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
                aws_access_key_id=settings.R2_ACCESS_KEY_ID,
                aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
                config=Config(signature_version="s3v4"),
                region_name="auto",
            )
            r2.put_object(
                Bucket=settings.R2_BUCKET_NAME,
                Key=r2_key,
                Body=raw_bytes,
                ContentType=_get_content_type(file_type),
            )
            logger.info("File uploaded to R2: %s (%d bytes)", r2_key, len(raw_bytes))
        except Exception as exc:
            logger.error("R2 upload failed: %s", exc, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="File storage temporarily unavailable. Please try again.",
            )
    else:
        # Save to local disk
        local_path = LOCAL_UPLOADS_DIR / r2_key
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(raw_bytes)
        logger.info("File saved locally: %s (%d bytes)", local_path, len(raw_bytes))


def _queue_processing(upload_id: str, background_tasks: BackgroundTasks) -> None:
    """
    Queue processing via Celery (production) or FastAPI BackgroundTask (development).

    In development / when USE_CELERY is not explicitly 'true', always use background
    tasks — this avoids the silent failure where Redis accepts the task but no worker
    is running to consume it.
    """
    use_celery = getattr(settings, "USE_CELERY", "false").lower() == "true"

    if use_celery:
        try:
            from tasks.process_upload import process_upload_task
            process_upload_task.delay(upload_id)
            logger.info("Processing queued via Celery for upload: %s", upload_id)
            return
        except Exception as exc:
            logger.warning(
                "Celery unavailable (%s) — falling back to background task for upload: %s",
                type(exc).__name__, upload_id,
            )

    # Development / no worker: run pipeline in FastAPI background task
    logger.info("Processing via background task for upload: %s", upload_id)
    background_tasks.add_task(_run_pipeline_sync, upload_id)


def _run_pipeline_sync(upload_id: str) -> None:
    """Run the processing pipeline synchronously (dev fallback)."""
    try:
        from tasks.process_upload import run_pipeline
        run_pipeline(upload_id)
    except Exception as exc:
        logger.error("Background pipeline failed for upload %s: %s", upload_id, exc, exc_info=True)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("10/hour")
async def upload_file(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    ca_client_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Upload a Tally XML, Excel, or CSV file for analysis.

    Returns immediately with upload_id. Processing runs in the background.
    Poll /upload/{id}/status for progress.
    """
    user_id = current_user.user_id

    # --- Read & validate size ---
    raw_bytes = await file.read()
    file_size = len(raw_bytes)

    if file_size == 0:
        raise HTTPException(status_code=400, detail="File is empty.")

    if file_size > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {settings.MAX_FILE_SIZE_MB} MB.",
        )

    # --- Validate file type by magic bytes ---
    filename = file.filename or "upload"
    file_type = _detect_file_type(raw_bytes, filename)

    if file_type == "unknown":
        raise HTTPException(
            status_code=415,
            detail="Unsupported format. Please upload Tally XML (.xml), Excel (.xlsx/.xls), or CSV (.csv).",
        )

    # --- Generate safe storage key ---
    upload_id = uuid.uuid4()
    ext = {"tally_xml": "xml", "excel": "xlsx", "csv": "csv"}.get(file_type, "bin")
    r2_key = f"uploads/{user_id}/{upload_id}.{ext}"

    # --- Store file (R2 or local) ---
    _store_file(raw_bytes, r2_key, file_type)

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
        raise HTTPException(status_code=500, detail="Failed to create upload record. Please try again.")

    # --- Queue processing (Celery or background task) ---
    _queue_processing(str(upload_id), background_tasks)

    return UploadResponse(
        upload_id=upload_id,
        file_name=filename,
        file_type=file_type,
        file_size_bytes=file_size,
        status="pending",
        message=f"File uploaded. Analysis running in the background. Check /api/v1/upload/{upload_id}/status",
    )


@router.get("/{upload_id}/status")
async def get_upload_status(
    upload_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Poll for upload processing status. Includes analysis_id once processing is done."""
    result = await db.execute(
        text("""
            SELECT
                u.id,
                u.status,
                u.data_health_score,
                u.health_report,
                u.error_message,
                u.created_at,
                u.processed_at,
                ar.id::text AS analysis_id
            FROM uploads u
            LEFT JOIN analysis_results ar ON ar.upload_id = u.id
            WHERE u.id = :upload_id AND u.user_id = :user_id
        """),
        {"upload_id": upload_id, "user_id": str(current_user.user_id)},
    )
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Upload not found.")

    return {
        "upload_id": str(row.id),
        "status": row.status,
        "analysis_id": row.analysis_id,
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
