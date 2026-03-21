"""
Reports Router
===============
Generates WhatsApp-ready business reports using Gemini 2.0 Flash,
stores them, and sends them via the Meta WhatsApp Business API.

Endpoints:
  POST /api/v1/reports/generate              — generate report from analysis
  GET  /api/v1/reports                       — list reports for user
  GET  /api/v1/reports/{report_id}           — get a specific report
  POST /api/v1/reports/{report_id}/send      — send report to WhatsApp

Security:
  - All endpoints require JWT.
  - Report generation is rate-limited (5/day per user).
  - WhatsApp number validated before sending.
  - LLM receives only pre-computed JSON — no raw financial data.
"""

import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from auth import AuthenticatedUser, get_current_user
from config import settings
from db.neon_client import get_db_session
from services.reporter.llm_narrator import build_report_prompt, generate_report

logger = logging.getLogger(__name__)
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class GenerateReportRequest(BaseModel):
    analysis_id: str
    language: str = "hi"
    report_type: str = "weekly"
    owner_name: Optional[str] = None


class SendWhatsAppRequest(BaseModel):
    phone_number: str  # E.164 format: +919876543210


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/generate", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/day")
async def generate_report_endpoint(
    request: Request,
    payload: GenerateReportRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Generate a WhatsApp report from a completed analysis using Gemini 2.0 Flash.
    Returns immediately with report content — no async queue needed (LLM is fast).
    """
    # Validate language
    if payload.language not in ("hi", "en", "hinglish"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="language must be 'hi', 'en', or 'hinglish'",
        )
    if payload.report_type not in ("weekly", "monthly", "alert", "on_demand"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="report_type must be weekly, monthly, alert, or on_demand",
        )

    # Fetch analysis
    result = await db.execute(
        text("""
            SELECT ar.id::text, ar.period_start, ar.period_end,
                   ar.metrics, ar.anomalies, ar.customers, ar.seasonality_context,
                   u.user_id::text
            FROM analysis_results ar
            JOIN uploads u ON u.id = ar.upload_id
            WHERE ar.id = :analysis_id AND ar.user_id = :user_id
        """),
        {"analysis_id": payload.analysis_id, "user_id": current_user.user_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found.",
        )

    # Build prompt inputs
    metrics = row.metrics or {}
    anomalies_data = row.anomalies or {}
    customers_data = row.customers or {}
    seasonality = row.seasonality_context or {}

    top_anomalies = (anomalies_data.get("anomalies") or [])[:3]
    seasonality_notes = seasonality.get("events", [])

    owner_name = payload.owner_name or current_user.name or "Business Owner"

    # Call LLM narrator (15s timeout, template fallback built-in)
    narrator_result = generate_report(
        owner_name=owner_name,
        language=payload.language,
        period_start=str(row.period_start),
        period_end=str(row.period_end),
        metrics_summary=metrics,
        top_anomalies=top_anomalies,
        seasonality_context=seasonality_notes,
    )

    # Persist report
    insert_result = await db.execute(
        text("""
            INSERT INTO reports (
                analysis_id, user_id, report_type, language,
                content_hindi, content_english
            ) VALUES (
                :analysis_id, :user_id, :report_type, :language,
                :content_hi, :content_en
            )
            RETURNING id::text, created_at::text
        """),
        {
            "analysis_id": payload.analysis_id,
            "user_id": current_user.user_id,
            "report_type": payload.report_type,
            "language": payload.language,
            "content_hi": narrator_result.content if payload.language in ("hi", "hinglish") else None,
            "content_en": narrator_result.content if payload.language == "en" else None,
        },
    )
    await db.commit()
    report_row = insert_result.fetchone()

    return {
        "report_id": report_row.id,
        "analysis_id": payload.analysis_id,
        "language": payload.language,
        "report_type": payload.report_type,
        "content": narrator_result.content,
        "used_fallback": narrator_result.used_fallback,
        "created_at": report_row.created_at,
    }


@router.get("")
async def list_reports(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """List all generated reports for the authenticated user."""
    result = await db.execute(
        text("""
            SELECT
                r.id::text, r.analysis_id::text, r.report_type, r.language,
                r.whatsapp_sent, r.whatsapp_sent_at::text, r.created_at::text,
                ar.period_start::text, ar.period_end::text
            FROM reports r
            JOIN analysis_results ar ON ar.id = r.analysis_id
            WHERE r.user_id = :user_id
            ORDER BY r.created_at DESC
            LIMIT :limit OFFSET :offset
        """),
        {"user_id": current_user.user_id, "limit": limit, "offset": offset},
    )
    rows = result.fetchall()

    count_result = await db.execute(
        text("SELECT COUNT(*) FROM reports WHERE user_id = :user_id"),
        {"user_id": current_user.user_id},
    )
    total = count_result.scalar()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "report_id": r.id,
                "analysis_id": r.analysis_id,
                "report_type": r.report_type,
                "language": r.language,
                "whatsapp_sent": r.whatsapp_sent,
                "whatsapp_sent_at": r.whatsapp_sent_at,
                "period_start": r.period_start,
                "period_end": r.period_end,
                "created_at": r.created_at,
            }
            for r in rows
        ],
    }


@router.get("/{report_id}")
async def get_report(
    report_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Fetch a specific report with full content."""
    result = await db.execute(
        text("""
            SELECT
                r.id::text, r.analysis_id::text, r.report_type, r.language,
                r.content_hindi, r.content_english,
                r.whatsapp_sent, r.whatsapp_sent_at::text, r.created_at::text,
                ar.period_start::text, ar.period_end::text
            FROM reports r
            JOIN analysis_results ar ON ar.id = r.analysis_id
            WHERE r.id = :report_id AND r.user_id = :user_id
        """),
        {"report_id": report_id, "user_id": current_user.user_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")

    content = row.content_hindi or row.content_english or ""
    return {
        "report_id": row.id,
        "analysis_id": row.analysis_id,
        "report_type": row.report_type,
        "language": row.language,
        "content": content,
        "whatsapp_sent": row.whatsapp_sent,
        "whatsapp_sent_at": row.whatsapp_sent_at,
        "period_start": row.period_start,
        "period_end": row.period_end,
        "created_at": row.created_at,
    }


@router.post("/{report_id}/send", status_code=status.HTTP_200_OK)
async def send_report_whatsapp(
    report_id: str,
    payload: SendWhatsAppRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Send a report to a WhatsApp number via the Meta Business API."""
    import re
    if not re.match(r"^\+\d{10,15}$", payload.phone_number):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="phone_number must be in E.164 format: +919876543210",
        )

    # Fetch report
    result = await db.execute(
        text("""
            SELECT id::text, content_hindi, content_english, whatsapp_sent
            FROM reports
            WHERE id = :report_id AND user_id = :user_id
        """),
        {"report_id": report_id, "user_id": current_user.user_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found.")

    content = row.content_hindi or row.content_english
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Report has no content to send.",
        )

    # Send via Meta WhatsApp Business API
    wa_message_id = await _send_whatsapp_message(
        phone_number=payload.phone_number,
        text=content,
    )

    # Mark as sent
    await db.execute(
        text("""
            UPDATE reports SET
                whatsapp_sent = TRUE,
                whatsapp_sent_at = NOW(),
                whatsapp_message_id = :msg_id
            WHERE id = :report_id
        """),
        {"msg_id": wa_message_id, "report_id": report_id},
    )
    await db.commit()

    return {
        "report_id": report_id,
        "sent_to": payload.phone_number,
        "whatsapp_message_id": wa_message_id,
        "status": "sent",
    }


# ---------------------------------------------------------------------------
# WhatsApp sender — supports Twilio (easy) and Meta Business API
# ---------------------------------------------------------------------------

async def _send_whatsapp_message(phone_number: str, text: str) -> str:
    """
    Send a WhatsApp message via Twilio (preferred) or Meta Business API.
    Twilio is used when TWILIO_ACCOUNT_SID is set.
    Meta is used when WHATSAPP_ACCESS_TOKEN is set.
    Returns a message ID string.
    """

    # --- Twilio (sandbox-friendly, no business verification needed) ----------
    if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
        logger.info("Sending WhatsApp via Twilio to %s", phone_number)

        # Twilio expects "whatsapp:+91XXXXXXXXXX" format
        to_wa   = f"whatsapp:{phone_number}" if not phone_number.startswith("whatsapp:") else phone_number
        from_wa = settings.TWILIO_WHATSAPP_FROM

        url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json"

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                url,
                data={"From": from_wa, "To": to_wa, "Body": text[:1600]},
                auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
            )

        if response.status_code not in (200, 201):
            logger.error("Twilio error: %s %s", response.status_code, response.text)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Twilio error: {response.json().get('message', 'Unknown error')}",
            )

        return response.json().get("sid", "twilio_ok")

    # --- Meta WhatsApp Business API ------------------------------------------
    if settings.WHATSAPP_PHONE_NUMBER_ID and settings.WHATSAPP_ACCESS_TOKEN:
        logger.info("Sending WhatsApp via Meta API to %s", phone_number)

        url = f"https://graph.facebook.com/v21.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": phone_number,
            "type": "text",
            "text": {"body": text[:4096]},
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
                    "Content-Type": "application/json",
                },
            )

        if response.status_code != 200:
            logger.error("Meta WhatsApp API error: %s %s", response.status_code, response.text)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to send WhatsApp message. Please try again.",
            )

        return response.json().get("messages", [{}])[0].get("id", "unknown")

    # --- Not configured -------------------------------------------------------
    logger.warning("WhatsApp not configured — set TWILIO_ACCOUNT_SID or WHATSAPP_ACCESS_TOKEN in .env")
    return "mock_message_id"
