"""
Core Business Metrics Calculator
==================================
Computes the 5 business health KPIs shown on the main dashboard.

All monetary values use Python Decimal — NEVER float.
All period comparisons use the same number of days for fairness.

The 5 metrics (per spec):
  1. Revenue this week vs last week (₹ + % change)
  2. Top 5 products by revenue (with trend vs previous week)
  3. Bottom 5 / dead stock (zero sales > 14 days)
  4. Gross margin trend (if cost data available, else skipped gracefully)
  5. New vs repeat customer split (count + revenue contribution)
"""

import logging
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

TWO_PLACES = Decimal("0.01")
DEAD_STOCK_DAYS = 14   # Per spec: no sales > 14 days = dead stock


def _detect_period_days(df: pd.DataFrame) -> int:
    """
    Auto-detect the comparison window size based on data span.

    - Data ≤ 14 days  → compare last 7 days vs previous 7 days
    - Data 15–90 days → compare last 30 days vs previous 30 days
    - Data > 90 days  → compare last 90 days vs previous 90 days

    This ensures the analysis is meaningful regardless of whether someone
    uploads a week's invoices or 2 years of full accounts.
    """
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
class RevenueMetric:
    current_period: Decimal
    previous_period: Decimal
    change_amount: Decimal
    change_pct: Optional[Decimal]   # None if no previous data
    trend: str                       # "up" | "down" | "flat" | "new"
    period_label: str                # e.g. "This week vs last week"


@dataclass
class ProductRanking:
    rank: int
    name: str
    revenue: Decimal
    previous_revenue: Decimal
    change_pct: Optional[Decimal]
    trend: str          # "up" | "down" | "flat" | "new"
    units_sold: int     # If quantity data available, else 0


@dataclass
class DeadStockItem:
    product: str
    days_since_last_sale: int
    last_sale_date: pd.Timestamp
    estimated_locked_value: Decimal  # Total historical revenue from this product


@dataclass
class CustomerSplit:
    new_customers: int          # First purchase in analysis period
    repeat_customers: int       # More than 1 purchase ever
    new_revenue: Decimal
    repeat_revenue: Decimal
    new_revenue_pct: Decimal    # % of total revenue from new customers


@dataclass
class BusinessMetrics:
    """Complete set of 5 KPIs for the dashboard."""
    revenue: RevenueMetric
    top_products: list[ProductRanking]       # Top 5 by revenue
    dead_stock: list[DeadStockItem]          # Products not sold > 14 days
    customer_split: CustomerSplit
    margin: Optional[dict] = None            # Only present if cost data available
    computed_at: pd.Timestamp = field(default_factory=pd.Timestamp.now)
    period_start: Optional[pd.Timestamp] = None
    period_end: Optional[pd.Timestamp] = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_metrics(
    df: pd.DataFrame,
    reference_date: Optional[pd.Timestamp] = None,
) -> BusinessMetrics:
    """
    Compute all 5 business health metrics from a parsed, normalised DataFrame.

    Args:
        df:             Clean DataFrame with columns: date, customer, product, amount.
        reference_date: The "today" date for relative calculations.
                        Defaults to the latest date in the dataset.

    Returns:
        BusinessMetrics with all 5 KPIs populated.
    """
    _validate_df(df)

    # Use latest date in data as reference (better than today for historical uploads)
    if reference_date is None:
        reference_date = df["date"].max()

    # Work only with positive amounts (exclude returns for main KPIs)
    sales_df = df[df["amount"].apply(lambda x: isinstance(x, Decimal) and x > Decimal(0))].copy()

    # Auto-detect comparison window based on data span
    period_days = _detect_period_days(df)
    period_start = reference_date - pd.Timedelta(days=period_days - 1)
    prev_period_start = period_start - pd.Timedelta(days=period_days)
    prev_period_end = period_start - pd.Timedelta(days=1)

    current_period = sales_df[sales_df["date"].between(period_start, reference_date)]
    previous_period = sales_df[sales_df["date"].between(prev_period_start, prev_period_end)]

    revenue = _compute_revenue(current_period, previous_period, reference_date, period_days)
    top_products = _compute_top_products(current_period, previous_period)
    dead_stock = _compute_dead_stock(sales_df, reference_date, period_days)
    customer_split = _compute_customer_split(sales_df, current_period, reference_date, period_days)

    logger.info(
        "Metrics computed | period: %s→%s (%dd window) | revenue: ₹%s | products: %d | dead_stock: %d",
        period_start.date(), reference_date.date(), period_days,
        revenue.current_period, len(top_products), len(dead_stock),
    )

    return BusinessMetrics(
        revenue=revenue,
        top_products=top_products,
        dead_stock=dead_stock,
        customer_split=customer_split,
        period_start=period_start,
        period_end=reference_date,
    )


