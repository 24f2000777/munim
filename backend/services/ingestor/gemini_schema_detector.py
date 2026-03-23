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

GEMINI_MODEL = "gemini-2.0-flash-lite"
MIN_CONFIDENCE = 0.3  # Lowered — validation stage catches bad guesses


@dataclass
class GeminiSchemaResult:
    date_column: str | None
    amount_column: str | None
    customer_column: str | None
    product_column: str | None
    quantity_column: str | None
    debit_column: str | None
    credit_column: str | None
    compute_amount_as: str | None   # Expression: "UnitPrice * Quantity", "Credit - Debit", etc.
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


def heal_schema_with_gemini(
    headers: list[str],
    sample_rows: list[dict],
    filename: str,
    error_context: str,
) -> GeminiSchemaResult | None:
    """
    Re-call Gemini with error feedback so it can correct its mapping.
    Called when validation of the first mapping attempt fails.
    """
    if not settings.GOOGLE_API_KEY:
        return None
    try:
        return _call_gemini(headers, sample_rows, filename, error_context=error_context)
    except Exception as exc:
        logger.warning("Gemini schema healing failed: %s", exc)
        return None


def _call_gemini(
    headers: list[str],
    sample_rows: list[dict],
    filename: str,
    error_context: str | None = None,
) -> GeminiSchemaResult | None:
    from services.ai.model_router import router as _router

    sample_text = json.dumps(sample_rows[:8], ensure_ascii=False, indent=2)

    healing_section = ""
    if error_context:
        healing_section = f"""
PREVIOUS ATTEMPT FAILED:
{error_context}
Please correct your mapping to fix this issue. Pay special attention to the actual data values.
"""

    prompt = f"""ROLE: You are a data analyst expert in financial/sales data from any country — Tally exports, e-commerce orders, kirana registers, medical ledgers, inventory sheets.

TASK: Analyze this file sample and identify column mappings for a sales analytics pipeline.
{healing_section}
FILE INFO:
Filename: {filename!r}
All column names: {headers}
First 8 data rows:
{sample_text}

OUTPUT: Return ONLY valid JSON (no markdown, no ```, no explanation):
{{
  "date_col": "<exact column name or null>",
  "amount_col": "<pre-computed revenue/total column if it exists, else null>",
  "compute_amount_as": "<arithmetic expression to compute amount, e.g. 'UnitPrice * Quantity' or 'Credit - Debit' — use exact column names from headers — or null if amount_col is set>",
  "debit_col": "<debit/expense column or null>",
  "credit_col": "<credit/income column or null>",
  "customer_col": "<customer/party/client name column or null>",
  "product_col": "<product/item/narration/description column or null>",
  "quantity_col": "<quantity/qty/units column or null>",
  "business_type": "<kirana grocery | restaurant | medical pharmacy | textile clothing | electronics | hardware | wholesale distributor | service business | manufacturing | general retail | e-commerce>",
  "data_type": "<sales_register | ledger | tally_export | vyapar_export | bank_statement | ecommerce_orders | inventory | unknown>",
  "confidence": <0.0 to 1.0>,
  "notes": "<one specific observation about the data>"
}}

COLUMN IDENTIFICATION RULES:
1. "amount_col" = a SINGLE column that already contains the total revenue per row
   - Set to null if no such column exists
2. "compute_amount_as" = arithmetic expression to derive amount when no single column has it
   - Examples: "UnitPrice * Quantity", "Rate * Qty", "Credit - Debit", "SalePrice * Units"
   - Use EXACT column names from the headers list above
   - Set to null if amount_col is already set
   - If BOTH debit AND credit columns exist: use "Credit - Debit"
   - If price + quantity exist but no total: use "PriceCol * QtyCol"
3. "date_col" = any date format valid: "3-Jan-24", "03/01/2024", "2024-01-03", timestamps all count
4. "product_col" = Narration/Particulars/Description columns often contain product info
5. "customer_col" = Party Name / Ledger Name / Client / Buyer column
6. Look at ACTUAL DATA VALUES to confirm — not just column names alone
7. business_type: infer from product names in sample rows
8. confidence: 0.9+ if all clearly identified; 0.6 if some guessed; 0.3 if uncertain but best guess
9. ALWAYS return your best guess — even at low confidence — downstream validation will verify
10. ONLY use column names that exist EXACTLY in the headers list — no invented names"""

    raw = _router.call_text(prompt, max_tokens=500, temperature=0.1)
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    data = json.loads(raw)
    confidence = float(data.get("confidence", 0))

    if confidence < MIN_CONFIDENCE:
        logger.info("Gemini confidence %.2f below threshold — falling back to rule-based", confidence)
        return None

    # Support both old key format (date_column) and new format (date_col)
    def _get(new_key: str, old_key: str):
        return data.get(new_key) or data.get(old_key)

    date_col        = _get("date_col", "date_column")
    amount_col      = _get("amount_col", "amount_column")
    compute_expr    = data.get("compute_amount_as")
    debit_col       = _get("debit_col", "debit_column")
    credit_col      = _get("credit_col", "credit_column")
    customer_col    = _get("customer_col", "customer_column")
    product_col     = _get("product_col", "product_column")
    quantity_col    = _get("quantity_col", "quantity_column")

    # Validate compute_amount_as expression — all tokens must be known operators or real columns
    if compute_expr:
        compute_expr = _validate_expr(compute_expr, headers)

    logger.info(
        "Gemini schema: business=%r confidence=%.2f date=%r amount=%r expr=%r customer=%r product=%r",
        data.get("business_type"), confidence,
        date_col, amount_col, compute_expr, customer_col, product_col,
    )

    return GeminiSchemaResult(
        date_column=_valid_col(date_col, headers),
        amount_column=_valid_col(amount_col, headers),
        compute_amount_as=compute_expr,
        debit_column=_valid_col(debit_col, headers),
        credit_column=_valid_col(credit_col, headers),
        customer_column=_valid_col(customer_col, headers),
        product_column=_valid_col(product_col, headers),
        quantity_column=_valid_col(quantity_col, headers),
        business_type=data.get("business_type", "business"),
        data_type=data.get("data_type", "sales_register"),
        confidence=confidence,
        notes=data.get("notes", ""),
    )


