"""
Schema Detector
================
Detects the file type and routes to the correct parser automatically.
Also validates that the parsed DataFrame has minimum usable structure.

Input:  raw file bytes + filename
Output: ParsedFileResult (unified format regardless of source file type)

Self-healing pipeline (for CSV/Excel):
  Stage 1: Gemini schema detection (primary)
  Stage 2: Validate result — if < 50% rows valid, trigger healing
  Stage 3: Gemini retry with error context
  Stage 4: Rule-based fallback
  Stage 5: Last-resort LLM parser (raw text → JSON → DataFrame)
"""

import json
import logging
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Literal

import pandas as pd

from services.ingestor.tally_parser import parse_tally_xml, TallyParseResult, TallyParseError
from services.ingestor.excel_parser import (
    parse_excel, parse_csv, ExcelParseResult, ExcelParseError,
    peek_raw_sample, peek_raw_sample_csv,
)
from services.ingestor.gemini_schema_detector import (
    detect_schema_with_gemini, heal_schema_with_gemini, gemini_result_to_column_map,
)

logger = logging.getLogger(__name__)

FileType = Literal["tally_xml", "excel", "csv", "image", "unknown"]


@dataclass
class ParsedFileResult:
    """Unified result from any supported file format."""
    df: pd.DataFrame
    file_type: FileType
    company_name: str
    detected_columns: dict[str, str]
    total_rows: int
    date_range: tuple[pd.Timestamp, pd.Timestamp] | None
    warnings: list[str]
    raw_metadata: dict  # Format-specific metadata
    business_type: str = "business"


def detect_and_parse(
    raw_bytes: bytes,
    filename: str,
) -> ParsedFileResult:
    """
    Auto-detect file type from content + extension, then parse.

    Args:
        raw_bytes: Raw file contents.
        filename:  Original filename (used for extension hint + display).

    Returns:
        ParsedFileResult with unified DataFrame.

    Raises:
        ValueError: If file type cannot be determined or parsed.
    """
    file_type = _detect_file_type(raw_bytes, filename)
    logger.info("Detected file type: %s for file: %s", file_type, filename)

    if file_type == "tally_xml":
        return _handle_tally(raw_bytes, filename)
    elif file_type == "excel":
        return _handle_excel(raw_bytes, filename)
    elif file_type == "csv":
        return _handle_csv(raw_bytes, filename)
    elif file_type == "image":
        return _handle_image(raw_bytes, filename)
    else:
        raise ValueError(
            f"Unsupported file type for {filename!r}. "
            f"Accepted formats: Tally XML (.xml), Excel (.xlsx, .xls), CSV (.csv), Image (.jpg, .jpeg, .png)"
        )


