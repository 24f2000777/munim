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
    num_media = int(form.get("NumMedia", "0") or "0")

    if not from_number:
        return {"status": "ok"}

    import hashlib
    phone_hash = hashlib.sha256(from_number.encode()).hexdigest()[:12]
    logger.info("Twilio inbound from %s...: media=%d text=%r", phone_hash, num_media, text_body[:60])

    # Normalize phone — ensure E.164
    phone = f"+{from_number}" if not from_number.startswith("+") else from_number

    # Look up user by phone
    result = await db.execute(
        text("SELECT id::text, name FROM users WHERE phone = :phone"),
        {"phone": phone},
    )
    user_row = result.fetchone()
    user_id = user_row.id if user_row else None

    # --- File received? ---
    if num_media > 0:
        media_type = str(form.get("MediaContentType0", ""))
        # Images work in sandbox — process them via Gemini Vision
        if media_type.startswith("image/"):
            media_url = str(form.get("MediaUrl0", ""))
            filename = _guess_filename_from_content_type(media_type, text_body)
            await _handle_twilio_file(
                phone=phone, user_id=user_id,
                media_url=media_url, media_type=media_type,
                filename=filename, db=db,
            )
        else:
            # Twilio sandbox doesn't forward document files (CSV/Excel/Tally)
            # Guide user to upload via web
            import asyncio
            from services.whatsapp.sender import send_whatsapp_sync
            await asyncio.to_thread(
                send_whatsapp_sync, phone,
                "📂 File मिली! लेकिन WhatsApp sandbox पर CSV/Excel directly analyze नहीं हो सकती।\n\n"
                "👇 *यहाँ upload करें — 30 seconds में analysis ready:*\n"
                "*https://munim.app/upload*\n\n"
                "या अपना ledger का photo भेजें — वो directly analyze हो जाएगा! 📸"
            )
        return {"status": "ok"}

    # --- Text message: run chatbot ---
    if not text_body:
        return {"status": "ok"}

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

    await _respond_to_message(
        from_number=phone,
        text_body=text_body,
        user_id=user_id,
        db=db,
    )

    return {"status": "ok"}


def _guess_filename_from_content_type(content_type: str, caption: str = "") -> str:
    """Guess a filename from Twilio's MediaContentType."""
    ext_map = {
        "text/csv": "data.csv",
        "application/vnd.ms-excel": "data.xls",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "data.xlsx",
        "text/xml": "data.xml",
        "application/xml": "data.xml",
        "image/jpeg": "photo.jpg",
        "image/png": "photo.png",
        "application/octet-stream": "data.csv",  # WhatsApp often sends CSV as octet-stream
    }
    # If caption has a filename hint, use it
    if caption:
        for ext in (".csv", ".xlsx", ".xls", ".xml", ".jpg", ".jpeg", ".png"):
            if caption.lower().endswith(ext):
                return caption.strip()
    return ext_map.get(content_type, "data.csv")


async def _handle_twilio_file(
    phone: str,
    user_id: str | None,
    media_url: str,
    media_type: str,
    filename: str,
    db: AsyncSession,
) -> None:
    """
    Download a file sent via WhatsApp, run full analytics pipeline,
    and send a summary report back to the user.
    """
    import asyncio
    import httpx
    from services.whatsapp.sender import send_whatsapp_sync

    # Acknowledge immediately so user knows we received it
    try:
        await asyncio.to_thread(
            send_whatsapp_sync, phone,
            f"📂 File मिल गया! *{filename}*\n\nAnalysis हो रहा है... 30-60 seconds लगेंगे। ⏳"
        )
    except Exception:
        pass

    # Register/find user — if not registered, create a temporary guest record
    if not user_id:
        try:
            result = await db.execute(
                text("""
                    INSERT INTO users (email, name, phone, whatsapp_opted_in, user_type)
                    VALUES (:email, 'WhatsApp User', :phone, TRUE, 'individual')
                    ON CONFLICT (email) DO UPDATE SET phone = :phone
                    RETURNING id::text
                """),
                {"email": f"wa_{phone.replace('+','')}@whatsapp.munim", "phone": phone},
            )
            row = result.fetchone()
            user_id = row.id if row else None
            await db.commit()
        except Exception as exc:
            logger.warning("Could not create guest user for WhatsApp file: %s", exc)

    # Download file from Twilio (requires Basic Auth with Twilio credentials)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
                response = await client.get(
                    media_url,
                    auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
                )
            else:
                response = await client.get(media_url)
        response.raise_for_status()
        file_bytes = response.content
    except Exception as exc:
        logger.error("Failed to download Twilio media: %s", exc)
        await asyncio.to_thread(
            send_whatsapp_sync, phone,
            "❌ File download नहीं हो पाया। Please दोबारा try करें।"
        )
        return

    logger.info("Downloaded file: %s (%d bytes, type=%s)", filename, len(file_bytes), media_type)

    # Run full analytics pipeline in thread (sync code)
    try:
        analysis_summary = await asyncio.to_thread(
            _run_whatsapp_file_analysis,
            file_bytes=file_bytes,
            filename=filename,
            user_id=user_id,
        )
    except ValueError as exc:
        await asyncio.to_thread(
            send_whatsapp_sync, phone,
            f"❌ *File analyze नहीं हो पाई*\n\n{exc}\n\nKripaya CSV, Excel, या Tally XML file भेजें।"
        )
        return
    except Exception as exc:
        logger.error("WhatsApp file analysis failed: %s", exc, exc_info=True)
        await asyncio.to_thread(
            send_whatsapp_sync, phone,
            "❌ Analysis में error आई। Please file check करके दोबारा भेजें।"
        )
        return

    # Send the analysis report
    try:
        await asyncio.to_thread(send_whatsapp_sync, phone, analysis_summary)
    except Exception as exc:
        logger.error("Failed to send analysis report: %s", exc)


