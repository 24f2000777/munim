"""
Tally XML Parser
=================
Parses TallyPrime and Tally ERP 9 XML exports into clean, analysis-ready
pandas DataFrames.

Tally-specific conventions handled here:
  - Amounts: NEGATIVE value = sale/income (Tally debit/credit convention).
             We flip the sign so positive = sale in our system.
  - Dates:   Always in YYYYMMDD format inside Tally XML. No exceptions.
  - VCHTYPE: Determines transaction type. We extract "Sales" variants only
             for revenue analysis unless the caller requests otherwise.
  - PARTYLEDGERNAME: Customer name. Null/empty → "Walk-in Customer".
  - ALLLEDGERENTRIES.LIST: Line items (product + amount) per voucher.
  - Zero-value entries: Filtered out (journal adjustments, not real sales).
  - Unicode: Full Devanagari (Hindi) product/customer names via UTF-8.

Supported formats:
  - TallyPrime (Tally 3.x, 4.x)
  - Tally ERP 9 (Tally 2.x)
  - Custom Tally exports with non-standard VCHTYPE values

Returns a clean DataFrame with columns:
  date, customer, product, amount (Decimal), voucher_id, vch_type, company
"""

import logging
import re
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path
from typing import Optional

import pandas as pd
from lxml import etree

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# VCHTYPE values that count as "Sales" in different Tally configurations.
# Lowercase comparison is used to handle case inconsistencies.
SALES_VOUCHER_TYPES: frozenset[str] = frozenset({
    "sales",
    "credit sales",
    "cash sales",
    "retail sales",
    "wholesale sales",
    "export sales",
    "local sales",
    "interstate sales",
    "intrastate sales",
    "tax invoice",
    "sale",
    "sale invoice",
})

# Tally date format is always YYYYMMDD — no exceptions per official docs.
TALLY_DATE_FORMAT = "%Y%m%d"

# Voucher field xpaths — handles both TallyPrime and ERP9 structures.
# TallyPrime wraps vouchers in TALLYMESSAGE; ERP9 may use different nesting.
VOUCHER_XPATHS = [
    ".//TALLYMESSAGE/VOUCHER",   # TallyPrime
    ".//VOUCHER",                 # ERP9 fallback
]

WALK_IN_CUSTOMER = "Walk-in Customer"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class TallyParseError(Exception):
    """Raised when the XML cannot be parsed as a valid Tally export."""


class TallyParseResult:
    """Container for parser output + metadata."""

    def __init__(
        self,
        df: pd.DataFrame,
        company_name: str,
        total_vouchers_found: int,
        sales_vouchers_extracted: int,
        skipped_zero_value: int,
        skipped_non_sales: int,
        warnings: list[str],
    ):
        self.df = df
        self.company_name = company_name
        self.total_vouchers_found = total_vouchers_found
        self.sales_vouchers_extracted = sales_vouchers_extracted
        self.skipped_zero_value = skipped_zero_value
        self.skipped_non_sales = skipped_non_sales
        self.warnings = warnings

    def __repr__(self) -> str:
        return (
            f"TallyParseResult("
            f"company='{self.company_name}', "
            f"rows={len(self.df)}, "
            f"vouchers_found={self.total_vouchers_found}, "
            f"sales_extracted={self.sales_vouchers_extracted}"
            f")"
        )


def parse_tally_xml(
    source: str | Path | bytes | BytesIO,
    *,
    include_vch_types: Optional[frozenset[str]] = None,
    encoding: str = "utf-8",
) -> TallyParseResult:
    """
    Parse a Tally XML export and return a TallyParseResult.

    Args:
        source:            File path (str/Path), raw bytes, or BytesIO buffer.
        include_vch_types: Override the default SALES_VOUCHER_TYPES set.
                           Pass None to use the default.
        encoding:          XML encoding. Tally always uses UTF-8 by default.

    Returns:
        TallyParseResult with a clean DataFrame and metadata.

    Raises:
        TallyParseError: If the file is not a valid Tally XML export.
        FileNotFoundError: If a file path is given and does not exist.
    """
    vch_types = include_vch_types if include_vch_types is not None else SALES_VOUCHER_TYPES

    raw_bytes = _load_source(source)
    root = _parse_xml(raw_bytes, encoding)
    company_name = _extract_company_name(root)

    vouchers = _find_vouchers(root)
    total_found = len(vouchers)

    rows: list[dict] = []
    warnings: list[str] = []
    skipped_zero = 0
    skipped_non_sales = 0

    for voucher in vouchers:
        vch_type = _get_text(voucher, "VCHTYPE") or ""
        vch_type_lower = vch_type.strip().lower()

        if vch_type_lower not in vch_types:
            skipped_non_sales += 1
            continue

        try:
            extracted = _extract_voucher(voucher, vch_type, company_name)
        except Exception as exc:
            voucher_id = _get_text(voucher, "VOUCHERNUMBER") or "unknown"
            warnings.append(f"Skipped voucher {voucher_id!r}: {exc}")
            logger.debug("Voucher extraction failed: %s", exc, exc_info=True)
            continue

        if not extracted:
            # Voucher had no extractable line items
            continue

        for entry in extracted:
            if entry["amount"] == Decimal(0):
                skipped_zero += 1
                continue
            rows.append(entry)

    if not rows and total_found > 0:
        warnings.append(
            f"Found {total_found} vouchers but extracted 0 sales rows. "
            f"Check VCHTYPE values in the file — found types may not be in "
            f"the recognised sales set: {vch_types!r}"
        )

    df = _build_dataframe(rows)

    sales_extracted = len(df["voucher_id"].unique()) if not df.empty else 0

    logger.info(
        "Parsed Tally XML | company=%r | vouchers_found=%d | "
        "sales_extracted=%d | rows=%d | warnings=%d",
        company_name, total_found, sales_extracted, len(df), len(warnings),
    )

    return TallyParseResult(
        df=df,
        company_name=company_name,
        total_vouchers_found=total_found,
        sales_vouchers_extracted=sales_extracted,
        skipped_zero_value=skipped_zero,
        skipped_non_sales=skipped_non_sales,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_source(source: str | Path | bytes | BytesIO) -> bytes:
    """Normalise input to raw bytes."""
    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"Tally XML file not found: {path}")
        return path.read_bytes()
    if isinstance(source, BytesIO):
        source.seek(0)
        return source.read()
    if isinstance(source, bytes):
        return source
    raise TypeError(f"Unsupported source type: {type(source)}")


