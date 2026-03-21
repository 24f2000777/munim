"""
Gemini-Powered Schema Detector
================================
Calls Google Gemini to detect column mappings and business type from any
financial file — handles any language, any naming convention.
"""

import json
import logging
from dataclasses import dataclass, field

from google import genai
from google.genai import types
import pandas as pd

from config import settings

logger = logging.getLogger(__name__)

GEMINI_MODEL = "gemini-flash-latest"
MIN_CONFIDENCE = 0.65


@dataclass
class GeminiSchemaResult:
    date_column: str | None
    amount_column: str | None
    customer_column: str | None
    product_column: str | None
    quantity_column: str | None
    debit_column: str | None
    credit_column: str | None
    business_type: str
    data_type: str
    confidence: float
    notes: str = ""


def detect_schema_with_gemini(
    headers: list[str],
    sample_rows: list[dict],
    filename: str = "",
) -> GeminiSchemaResult | None:
    """
    Call Gemini with file headers + sample rows to detect column mappings.
    Returns None if API key missing, call fails, or confidence too low.
    """
    if not settings.GOOGLE_API_KEY:
        return None
    try:
        return _call_gemini(headers, sample_rows, filename)
    except Exception as exc:
        logger.warning("Gemini schema detection failed: %s", exc)
        return None


def _call_gemini(headers, sample_rows, filename) -> GeminiSchemaResult | None:
    client = genai.Client(api_key=settings.GOOGLE_API_KEY)

    sample_text = json.dumps(sample_rows[:8], ensure_ascii=False, indent=2)

    prompt = f"""You are analyzing a business financial data file exported from accounting software.
Filename: {filename!r}
Column headers: {headers}
Sample rows (first few):
{sample_text}

Identify what each column represents. Return ONLY valid JSON, no markdown, no explanation:
{{
  "date_column": "<exact column name from headers, or null>",
  "amount_column": "<single net/total amount column, or null if split into debit/credit>",
  "debit_column": "<debit/withdrawal/expense column, or null>",
  "credit_column": "<credit/deposit/income column, or null>",
  "customer_column": "<customer/party/client/vendor column, or null>",
  "product_column": "<product/item/service/narration/description column, or null>",
  "quantity_column": "<quantity/units/qty column, or null>",
  "business_type": "<concise type e.g. 'kirana grocery', 'medical pharmacy', 'textile wholesale', 'restaurant', 'freelance IT services', 'construction materials', 'clothing retail'>",
  "data_type": "<'sales_register' | 'purchase_register' | 'ledger' | 'bank_statement' | 'inventory' | 'mixed'>",
  "confidence": <0.0 to 1.0>,
  "notes": "<one brief observation>"
}}

Rules:
- Only return exact column names from the provided headers list, or null
- If amount is in separate debit/credit columns, set amount_column to null
- confidence should be 0.85+ when columns are clearly labeled, 0.5-0.7 for ambiguous data
- business_type must describe the actual business sector, not the file format"""

    response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    raw = response.text.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    data = json.loads(raw)
    confidence = float(data.get("confidence", 0))

    if confidence < MIN_CONFIDENCE:
        logger.info("Gemini confidence %.2f below threshold — falling back to rule-based", confidence)
        return None

    logger.info(
        "Gemini schema: business=%r confidence=%.2f date=%r amount=%r customer=%r product=%r",
        data.get("business_type"), confidence,
        data.get("date_column"), data.get("amount_column"),
        data.get("customer_column"), data.get("product_column"),
    )

    return GeminiSchemaResult(
        date_column=_valid_col(data.get("date_column"), headers),
        amount_column=_valid_col(data.get("amount_column"), headers),
        debit_column=_valid_col(data.get("debit_column"), headers),
        credit_column=_valid_col(data.get("credit_column"), headers),
        customer_column=_valid_col(data.get("customer_column"), headers),
        product_column=_valid_col(data.get("product_column"), headers),
        quantity_column=_valid_col(data.get("quantity_column"), headers),
        business_type=data.get("business_type", "business"),
        data_type=data.get("data_type", "sales_register"),
        confidence=confidence,
        notes=data.get("notes", ""),
    )


def gemini_result_to_column_map(result: GeminiSchemaResult) -> dict[str, str]:
    """Convert GeminiSchemaResult to the column_map format used by _normalise_dataframe."""
    mapping = {}
    if result.date_column:     mapping["date"]     = result.date_column
    if result.amount_column:   mapping["amount"]   = result.amount_column
    if result.debit_column:    mapping["debit"]    = result.debit_column
    if result.credit_column:   mapping["credit"]   = result.credit_column
    if result.customer_column: mapping["customer"] = result.customer_column
    if result.product_column:  mapping["product"]  = result.product_column
    if result.quantity_column: mapping["quantity"] = result.quantity_column
    return mapping


def _valid_col(col: str | None, headers: list[str]) -> str | None:
    """Return col only if it exists in the actual headers (Gemini can hallucinate)."""
    if col and col in headers:
        return col
    return None
