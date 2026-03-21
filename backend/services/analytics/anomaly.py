"""
Anomaly Detection Engine
=========================
Detects business anomalies using a combination of:
  1. Rule-based triggers (per spec — fast, explainable, high precision)
  2. Z-score detection (statistical — weekly revenue outliers)
  3. IsolationForest (ML — multi-dimensional, catches complex patterns)

All anomalies include:
  - severity: HIGH | MEDIUM | LOW
  - confidence: 0.0–1.0 (don't alert below 0.5)
  - plain English explanation
  - suggested action
  - seasonal context (checked against India calendar)

Rule: Check seasonality BEFORE assigning final severity.
      A revenue dip near Diwali/GST deadline should not be HIGH.
"""

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from services.analytics.seasonality import is_anomaly_seasonal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thresholds (per spec)
# ---------------------------------------------------------------------------

SLOW_MOVING_DAYS = 14           # Product not sold > 14 days → alert
CHURN_RISK_DAYS = 21            # Customer silent > 21 days → alert
BIG_ORDER_MULTIPLIER = 3        # Single tx > 3× avg → investigate
REVENUE_DROP_THRESHOLD = 20     # Period-over-period drop > 20% → urgent
MIN_WEEKS_FOR_ML = 4            # IsolationForest needs ≥ 4 data points
ISOLATION_CONTAMINATION = 0.1   # Expected anomaly rate
ZSCORE_THRESHOLD = 2.5          # Z-score threshold for weekly revenue
MIN_CONFIDENCE = 0.5            # Don't surface anomalies below this confidence


def _detect_period_days(df: pd.DataFrame) -> int:
    """Auto-detect comparison window — mirrors the same logic in metrics.py."""
    if df.empty or "date" not in df.columns:
        return 7
    span_days = (df["date"].max() - df["date"].min()).days
    if span_days <= 14:
        return 7
    elif span_days <= 90:
        return 30
    else:
        return 90


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Anomaly:
    anomaly_type: str           # e.g. "slow_moving_stock"
    severity: str               # "HIGH" | "MEDIUM" | "LOW"
    confidence: float           # 0.0–1.0
    title: str                  # Short title for dashboard card
    explanation: str            # Plain English: what happened
    action: str                 # Plain English: what to do
    context_notes: list[str] = field(default_factory=list)  # Seasonal context
    metadata: dict = field(default_factory=dict)             # Raw numbers


@dataclass
class AnomalyReport:
    anomalies: list[Anomaly]
    total_detected: int
    high_count: int
    medium_count: int
    low_count: int


SEVERITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_anomalies(
    df: pd.DataFrame,
    reference_date: Optional[pd.Timestamp] = None,
) -> AnomalyReport:
    """
    Run all anomaly detection methods on the DataFrame.

    Args:
        df:             Clean, normalised DataFrame (date, customer, product, amount).
        reference_date: The "today" date for relative calculations.

    Returns:
        AnomalyReport sorted by severity (HIGH first).
    """
    _validate_df(df)

    if reference_date is None:
        reference_date = df["date"].max()

    sales_df = df[df["amount"].apply(lambda x: isinstance(x, Decimal) and x > Decimal(0))].copy()

    all_anomalies: list[Anomaly] = []

    # Rule-based detection (fast, high precision)
    all_anomalies.extend(_detect_slow_moving_stock(sales_df, reference_date))
    all_anomalies.extend(_detect_customer_churn_risk(sales_df, reference_date))
    all_anomalies.extend(_detect_big_transactions(sales_df))
    all_anomalies.extend(_detect_revenue_drop(sales_df, reference_date))

    # Statistical detection
    all_anomalies.extend(_detect_zscore_anomalies(sales_df, reference_date))

    # ML-based detection (needs ≥ 4 weeks of data)
    all_anomalies.extend(_detect_isolation_forest(sales_df))

    # Filter below minimum confidence
    all_anomalies = [a for a in all_anomalies if a.confidence >= MIN_CONFIDENCE]

    # Apply seasonality adjustment
    for anomaly in all_anomalies:
        _apply_seasonality(anomaly, reference_date)

    # Remove duplicates (same type + same metadata key)
    all_anomalies = _deduplicate(all_anomalies)

    # Sort: HIGH first, then MEDIUM, then LOW; within same severity: confidence desc
    all_anomalies.sort(
        key=lambda a: (SEVERITY_ORDER.get(a.severity, 2), -a.confidence)
    )

    high = sum(1 for a in all_anomalies if a.severity == "HIGH")
    medium = sum(1 for a in all_anomalies if a.severity == "MEDIUM")
    low = sum(1 for a in all_anomalies if a.severity == "LOW")

    logger.info(
        "Anomaly detection: %d total (HIGH=%d, MEDIUM=%d, LOW=%d)",
        len(all_anomalies), high, medium, low,
    )

    return AnomalyReport(
        anomalies=all_anomalies,
        total_detected=len(all_anomalies),
        high_count=high,
        medium_count=medium,
        low_count=low,
    )


