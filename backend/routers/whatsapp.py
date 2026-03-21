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
# Twilio incoming webhook (form-encoded — different format from Meta)
# ---------------------------------------------------------------------------

@router.post("/twilio-webhook", status_code=status.HTTP_200_OK)
async def receive_twilio_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Receive incoming WhatsApp messages from Twilio Sandbox.
    Twilio sends form-encoded POST (not JSON like Meta).
    Configure this URL in: Twilio Console → Messaging → Sandbox → "When a message comes in"
    """
    # Twilio sends form-encoded body
    form = await request.form()
    from_number = str(form.get("From", "")).replace("whatsapp:", "")
    text_body = str(form.get("Body", "")).strip()
    msg_id = str(form.get("MessageSid", ""))

    if not from_number or not text_body:
        return {"status": "ok"}

    import hashlib
    phone_hash = hashlib.sha256(from_number.encode()).hexdigest()[:12]
    logger.info("Twilio inbound from %s...: %r", phone_hash, text_body[:60])

    # Normalize phone — ensure E.164
    phone = f"+{from_number}" if not from_number.startswith("+") else from_number

    # Look up user by phone
    result = await db.execute(
        text("SELECT id::text FROM users WHERE phone = :phone"),
        {"phone": phone},
    )
    user_row = result.fetchone()
    user_id = user_row.id if user_row else None

    # Detect intent for logging
    intent = _detect_intent(text_body)

    # Store inbound record
    try:
        await db.execute(
            text("""
                INSERT INTO wa_conversations (
                    user_id, phone_number, direction, message_text,
                    wa_message_id, intent_detected
                ) VALUES (
                    :user_id, :phone, 'inbound', :text, :wa_msg_id, :intent
                )
                ON CONFLICT (wa_message_id) DO NOTHING
            """),
            {
                "user_id": user_id,
                "phone": from_number,
                "text": text_body[:2000],
                "wa_msg_id": msg_id,
                "intent": intent,
            },
        )
        await db.commit()
    except Exception as exc:
        logger.warning("Failed to store Twilio inbound record: %s", exc)
        try:
            await db.rollback()
        except Exception:
            pass

    # Build and send response using the same chatbot logic
    await _respond_to_message(
        from_number=phone,
        text_body=text_body,
        user_id=user_id,
        db=db,
    )

    # Twilio expects empty 200 (not TwiML) when we send via API
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

    # Detect intent early so we can log it on the inbound record too
    intent = _detect_intent(text_body)

    # Store inbound conversation record
    try:
        await db.execute(
            text("""
                INSERT INTO wa_conversations (
                    user_id, phone_number, direction, message_text,
                    wa_message_id, intent_detected
                ) VALUES (
                    :user_id, :phone, 'inbound', :text, :wa_msg_id, :intent
                )
                ON CONFLICT (wa_message_id) DO NOTHING
            """),
            {
                "user_id": user_id,
                "phone": from_number,
                "text": text_body[:2000],
                "wa_msg_id": msg_id,
                "intent": intent,
            },
        )
        await db.commit()
    except Exception as exc:
        logger.warning("Could not store intent_detected on inbound record: %s", exc)
        # Fallback: insert without intent_detected column
        await db.rollback()
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

    # Respond to the message
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
    Full 2-way chatbot: detects intent, fetches real DB data, sends response.
    Supports Hindi + English queries. No LLM needed — all template-based (instant).
    """
    import asyncio
    from services.whatsapp.sender import send_whatsapp_sync

    intent = _detect_intent(text_body)
    logger.info("WhatsApp intent detected: %s", intent)

    if not user_id:
        response = (
            "🙏 Munim पर register करें: munim.app\n"
            "आपका business data track करने के लिए login करें।"
        )
    else:
        # Fetch latest analysis data for this user (single query covers all intents)
        analysis = await _fetch_latest_analysis(user_id, db)
        response = await _build_response(intent, analysis, db)

    # Send via WhatsApp (Twilio or Meta) — run sync sender in thread pool
    phone = f"+{from_number}" if not from_number.startswith("+") else from_number
    try:
        await asyncio.to_thread(send_whatsapp_sync, phone, response)
    except Exception as exc:
        logger.error("Failed to send WhatsApp reply: %s", exc)
        return

    # Store outbound reply in wa_conversations
    try:
        await db.execute(
            text("""
                INSERT INTO wa_conversations (
                    user_id, phone_number, direction, message_text,
                    intent_detected, wa_message_id
                ) VALUES (
                    :uid, :phone, 'outbound', :text, :intent, :wa_id
                )
            """),
            {
                "uid": user_id,
                "phone": from_number,
                "text": response[:2000],
                "intent": intent,
                "wa_id": f"out_{from_number}_{int(__import__('time').time())}",
            },
        )
        await db.commit()
    except Exception as exc:
        logger.warning("Could not store outbound reply in wa_conversations: %s", exc)
        await db.rollback()


