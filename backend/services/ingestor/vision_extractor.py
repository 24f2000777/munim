"""
Vision Extractor
================
Uses Gemini Vision to extract transaction table data from photos of
ledgers, handwritten records, or accounting app screenshots.

Input:  image bytes (JPEG or PNG)
Output: pandas DataFrame with columns: date, amount, product, customer

Raises ValueError if:
  - Gemini Vision cannot find a transaction table in the image
  - Fewer than 2 valid rows are extracted
  - The image is unreadable (blurry, dark, etc.)
"""

import base64
import json
import logging
from decimal import Decimal, InvalidOperation

import pandas as pd
from google import genai
from google.genai import types as genai_types

from config import settings

logger = logging.getLogger(__name__)

VISION_MODEL = "gemini-2.0-flash"

_SYSTEM_PROMPT = """You are a data extraction assistant for Indian small business owners.
Your job is to extract transaction data from photos of:
- Handwritten ledgers (khata)
- Vyapar app screenshots
- Busy/Tally app screenshots
- Receipt books or billing registers

Extract ALL transaction rows you can see. Return ONLY a JSON array of objects.
Each object must have these keys:
  "date": date in any format you see (DD/MM/YYYY, YYYY-MM-DD, etc.)
  "amount": numeric value only (no ₹ symbol, no commas) — the sale/revenue amount
  "product": item name or description (use "General" if not visible)
  "customer": customer name (use "Walk-in" if not visible)

Rules:
- Return ONLY the JSON array. No markdown, no explanation, no code blocks.
- If a field is not visible or unclear, use null.
- For amount: if debit/credit columns exist, use the positive/credit amount.
- Skip rows that have no amount.
- Minimum 2 rows required.

Example output:
[
  {"date": "15/03/2024", "amount": 450, "product": "Rice 5kg", "customer": "Ramesh"},
  {"date": "15/03/2024", "amount": 120, "product": "Dal 1kg", "customer": "Walk-in"}
]"""


def extract_table_from_image(image_bytes: bytes, filename: str = "upload.jpg") -> pd.DataFrame:
    """
    Extract a transaction table from an image using Gemini Vision.

    Args:
        image_bytes: Raw bytes of JPEG or PNG image
        filename: Original filename (used for MIME type detection)

    Returns:
        pandas DataFrame with columns: date, amount, product, customer

    Raises:
        ValueError: If extraction fails or returns too few rows
    """
    if not settings.GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY not configured — cannot use Gemini Vision")

    # Detect MIME type from magic bytes
    if image_bytes[:4] == b"\x89PNG":
        mime_type = "image/png"
    elif image_bytes[:3] == b"\xff\xd8\xff":
        mime_type = "image/jpeg"
    else:
        # Try to guess from filename
        lower_name = (filename or "").lower()
        if lower_name.endswith(".png"):
            mime_type = "image/png"
        else:
            mime_type = "image/jpeg"

    # Encode to base64
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    # Call Gemini Vision
    client = genai.Client(api_key=settings.GOOGLE_API_KEY)

    try:
        response = client.models.generate_content(
            model=VISION_MODEL,
            contents=[
                genai_types.Content(
                    parts=[
                        genai_types.Part(text=_SYSTEM_PROMPT),
                        genai_types.Part(
                            inline_data=genai_types.Blob(
                                mime_type=mime_type,
                                data=image_b64,
                            )
                        ),
                        genai_types.Part(text="Extract all transaction rows from this image as a JSON array:"),
                    ]
                )
            ],
            config=genai_types.GenerateContentConfig(
                temperature=0.1,  # Low temperature for factual extraction
                max_output_tokens=2048,
            ),
        )
    except Exception as exc:
        logger.error("Gemini Vision API call failed: %s", exc)
        raise ValueError(f"Could not analyze image: {exc}") from exc

    raw_text = response.text.strip() if response.text else ""

    if not raw_text:
        raise ValueError("Gemini returned empty response — image may be unreadable")

    # Strip markdown code blocks if present
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        raw_text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

    # Parse JSON
    try:
        rows = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        logger.error("Gemini returned invalid JSON: %s...", raw_text[:200])
        raise ValueError("Could not parse extracted data — please try a clearer photo") from exc

    if not isinstance(rows, list) or len(rows) < 2:
        raise ValueError(
            f"Only {len(rows) if isinstance(rows, list) else 0} rows found. "
            "Please use a photo with at least 2 visible transaction rows."
        )

    # Convert to DataFrame
    df = pd.DataFrame(rows)

    # Normalize columns — ensure required ones exist
    if "amount" not in df.columns:
        raise ValueError("No 'amount' column found in extracted data")
    if "date" not in df.columns:
        raise ValueError("No 'date' column found in extracted data")

    # Fill missing optional columns
    if "product" not in df.columns:
        df["product"] = "General"
    if "customer" not in df.columns:
        df["customer"] = "Walk-in"

    df["product"] = df["product"].fillna("General")
    df["customer"] = df["customer"].fillna("Walk-in")

    # Convert amount to Decimal (drop invalid rows)
    def _to_decimal(val):
        if val is None:
            return None
        try:
            # Remove common formatting characters
            cleaned = str(val).replace(",", "").replace("₹", "").replace(" ", "")
            d = Decimal(cleaned)
            return d if d > 0 else None
        except (InvalidOperation, ValueError):
            return None

    df["amount"] = df["amount"].apply(_to_decimal)
    df = df.dropna(subset=["amount"])

    if len(df) < 2:
        raise ValueError(
            "Could not extract valid transaction amounts. "
            "Please ensure the photo shows numeric amounts clearly."
        )

    # Parse dates — let normaliser handle the actual conversion later
    df["date"] = df["date"].astype(str)

    logger.info(
        "Vision extraction complete | filename=%s | rows=%d",
        filename, len(df),
    )
    return df[["date", "amount", "product", "customer"]]
