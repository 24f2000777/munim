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

# In-memory deduplication — prevents duplicate processing when Meta retries
_processed_msg_ids: set[str] = set()
_MAX_DEDUP_CACHE = 1000  # keep last 1000 message IDs


def _app_url() -> str:
    """Return the public app URL — set APP_URL in .env for production."""
    return settings.APP_URL.rstrip("/")


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
                    msg_id = msg.get("id", "")
                    if msg_id and msg_id in _processed_msg_ids:
                        logger.info("Skipping duplicate message id=%s", msg_id)
                        continue
                    if msg_id:
                        _processed_msg_ids.add(msg_id)
                        if len(_processed_msg_ids) > _MAX_DEDUP_CACHE:
                            _processed_msg_ids.pop()
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
    # Debug: log all media fields so we can see what Twilio actually forwards
    for i in range(num_media):
        logger.info("  Media[%d]: url=%s type=%s", i,
                    str(form.get(f"MediaUrl{i}", ""))[:80],
                    str(form.get(f"MediaContentType{i}", "")))

    # Normalize phone — ensure E.164
    phone = f"+{from_number}" if not from_number.startswith("+") else from_number

    # Auto-register or look up user — WhatsApp-first: no account needed
    user_id = await _get_or_create_whatsapp_user(phone, db)

    # --- File received? ---
    if num_media > 0:
        media_url  = str(form.get("MediaUrl0", ""))
        media_type = str(form.get("MediaContentType0", ""))
        filename   = _guess_filename_from_content_type(media_type, text_body)
        # All file types (CSV, Excel, XML, images) go through the same pipeline
        await _handle_twilio_file(
            phone=phone, user_id=user_id,
            media_url=media_url, media_type=media_type,
            filename=filename, db=db,
        )
        return {"status": "ok"}

    # --- Twilio sandbox limitation: documents sent as filename-only text ---
    # When Twilio sandbox can't forward a file as media (XML, CSV, Excel),
    # it sets NumMedia=0 and puts the filename in the Body field.
    # Detect this and explain the limitation clearly.
    _UNSUPPORTED_EXTS = (".xml", ".xlsx", ".xls", ".csv", ".pdf", ".txt")
    _body_lower = text_body.lower()
    if num_media == 0 and any(_body_lower.endswith(ext) for ext in _UNSUPPORTED_EXTS):
        import asyncio
        from services.whatsapp.sender import send_whatsapp_sync
        logger.info("Twilio sandbox: document file sent as text body — %r", text_body)
        await asyncio.to_thread(
            send_whatsapp_sync, phone,
            f"📎 *'{text_body}'* मिली, लेकिन Twilio sandbox इस file type को directly process नहीं कर सकता।\n\n"
            "*अभी 2 तरीके काम करते हैं:*\n\n"
            "📸 *Option 1 (सबसे आसान):*\n"
            "Tally या Vyapar screen का screenshot लें और यहाँ photo की तरह भेजें। ✅\n\n"
            "📊 *Option 2:*\n"
            "Tally से data को *CSV format में export* करें, फिर वो CSV file भेजें।\n"
            "(Gateway of Tally → Reports → Export → CSV)\n\n"
            "⚡ दोनों में 60 seconds में analysis आ जाएगी!"
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


async def _get_or_create_whatsapp_user(phone: str, db: AsyncSession) -> str | None:
    """
    WhatsApp-first onboarding with beta whitelist gate.

    Flow:
      1. Check beta_waitlist — if phone not approved, return None (bot sends join-beta message)
      2. Look up existing user by phone
      3. If not found, auto-create a guest account tied to this phone

    Returns the user's UUID string, or None if not whitelisted / creation fails.
    """
    # Gate: phone must be on the approved beta whitelist
    wl = await db.execute(
        text("SELECT approved FROM beta_waitlist WHERE phone = :phone"),
        {"phone": phone},
    )
    wl_row = wl.fetchone()
    if not wl_row or not wl_row.approved:
        return None  # Not whitelisted — bot will send "join beta" message

    # Try to find existing user
    result = await db.execute(
        text("SELECT id::text FROM users WHERE phone = :phone"),
        {"phone": phone},
    )
    row = result.fetchone()
    if row:
        return row.id

    # Whitelisted but no user yet — auto-register
    try:
        result = await db.execute(
            text("""
                INSERT INTO users (email, name, phone, whatsapp_opted_in, user_type)
                VALUES (:email, 'WhatsApp User', :phone, TRUE, 'smb_owner')
                ON CONFLICT (email) DO UPDATE SET phone = EXCLUDED.phone
                RETURNING id::text
            """),
            {
                "email": f"wa_{phone.replace('+', '')}@whatsapp.munim",
                "phone": phone,
            },
        )
        row = result.fetchone()
        await db.commit()
        if row:
            logger.info("Auto-registered whitelisted WhatsApp user phone=%s****", phone[:6])
            return row.id
    except Exception as exc:
        logger.warning("Could not auto-create WhatsApp user: %s", exc)
        try:
            await db.rollback()
        except Exception:
            pass
    return None


def _not_whitelisted_response() -> str:
    """Message shown to phones not yet on the beta whitelist."""
    return (
        "🙏 Namaskar! Main *Munim* hoon — aapka AI business advisor.\n\n"
        "Abhi hum *private beta* mein hain.\n\n"
        "👉 Access ke liye yahan join karein:\n"
        f"{_app_url()}\n\n"
        "Join karne ke baad seedha yahan file bhejein — koi app download nahi! 🚀"
    )


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

    # Gate: only whitelisted phones can trigger file analysis
    if not user_id:
        await asyncio.to_thread(
            send_whatsapp_sync, phone, _not_whitelisted_response()
        )
        return

    # Acknowledge immediately so user knows we received it
    try:
        await asyncio.to_thread(
            send_whatsapp_sync, phone,
            f"📂 File मिल गया! *{filename}*\n\n"
            "⏳ Analysis हो रही है... 30-60 seconds रुकें।\n"
            "Report यहीं WhatsApp पर आ जाएगी। ✅"
        )
    except Exception:
        pass

    # Download file from Twilio (requires Basic Auth + redirect following)
    # Twilio media URLs issue a 302 redirect to S3 — must follow_redirects=True
    logger.info("Downloading media from Twilio: %s (type=%s)", media_url[:80], media_type)
    try:
        async with httpx.AsyncClient(
            timeout=60.0,
            follow_redirects=True,        # Critical: Twilio redirects to S3
        ) as client:
            if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
                response = await client.get(
                    media_url,
                    auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
                )
            else:
                response = await client.get(media_url)
        logger.info("Download response: status=%d size=%d bytes", response.status_code, len(response.content))
        response.raise_for_status()
        file_bytes = response.content
        if len(file_bytes) == 0:
            raise ValueError("Empty file received from Twilio")
    except Exception as exc:
        logger.error("Failed to download Twilio media: %s — url=%s", exc, media_url[:80], exc_info=True)
        await asyncio.to_thread(
            send_whatsapp_sync, phone,
            f"❌ File download नहीं हो पाया।\n\nError: {type(exc).__name__}\n\nPlease दोबारा try करें।"
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


def _run_whatsapp_file_analysis(file_bytes: bytes, filename: str, user_id: str | None) -> str:  # noqa: C901
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
                "current_revenue": _float(metrics.revenue.current_period),
                "previous_revenue": _float(metrics.revenue.previous_period),
                "change_pct": _float(metrics.revenue.change_pct) if metrics.revenue.change_pct else None,
                "trend": metrics.revenue.trend,
                "top_products": [
                    {"name": p.name, "revenue": _float(p.revenue), "units_sold": p.units_sold}
                    for p in (metrics.top_products or [])
                ],
                "dead_stock": [{"name": p.product} for p in (metrics.dead_stock or [])],
            }

            serialized_anomalies = {
                "total": anomaly_report.total_detected,
                "high_count": anomaly_report.high_count,
                "medium_count": anomaly_report.medium_count,
                "low_count": anomaly_report.low_count,
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
                    VALUES (:id, :uid, :fname, :fpath, :ftype, :fsize, 'done')
                """), {"id": upload_id, "uid": user_id, "fname": filename,
                       "fpath": f"whatsapp/{upload_id}/{filename}",
                       "ftype": parsed.file_type,
                       "fsize": len(file_bytes)})
                conn.execute(sql_text("""
                    INSERT INTO analysis_results (
                        id, upload_id, user_id, period_start, period_end,
                        metrics, anomalies, products, customers, seasonality_context
                    ) VALUES (
                        :id, :uid, :user_id,
                        :pstart, :pend,
                        CAST(:metrics AS jsonb), CAST(:anomalies AS jsonb),
                        '[]'::jsonb, CAST(:customers AS jsonb), '{}'::jsonb
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
    rev = float(metrics.revenue.current_period or 0)
    change = metrics.revenue.change_pct
    trend = metrics.revenue.trend or ""
    trend_emoji = "📈" if trend == "up" else ("📉" if trend == "down" else "➡️")
    change_str = f"({float(change):+.1f}%)" if change is not None else ""

    top_prods = metrics.top_products or []
    prod_lines = "\n".join(
        f"   {i+1}. {p.name} — ₹{float(p.revenue):,.0f}"
        for i, p in enumerate(top_prods)
    ) or "   N/A"

    dead = metrics.dead_stock[:5] if metrics.dead_stock else []
    dead_lines = "\n".join(f"   • {p.product}" for p in dead) if dead else "   कोई नहीं ✅"
    if metrics.dead_stock and len(metrics.dead_stock) > 5:
        dead_lines += f"\n   ...और {len(metrics.dead_stock) - 5} items"

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

    msg += (
        f"\n💬 कोई भी सवाल पूछें — data के बारे में कुछ भी!\n\n"
        f"📊 *Full charts & dashboard:*\n"
        f"{_app_url()}\n\n"
        f"— Munim (आपका digital मुनीम)"
    )

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

    # Auto-register or look up user — WhatsApp-first: no account needed
    phone_e164 = f"+{from_number}" if not from_number.startswith("+") else from_number
    user_id = await _get_or_create_whatsapp_user(phone_e164, db)

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
        logger.warning("Could not store inbound record: %s", exc)
        await db.rollback()

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
    AI-brain chatbot: understands ANY message in any language/style.
    Two fast-paths (greetings + upload request) skip LLM for instant response.
    All other messages → LLM with full business context + conversation history.
    """
    import asyncio
    from services.whatsapp.sender import send_whatsapp_sync

    lower = text_body.strip().lower()

    # Fast-path 1: exact greetings → static help menu (instant, no LLM)
    if lower in ("hi", "hello", "start", "help", "menu", "namaste", "नमस्ते", "हेलो", "helo", "hey"):
        response = _static_help_menu()
        intent = "help"

    # Not on beta whitelist
    elif not user_id:
        response = _not_whitelisted_response()
        intent = "not_whitelisted"

    # Fast-path 2: file upload request → static instructions (instant, no LLM)
    elif any(w in lower for w in ("upload", "csv", "excel", "file bhejo", "data bhejo", "data send", "tally export")):
        response = _static_upload_instructions()
        intent = "upload_link"

    # Full AI brain path — LLM with business data + conversation history
    # New whitelisted users (no analysis yet) are guided to upload their file via the LLM prompt
    else:
        analysis = await _fetch_latest_analysis(user_id, db)
        history = await _fetch_conversation_history(user_id, from_number, db)
        response = _ai_chatbot_respond(text_body, analysis, history)
        intent = "ai_generated"

    logger.info("WhatsApp response intent: %s | len=%d", intent, len(response))

    # Send via WhatsApp — run sync sender in thread pool
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
    Lightweight intent classifier for DB logging only.
    Not used for response generation (LLM handles that).
    """
    lower = text.lower().strip()

    def has(*tokens):
        return any(t in lower for t in tokens)

    if has("aaj", "आज", "today", "abhi"):
        return "revenue_today"
    if has("alert", "problem", "gadbad", "dikkat", "loss", "nuksan"):
        return "alerts"
    if has("top", "best", "sabse", "sbse", "popular", "most sold"):
        return "best_product"
    if has("slow", "dead stock", "nahi bik", "nhi bik", "unsold"):
        return "slow_stock"
    if has("customer", "grahak", "ग्राहक", "buyers"):
        return "customer_count"
    if has("biki", "bikri", "sales", "revenue", "kamai", "income", "profit"):
        return "revenue_query"
    if has("report", "summary", "weekly", "monthly"):
        return "report"
    if has("upload", "csv", "excel", "file", "tally"):
        return "upload_link"
    if has("help", "hi", "hello", "namaste", "menu", "start"):
        return "help"
    return "ai_generated"


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


async def _fetch_conversation_history(
    user_id: str | None,
    phone: str,
    db: AsyncSession,
    limit: int = 10,
) -> list[dict]:
    """
    Fetch last N messages (inbound + outbound) for conversation memory.
    Returns list ordered oldest→newest for natural dialogue flow.
    """
    try:
        result = await db.execute(
            text("""
                SELECT direction, message_text, created_at
                FROM wa_conversations
                WHERE (user_id = :uid OR phone_number = :phone)
                  AND direction IN ('inbound', 'outbound')
                ORDER BY created_at DESC
                LIMIT :lim
            """),
            {"uid": user_id, "phone": phone.lstrip("+"), "lim": limit},
        )
        rows = result.fetchall()
        return [
            {
                "role": "user" if r.direction == "inbound" else "assistant",
                "text": r.message_text or "",
            }
            for r in reversed(rows)
        ]
    except Exception as exc:
        logger.warning("Could not fetch conversation history: %s", exc)
        return []


def _ai_chatbot_respond(user_message: str, analysis: dict | None, history: list[dict]) -> str:
    """
    Core AI chatbot brain. Sends full business context + conversation history to LLM.
    Falls back to structured template when all models are exhausted.
    """
    from services.ai.model_router import router as _router

    # Log what data is being sent to LLM so we can debug wrong-product issues
    if analysis:
        m = analysis.get("metrics", {})
        top = [p.get("name") for p in m.get("top_products", [])[:3]]
        logger.info(
            "[chatbot] Context: period=%s→%s revenue=%.0f top_products=%s",
            analysis.get("period_start"), analysis.get("period_end"),
            float(m.get("current_revenue", 0) or 0), top,
        )
    else:
        logger.info("[chatbot] Context: no analysis data found for user")

    prompt = _build_chatbot_prompt(user_message, analysis, history)
    try:
        return _router.call_text(prompt, max_tokens=350, temperature=0.25)
    except RuntimeError as exc:
        logger.warning("All AI models exhausted for chatbot: %s", exc)
        return _build_ai_failure_response(analysis, exc)


def _build_chatbot_prompt(user_message: str, analysis: dict | None, history: list[dict]) -> str:
    """
    Build the expert chatbot prompt with full business data context + conversation history.
    The LLM handles ALL intent detection, response generation, and edge cases.
    """
    # ── Section 1: Business data context ──
    if analysis:
        m = analysis.get("metrics", {})
        a = analysis.get("anomalies", {})
        c = analysis.get("customers", {})
        owner_name = analysis.get("owner_name", "Owner")
        period_start = analysis.get("period_start", "?")
        period_end = analysis.get("period_end", "?")

        top_products = m.get("top_products", [])
        dead_stock = m.get("dead_stock", [])
        anomaly_list = a.get("anomalies", [])
        segments = c.get("segments", {})

        current_rev = float(m.get("current_revenue", 0) or 0)
        prev_rev = float(m.get("previous_revenue", 0) or 0)
        change_pct = m.get("change_pct")
        trend = m.get("trend", "flat")
        change_str = f"{float(change_pct):+.1f}%" if change_pct is not None else "first period"

        # Format top products
        if top_products:
            prod_lines = "\n".join(
                f"  {i+1}. {p.get('name', '?')} — ₹{float(p.get('revenue', 0)):,.0f}"
                for i, p in enumerate(top_products[:10])
            )
            prod_note = f"(sirf {len(top_products)} products hain data mein)" if len(top_products) < 10 else ""
            product_names_list = ", ".join(f'"{p.get("name","?")}"' for p in top_products)
        else:
            prod_lines = "  Data available nahi"
            prod_note = ""
            product_names_list = "none"

        # Format dead stock
        if dead_stock:
            dead_lines = "\n".join(
                f"  • {d.get('name', d.get('product', '?'))}" for d in dead_stock
            )
        else:
            dead_lines = "  Koi nahi — sab products bik rahe hain ✅"

        # Format alerts
        high_count = int(a.get("high_count", 0))
        total_alerts = int(a.get("total", len(anomaly_list)))
        if anomaly_list:
            alert_lines = "\n".join(
                f"  [{al.get('severity', '?')}] {al.get('title', '')}: {al.get('explanation', '')[:120]}"
                for al in anomaly_list[:5]
            )
        else:
            alert_lines = "  Koi alert nahi."

        data_block = f"""
=== BUSINESS DATA (latest uploaded file) ===
Owner: {owner_name}
Data period: {period_start} → {period_end}
Revenue this period: ₹{current_rev:,.0f}
Revenue previous period: ₹{prev_rev:,.0f}
Change: {change_str} | Trend: {trend}

Top products (by revenue): {prod_note}
{prod_lines}

Dead/slow stock (14+ days not sold):
{dead_lines}

Customers: {c.get('total', 0)} total
  Champions (best customers): {segments.get('Champion', 0)}
  Loyal: {segments.get('Loyal', 0)}
  At Risk: {segments.get('At Risk', 0)}
  Lost: {segments.get('Lost', 0)}

Active alerts: {high_count} HIGH | {total_alerts - high_count} MEDIUM/LOW
{alert_lines}
============================================"""
    else:
        owner_name = "Owner"
        period_end = None
        top_products = []
        product_names_list = "none (no data uploaded yet)"
        data_block = """
=== BUSINESS DATA ===
STATUS: Naya user — abhi tak koi sales file upload nahi ki gayi.
ACTION REQUIRED: Owner ko warmly welcome karo aur samjhao ki sirf ek file ya photo bhejni hai.
====================="""

    # ── Section 2: Conversation history ──
    if history:
        history_block = "\n=== RECENT CONVERSATION ===\n"
        for msg in history[-8:]:
            role = "Owner" if msg["role"] == "user" else "Munim"
            history_block += f"{role}: {msg['text'][:200]}\n"
        history_block += "==========================="
    else:
        history_block = ""

    # ── Section 3: Full prompt ──
    period_end_str = (period_end or "?")[:10] if period_end else "pichla upload"
    return f"""You are Munim (मुनीम) — a brilliant, trusted digital accountant for Indian small business owners. You are their most helpful advisor — always honest, always clear, never confusing.

YOUR PERSONALITY:
- Speak in natural Hinglish (Hindi + English mix) like a trusted friend who knows accounts
- Be warm but professional — like a CA who also understands a shopkeeper's reality
- Never use jargon: no "CAGR", no "YoY", no "ROI", no "cohort", no "churn" — speak simply
- Be HONEST: if you don't have data for something, say so clearly with the reason

{data_block}
{history_block}

⚠️ CRITICAL DATA INTEGRITY RULE:
The ONLY product names that exist in this owner's data are: {product_names_list}
You MUST NEVER mention any product name that is not in this list.
If asked about "top 10" but only {len(top_products) if top_products else 0} products are listed above — give exactly those products, do not invent others.

RESPONSE RULES (follow every one):
1. Answer in Hinglish — mix Hindi + English naturally, like: "Bhai, is mahine ₹1,80,000 ki bikri hui"
2. Keep responses SHORT — max 6 lines for simple queries, max 10 lines for complex ones. WhatsApp is not email.
3. Use ₹ Indian format: ₹1,80,000 (NOT ₹180000 or 1.8L)
4. Max 2 emojis — only where they add meaning (📈 growth, ⚠️ alert, ✅ good)
5. USE ONLY the numbers AND product names from BUSINESS DATA above — never invent any figure or name
6. If asked about "today" but data is from {period_end_str} → say "aapke last upload ({period_end_str}) mein yeh tha..."
7. If STATUS shows "Naya user" → warmly welcome them and ONLY say: send your sales file here on WhatsApp (CSV/Excel/Tally) OR send a photo of your ledger/Vyapar screen. Analysis 60 seconds mein aa jayegi. No app needed, no login needed.
8. For follow-up questions → use RECENT CONVERSATION above to understand context, don't ask them to repeat
9. If genuinely cannot answer (e.g. tax advice, predictions) → say exactly why and redirect helpfully
10. Never say "I don't know" — either answer from data, explain the limitation, or redirect constructively

Owner's message: {user_message}

Reply as Munim now (Hinglish, short, WhatsApp-friendly):"""


def _build_ai_failure_response(analysis: dict | None, error: Exception) -> str:
    """
    Transparent fallback when ALL LLM models are exhausted.
    Shows available structured data so user is never left empty-handed.
    """
    if analysis:
        m = analysis.get("metrics", {})
        top = m.get("top_products", [{}])
        top_name = top[0].get("name", "N/A") if top else "N/A"
        top_rev = float(top[0].get("revenue", 0)) if top else 0
        total_cust = analysis.get("customers", {}).get("total", "?")
        period_end = (analysis.get("period_end") or "?")[:10]
        return (
            f"⚠️ AI abhi busy hai — lekin yeh data available hai ({period_end} tak):\n\n"
            f"💰 Revenue: ₹{float(m.get('current_revenue', 0) or 0):,.0f}\n"
            f"🏆 Top product: {top_name} — ₹{top_rev:,.0f}\n"
            f"👥 Customers: {total_cust}\n\n"
            f"Thodi der baad dobara try karein. Full data: {_app_url()}"
        )
    return (
        "⚠️ AI service thodi der ke liye unavailable hai.\n"
        "Kripaya 5 minutes baad dobara try karein.\n\n"
        f"Data dekhne ke liye: {_app_url()}"
    )


def _static_help_menu() -> str:
    """Instant help menu — no LLM needed."""
    return (
        "🙏 *Namaskar! Main Munim hoon.*\n"
        "Aapka AI business advisor. 🤖\n\n"
        "*📲 Data bhejne ke liye:*\n"
        "• CSV / Excel / Tally XML file attach karein\n"
        "• Ya ledger ya Vyapar screen ki *photo bhejein*\n"
        "60 seconds mein analysis yahan aa jayegi! ✅\n\n"
        "*💬 Kuch bhi poochh sakte hain, jaise:*\n"
        "• \"Meri revenue kitni hai?\"\n"
        "• \"Top 10 products kaun se hain?\"\n"
        "• \"Kaunsa maal nahi bik raha?\"\n"
        "• \"Mere customers ki situation kaisi hai?\"\n"
        "• \"Koi badi problem hai kya?\"\n\n"
        "Koi bhi sawaal poochho — main samjhunga! 🚀"
    )


def _static_upload_instructions() -> str:
    """Instant upload instructions — no LLM needed."""
    return (
        "📂 *Data bhejein — yahan WhatsApp par!*\n\n"
        "Is chat mein apni file attach karke bhejein:\n"
        "✅ CSV file\n"
        "✅ Excel file (.xlsx)\n"
        "✅ Tally XML\n"
        "📸 Ledger ya Vyapar screen ki photo (JPG/PNG)\n\n"
        "Analysis 30-60 seconds mein yahan aa jayegi.\n"
        "Koi app download nahi, koi login nahi! 🚀"
    )


# ---------------------------------------------------------------------------
# HMAC verification
# ---------------------------------------------------------------------------

def _verify_signature(body: bytes, signature_header: str | None) -> None:
    """
    Verify X-Hub-Signature-256 from Meta.
    Raises HTTP 403 if signature is missing or invalid.
    """
    app_secret = settings.WHATSAPP_APP_SECRET
    if not app_secret:
        return  # Skip verification if app secret not configured (dev mode)

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