# ---------------------------------------------------------------------------
# Rule-based detectors
# ---------------------------------------------------------------------------

def _detect_slow_moving_stock(df: pd.DataFrame, today: pd.Timestamp) -> list[Anomaly]:
    """Rule: Product not sold in > 14 days → slow moving / dead stock."""
    if df.empty or "product" not in df.columns:
        return []
    anomalies = []

    last_sale = df.groupby("product")["date"].max()
    days_since = (today - last_sale).dt.days

    slow = days_since[days_since > SLOW_MOVING_DAYS]

    for product, days in slow.items():
        product_df = df[df["product"] == product]
        locked_value = float(sum(
            x for x in product_df["amount"]
            if isinstance(x, Decimal)
        ))

        severity = "HIGH" if days > 30 else "MEDIUM"
        confidence = min(0.95, 0.6 + (days - SLOW_MOVING_DAYS) / 60)

        anomalies.append(Anomaly(
            anomaly_type="slow_moving_stock",
            severity=severity,
            confidence=confidence,
            title=f"Dead stock: {product}",
            explanation=(
                f"{product!r} has not been sold in {days} days "
                f"(last sold on {last_sale[product].strftime('%d %b %Y')}). "
                f"Total historical revenue from this product: ₹{locked_value:,.0f}."
            ),
            action=(
                "Consider running a discount offer, bundling with a fast-moving product, "
                "or returning to supplier if possible."
            ),
            metadata={
                "product": str(product),
                "days_since_sale": int(days),
                "locked_value": locked_value,
                "last_sale_date": str(last_sale[product].date()),
            },
        ))

    return anomalies


def _detect_customer_churn_risk(df: pd.DataFrame, today: pd.Timestamp) -> list[Anomaly]:
    """Rule: Customer with no order in > 21 days → churn risk."""
    if df.empty or "customer" not in df.columns:
        return []
    anomalies = []

    last_order = df.groupby("customer")["date"].max()
    days_since = (today - last_order).dt.days

    at_risk = days_since[days_since > CHURN_RISK_DAYS]

    for customer, days in at_risk.items():
        customer_df = df[df["customer"] == customer]
        avg_order = float(sum(
            x for x in customer_df["amount"] if isinstance(x, Decimal)
        )) / max(1, len(customer_df))

        severity = "HIGH" if avg_order > 5000 else "MEDIUM"
        confidence = min(0.9, 0.55 + (days - CHURN_RISK_DAYS) / 90)

        anomalies.append(Anomaly(
            anomaly_type="customer_churn_risk",
            severity=severity,
            confidence=confidence,
            title=f"Churn risk: {customer}",
            explanation=(
                f"{customer!r} has not ordered in {days} days "
                f"(last order: {last_order[customer].strftime('%d %b %Y')}). "
                f"Their average order value is ₹{avg_order:,.0f}."
            ),
            action=(
                f"Call or message {customer!r} today. "
                f"A quick check-in can recover the relationship. "
                f"They may have switched to a competitor."
            ),
            metadata={
                "customer": str(customer),
                "days_since_order": int(days),
                "avg_order_value": avg_order,
                "last_order_date": str(last_order[customer].date()),
            },
        ))

    return anomalies


