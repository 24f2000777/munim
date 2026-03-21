"""
Schema Detector
================
Detects the file type and routes to the correct parser automatically.
Also validates that the parsed DataFrame has minimum usable structure.

Input:  raw file bytes + filename
Output: ParsedFileResult (unified format regardless of source file type)
"""

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from io import BytesIO
from typing import Literal

import pandas as pd

from services.ingestor.tally_parser import parse_tally_xml, TallyParseResult, TallyParseError
from services.ingestor.excel_parser import (
    parse_excel, parse_csv, ExcelParseResult, ExcelParseError,
    peek_raw_sample, peek_raw_sample_csv,
)
from services.ingestor.gemini_schema_detector import (
    detect_schema_with_gemini, gemini_result_to_column_map,
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
    # Try Gemini schema detection first
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
    except ExcelParseError as exc:
        # If Gemini-guided parse fails, retry without override
        if column_map_override:
            logger.warning("Gemini-guided parse failed, retrying rule-based: %s", exc)
            try:
                result = parse_excel(raw_bytes)
                business_type = "business"
            except ExcelParseError as exc2:
                raise ValueError(f"Failed to parse Excel file ({filename}): {exc2}") from exc2
        else:
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
    except ExcelParseError as exc:
        if column_map_override:
            logger.warning("Gemini-guided CSV parse failed, retrying rule-based: %s", exc)
            try:
                result = parse_csv(raw_bytes)
                business_type = "business"
            except ExcelParseError as exc2:
                raise ValueError(f"Failed to parse CSV file ({filename}): {exc2}") from exc2
        else:
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
