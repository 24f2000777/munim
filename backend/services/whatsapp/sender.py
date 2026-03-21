"""
WhatsApp Sender Utility
=======================
Synchronous httpx.Client wrapper for sending WhatsApp messages.
Safe to use in Celery workers, background threads, and async contexts.

Supports:
  - Twilio sandbox (primary — no business verification needed)
  - Meta WhatsApp Business API (production fallback)
"""

import logging
import httpx
from config import settings

logger = logging.getLogger(__name__)


def send_whatsapp_sync(phone_number: str, text: str) -> str:
    """
    Send a WhatsApp message synchronously.
    Uses Twilio if TWILIO_ACCOUNT_SID is set, otherwise Meta Business API.

    Args:
        phone_number: E.164 format (+919876543210)
        text: Message body (max 1600 chars for Twilio, 4096 for Meta)

    Returns:
        Message ID string (Twilio SID or Meta message ID)

    Raises:
        RuntimeError: If neither Twilio nor Meta is configured
        httpx.HTTPStatusError: If API call fails
    """
    # --- Twilio (preferred — sandbox-friendly) ---
    if settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN:
        logger.info("Sending WhatsApp via Twilio")
        to_wa = f"whatsapp:{phone_number}" if not phone_number.startswith("whatsapp:") else phone_number
        from_wa = settings.TWILIO_WHATSAPP_FROM

        url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.TWILIO_ACCOUNT_SID}/Messages.json"
        with httpx.Client(timeout=15.0) as client:
            response = client.post(
                url,
                data={"From": from_wa, "To": to_wa, "Body": text[:1600]},
                auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
            )

        if response.status_code not in (200, 201):
            logger.error("Twilio error: %s — %s", response.status_code, response.text[:200])
            response.raise_for_status()

        sid = response.json().get("sid", "twilio_ok")
        logger.info("WhatsApp sent via Twilio: %s", sid[:8] + "...")
        return sid

    # --- Meta WhatsApp Business API ---
    if settings.WHATSAPP_PHONE_NUMBER_ID and settings.WHATSAPP_ACCESS_TOKEN:
        logger.info("Sending WhatsApp via Meta API")
        url = f"https://graph.facebook.com/v21.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": phone_number,
            "type": "text",
            "text": {"body": text[:4096]},
        }
        with httpx.Client(timeout=10.0) as client:
            response = client.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
                    "Content-Type": "application/json",
                },
            )
        if response.status_code != 200:
            logger.error("Meta WhatsApp error: %s — %s", response.status_code, response.text[:200])
            response.raise_for_status()

        msg_id = response.json().get("messages", [{}])[0].get("id", "unknown")
        logger.info("WhatsApp sent via Meta: %s", msg_id[:8] + "..." if len(msg_id) > 8 else msg_id)
        return msg_id

    # --- Not configured ---
    logger.warning("WhatsApp not configured — set TWILIO_ACCOUNT_SID or WHATSAPP_ACCESS_TOKEN in .env")
    raise RuntimeError("WhatsApp not configured. Set TWILIO_ACCOUNT_SID or WHATSAPP_ACCESS_TOKEN.")