def _detect_big_transactions(df: pd.DataFrame) -> list[Anomaly]:
    """Rule: Single transaction > 3× average order value → investigate."""
    if df.empty or "amount" not in df.columns:
        return []

    amounts = [float(x) for x in df["amount"] if isinstance(x, Decimal) and x > Decimal(0)]
    if len(amounts) < 3:
        return []

    avg = np.mean(amounts)
    threshold = avg * BIG_ORDER_MULTIPLIER

    anomalies = []
    for _, row in df.iterrows():
        amount = float(row["amount"]) if isinstance(row["amount"], Decimal) else 0
        if amount > threshold:
            anomalies.append(Anomaly(
                anomaly_type="large_transaction",
                severity="MEDIUM",
                confidence=0.75,
                title=f"Unusually large sale: ₹{amount:,.0f}",
                explanation=(
                    f"A transaction of ₹{amount:,.0f} on {row['date'].strftime('%d %b %Y')} "
                    f"is {amount / avg:.1f}× your average order value (₹{avg:,.0f}). "
                    f"Customer: {row.get('customer', 'Unknown')}."
                ),
                action=(
                    "Verify this is a genuine sale and not a data entry error. "
                    "If real, this is a big win — consider how to replicate it."
                ),
                metadata={
                    "amount": amount,
                    "avg_amount": avg,
                    "date": str(row["date"].date()),
                    "customer": str(row.get("customer", "")),
                },
            ))

    return anomalies


def _detect_revenue_drop(df: pd.DataFrame, today: pd.Timestamp) -> list[Anomaly]:
    """Rule: Period-over-period revenue drop > 20% → urgent alert."""
    if df.empty or "date" not in df.columns or pd.isna(today):
        return []

    period_days = _detect_period_days(df)
    period_start = today - pd.Timedelta(days=period_days - 1)
    prev_start = period_start - pd.Timedelta(days=period_days)
    prev_end = period_start - pd.Timedelta(days=1)

    current = df[df["date"].between(period_start, today)]
    previous = df[df["date"].between(prev_start, prev_end)]

    current_rev = sum(float(x) for x in current["amount"] if isinstance(x, Decimal))
    prev_rev = sum(float(x) for x in previous["amount"] if isinstance(x, Decimal))

    if prev_rev == 0:
        return []

    drop_pct = ((prev_rev - current_rev) / prev_rev) * 100

    if drop_pct < REVENUE_DROP_THRESHOLD:
        return []

    period_label = "this week" if period_days <= 7 else ("this month" if period_days <= 30 else "this quarter")
    prev_label = "last week" if period_days <= 7 else ("last month" if period_days <= 30 else "last quarter")

    return [Anomaly(
        anomaly_type="revenue_drop",
        severity="HIGH",
        confidence=0.9,
        title=f"Revenue dropped {drop_pct:.0f}% {period_label}",
        explanation=(
            f"Revenue {period_label} is ₹{current_rev:,.0f}, down {drop_pct:.0f}% "
            f"from ₹{prev_rev:,.0f} {prev_label}. "
            f"This is a significant drop that needs immediate attention."
        ),
        action=(
            f"Review which products or customers drove {prev_label}'s revenue and "
            f"check if those sales are missing {period_label}. "
            "Check for pending orders that haven't been invoiced yet."
        ),
        metadata={
            "current_revenue": current_rev,
            "previous_revenue": prev_rev,
            "drop_pct": drop_pct,
            "period_days": period_days,
        },
    )]


# ---------------------------------------------------------------------------
# Statistical detectors
# ---------------------------------------------------------------------------

def _detect_zscore_anomalies(df: pd.DataFrame, today: pd.Timestamp) -> list[Anomaly]:
    """Z-score on weekly revenue — flags statistically unusual weeks."""
    if df.empty:
        return []

    weekly = df.set_index("date").resample("W")["amount"].apply(
        lambda s: sum(float(x) for x in s if isinstance(x, Decimal))
    )

    if len(weekly) < 3:
        return []

    values = weekly.values.astype(float)
    mean = np.mean(values)
    std = np.std(values)

    if std == 0:
        return []

    zscores = (values - mean) / std
    anomalies = []

    for i, (week_end, z) in enumerate(zip(weekly.index, zscores)):
        if abs(z) < ZSCORE_THRESHOLD:
            continue

        direction = "high" if z > 0 else "low"
        rev = values[i]

        anomalies.append(Anomaly(
            anomaly_type="revenue_anomaly_zscore",
            severity="MEDIUM",
            confidence=min(0.9, abs(z) / (ZSCORE_THRESHOLD * 2)),
            title=f"Unusual revenue week ending {week_end.strftime('%d %b')}",
            explanation=(
                f"Revenue of ₹{rev:,.0f} for the week ending {week_end.strftime('%d %b %Y')} "
                f"is statistically {direction} (z-score: {z:.1f}). "
                f"Your typical weekly revenue is ₹{mean:,.0f} ± ₹{std:,.0f}."
            ),
            action="Investigate what drove the unusual activity this week.",
            metadata={
                "week_end": str(week_end.date()),
                "revenue": rev,
                "zscore": float(z),
                "mean_revenue": mean,
            },
        ))

    return anomalies


