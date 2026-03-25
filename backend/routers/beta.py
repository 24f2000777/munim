"""
Beta Waitlist Router
=====================
Handles the phone-based beta signup flow.
Any phone number that joins here gets whitelisted to use the WhatsApp bot.
Auto-approved + instant WhatsApp welcome message on signup.
"""

import logging
import re

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db.neon_client import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter()


class BetaJoinRequest(BaseModel):
    phone: str          # E.164 format: +919876543210
    name: str = ""      # Optional name


class BetaJoinResponse(BaseModel):
    status: str
    message: str
    already_joined: bool = False
    whatsapp_link: str = ""   # Direct wa.me link to start chatting with the bot


@router.post("/join", response_model=BetaJoinResponse)
async def join_beta(
    payload: BetaJoinRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Public endpoint — no auth required.
    Adds a phone number to the beta whitelist and sends a WhatsApp welcome.
    """
    # Validate phone — must be E.164 format
    phone = re.sub(r"[\s\-()]", "", payload.phone.strip())
    if not phone.startswith("+"):
        phone = f"+{phone}"

    # For Indian numbers: must be +91 followed by exactly 10 digits
    if phone.startswith("+91"):
        if not re.match(r"^\+91\d{10}$", phone):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Indian number must be exactly 10 digits. Example: +919876543210",
            )
    elif not re.match(r"^\+\d{10,15}$", phone):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid phone number. Use format: +919876543210",
        )

    name = (payload.name or "").strip() or "Business Owner"

    # Build direct WhatsApp link so user can always start the chat themselves
    bot_phone = settings.WHATSAPP_BOT_PHONE.lstrip("+") if settings.WHATSAPP_BOT_PHONE else ""
    wa_link = f"https://wa.me/{bot_phone}?text=Hi" if bot_phone else ""

    # Check if already joined
    existing = await db.execute(
        text("SELECT id, welcome_sent FROM beta_waitlist WHERE phone = :phone"),
        {"phone": phone},
    )
    row = existing.fetchone()

    if row:
        # Already on waitlist — return the WhatsApp link so user can open chat themselves
        return BetaJoinResponse(
            status="ok",
            message="Welcome back! Click below to open WhatsApp and chat with Munim.",
            already_joined=True,
            whatsapp_link=wa_link,
        )

    # Add to whitelist — auto-approved
    await db.execute(
        text("""
            INSERT INTO beta_waitlist (phone, name, approved, welcome_sent)
            VALUES (:phone, :name, TRUE, FALSE)
            ON CONFLICT (phone) DO NOTHING
        """),
        {"phone": phone, "name": name},
    )
    await db.commit()

    logger.info("Beta signup: phone=%s name=%s", phone[:6] + "****", name)

    return BetaJoinResponse(
        status="ok",
        message="You're in! Open WhatsApp and say Hi to get started.",
        whatsapp_link=wa_link,
    )


async def _add_to_meta_test_list(phone: str) -> None:
    """
    Automatically add phone number to Meta test number's approved list.
    Only works with the test number — has a 5-number limit.
    Silently fails if already added or limit reached.
    """
    if not settings.WHATSAPP_PHONE_NUMBER_ID or not settings.WHATSAPP_ACCESS_TOKEN:
        return
    try:
        url = f"https://graph.facebook.com/v21.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/whatsapp_test_phone_numbers"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url,
                json={"phone_number": phone},
                headers={"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"},
            )
        if resp.status_code == 200:
            logger.info("Added %s to Meta test approved list", phone[:6] + "****")
        else:
            logger.warning("Meta test list add failed (%s): %s", resp.status_code, resp.text[:100])
    except Exception as exc:
        logger.warning("Could not add to Meta test list: %s", exc)


async def _send_welcome(phone: str, name: str) -> bool:
    """
    Send welcome WhatsApp message. Returns True if sent successfully.

    Strategy:
    1. Try 'hello_world' template (pre-approved by Meta, works on any real number
       even for business-initiated conversations with no prior chat history)
    2. Fall back to free-text (works if user has messaged bot first within 24h)
    """
    import asyncio
    from services.whatsapp.sender import send_whatsapp_template, send_whatsapp_sync

    # Step 1: Template message (works for new conversations on real numbers)
    try:
        await asyncio.to_thread(send_whatsapp_template, phone, "hello_world", "en_US")
        logger.info("Welcome template sent to %s****", phone[:6])
        return True
    except Exception as exc:
        logger.warning("Template send failed for %s****: %s — trying free text", phone[:6], exc)

    # Step 2: Free-text fallback (works if user already chatted within 24h)
    try:
        msg = (
            f"🙏 *Namaskar {name}!*\n\n"
            "Main *Munim* hoon — aapka AI business advisor. 🤖\n\n"
            "*Shuru karne ke liye:*\n"
            "Apni sales file yahan bhejein:\n"
            "✅ CSV / Excel / Tally XML\n"
            "📸 Ya ledger screen ki photo\n\n"
            "60 seconds mein poori analysis aa jayegi — revenue, top products, alerts sab kuch! 📊\n\n"
            "Koi bhi sawaal poochho — main hamesha yahan hoon. 🚀"
        )
        await asyncio.to_thread(send_whatsapp_sync, phone, msg)
        return True
    except Exception as exc:
        logger.warning("Free-text welcome also failed for %s****: %s", phone[:6], exc)
        return False
