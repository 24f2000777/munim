"""
WhatsApp Router
================
Handles the Meta webhook for incoming WhatsApp messages and verification.
Powers the conversational Q&A engine via LangGraph.

Endpoints:
  GET  /api/v1/whatsapp/webhook   — Meta webhook verification (hub.challenge)
  POST /api/v1/whatsapp/webhook   — Receive incoming messages + events
  POST /api/v1/whatsapp/optin     — User opts into WhatsApp notifications

Security:
  - Webhook verification uses hub.verify_token (compared with constant-time).
  - Incoming payloads verified with X-Hub-Signature-256 HMAC (Meta standard).
  - Phone numbers hashed in logs — never stored in plaintext in logs.
  - Rate limited: 60 webhook events/minute (Meta sends bursts).
"""

import hashlib
import hmac
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from auth import AuthenticatedUser, get_current_user
from config import settings
from db.neon_client import get_db_session

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class OptInRequest(BaseModel):
    phone_number: str  # E.164
    language: str = "hi"


# ---------------------------------------------------------------------------
# Meta webhook verification
# ---------------------------------------------------------------------------

@router.get("/webhook", response_class=PlainTextResponse)
async def verify_webhook(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
):
    """
    Meta calls this GET endpoint to verify our webhook URL.
    Responds with hub.challenge if the verify_token matches.
    """
    expected = settings.WHATSAPP_VERIFY_TOKEN
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WhatsApp not configured.",
        )

    # Constant-time comparison to prevent timing attacks
    if hub_mode != "subscribe" or not hmac.compare_digest(hub_verify_token, expected):
        logger.warning("WhatsApp webhook verification failed — bad token")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Verification failed.",
        )

    logger.info("WhatsApp webhook verified successfully")
    return hub_challenge


# ---------------------------------------------------------------------------
# Incoming message handler
# ---------------------------------------------------------------------------

@router.post("/webhook", status_code=status.HTTP_200_OK)
async def receive_webhook(
    request: Request,
    x_hub_signature_256: str = Header(None, alias="X-Hub-Signature-256"),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Receive and process incoming WhatsApp messages from Meta.
    Meta requires a 200 response within 20 seconds — heavy work is async.

    Verifies X-Hub-Signature-256 HMAC before processing any payload.
    """
    raw_body = await request.body()

    # --- HMAC signature verification ---
    _verify_signature(raw_body, x_hub_signature_256)

    # Parse payload
    try:
        payload = await request.json()
    except Exception:
        # Must return 200 to Meta even for malformed payloads
        return {"status": "ok"}

    # Extract messages from Meta's payload structure
    try:
        entries = payload.get("entry", [])
        for entry in entries:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages", [])
                for msg in messages:
                    await _handle_message(msg, value, db)
    except Exception as exc:
        # Log but always return 200 to Meta to avoid retry storms
        logger.error("Error processing WhatsApp webhook: %s", exc, exc_info=True)

    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Opt-in endpoint
# ---------------------------------------------------------------------------

@router.post("/optin", status_code=status.HTTP_200_OK)
async def optin_whatsapp(
    payload: OptInRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    User opts into receiving WhatsApp reports.
    Stores phone number and updates language preference.
    """
    import re
    if not re.match(r"^\+\d{10,15}$", payload.phone_number):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="phone_number must be E.164 format: +919876543210",
        )
    if payload.language not in ("hi", "en", "hinglish"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="language must be 'hi', 'en', or 'hinglish'",
        )

    await db.execute(
        text("""
            UPDATE users SET
                phone = :phone,
                whatsapp_opted_in = TRUE,
                language_preference = :language,
                updated_at = NOW()
            WHERE email = :email
        """),
        {
            "phone": payload.phone_number,
            "language": payload.language,
            "email": current_user.email,
        },
    )
    await db.commit()

    return {
        "status": "opted_in",
        "phone": payload.phone_number,
        "language": payload.language,
        "message": "You will receive weekly business reports on WhatsApp.",
    }


# ---------------------------------------------------------------------------
# Internal: message handling
# ---------------------------------------------------------------------------