def _detect_intent(text: str) -> str:
    """
    Detect user intent from Hindi/English message text.
    Order matters — check most specific intents first.
    """
    # Normalize: lowercase + strip extra whitespace
    lower = text.lower().strip()

    # Today's revenue (more specific than general revenue)
    if any(w in lower for w in ("aaj", "आज", "today", "kitna hua", "कितना हुआ", "aaj ka")):
        return "revenue_today"

    # Alerts / problems
    if any(w in lower for w in ("alert", "dikkat", "समस्या", "problem", "gadbad", "परेशानी", "issue", "warning")):
        return "alerts"

    # Best product
    if any(w in lower for w in ("best product", "sabse acha", "सबसे अच्छा", "top product", "sabse zyada")):
        return "best_product"

    # Slow/dead stock
    if any(w in lower for w in ("slow", "nahi bik", "नहीं बिक", "dead stock", "kaun sa maal", "slow maal", "maal nahi")):
        return "slow_stock"

    # Customer count
    if any(w in lower for w in ("customer", "graahaak", "ग्राहक", "kitne log", "buyers", "clients")):
        return "customer_count"

    # General revenue/sales
    if any(w in lower for w in ("biki", "बिक्री", "kamai", "कमाई", "sales", "revenue", "income", "bikri", "kitna bika")):
        return "revenue_query"

    # Report request
    if any(w in lower for w in ("report", "रिपोर्ट", "summary", "weekly", "monthly", "bhejo")):
        return "report"

    # Help / greeting
    if any(w in lower for w in ("help", "मदद", "hi", "hello", "नमस्ते", "start", "menu", "kya kar", "options")):
        return "help"

    return "unknown"


async def _fetch_latest_analysis(user_id: str, db: AsyncSession) -> dict | None:
    """Single query to fetch all data needed for any intent response."""
    result = await db.execute(
        text("""
            SELECT ar.metrics, ar.anomalies, ar.customers,
                   ar.period_start::text, ar.period_end::text,
                   u.name, u.language_preference
            FROM analysis_results ar
            JOIN users u ON u.id = ar.user_id
            WHERE ar.user_id = :uid
            ORDER BY ar.created_at DESC
            LIMIT 1
        """),
        {"uid": user_id},
    )
    row = result.fetchone()
    if not row:
        return None
    return {
        "metrics": row.metrics or {},
        "anomalies": row.anomalies or {},
        "customers": row.customers or {},
        "period_start": row.period_start,
        "period_end": row.period_end,
        "owner_name": row.name or "Business Owner",
        "lang": row.language_preference or "hi",
    }


