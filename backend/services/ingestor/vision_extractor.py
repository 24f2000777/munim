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

import io
import json
import logging
from decimal import Decimal, InvalidOperation

import pandas as pd

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """ROLE: You are a precision OCR engine trained specifically on Indian business documents.

TASK: Extract every line item from this image and return as a JSON array.

DOCUMENT TYPES you may see:
• Handwritten khata/ledger with columns for date, item, quantity, rate, amount
• Printed kirana/medical/wholesale bills with S.No, Item Description, Qty, Rate, Amount columns
• Vyapar/Busy/Tally app screenshots showing sales entries
• Any tabular sales or purchase record

OUTPUT: Return ONLY a valid JSON array — no markdown, no ```, no explanation text.

SCHEMA (each object must have ALL 4 keys):
[
  {
    "date": "DD/MM/YYYY",
    "amount": 56,
    "product": "Tata Salt 1kg",
    "customer": "Ravi Sharma"
  }
]

FIELD RULES:
• "date": Transaction date. ONE date on the bill? Use it for ALL rows. Format: DD/MM/YYYY.
• "amount": THE AMOUNT COLUMN ONLY — this is QTY × RATE = AMOUNT (the final/rightmost money column).
  NEVER use the "Rate", "MRP", or "Unit Price" column.
  Example: QTY=2, Rate=₹28, Amount=₹56 → use 56 (NOT 28).
  If QTY × Rate ≠ Amount column → ALWAYS trust the Amount column value.
• "product": Exact item name. Remove S.No prefix (e.g. strip "1.", "2." from start).
• "customer": Customer name if visible. "Walk-in" if not shown.

EXTRACTION RULES:
✓ Extract EVERY product row — no skipping, even if handwriting is unclear (best guess > skipping)
✓ Single bill date → same date for every extracted row
✓ "amount" must be pure numeric (no ₹, no commas, no "Rs." — just the number)
✓ Skip ONLY: header rows, subtotals, grand totals, tax/GST lines, blank rows
✗ DO NOT skip product rows just because they are hard to read

WORKED EXAMPLES:
Bill row: "1 | Aashirvaad Atta 5kg | QTY: 1 | Rate: 320 | Amount: 320"
→ CORRECT: {"date": "12/10/2023", "amount": 320, "product": "Aashirvaad Atta 5kg", "customer": "Walk-in"}

Bill row: "2 | Tata Salt 1kg | QTY: 2 | Rate: 28 | Amount: 56"
→ CORRECT: {"date": "12/10/2023", "amount": 56, "product": "Tata Salt 1kg", "customer": "Walk-in"}
→ WRONG:   {"amount": 28}  ← This used Rate column, not Amount column"""


def _compress_image(image_bytes: bytes, mime_type: str, max_px: int = 1600, quality: int = 85) -> tuple[bytes, str]:
    """Resize and compress image to stay under API payload limits (~1MB)."""
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes))
        # Convert RGBA/palette to RGB for JPEG compatibility
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        # Downscale if either dimension exceeds max_px
        if max(img.width, img.height) > max_px:
            img.thumbnail((max_px, max_px), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        compressed = buf.getvalue()
        logger.info(
            "Image compressed: %d KB → %d KB",
            len(image_bytes) // 1024, len(compressed) // 1024,
        )
        return compressed, "image/jpeg"
    except Exception as exc:
        logger.warning("Image compression failed (%s) — using original", exc)
        return image_bytes, mime_type


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
    # Detect MIME type from magic bytes
    if image_bytes[:4] == b"\x89PNG":
        mime_type = "image/png"
    elif image_bytes[:3] == b"\xff\xd8\xff":
        mime_type = "image/jpeg"
    else:
        lower_name = (filename or "").lower()
        mime_type = "image/png" if lower_name.endswith(".png") else "image/jpeg"

    # Compress image to stay under API payload limits (~1MB after compression)
    # WhatsApp photos can be 5-10MB which breaks Groq/OpenRouter limits
    image_bytes, mime_type = _compress_image(image_bytes, mime_type)

    # Call vision model router (tries Gemini → Groq vision → OpenRouter vision)
    from services.ai.model_router import router as _router

    vision_prompt = f"{_SYSTEM_PROMPT}\n\nExtract all transaction rows from this image as a JSON array:"
    try:
        raw_text = _router.call_vision(image_bytes, mime_type, vision_prompt, max_tokens=2048)
    except Exception as exc:
        logger.error("Vision model router failed: %s", exc)
        raise ValueError(f"Could not analyze image: {exc}") from exc

    raw_text = raw_text.strip()
    if not raw_text:
        raise ValueError("Vision model returned empty response — image may be unreadable")

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