# ---------------------------------------------------------------------------
# Individual metric calculators
# ---------------------------------------------------------------------------

def _compute_revenue(
    current: pd.DataFrame,
    previous: pd.DataFrame,
    reference_date: pd.Timestamp,
    period_days: int = 7,
) -> RevenueMetric:
    """Metric 1: Revenue this period vs previous period (adaptive window)."""
    current_total = _sum_amount(current)
    previous_total = _sum_amount(previous)

    change_amount = current_total - previous_total

    if previous_total == Decimal(0):
        change_pct = None
        trend = "new"
    else:
        change_pct = ((change_amount / previous_total) * 100).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        if change_pct > Decimal("5"):
            trend = "up"
        elif change_pct < Decimal("-5"):
            trend = "down"
        else:
            trend = "flat"

    if period_days <= 7:
        label = "This week vs last week"
    elif period_days <= 30:
        label = "This month vs last month"
    else:
        label = "This quarter vs last quarter"

    return RevenueMetric(
        current_period=current_total.quantize(TWO_PLACES),
        previous_period=previous_total.quantize(TWO_PLACES),
        change_amount=change_amount.quantize(TWO_PLACES),
        change_pct=change_pct,
        trend=trend,
        period_label=label,
    )


def _compute_top_products(
    current: pd.DataFrame,
    previous: pd.DataFrame,
) -> list[ProductRanking]:
    """
    Metric 2: Top 5 products by revenue this week with trend vs last week.
    Also Metric 3 data source (bottom products are the inverse).
    """
    if current.empty:
        return []

    current_by_product = (
        current.groupby("product")["amount"]
        .apply(_sum_amount)
        .sort_values(ascending=False)
    )

    prev_by_product = (
        previous.groupby("product")["amount"]
        .apply(_sum_amount)
        if not previous.empty
        else pd.Series(dtype=object)
    )

    rankings: list[ProductRanking] = []

    for rank, (product, revenue) in enumerate(current_by_product.head(5).items(), start=1):
        prev_revenue = prev_by_product.get(product, Decimal(0))

        if prev_revenue == Decimal(0):
            change_pct = None
            trend = "new"
        else:
            change_pct = (((revenue - prev_revenue) / prev_revenue) * 100).quantize(
                TWO_PLACES, rounding=ROUND_HALF_UP
            )
            trend = "up" if change_pct > 5 else ("down" if change_pct < -5 else "flat")

        # Unit count if quantity column exists
        units = 0
        if "quantity" in current.columns:
            units = int(current[current["product"] == product]["quantity"].sum())

        rankings.append(ProductRanking(
            rank=rank,
            name=str(product),
            revenue=revenue.quantize(TWO_PLACES),
            previous_revenue=prev_revenue.quantize(TWO_PLACES),
            change_pct=change_pct,
            trend=trend,
            units_sold=units,
        ))

    return rankings


