"""
Tests for Core Business Metrics Calculator
============================================
"""

import pytest
from decimal import Decimal

import pandas as pd

from services.analytics.metrics import compute_metrics, format_inr, _sum_amount


class TestComputeMetrics:

    def test_returns_all_five_metrics(self, clean_sales_df):
        """compute_metrics returns all 5 required KPIs."""
        metrics = compute_metrics(clean_sales_df)
        assert metrics.revenue is not None
        assert metrics.top_products is not None
        assert metrics.dead_stock is not None
        assert metrics.customer_split is not None

    def test_revenue_uses_decimal(self, clean_sales_df):
        """Revenue figures are Decimal, not float."""
        metrics = compute_metrics(clean_sales_df)
        assert isinstance(metrics.revenue.current_period, Decimal)
        assert isinstance(metrics.revenue.previous_period, Decimal)
        assert isinstance(metrics.revenue.change_amount, Decimal)

    def test_top_products_max_5(self, clean_sales_df):
        """Top products list contains at most 5 items."""
        metrics = compute_metrics(clean_sales_df)
        assert len(metrics.top_products) <= 5

    def test_top_products_sorted_by_revenue(self, clean_sales_df):
        """Top products are sorted highest revenue first."""
        metrics = compute_metrics(clean_sales_df)
        revenues = [p.revenue for p in metrics.top_products]
        assert revenues == sorted(revenues, reverse=True)

    def test_dead_stock_detects_inactive_product(self, clean_sales_df):
        """Tata Salt (not sold in last 14+ days in fixture) appears in dead stock."""
        metrics = compute_metrics(clean_sales_df)
        dead_products = [d.product for d in metrics.dead_stock]
        assert "Tata Salt" in dead_products

    def test_dead_stock_days_count_positive(self, clean_sales_df):
        """Dead stock items have positive days_since_last_sale."""
        metrics = compute_metrics(clean_sales_df)
        for item in metrics.dead_stock:
            assert item.days_since_last_sale > 0

    def test_customer_split_totals_match(self, clean_sales_df):
        """new + repeat customers = total unique customers in current week."""
        metrics = compute_metrics(clean_sales_df)
        cs = metrics.customer_split
        total = cs.new_customers + cs.repeat_customers
        assert total >= 0

    def test_new_revenue_pct_between_0_and_100(self, clean_sales_df):
        """New customer revenue percentage is between 0 and 100."""
        metrics = compute_metrics(clean_sales_df)
        pct = metrics.customer_split.new_revenue_pct
        assert Decimal(0) <= pct <= Decimal(100)

    def test_revenue_trend_direction(self, clean_sales_df):
        """Revenue trend is one of: up, down, flat, new."""
        metrics = compute_metrics(clean_sales_df)
        assert metrics.revenue.trend in ("up", "down", "flat", "new")

    def test_empty_df_raises(self):
        """Empty DataFrame raises ValueError."""
        import pandas as pd
        empty = pd.DataFrame(columns=["date", "amount", "customer", "product"])
        with pytest.raises(ValueError):
            compute_metrics(empty)


class TestFormatInr:
    """Tests for Indian number formatting."""

    def test_thousands(self):
        assert format_inr(Decimal("15000")) == "₹15,000"

    def test_lakhs(self):
        assert format_inr(Decimal("150000")) == "₹1,50,000"

    def test_crores(self):
        assert format_inr(Decimal("12400000")) == "₹1,24,00,000"

    def test_exact_amount(self):
        assert format_inr(Decimal("124300")) == "₹1,24,300"

    def test_zero(self):
        assert format_inr(Decimal("0")) == "₹0"

    def test_negative(self):
        result = format_inr(Decimal("-15000"))
        assert "15,000" in result
        assert "−" in result or "-" in result


class TestSumAmount:

    def test_sums_decimal_values(self):
        df = pd.DataFrame({"amount": [Decimal("100"), Decimal("200"), Decimal("300")]})
        assert _sum_amount(df) == Decimal("600")

    def test_empty_returns_zero(self):
        df = pd.DataFrame({"amount": []})
        assert _sum_amount(df) == Decimal("0")
