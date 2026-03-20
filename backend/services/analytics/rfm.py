"""
RFM Customer Segmentation
==========================
Segments customers using Recency, Frequency, Monetary (RFM) analysis.

Segments:
  Champions       — Bought recently, buy often, spend the most
  Loyal           — Buy often, decent spend
  Potential       — Recent buyers, not yet frequent
  At Risk         — Used to buy often but haven't recently
  Lost            — Low recency, low frequency, low monetary
  New             — Bought only once, recently

Each customer gets:
  - RFM scores (1–5 each)
  - Segment label
  - Plain English description
  - Recommended action for the business owner
"""

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class CustomerSegment:
    customer: str
    recency_days: int          # Days since last purchase
    frequency: int             # Total number of purchases
    monetary: float            # Total spend (float for display — calculations use Decimal)
    r_score: int               # 1–5 (5 = best)
    f_score: int               # 1–5
    m_score: int               # 1–5
    rfm_score: str             # e.g. "554"
    segment: str               # e.g. "Champion"
    description: str
    action: str


def compute_rfm(
    df: pd.DataFrame,
    reference_date: Optional[pd.Timestamp] = None,
) -> list[CustomerSegment]:
    """
    Compute RFM segmentation for all customers in the DataFrame.

    Args:
        df:             Clean DataFrame with date, customer, amount columns.
        reference_date: The snapshot date. Defaults to max date in data.

    Returns:
        List of CustomerSegment objects sorted by monetary value (desc).
    """
    if df.empty or "customer" not in df.columns:
        return []

    if reference_date is None:
        reference_date = df["date"].max()

    # Build RFM table
    rfm = df.groupby("customer").agg(
        last_purchase=("date", "max"),
        frequency=("date", "count"),
        monetary=("amount", lambda x: float(sum(
            v for v in x if isinstance(v, Decimal) and v > Decimal(0)
        ))),
    ).reset_index()

    rfm["recency_days"] = (reference_date - rfm["last_purchase"]).dt.days.astype(int)

    # Score each dimension 1–5 (5 = best)
    # Use quantile-based scoring with fallback for small datasets
    rfm["r_score"] = _score_column(rfm["recency_days"], ascending=True)   # Lower recency = better
    rfm["f_score"] = _score_column(rfm["frequency"], ascending=False)
    rfm["m_score"] = _score_column(rfm["monetary"], ascending=False)

    rfm["rfm_score"] = (
        rfm["r_score"].astype(str)
        + rfm["f_score"].astype(str)
        + rfm["m_score"].astype(str)
    )

    rfm["segment"] = rfm["rfm_score"].apply(_assign_segment)
    rfm["description"] = rfm["segment"].map(_SEGMENT_DESCRIPTIONS)
    rfm["action"] = rfm["segment"].map(_SEGMENT_ACTIONS)

    # Sort by monetary value
    rfm = rfm.sort_values("monetary", ascending=False)

    segments: list[CustomerSegment] = []
    for _, row in rfm.iterrows():
        segments.append(CustomerSegment(
            customer=str(row["customer"]),
            recency_days=int(row["recency_days"]),
            frequency=int(row["frequency"]),
            monetary=float(row["monetary"]),
            r_score=int(row["r_score"]),
            f_score=int(row["f_score"]),
            m_score=int(row["m_score"]),
            rfm_score=str(row["rfm_score"]),
            segment=str(row["segment"]),
            description=str(row["description"]),
            action=str(row["action"]),
        ))

    logger.info(
        "RFM segmentation: %d customers | segments: %s",
        len(segments),
        {seg: sum(1 for s in segments if s.segment == seg) for seg in _SEGMENT_DESCRIPTIONS},
    )

    return segments


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _score_column(series: pd.Series, ascending: bool) -> pd.Series:
    """
    Score a series into 1–5 buckets using quintiles.
    ascending=True means lower values get higher scores (e.g. recency).
    ascending=False means higher values get higher scores (e.g. spend).
    """
    if series.nunique() < 5:
        # Not enough unique values for quintiles — use rank-based scoring
        ranked = series.rank(method="first", ascending=not ascending)
        n = len(series)
        scores = pd.cut(ranked, bins=5, labels=[1, 2, 3, 4, 5])
        return scores.astype(int)

    try:
        if ascending:
            # Lower = better (recency: fewer days = more recent)
            labels = [5, 4, 3, 2, 1]
        else:
            # Higher = better (frequency, monetary)
            labels = [1, 2, 3, 4, 5]

        return pd.qcut(series, q=5, labels=labels, duplicates="drop").astype(int)
    except Exception:
        # Fallback: median split into 3 groups
        median = series.median()
        result = pd.Series(3, index=series.index)
        if ascending:
            result[series < median] = 5
            result[series > median] = 1
        else:
            result[series > median] = 5
            result[series < median] = 1
        return result


def _assign_segment(rfm_score: str) -> str:
    """Map 3-digit RFM score to segment label."""
    r = int(rfm_score[0])
    f = int(rfm_score[1])
    m = int(rfm_score[2])

    if r >= 4 and f >= 4 and m >= 4:
        return "Champion"
    elif r >= 3 and f >= 3:
        return "Loyal"
    elif r >= 4 and f <= 2:
        return "Potential"
    elif r <= 2 and f >= 3:
        return "At Risk"
    elif r <= 2 and f <= 2 and m <= 2:
        return "Lost"
    elif f == 1 and r >= 4:
        return "New"
    else:
        return "Average"


_SEGMENT_DESCRIPTIONS: dict[str, str] = {
    "Champion":  "Your best customers — buy often, spend the most, bought recently.",
    "Loyal":     "Regular buyers with consistent spend. High retention value.",
    "Potential": "Recent buyers who haven't become regulars yet. High growth potential.",
    "At Risk":   "Used to buy often but have gone quiet. Intervention needed now.",
    "Lost":      "Haven't bought in a long time and were low-value. Low priority to recover.",
    "New":       "Brand new customer — only bought once. Focus on second purchase.",
    "Average":   "Middle-of-the-road customers. Can be nudged up with offers.",
}

_SEGMENT_ACTIONS: dict[str, str] = {
    "Champion":  "Treat them as VIPs. Offer early access to new products. Ask for referrals.",
    "Loyal":     "Reward with loyalty benefits. Ask for testimonials or referrals.",
    "Potential": "Send personalised follow-up. Offer a small discount on next order.",
    "At Risk":   "Call them personally. Find out why they stopped. Offer to win them back.",
    "Lost":      "Send a re-engagement offer. If no response, deprioritise.",
    "New":       "Send a thank-you message. Recommend complementary products.",
    "Average":   "Send targeted promotions on their most-purchased category.",
}