def gemini_result_to_column_map(result: GeminiSchemaResult) -> dict[str, str]:
    """Convert GeminiSchemaResult to the column_map format used by _normalise_dataframe."""
    mapping = {}
    if result.date_column:      mapping["date"]             = result.date_column
    if result.amount_column:    mapping["amount"]           = result.amount_column
    if result.debit_column:     mapping["debit"]            = result.debit_column
    if result.credit_column:    mapping["credit"]           = result.credit_column
    if result.customer_column:  mapping["customer"]         = result.customer_column
    if result.product_column:   mapping["product"]          = result.product_column
    if result.quantity_column:  mapping["quantity"]         = result.quantity_column
    if result.compute_amount_as: mapping["_compute_expr"]   = result.compute_amount_as
    return mapping


def _valid_col(col: str | None, headers: list[str]) -> str | None:
    """Return col only if it exists in the actual headers (Gemini can hallucinate)."""
    if col and col in headers:
        return col
    return None


def _validate_expr(expr: str, headers: list[str]) -> str | None:
    """
    Validate that an expression like 'UnitPrice * Quantity' only references
    real column names. Returns the expression if valid, None otherwise.
    """
    import re
    # Tokenize: split by operators
    tokens = re.split(r"[\*\+\-\/\s]+", expr.strip())
    tokens = [t.strip() for t in tokens if t.strip()]
    for token in tokens:
        if token not in headers:
            logger.warning("Gemini expr %r references unknown column %r — discarding expr", expr, token)
            return None
    return expr