def _detect_isolation_forest(df: pd.DataFrame) -> list[Anomaly]:
    """
    IsolationForest on weekly revenue pattern.
    Requires at least MIN_WEEKS_FOR_ML weeks of data.
    """
    if df.empty:
        return []

    weekly = df.set_index("date").resample("W")["amount"].apply(
        lambda s: sum(float(x) for x in s if isinstance(x, Decimal))
    )

    if len(weekly) < MIN_WEEKS_FOR_ML:
        logger.debug(
            "IsolationForest skipped: only %d weeks of data (need %d)",
            len(weekly), MIN_WEEKS_FOR_ML,
        )
        return []

    values = weekly.values.reshape(-1, 1).astype(float)

    # Scale before fitting
    scaler = StandardScaler()
    scaled = scaler.fit_transform(values)

    clf = IsolationForest(contamination=ISOLATION_CONTAMINATION, random_state=42)
    predictions = clf.fit_predict(scaled)
    scores = clf.score_samples(scaled)  # More negative = more anomalous

    anomalies = []
    for i, (week_end, pred) in enumerate(zip(weekly.index, predictions)):
        if pred != -1:  # -1 = anomaly
            continue

        rev = float(weekly.iloc[i])
        # Normalize score to confidence: more negative score = higher confidence
        raw_score = abs(float(scores[i]))
        confidence = min(0.85, 0.5 + raw_score * 0.3)

        anomalies.append(Anomaly(
            anomaly_type="revenue_anomaly_ml",
            severity="LOW",  # ML anomalies are LOW by default — rule-based are more reliable
            confidence=confidence,
            title=f"ML: unusual pattern week of {week_end.strftime('%d %b')}",
            explanation=(
                f"Machine learning detected an unusual revenue pattern "
                f"for the week ending {week_end.strftime('%d %b %Y')} "
                f"(₹{rev:,.0f}). This week's pattern doesn't fit your historical trend."
            ),
            action="Review what was different this week — products, customers, or external factors.",
            metadata={
                "week_end": str(week_end.date()),
                "revenue": rev,
                "anomaly_score": float(scores[i]),
            },
        ))

    return anomalies


# ---------------------------------------------------------------------------
# Post-processing
# ---------------------------------------------------------------------------

def _apply_seasonality(anomaly: Anomaly, reference_date: pd.Timestamp) -> None:
    """
    Check if the anomaly falls near a known seasonal event.
    If yes, downgrade severity from HIGH → MEDIUM.
    Modifies anomaly in place.
    """
    is_seasonal, context_notes = is_anomaly_seasonal(reference_date.date())

    if is_seasonal and context_notes:
        anomaly.context_notes = context_notes
        if anomaly.severity == "HIGH" and anomaly.anomaly_type in (
            "revenue_drop", "revenue_anomaly_zscore", "revenue_anomaly_ml"
        ):
            logger.info(
                "Downgraded %s from HIGH to MEDIUM due to seasonal context: %s",
                anomaly.anomaly_type, context_notes[0][:60],
            )
            anomaly.severity = "MEDIUM"


def _deduplicate(anomalies: list[Anomaly]) -> list[Anomaly]:
    """Remove duplicate anomalies of the same type targeting the same entity."""
    seen: set[str] = set()
    unique: list[Anomaly] = []

    for a in anomalies:
        # Create a dedup key from type + primary metadata field
        key_val = (
            a.metadata.get("product")
            or a.metadata.get("customer")
            or a.metadata.get("week_end")
            or a.metadata.get("date")
            or "global"
        )
        key = f"{a.anomaly_type}::{key_val}"

        if key not in seen:
            seen.add(key)
            unique.append(a)

    return unique


def _validate_df(df: pd.DataFrame) -> None:
    required = ["date", "amount"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"DataFrame missing required columns: {missing}")
    # Empty DataFrame is valid for anomaly detection — returns 0 anomalies.
