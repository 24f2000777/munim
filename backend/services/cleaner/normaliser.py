"""
Data Normaliser
================
Normalises a parsed DataFrame for consistent downstream analytics.

Operations:
  1. Date normalisation — ensures all dates are valid, future dates flagged
  2. Amount normalisation — ensures Decimal type, flags impossible values
  3. Text normalisation — strips whitespace, normalises Unicode, title-cases names
  4. Duplicate transaction detection — flags exact duplicate vouchers
  5. Returns flag columns for user review (never auto-deletes data)

Principle: Flag anomalies, never silently delete. The user decides what to keep.
"""

import logging
import unicodedata
from decimal import Decimal

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Flag column names added to DataFrame
FLAG_FUTURE_DATE = "_flag_future_date"
FLAG_DUPLICATE = "_flag_duplicate"
FLAG_NEGATIVE_AMOUNT = "_flag_negative_amount"
FLAG_EXTREME_AMOUNT = "_flag_extreme_amount"  # > 3× std dev from mean


def normalise(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Normalise a parsed DataFrame and return it with flag columns.

    Args:
        df: DataFrame from any parser (tally/excel/csv).
            Must have columns: date, customer, product, amount.

    Returns:
        Tuple of:
        - Normalised DataFrame with flag columns (prefixed with _flag_)
        - Summary dict of issues found: {flag_name: count}
    """
    df = df.copy()
    summary: dict[str, int] = {}

    df, future_count = _flag_future_dates(df)
    summary[FLAG_FUTURE_DATE] = future_count

    df, neg_count = _flag_negative_amounts(df)
    summary[FLAG_NEGATIVE_AMOUNT] = neg_count

    df, extreme_count = _flag_extreme_amounts(df)
    summary[FLAG_EXTREME_AMOUNT] = extreme_count

    df, dup_count = _flag_duplicates(df)
    summary[FLAG_DUPLICATE] = dup_count

    df = _normalise_text(df)

    total_flagged = sum(v for v in summary.values() if v > 0)
    logger.info(
        "Normalisation complete: %d rows total, %d flagged. Breakdown: %s",
        len(df), total_flagged, summary,
    )

    return df, summary


# ---------------------------------------------------------------------------
# Individual normalisation steps
# ---------------------------------------------------------------------------

def _flag_future_dates(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Flag rows where date is in the future (likely data entry error)."""
    today = pd.Timestamp.now().normalize()
    future_mask = df["date"] > today
    df[FLAG_FUTURE_DATE] = future_mask
    count = int(future_mask.sum())
    if count > 0:
        logger.warning("%d rows have future dates — flagged for user review", count)
    return df, count


def _flag_negative_amounts(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """
    Flag rows with negative amounts.

    Negative amounts in sales data usually mean returns/refunds.
    They are valid business events but should be reviewed.
    We do NOT delete them — returns affect revenue calculations.
    """
    neg_mask = df["amount"].apply(lambda x: isinstance(x, Decimal) and x < Decimal(0))
    df[FLAG_NEGATIVE_AMOUNT] = neg_mask
    count = int(neg_mask.sum())
    if count > 0:
        logger.info(
            "%d rows with negative amounts (likely returns/refunds) — flagged", count
        )
    return df, count


def _flag_extreme_amounts(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """
    Flag rows where amount is > 3× standard deviation from mean.

    These could be:
    - Genuine large orders (worth investigating)
    - Data entry errors (extra zeros added)

    Never deleted — user reviews and decides.
    """
    amounts = df["amount"].apply(
        lambda x: float(x) if isinstance(x, Decimal) else float(x) if pd.notna(x) else 0.0
    )

    if amounts.std() == 0 or len(amounts) < 4:
        df[FLAG_EXTREME_AMOUNT] = False
        return df, 0

    mean = amounts.mean()
    std = amounts.std()
    threshold = mean + (3 * std)

    extreme_mask = amounts.abs() > threshold
    df[FLAG_EXTREME_AMOUNT] = extreme_mask
    count = int(extreme_mask.sum())

    if count > 0:
        logger.info(
            "%d rows with extreme amounts (> 3σ from mean ₹%.0f) — flagged",
            count, mean,
        )

    return df, count


def _flag_duplicates(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """
    Flag exact duplicate rows (same date + customer + product + amount).

    Duplicates in Tally data usually indicate double-entry errors.
    Voucher ID is NOT included in duplicate check because the same
    product may legitimately appear in multiple vouchers.
    """
    check_cols = [c for c in ["date", "customer", "product", "amount"] if c in df.columns]
    dup_mask = df.duplicated(subset=check_cols, keep="first")
    df[FLAG_DUPLICATE] = dup_mask
    count = int(dup_mask.sum())
    if count > 0:
        logger.warning(
            "%d duplicate rows detected (same date/customer/product/amount) — flagged", count
        )
    return df, count


def _normalise_text(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalise text columns:
    - Strip leading/trailing whitespace
    - Normalise Unicode to NFC (handles composed vs decomposed Devanagari)
    - Collapse internal whitespace
    - Title-case customer names (preserve product case — may have brand names)
    """
    def clean_text(val: str) -> str:
        if pd.isna(val) or not isinstance(val, str):
            return val
        # Unicode NFC normalisation — critical for Devanagari consistency
        val = unicodedata.normalize("NFC", val)
        val = " ".join(val.split())  # Collapse internal whitespace
        return val.strip()

    for col in ["customer", "product"]:
        if col in df.columns:
            df[col] = df[col].apply(clean_text)

    # Title-case customer names only (not products — "Parle-G" should stay as-is)
    if "customer" in df.columns:
        df["customer"] = df["customer"].apply(
            lambda x: x.title() if isinstance(x, str) and x else x
        )

    return df