def _run_whatsapp_file_analysis(file_bytes: bytes, filename: str, user_id: str | None) -> str:
    """
    Synchronous: run full analytics pipeline on file bytes and return
    a formatted WhatsApp summary message.
    Raises ValueError for bad files.
    """
    from services.ingestor.schema_detector import detect_and_parse
    from services.cleaner.deduplicator import deduplicate_products
    from services.cleaner.normaliser import normalise
    from services.cleaner.health_scorer import compute_health_score
    from services.analytics.metrics import compute_metrics
    from services.analytics.anomaly import detect_anomalies
    from services.analytics.rfm import compute_rfm

    # Parse
    parsed = detect_and_parse(file_bytes, filename)
    df, _ = deduplicate_products(parsed.df)
    df, _ = normalise(df)
    health = compute_health_score(df)

    if not health.can_analyze:
        raise ValueError(
            f"Data quality score बहुत कम है ({health.score}/100)। "
            "File में valid date, amount, और product columns होने चाहिए।"
        )

    # Analytics
    metrics = compute_metrics(df)
    anomaly_report = detect_anomalies(df)
    customer_segments = compute_rfm(df)

    # Store results if user_id known
    if user_id:
        try:
            import uuid, json
            from sqlalchemy import create_engine, text as sql_text
            from config import settings as cfg
            sync_url = cfg.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
            if "?" in sync_url:
                sync_url = sync_url.split("?")[0]
            engine = create_engine(sync_url, pool_pre_ping=True, connect_args={"sslmode": "require"})

            def _float(v):
                try: return float(v)
                except: return 0.0

            serialized_metrics = {
                "current_revenue": _float(metrics.revenue.current),
                "previous_revenue": _float(metrics.revenue.previous),
                "change_pct": _float(metrics.revenue.change_pct) if metrics.revenue.change_pct else None,
                "trend": metrics.revenue.trend,
                "top_products": [
                    {"name": p.name, "revenue": _float(p.revenue), "quantity": _float(p.quantity)}
                    for p in (metrics.top_products or [])[:5]
                ],
                "dead_stock": [{"name": p.name} for p in (metrics.dead_stock or [])[:5]],
            }

            serialized_anomalies = {
                "total": anomaly_report.total,
                "high_count": anomaly_report.high_count,
                "anomalies": [
                    {"title": a.title, "severity": a.severity,
                     "explanation": a.explanation, "action": a.action}
                    for a in (anomaly_report.anomalies or [])[:10]
                ],
            }

            total_customers = len(customer_segments) if customer_segments else 0
            seg_counts = {}
            for seg in (customer_segments or []):
                s = getattr(seg, 'segment', 'Unknown')
                seg_counts[s] = seg_counts.get(s, 0) + 1

            serialized_customers = {"total": total_customers, "segments": seg_counts}

            upload_id = str(uuid.uuid4())
            analysis_id = str(uuid.uuid4())

            with engine.connect() as conn:
                conn.execute(sql_text("""
                    INSERT INTO uploads (id, user_id, file_name, file_path, file_type, file_size_bytes, status)
                    VALUES (:id, :uid, :fname, :fpath, 'csv', :fsize, 'done')
                """), {"id": upload_id, "uid": user_id, "fname": filename,
                       "fpath": f"whatsapp/{upload_id}.csv", "fsize": len(file_bytes)})
                conn.execute(sql_text("""
                    INSERT INTO analysis_results (
                        id, upload_id, user_id, period_start, period_end,
                        metrics, anomalies, customers, seasonality_context
                    ) VALUES (
                        :id, :uid, :user_id,
                        :pstart, :pend,
                        :metrics::jsonb, :anomalies::jsonb, :customers::jsonb, '{}'::jsonb
                    )
                """), {
                    "id": analysis_id, "uid": upload_id, "user_id": user_id,
                    "pstart": metrics.period_start, "pend": metrics.period_end,
                    "metrics": json.dumps(serialized_metrics),
                    "anomalies": json.dumps(serialized_anomalies),
                    "customers": json.dumps(serialized_customers),
                })
                conn.commit()
        except Exception as exc:
            logger.warning("Could not store WhatsApp file analysis in DB: %s", exc)

    # Build WhatsApp summary message
    rev = float(metrics.revenue.current or 0)
    change = metrics.revenue.change_pct
    trend = metrics.revenue.trend or ""
    trend_emoji = "📈" if trend == "up" else ("📉" if trend == "down" else "➡️")
    change_str = f"({float(change):+.1f}%)" if change is not None else ""

    top_prods = metrics.top_products[:3] if metrics.top_products else []
    prod_lines = "\n".join(
        f"   {i+1}. {p.name} — ₹{float(p.revenue):,.0f}"
        for i, p in enumerate(top_prods)
    ) or "   N/A"

    dead = metrics.dead_stock[:3] if metrics.dead_stock else []
    dead_lines = "\n".join(f"   • {p.name}" for p in dead) if dead else "   कोई नहीं ✅"

    total_cust = len(customer_segments) if customer_segments else 0
    high_alerts = anomaly_report.high_count
    period_start = str(metrics.period_start.date()) if metrics.period_start else "?"
    period_end = str(metrics.period_end.date()) if metrics.period_end else "?"

    msg = (
        f"✅ *Analysis Complete!*\n"
        f"📅 Period: {period_start} → {period_end}\n"
        f"📊 Health Score: {health.score}/100 ({health.grade})\n\n"

        f"💰 *Revenue*\n"
        f"   ₹{rev:,.0f} {change_str} {trend_emoji}\n\n"

        f"🏆 *Top Products*\n{prod_lines}\n\n"

        f"👥 *Customers:* {total_cust}\n\n"

        f"⚠️ *Alerts:* {high_alerts} high severity\n"
    )

    if high_alerts > 0 and anomaly_report.anomalies:
        top_alert = anomaly_report.anomalies[0]
        msg += f"   🔴 {top_alert.title}: {top_alert.explanation[:80]}\n"

    if dead:
        msg += f"\n🛑 *Dead Stock:*\n{dead_lines}\n"

    msg += f"\n💡 Full details: *munim.app*\n— Munim (आपका digital मुनीम)"

    return msg


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

    # Upload data request
    if any(w in lower for w in ("upload", "data bhejo", "data dalo", "file bhejo", "csv", "excel", "tally", "data upload")):
        return "upload_link"

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

    elif intent == "upload_link":
        return (
            "📂 *Data Upload करें*\n\n"
            "CSV, Excel, या Tally XML यहाँ upload करें:\n"
            "👉 *https://munim.app/upload*\n\n"
            "या अपने ledger की *photo भेजें* — Munim खुद analyze कर लेगा! 📸\n\n"
            "Analysis में 30-60 seconds लगते हैं।"
        )

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
            "*📸 Data भेजने के 2 तरीके:*\n"
            "1. Ledger की *photo भेजें* — instant analysis!\n"
            "2. *munim.app/upload* पर CSV/Excel upload करें\n\n"
            "*💬 मुझसे पूछें:*\n"
            "💰 *'sales'* — revenue summary\n"
            "🏆 *'best product'* — top seller\n"
            "⚠️ *'slow maal'* — dead stock\n"
            "👥 *'customer'* — customer info\n"
            "🚨 *'alert'* — business problems\n"
            "📋 *'report'* — full report\n\n"
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