def _compute_dead_stock(
    df: pd.DataFrame,
    reference_date: pd.Timestamp,
    period_days: int = 7,
) -> list[DeadStockItem]:
    """
    Metric 3 (partial): Products with zero sales in the last DEAD_STOCK_DAYS days.

    Only products that have been sold at least once historically are included
    (we need a last_sale_date to compute staleness).
    """
    if df.empty:
        return []

    last_sale = df.groupby("product")["date"].max()
    days_since = (reference_date - last_sale).dt.days

    dead = days_since[days_since > DEAD_STOCK_DAYS].sort_values(ascending=False)

    result: list[DeadStockItem] = []
    for product, days in dead.items():
        locked_value = _sum_amount(df[df["product"] == product])
        last_date = last_sale[product]
        result.append(DeadStockItem(
            product=str(product),
            days_since_last_sale=int(days),
            last_sale_date=last_date,
            estimated_locked_value=locked_value.quantize(TWO_PLACES),
        ))

    return result


def _compute_customer_split(
    all_df: pd.DataFrame,
    current_period: pd.DataFrame,
    reference_date: pd.Timestamp,
    period_days: int = 7,
) -> CustomerSplit:
    """
    Metric 5: New vs repeat customer split in the current period.

    New = customer's first-ever purchase falls within current period.
    Repeat = customer has purchased before the current period.
    """
    if current_period.empty:
        return CustomerSplit(
            new_customers=0,
            repeat_customers=0,
            new_revenue=Decimal(0),
            repeat_revenue=Decimal(0),
            new_revenue_pct=Decimal(0),
        )

    period_start = reference_date - pd.Timedelta(days=period_days - 1)

    # First purchase date per customer (across all history)
    first_purchase = all_df.groupby("customer")["date"].min()

    current_customers = current_period["customer"].unique()

    new_customers_list = [
        c for c in current_customers
        if first_purchase.get(c, pd.NaT) >= period_start
    ]
    repeat_customers_list = [
        c for c in current_customers
        if c not in new_customers_list
    ]

    new_revenue = _sum_amount(
        current_period[current_period["customer"].isin(new_customers_list)]
    )
    repeat_revenue = _sum_amount(
        current_period[current_period["customer"].isin(repeat_customers_list)]
    )
    total_revenue = new_revenue + repeat_revenue

    new_pct = (
        ((new_revenue / total_revenue) * 100).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
        if total_revenue > 0
        else Decimal(0)
    )

    return CustomerSplit(
        new_customers=len(new_customers_list),
        repeat_customers=len(repeat_customers_list),
        new_revenue=new_revenue.quantize(TWO_PLACES),
        repeat_revenue=repeat_revenue.quantize(TWO_PLACES),
        new_revenue_pct=new_pct,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_df(df: pd.DataFrame) -> None:
    required = ["date", "amount"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"DataFrame missing required columns: {missing}")
    if df.empty:
        raise ValueError("DataFrame is empty — no data to analyze.")


def _sum_amount(df) -> Decimal:
    """
    Sum amount values from a DataFrame or a pandas Series.

    When called from groupby(...)[col].apply(), pandas passes a Series.
    When called directly, we pass the full DataFrame and access "amount".
    Both cases are handled here.
    """
    if isinstance(df, pd.Series):
        values = df
    else:
        if df.empty or "amount" not in df.columns:
            return Decimal(0)
        values = df["amount"]

    total = Decimal(0)
    for val in values:
        if isinstance(val, Decimal):
            total += val
    return total


def format_inr(amount: Decimal) -> str:
    """
    Format a Decimal amount in Indian number format.
    Example: 124300 → "₹1,24,300"
    """
    amount_int = int(amount.to_integral_value(rounding=ROUND_HALF_UP))
    is_negative = amount_int < 0
    amount_int = abs(amount_int)

    s = str(amount_int)
    if len(s) <= 3:
        formatted = s
    else:
        # Indian format: last 3 digits, then groups of 2
        last3 = s[-3:]
        rest = s[:-3]
        groups = []
        while len(rest) > 2:
            groups.append(rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.append(rest)
        formatted = ",".join(reversed(groups)) + "," + last3

    return f"{'−' if is_negative else ''}₹{formatted}"