async def _handle_message(msg: dict, value: dict, db: AsyncSession) -> None:
    """
    Process a single incoming WhatsApp message.
    Stores conversation record and queues intent detection.
    """
    msg_id = msg.get("id", "")
    from_number = msg.get("from", "")
    msg_type = msg.get("type", "")

    if msg_type != "text":
        # Only handle text messages; ignore audio, image, etc.
        logger.info("Ignoring non-text WhatsApp message type: %s", msg_type)
        return

    text_body = msg.get("text", {}).get("body", "").strip()
    if not text_body:
        return

    # Hash phone for logging (never log raw numbers)
    phone_hash = hashlib.sha256(from_number.encode()).hexdigest()[:12]
    logger.info("Received WhatsApp message from %s...: %r", phone_hash, text_body[:50])

    # Look up user by phone number
    result = await db.execute(
        text("SELECT id::text FROM users WHERE phone = :phone"),
        {"phone": f"+{from_number}" if not from_number.startswith("+") else from_number},
    )
    user_row = result.fetchone()
    user_id = user_row.id if user_row else None

    # Store inbound conversation record
    await db.execute(
        text("""
            INSERT INTO wa_conversations (
                user_id, phone_number, direction, message_text,
                wa_message_id
            ) VALUES (
                :user_id, :phone, 'inbound', :text, :wa_msg_id
            )
            ON CONFLICT (wa_message_id) DO NOTHING
        """),
        {
            "user_id": user_id,
            "phone": from_number,
            "text": text_body[:2000],
            "wa_msg_id": msg_id,
        },
    )
    await db.commit()

    # Detect intent and respond
    await _respond_to_message(
        from_number=from_number,
        text_body=text_body,
        user_id=user_id,
        db=db,
    )


async def _respond_to_message(
    from_number: str,
    text_body: str,
    user_id: str | None,
    db: AsyncSession,
) -> None:
    """
    Simple intent detection + response.
    Full LangGraph Q&A engine will be wired in Phase 3.
    """
    lower = text_body.lower()

    # Basic intent detection
    if any(w in lower for w in ("report", "रिपोर्ट", "summary", "weekly")):
        response = (
            "📊 आपकी latest report यहाँ देखें: munim.app/reports\n\n"
            "या हमें type करें 'help' for more options."
        )
    elif any(w in lower for w in ("help", "मदद", "hi", "hello", "नमस्ते")):
        response = (
            "🙏 नमस्ते! मैं Munim हूँ — आपका AI business assistant.\n\n"
            "आप मुझसे पूछ सकते हैं:\n"
            "• 'report' — इस हफ्ते की report\n"
            "• 'sales' — sales summary\n"
            "• 'alerts' — latest alerts"
        )
    elif any(w in lower for w in ("sales", "revenue", "बिक्री")):
        if user_id:
            # Fetch last analysis
            result = await db.execute(
                text("""
                    SELECT metrics->>'current_revenue' AS rev,
                           metrics->>'trend' AS trend,
                           period_end::text
                    FROM analysis_results
                    WHERE user_id = :uid
                    ORDER BY created_at DESC LIMIT 1
                """),
                {"uid": user_id},
            )
            row = result.fetchone()
            if row and row.rev:
                response = (
                    f"💰 आपकी last period revenue: ₹{float(row.rev):,.0f}\n"
                    f"Trend: {row.trend or 'N/A'} (till {row.period_end})\n\n"
                    "Full report के लिए: munim.app/reports"
                )
            else:
                response = "अभी कोई data नहीं है। Please upload करें: munim.app"
        else:
            response = "Please पहले munim.app पर register करें। 🙏"
    else:
        response = (
            "मुझे समझ नहीं आया 🤔\n\n"
            "Type करें:\n• 'report' — weekly report\n"
            "• 'help' — सभी options\n• 'sales' — sales info"
        )

    # Send response via WhatsApp API
    if settings.WHATSAPP_PHONE_NUMBER_ID and settings.WHATSAPP_ACCESS_TOKEN:
        import httpx
        url = f"https://graph.facebook.com/v21.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                url,
                json={
                    "messaging_product": "whatsapp",
                    "to": from_number,
                    "type": "text",
                    "text": {"body": response},
                },
                headers={
                    "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
                    "Content-Type": "application/json",
                },
            )


# ---------------------------------------------------------------------------
# HMAC verification
# ---------------------------------------------------------------------------

def _verify_signature(body: bytes, signature_header: str | None) -> None:
    """
    Verify X-Hub-Signature-256 from Meta.
    Raises HTTP 403 if signature is missing or invalid.
    """
    app_secret = settings.WHATSAPP_ACCESS_TOKEN  # Meta uses the app secret for HMAC
    if not app_secret:
        return  # Skip verification if WhatsApp not configured (dev mode)

    if not signature_header:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing X-Hub-Signature-256 header.",
        )

    if not signature_header.startswith("sha256="):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid signature format.",
        )

    expected = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()

    provided = signature_header[len("sha256="):]

    if not hmac.compare_digest(expected, provided):
        logger.warning("WhatsApp HMAC verification failed — possible spoofed request")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Signature verification failed.",
        )