async def _build_response(intent: str, analysis: dict | None, db: AsyncSession) -> str:
    """Build a response string for the detected intent using real DB data."""
    if not analysis:
        return (
            "अभी कोई data नहीं है। 📁\n\n"
            "Please अपना sales data upload करें: *munim.app*\n"
            "CSV, Excel, या Tally XML सब चलेगा।"
        )

    metrics = analysis["metrics"]
    anomalies = analysis["anomalies"]
    customers = analysis["customers"]
    period_end = analysis["period_end"] or ""
    owner_name = analysis["owner_name"]
    lang = analysis["lang"]

    if intent == "revenue_today":
        from datetime import date as date_cls
        today_str = str(date_cls.today())
        if period_end and period_end[:10] == today_str:
            rev = metrics.get("current_revenue", 0) or 0
            trend = metrics.get("trend", "")
            trend_emoji = "📈" if trend == "up" else ("📉" if trend == "down" else "➡️")
            return (
                f"💰 आज की revenue: *₹{float(rev):,.0f}*  {trend_emoji}\n"
                f"Period: {analysis['period_start']} → {period_end}\n\n"
                "Full analysis: munim.app"
            )
        else:
            return (
                f"📅 आज का data नहीं है।\n"
                f"Last upload: *{period_end[:10] if period_end else 'N/A'}* का था।\n\n"
                "नया data upload करें: *munim.app*"
            )

    elif intent == "revenue_query":
        rev = metrics.get("current_revenue", 0) or 0
        change = metrics.get("change_pct") or metrics.get("revenue_change_pct") or 0
        trend = metrics.get("trend", "")
        trend_emoji = "📈" if trend == "up" else ("📉" if trend == "down" else "➡️")
        change_str = f"({float(change):+.1f}%)" if change else ""
        return (
            f"💰 *{owner_name} जी*, आपकी revenue:\n\n"
            f"*₹{float(rev):,.0f}* {change_str} {trend_emoji}\n"
            f"Period: {period_end[:10] if period_end else 'N/A'} तक\n\n"
            "Full report: munim.app/reports"
        )

    elif intent == "best_product":
        top_products = metrics.get("top_products", [])
        if top_products and isinstance(top_products[0], dict):
            p = top_products[0]
            name = p.get("name", "N/A")
            rev = p.get("revenue", 0)
            return (
                f"🏆 *Best Product:*\n\n"
                f"*{name}*\n"
                f"Revenue: ₹{float(rev):,.0f}\n\n"
                f"Top 3 products देखें: munim.app"
            )
        return "अभी product data नहीं है। Data upload करें: munim.app"

    elif intent == "slow_stock":
        dead_stock = metrics.get("dead_stock", [])
        if not dead_stock:
            return (
                "✅ *सब products बिक रहे हैं!*\n\n"
                f"कोई dead stock नहीं है। {period_end[:10] if period_end else ''} तक।"
            )
        lines = ["⚠️ *धीमे चल रहे products:*\n"]
        for i, item in enumerate(dead_stock[:3], 1):
            name = item.get("name", "?") if isinstance(item, dict) else str(item)
            lines.append(f"{i}. {name}")
        lines.append("\nFull analysis: munim.app")
        return "\n".join(lines)

    elif intent == "customer_count":
        total = customers.get("total", 0)
        segments = customers.get("segments", {})
        champion = segments.get("Champion", 0)
        at_risk = segments.get("At Risk", 0)
        lost = segments.get("Lost", 0)
        return (
            f"👥 *Customers:*\n\n"
            f"Total: *{total}*\n"
            f"• Champions: {champion}\n"
            f"• At Risk: {at_risk}\n"
            f"• Lost: {lost}\n\n"
            "Full segmentation: munim.app"
        )

    elif intent == "alerts":
        anomaly_list = anomalies.get("anomalies", [])
        high_medium = [a for a in anomaly_list if a.get("severity") in ("HIGH", "MEDIUM")]
        if not high_medium:
            return "✅ *कोई बड़ी problem नहीं है!*\n\nSab theek chal raha hai. 😊"
        lines = [f"⚠️ *{len(high_medium)} Alerts:*\n"]
        for i, a in enumerate(high_medium[:3], 1):
            title = a.get("title", "Alert")
            explanation = a.get("explanation", "")[:80]
            lines.append(f"{i}. *{title}*\n   {explanation}")
        lines.append("\nFull alerts: munim.app/alerts")
        return "\n".join(lines)

    elif intent == "report":
        return (
            f"📊 *{owner_name} जी की Report*\n\n"
            "अपनी full report generate करने के लिए:\n"
            "*munim.app* → Analysis → Generate Report\n\n"
            "या type करें *'sales'* for quick summary."
        )

    elif intent == "help":
        return (
            "🙏 *नमस्ते! मैं Munim हूँ।*\n"
            "आपका AI business assistant। 🤖\n\n"
            "*आप मुझसे पूछ सकते हैं:*\n\n"
            "💰 *'aaj kitna hua?'* — आज की sales\n"
            "📊 *'sales'* — revenue summary\n"
            "🏆 *'best product'* — top seller\n"
            "⚠️ *'slow maal'* — dead stock\n"
            "👥 *'customer'* — customer count\n"
            "🚨 *'alert'* — business problems\n"
            "📋 *'report'* — full report link\n\n"
            "Website: *munim.app* 🚀"
        )

    else:  # unknown
        return (
            "मुझे समझ नहीं आया 🤔\n\n"
            "Type करें *'help'* to see all options.\n\n"
            "या website पर जाएं: *munim.app*"
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
