"""
Beta Waitlist Router
=====================
Handles the phone-based beta signup flow.
Any phone number that joins here gets whitelisted to use the WhatsApp bot.
Auto-approved + instant WhatsApp welcome message on signup.
"""

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

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
    phone = payload.phone.strip()
    if not phone.startswith("+"):
        phone = f"+{phone}"

    if not re.match(r"^\+\d{10,15}$", phone):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid phone number. Use format: +919876543210",
        )

    name = (payload.name or "").strip() or "Business Owner"

    # Check if already joined
    existing = await db.execute(
        text("SELECT id, welcome_sent FROM beta_waitlist WHERE phone = :phone"),
        {"phone": phone},
    )
    row = existing.fetchone()

    if row:
        # Already on waitlist
        if not row.welcome_sent:
            # Try sending welcome again if it failed before
            _send_welcome(phone, name)
            await db.execute(
                text("UPDATE beta_waitlist SET welcome_sent = TRUE WHERE phone = :phone"),
                {"phone": phone},
            )
            await db.commit()
        return BetaJoinResponse(
            status="ok",
            message="You're already on the beta! Check WhatsApp.",
            already_joined=True,
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

    # Send WhatsApp welcome message
    welcome_sent = _send_welcome(phone, name)

    # Mark welcome as sent
    if welcome_sent:
        await db.execute(
            text("UPDATE beta_waitlist SET welcome_sent = TRUE WHERE phone = :phone"),
            {"phone": phone},
        )
        await db.commit()

    logger.info("Beta signup: phone=%s name=%s welcome_sent=%s", phone[:6] + "****", name, welcome_sent)

    return BetaJoinResponse(
        status="ok",
        message="Welcome to Munim beta! Check WhatsApp for your first message. 🚀",
    )


def _send_welcome(phone: str, name: str) -> bool:
    """Send welcome WhatsApp message. Returns True if sent successfully."""
    try:
        from services.whatsapp.sender import send_whatsapp_sync
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
        send_whatsapp_sync(phone, msg)
        return True
    except Exception as exc:
        logger.warning("Could not send WhatsApp welcome to beta user: %s", exc)
        return False