def _parse_xml(raw_bytes: bytes, encoding: str) -> etree._Element:
    """
    Parse raw bytes into an lxml element tree.

    Handles:
    - BOM (Byte Order Mark) stripping
    - Encoding declaration mismatches
    - Recovering parser for slightly malformed Tally exports
    """
    # Strip BOM if present (some Tally versions add UTF-8 BOM)
    if raw_bytes.startswith(b"\xef\xbb\xbf"):
        raw_bytes = raw_bytes[3:]

    # Remove any XML declaration that might conflict with lxml's parser,
    # then re-add a clean one. Tally sometimes has encoding mismatches.
    clean_bytes = re.sub(
        rb"<\?xml[^?]*\?>",
        b'<?xml version="1.0" encoding="utf-8"?>',
        raw_bytes,
        count=1,
    )

    parser = etree.XMLParser(
        encoding="utf-8",
        recover=True,           # Tolerate minor XML errors (Tally quirk)
        resolve_entities=False,
        no_network=True,        # Security: prevent XXE attacks
    )

    try:
        root = etree.fromstring(clean_bytes, parser=parser)
    except etree.XMLSyntaxError as exc:
        raise TallyParseError(f"Invalid XML: {exc}") from exc

    if root is None:
        raise TallyParseError("XML parsed to empty document — file may be corrupt or empty.")

    return root


def _extract_company_name(root: etree._Element) -> str:
    """
    Extract the company name from the XML.

    TallyPrime: <HEADER><TALLYREQUEST>...</TALLYREQUEST></HEADER>
    Company name may appear in COMPANYNAME, COMPANY, or as an attribute.
    Falls back to "Unknown Company" gracefully.
    """
    candidates = [
        ".//COMPANYNAME",
        ".//COMPANY",
        ".//BASICCOMPANYNAME",
        ".//HEADER/TALLYREQUEST",  # sometimes embedded in request header
    ]
    for xpath in candidates:
        el = root.find(xpath)
        if el is not None and el.text and el.text.strip():
            return el.text.strip()

    # Some exports have it as an attribute on the root or BODY element
    company_attr = root.get("COMPANY") or root.get("company")
    if company_attr:
        return company_attr.strip()

    logger.debug("Company name not found in XML — using fallback")
    return "Unknown Company"


def _find_vouchers(root: etree._Element) -> list[etree._Element]:
    """
    Find all VOUCHER elements regardless of nesting depth.

    Tries TallyPrime xpath first, then ERP9 fallback.
    """
    for xpath in VOUCHER_XPATHS:
        vouchers = root.findall(xpath)
        if vouchers:
            logger.debug("Found %d vouchers via xpath %r", len(vouchers), xpath)
            return vouchers

    # Last resort: find all VOUCHER elements anywhere in document
    all_vouchers = root.findall(".//VOUCHER")
    logger.debug("Used fallback xpath — found %d vouchers", len(all_vouchers))
    return all_vouchers


