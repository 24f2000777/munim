"""
WhatsApp Sender Utility
=======================
Synchronous httpx.Client wrapper for sending WhatsApp messages.
Safe to use in Celery workers, background threads, and async contexts.

Priority:
  1. Meta WhatsApp Business API (production — no sandbox restrictions)
  2. Twilio sandbox (fallback — for local dev)
"""

import logging
import httpx
from config import settings

logger = logging.getLogger(__name__)


def send_whatsapp_template(phone_number: str, template_name: str = "hello_world", lang: str = "en_US") -> str:
    """
    Send a pre-approved WhatsApp template message.
    Use this for business-initiated conversations on real numbers.
    Template messages bypass the 24-hour window restriction.
    """
    if not (settings.WHATSAPP_PHONE_NUMBER_ID and settings.WHATSAPP_ACCESS_TOKEN):
        raise RuntimeError("Meta WhatsApp not configured.")

    clean_number = phone_number.lstrip("+")
    url = f"https://graph.facebook.com/v21.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": clean_number,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": lang},
        },
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
        logger.error(
            "Meta template send FAILED: status=%s phone=%s error=%s",
            response.status_code, clean_number[:6] + "****", response.text[:400]
        )
        response.raise_for_status()

    msg_id = response.json().get("messages", [{}])[0].get("id", "unknown")
    logger.info("WhatsApp template '%s' sent to %s****", template_name, clean_number[:6])
    return msg_id


def send_whatsapp_sync(phone_number: str, text: str) -> str:
    """
    Send a WhatsApp message synchronously.
    Prefers Meta Business API over Twilio.

    Args:
        phone_number: E.164 format (+919876543210)
        text: Message body (max 4096 chars for Meta, 1600 for Twilio)

    Returns:
        Message ID string

    Raises:
        RuntimeError: If neither Meta nor Twilio is configured
        httpx.HTTPStatusError: If API call fails
    """
    # --- Meta WhatsApp Business API (preferred — production) ---
    if settings.WHATSAPP_PHONE_NUMBER_ID and settings.WHATSAPP_ACCESS_TOKEN:
        # Meta API requires phone number WITHOUT '+' prefix
        clean_number = phone_number.lstrip("+")
        logger.info("Sending WhatsApp via Meta API to %s...", clean_number[:6])
        url = f"https://graph.facebook.com/v21.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": clean_number,
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
            logger.error(
                "Meta WhatsApp SEND FAILED: status=%s phone=%s error=%s",
                response.status_code, clean_number[:6] + "****", response.text[:400]
            )
            response.raise_for_status()

        msg_id = response.json().get("messages", [{}])[0].get("id", "unknown")
        logger.info("WhatsApp sent via Meta: %s", msg_id[:8] + "..." if len(msg_id) > 8 else msg_id)
        return msg_id

    # --- Twilio (fallback — sandbox) ---
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

    # --- Not configured ---
    logger.warning("WhatsApp not configured — set WHATSAPP_ACCESS_TOKEN or TWILIO_ACCOUNT_SID in .env")
    raise RuntimeError("WhatsApp not configured.")