def _detect_file_type(raw_bytes: bytes, filename: str) -> FileType:
    """
    Detect file type using magic bytes first, then extension fallback.
    Never trust filename alone — users rename files.
    """
    # Image detection (check before CSV/Excel)
    if raw_bytes[:3] == b"\xff\xd8\xff":
        return "image"  # JPEG
    if raw_bytes[:4] == b"\x89PNG":
        return "image"  # PNG

    # Magic byte detection
    if raw_bytes[:5] in (b"<?xml", b"<ENVE", b"<TALL"):
        return "tally_xml"
    if raw_bytes[:5].startswith(b"<?xml"):
        return "tally_xml"
    if raw_bytes[:4] == b"PK\x03\x04":  # ZIP = .xlsx
        return "excel"
    if raw_bytes[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":  # OLE = .xls
        return "excel"

    # Check if XML by scanning for <ENVELOPE or <TALLYMESSAGE
    if b"<ENVELOPE" in raw_bytes[:2000] or b"<TALLYMESSAGE" in raw_bytes[:2000]:
        return "tally_xml"

    # Extension fallback
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == "xml":
        return "tally_xml"
    if ext in ("xlsx", "xls"):
        return "excel"
    if ext == "csv":
        return "csv"

    # Try CSV heuristic: first 1000 bytes are mostly printable + has commas
    sample = raw_bytes[:1000]
    try:
        text = sample.decode("utf-8", errors="ignore")
        if text.count(",") > 3 or text.count("\t") > 3:
            return "csv"
    except Exception:  # nosec B110 — decode heuristic, failure means unknown type
        pass

    return "unknown"


def _handle_tally(raw_bytes: bytes, filename: str) -> ParsedFileResult:
    try:
        result: TallyParseResult = parse_tally_xml(raw_bytes)
    except TallyParseError as exc:
        raise ValueError(f"Failed to parse Tally XML ({filename}): {exc}") from exc

    df = result.df
    date_range = _get_date_range(df)

    return ParsedFileResult(
        df=df,
        file_type="tally_xml",
        company_name=result.company_name,
        detected_columns={
            "date": "DATE", "customer": "PARTYLEDGERNAME",
            "product": "LEDGERNAME", "amount": "AMOUNT",
        },
        total_rows=len(df),
        date_range=date_range,
        warnings=result.warnings,
        raw_metadata={
            "total_vouchers_found": result.total_vouchers_found,
            "sales_vouchers_extracted": result.sales_vouchers_extracted,
            "skipped_zero_value": result.skipped_zero_value,
            "skipped_non_sales": result.skipped_non_sales,
        },
        business_type="business",
    )


def _handle_excel(raw_bytes: bytes, filename: str) -> ParsedFileResult:
    headers, sample = peek_raw_sample(raw_bytes)
    gemini = None
    business_type = "business"
    column_map_override = None

    if headers and sample:
        gemini = detect_schema_with_gemini(headers, sample, filename)
        if gemini:
            business_type = gemini.business_type
            column_map_override = gemini_result_to_column_map(gemini)

    try:
        result: ExcelParseResult = parse_excel(raw_bytes, column_map_override=column_map_override)

        # Validate result quality and heal if needed
        if column_map_override and headers and sample:
            result, business_type = _maybe_heal_excel(
                raw_bytes, result, headers, sample, filename, business_type
            )

    except ExcelParseError as exc:
        # If Gemini-guided parse fails, retry without override
        if column_map_override:
            logger.warning("Gemini-guided parse failed, retrying rule-based: %s", exc)
            try:
                result = parse_excel(raw_bytes)
                business_type = "business"
            except ExcelParseError as exc2:
                # Last resort: LLM direct parse
                try:
                    return _last_resort_llm_parse(raw_bytes, filename, "excel")
                except Exception as exc3:
                    logger.error("Last-resort LLM parse also failed: %s", exc3)
                    raise ValueError(f"Failed to parse Excel file ({filename}): {exc2}") from exc2
        else:
            try:
                return _last_resort_llm_parse(raw_bytes, filename, "excel")
            except Exception as exc3:
                logger.error("Last-resort LLM parse also failed: %s", exc3)
                raise ValueError(f"Failed to parse Excel file ({filename}): {exc}") from exc

    df = result.df
    date_range = _get_date_range(df)

    return ParsedFileResult(
        df=df,
        file_type="excel",
        company_name="Unknown Company",
        detected_columns=result.detected_columns,
        total_rows=len(df),
        date_range=date_range,
        warnings=result.warnings,
        raw_metadata={
            "sheets_processed": result.sheets_processed,
            "rows_dropped": result.rows_dropped,
            "gemini_confidence": gemini.confidence if gemini else 0.0,
        },
        business_type=business_type,
    )


def _handle_csv(raw_bytes: bytes, filename: str) -> ParsedFileResult:
    headers, sample = peek_raw_sample_csv(raw_bytes)
    gemini = None
    business_type = "business"
    column_map_override = None

    if headers and sample:
        gemini = detect_schema_with_gemini(headers, sample, filename)
        if gemini:
            business_type = gemini.business_type
            column_map_override = gemini_result_to_column_map(gemini)

    try:
        result: ExcelParseResult = parse_csv(raw_bytes, column_map_override=column_map_override)

        # Validate result quality and heal if needed
        if column_map_override and headers and sample:
            result, business_type = _maybe_heal_csv(
                raw_bytes, result, headers, sample, filename, business_type
            )

    except ExcelParseError as exc:
        if column_map_override:
            logger.warning("Gemini-guided CSV parse failed, retrying rule-based: %s", exc)
            try:
                result = parse_csv(raw_bytes)
                business_type = "business"
            except ExcelParseError as exc2:
                # Last resort: LLM direct parse
                try:
                    return _last_resort_llm_parse(raw_bytes, filename, "csv")
                except Exception as exc3:
                    logger.error("Last-resort LLM parse also failed: %s", exc3)
                    raise ValueError(f"Failed to parse CSV file ({filename}): {exc2}") from exc2
        else:
            try:
                return _last_resort_llm_parse(raw_bytes, filename, "csv")
            except Exception as exc3:
                logger.error("Last-resort LLM parse also failed: %s", exc3)
                raise ValueError(f"Failed to parse CSV file ({filename}): {exc}") from exc

    df = result.df
    date_range = _get_date_range(df)

    return ParsedFileResult(
        df=df,
        file_type="csv",
        company_name="Unknown Company",
        detected_columns=result.detected_columns,
        total_rows=len(df),
        date_range=date_range,
        warnings=result.warnings,
        raw_metadata={
            "rows_dropped": result.rows_dropped,
            "gemini_confidence": gemini.confidence if gemini else 0.0,
        },
        business_type=business_type,
    )


def _result_is_good_quality(result: ExcelParseResult) -> tuple[bool, str]:
    """
    Validate a parsed result using the normalized DataFrame (date + amount columns).
    A result is good quality if >= 50% of rows have non-null date AND non-zero amount.
    """
    df = result.df
    if df.empty:
        return False, "result DataFrame is empty"

    total = len(df)
    # Check date quality
    if "date" in df.columns:
        date_valid = df["date"].notna().sum()
    else:
        return False, "no date column in result"

    # Check amount quality
    if "amount" in df.columns:
        from decimal import Decimal
        amount_nonzero = df["amount"].apply(lambda x: x != Decimal(0) if hasattr(x, '__class__') else bool(x)).sum()
    else:
        return False, "no amount column in result"

    date_pct = date_valid / total
    amount_pct = amount_nonzero / total

    if date_pct >= 0.5 and amount_pct >= 0.5:
        return True, ""

    reasons = []
    if date_pct < 0.5:
        reasons.append(f"only {date_valid}/{total} rows have valid dates")
    if amount_pct < 0.5:
        reasons.append(f"only {amount_nonzero}/{total} rows have non-zero amounts")
    return False, "; ".join(reasons)


def _maybe_heal_csv(
    raw_bytes: bytes,
    result: ExcelParseResult,
    headers: list[str],
    sample: list[dict],
    filename: str,
    business_type: str,
) -> tuple[ExcelParseResult, str]:
    """
    Validate the parsed result. If quality is low, ask Gemini to correct its
    mapping and re-parse. Returns (result, business_type).
    """
    is_valid, error_reason = _result_is_good_quality(result)
    if is_valid:
        return result, business_type

    logger.warning("CSV parse quality low (%s) — triggering Gemini healing for %r", error_reason, filename)
    healed = heal_schema_with_gemini(headers, sample, filename, error_reason)
    if not healed:
        return result, business_type  # Use original result

    healed_override = gemini_result_to_column_map(healed)
    try:
        healed_result = parse_csv(raw_bytes, column_map_override=healed_override)
        is_valid2, _ = _result_is_good_quality(healed_result)
        if is_valid2:
            logger.info("Gemini healing succeeded for CSV %r", filename)
            return healed_result, healed.business_type
    except ExcelParseError as exc:
        logger.warning("Healed CSV parse also failed: %s", exc)

    return result, business_type  # Fall back to original


def _maybe_heal_excel(
    raw_bytes: bytes,
    result: ExcelParseResult,
    headers: list[str],
    sample: list[dict],
    filename: str,
    business_type: str,
) -> tuple[ExcelParseResult, str]:
    """Same as _maybe_heal_csv but for Excel files."""
    is_valid, error_reason = _result_is_good_quality(result)
    if is_valid:
        return result, business_type

    logger.warning("Excel parse quality low (%s) — triggering Gemini healing for %r", error_reason, filename)
    healed = heal_schema_with_gemini(headers, sample, filename, error_reason)
    if not healed:
        return result, business_type

    healed_override = gemini_result_to_column_map(healed)
    try:
        healed_result = parse_excel(raw_bytes, column_map_override=healed_override)
        is_valid2, _ = _result_is_good_quality(healed_result)
        if is_valid2:
            logger.info("Gemini healing succeeded for Excel %r", filename)
            return healed_result, healed.business_type
    except ExcelParseError as exc:
        logger.warning("Healed Excel parse also failed: %s", exc)

    return result, business_type


def _last_resort_llm_parse(raw_bytes: bytes, filename: str, file_type: str) -> ParsedFileResult:
    """
    Nuclear fallback: send raw file content to LLM, ask it to directly output
    date/amount/customer/product as a JSON array. Works for any format the
    LLM can understand, regardless of column naming.
    """
    from services.ai.model_router import router as _router

    logger.info("Attempting last-resort LLM parse for %r", filename)

    # Decode file to text
    raw_text = None
    if file_type == "csv":
        for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
            try:
                raw_text = raw_bytes.decode(enc)
                break
            except UnicodeDecodeError:
                continue
    else:
        # For Excel, try to read as CSV-like text
        try:
            import io
            df_raw = pd.read_excel(io.BytesIO(raw_bytes), dtype=str)
            raw_text = df_raw.to_csv(index=False)
        except Exception:
            pass

    if not raw_text:
        raise ValueError("Could not decode file for LLM parsing")

    # Send only first 200 rows to avoid token limits
    lines = raw_text.split("\n")
    truncated = "\n".join(lines[:201])  # header + 200 rows

    prompt = f"""You are a data extraction expert. Extract sales/transaction data from this file.

FILE: {filename!r}
CONTENT (first 200 rows):
{truncated}

OUTPUT: Return ONLY a valid JSON array (no markdown, no explanation). Each object must have:
- "date": ISO date string (YYYY-MM-DD)
- "amount": numeric value representing revenue/sale amount for that row
  - If the file has price + quantity columns: compute amount = price × quantity
  - If the file has debit/credit: compute amount = credit - debit
  - Use the column(s) that best represent revenue earned
- "customer": customer/buyer/party name (use "Walk-in Customer" if not present)
- "product": product/item/description (use "General" if not present)

Example output:
[{{"date": "2024-01-15", "amount": 1500.50, "customer": "Rahul Stores", "product": "T-Shirt"}}, ...]

Rules:
- Skip rows where date or amount cannot be determined
- Do NOT include header rows, subtotals, or blank rows
- Return at least the first 100 valid data rows
- Return ONLY the JSON array, nothing else"""

    raw_response = _router.call_text(prompt, max_tokens=8000, temperature=0.1)

    # Clean up markdown fences if present
    if raw_response.strip().startswith("```"):
        lines_r = raw_response.strip().split("\n")
        raw_response = "\n".join(lines_r[1:-1] if lines_r[-1].strip() == "```" else lines_r[1:])

    rows = json.loads(raw_response)
    if not isinstance(rows, list) or len(rows) == 0:
        raise ValueError("LLM returned empty or invalid JSON")

    # Build DataFrame
    clean_rows = []
    for r in rows:
        try:
            date = pd.to_datetime(r.get("date", ""), errors="coerce")
            if pd.isna(date):
                continue
            amount_raw = r.get("amount", 0)
            try:
                amount = Decimal(str(amount_raw))
            except InvalidOperation:
                amount = Decimal(0)
            if amount == Decimal(0):
                continue
            clean_rows.append({
                "date": date,
                "amount": amount,
                "customer": str(r.get("customer", "Walk-in Customer")).strip() or "Walk-in Customer",
                "product": str(r.get("product", "General")).strip() or "General",
                "source_row": 0,
                "sheet_name": "LLM",
            })
        except Exception:
            continue

    if not clean_rows:
        raise ValueError("LLM parsed 0 valid rows from the file")

    df = pd.DataFrame(clean_rows)
    df["date"] = pd.to_datetime(df["date"])
    df["customer"] = df["customer"].astype("string")
    df["product"] = df["product"].astype("string")
    df["sheet_name"] = df["sheet_name"].astype("string")
    df = df.sort_values("date").reset_index(drop=True)

    date_range = _get_date_range(df)
    logger.info("Last-resort LLM parse succeeded: %d rows extracted from %r", len(df), filename)

    return ParsedFileResult(
        df=df,
        file_type=file_type,
        company_name="Unknown Company",
        detected_columns={"date": "date", "amount": "amount", "customer": "customer", "product": "product"},
        total_rows=len(df),
        date_range=date_range,
        warnings=["Data extracted via LLM direct parsing — verify figures if amounts look incorrect"],
        raw_metadata={"source": "llm_last_resort", "rows_extracted": len(df)},
        business_type="business",
    )


def _handle_image(raw_bytes: bytes, filename: str) -> ParsedFileResult:
    from services.ingestor.vision_extractor import extract_table_from_image
    logger.info("Processing image file via Gemini Vision: %s", filename)
    df = extract_table_from_image(raw_bytes, filename)
    date_range = _get_date_range(df)

    return ParsedFileResult(
        df=df,
        file_type="image",
        company_name="",
        detected_columns={
            "date": "date", "amount": "amount",
            "product": "product", "customer": "customer",
        },
        total_rows=len(df),
        date_range=date_range,
        warnings=["Data extracted from image via Gemini Vision — please verify figures"],
        raw_metadata={"source": "gemini_vision", "filename": filename},
        business_type="kirana",
    )


def _get_date_range(df: pd.DataFrame) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    if df.empty or "date" not in df.columns:
        return None
    valid_dates = df["date"].dropna()
    if valid_dates.empty:
        return None
    return valid_dates.min(), valid_dates.max()