def _extract_voucher(
    voucher: etree._Element,
    vch_type: str,
    company_name: str,
) -> list[dict]:
    """
    Extract all line items from a single VOUCHER element.

    Each line item becomes one row in the final DataFrame.
    The voucher-level customer name is applied to all line items.

    Returns a list of dicts (may be empty if no valid line items found).
    """
    voucher_id = _get_text(voucher, "VOUCHERNUMBER") or _get_text(voucher, "REMOTEID") or ""
    date_raw = _get_text(voucher, "DATE") or ""
    date = _parse_tally_date(date_raw, voucher_id)
    customer = _get_customer_name(voucher)

    rows: list[dict] = []

    # Try ALLLEDGERENTRIES.LIST first (TallyPrime line items)
    line_items = voucher.findall(".//ALLLEDGERENTRIES.LIST")

    if not line_items:
        # ERP9 uses LEDGERENTRIES.LIST
        line_items = voucher.findall(".//LEDGERENTRIES.LIST")

    if line_items:
        for item in line_items:
            product = _get_text(item, "LEDGERNAME") or ""
            amount_raw = _get_text(item, "AMOUNT") or "0"
            amount = _parse_amount(amount_raw)

            # Skip the customer ledger entry itself (it mirrors the total)
            # We only want product/item ledger entries
            if product.strip() == customer.strip():
                continue

            rows.append({
                "voucher_id": voucher_id,
                "date": date,
                "customer": customer,
                "product": product.strip(),
                "amount": amount,
                "vch_type": vch_type,
                "company": company_name,
            })
    else:
        # No line items — use voucher-level amount as single entry
        amount_raw = _get_text(voucher, "AMOUNT") or "0"
        amount = _parse_amount(amount_raw)
        product = _get_text(voucher, "NARRATION") or "General Sales"

        rows.append({
            "voucher_id": voucher_id,
            "date": date,
            "customer": customer,
            "product": product.strip(),
            "amount": amount,
            "vch_type": vch_type,
            "company": company_name,
        })

    return rows


def _get_customer_name(voucher: etree._Element) -> str:
    """
    Extract customer name from voucher.

    Tally stores the customer (party) ledger name in PARTYLEDGERNAME.
    Some exports also use PARTYNAME or the first LEDGERNAME entry.
    Empty/null → "Walk-in Customer".
    """
    for tag in ("PARTYLEDGERNAME", "PARTYNAME", "PARTYLEDGER"):
        name = _get_text(voucher, tag)
        if name and name.strip():
            return name.strip()
    return WALK_IN_CUSTOMER


def _parse_tally_date(raw: str, voucher_id: str = "") -> pd.Timestamp:
    """
    Parse Tally's YYYYMMDD date format into a pandas Timestamp.

    Tally date is ALWAYS YYYYMMDD — no other formats appear in Tally XML.
    Raises ValueError if the format is not recognised (caller handles).
    """
    raw = raw.strip()
    if not raw:
        logger.warning("Empty date in voucher %r — using today", voucher_id)
        return pd.Timestamp.today().normalize()

    if len(raw) == 8 and raw.isdigit():
        try:
            return pd.Timestamp(raw, format=TALLY_DATE_FORMAT)
        except ValueError:
            pass

    # Attempt pandas inference as last resort
    try:
        return pd.Timestamp(raw)
    except Exception as exc:
        raise ValueError(f"Unrecognised date format {raw!r} in voucher {voucher_id!r}") from exc


def _parse_amount(raw: str) -> Decimal:
    """
    Parse Tally amount string to Python Decimal.

    Tally convention: NEGATIVE amount = sale/income.
    We flip the sign so positive = sale in our system.

    Handles:
    - Negative amounts: "-15000.00" → Decimal("15000.00")
    - Positive amounts: "15000.00"  → Decimal("-15000.00")  (expense side)
    - Amounts with commas: "1,24,300" → Decimal("124300")
    - Amounts with ₹ symbol: "₹15,000" → Decimal("15000")
    """
    # Remove currency symbols, spaces, commas
    cleaned = re.sub(r"[₹,\s]", "", raw.strip())

    if not cleaned or cleaned in ("-", "+"):
        return Decimal(0)

    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        logger.debug("Could not parse amount %r — returning 0", raw)
        return Decimal(0)

    # Flip sign: negative in Tally = sale = positive in our system
    return -value


def _get_text(element: etree._Element, tag: str) -> Optional[str]:
    """Safely extract text content from a child element."""
    child = element.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    return None


def _build_dataframe(rows: list[dict]) -> pd.DataFrame:
    """
    Convert extracted rows into a typed, clean DataFrame.

    Column types:
    - date:       datetime64[ns] — for time-series operations
    - customer:   string (pandas StringDtype) — memory efficient
    - product:    string (pandas StringDtype)
    - amount:     object (Python Decimal) — NEVER float (financial precision)
    - voucher_id: string
    - vch_type:   category — memory efficient for repeated values
    - company:    string
    """
    if not rows:
        return pd.DataFrame(columns=[
            "date", "customer", "product", "amount",
            "voucher_id", "vch_type", "company",
        ])

    df = pd.DataFrame(rows)

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["customer"] = df["customer"].astype("string")
    df["product"] = df["product"].astype("string")
    df["voucher_id"] = df["voucher_id"].astype("string")
    df["vch_type"] = df["vch_type"].astype("category")
    df["company"] = df["company"].astype("string")
    # amount stays as Decimal objects — do NOT cast to float

    # Drop rows where date parsing failed entirely
    invalid_dates = df["date"].isna().sum()
    if invalid_dates > 0:
        logger.warning("Dropped %d rows with unparseable dates", invalid_dates)
        df = df.dropna(subset=["date"])

    # Sort chronologically
    df = df.sort_values("date").reset_index(drop=True)

    return df
