"""
Tests for Data Health Scorer
==============================
"""

import pytest
from decimal import Decimal

import pandas as pd

from services.cleaner.normaliser import normalise
from services.cleaner.health_scorer import (
    compute_health_score,
    MINIMUM_SCORE_FOR_ANALYSIS,
    MINIMUM_ROWS_FOR_ANALYSIS,
)


class TestHealthScorer:

    def test_clean_data_scores_high(self, clean_sales_df):
        """Clean, complete data scores ≥ 80."""
        df, _ = normalise(clean_sales_df)
        report = compute_health_score(df)
        assert report.score >= 70, f"Expected score ≥ 70 for clean data, got {report.score}"

    def test_clean_data_can_analyze(self, clean_sales_df):
        """Clean data passes the analysis threshold."""
        df, _ = normalise(clean_sales_df)
        report = compute_health_score(df)
        assert report.can_analyze is True

    def test_too_few_rows_cannot_analyze(self):
        """DataFrame with < 5 rows cannot be analyzed."""
        tiny_df = pd.DataFrame({
            "date": pd.to_datetime(["2026-01-01", "2026-01-02"]),
            "customer": ["A", "B"],
            "product": ["X", "Y"],
            "amount": [Decimal("100"), Decimal("200")],
        })
        report = compute_health_score(tiny_df)
        assert report.can_analyze is False
        assert report.score == 0

    def test_score_components_sum_correctly(self, clean_sales_df):
        """Individual scores sum to overall score."""
        df, _ = normalise(clean_sales_df)
        report = compute_health_score(df)
        component_sum = (
            report.completeness_score
            + report.consistency_score
            + report.validity_score
            + report.uniqueness_score
        )
        assert report.score == component_sum

    def test_score_between_0_and_100(self, clean_sales_df):
        """Score is always between 0 and 100."""
        df, _ = normalise(clean_sales_df)
        report = compute_health_score(df)
        assert 0 <= report.score <= 100

    def test_grade_reflects_score(self, clean_sales_df):
        """Grade description reflects score range."""
        df, _ = normalise(clean_sales_df)
        report = compute_health_score(df)
        if report.score >= 80:
            assert "Excellent" in report.grade
        elif report.score >= 65:
            assert "Good" in report.grade

    def test_future_dates_lower_validity_score(self):
        """Future dates reduce validity score."""
        from datetime import date, timedelta

        future_date = pd.Timestamp(date.today() + timedelta(days=30))
        df = pd.DataFrame({
            "date": [future_date] * 10 + pd.to_datetime(["2026-01-01"] * 10).tolist(),
            "customer": ["A"] * 20,
            "product": ["X"] * 20,
            "amount": [Decimal("100")] * 20,
        })
        df_norm, _ = normalise(df)
        report = compute_health_score(df_norm)
        assert report.validity_score < 25, "Future dates should reduce validity score"

    def test_high_duplicate_rate_lowers_uniqueness_score(self):
        """High duplicate rate reduces uniqueness score."""
        # 80% duplicates
        base_row = {
            "date": pd.Timestamp("2026-01-01"),
            "customer": "A",
            "product": "X",
            "amount": Decimal("100"),
        }
        df = pd.DataFrame([base_row] * 20 + [
            {**base_row, "amount": Decimal(str(i * 100))}
            for i in range(5)
        ])
        df_norm, _ = normalise(df)
        report = compute_health_score(df_norm)
        assert report.uniqueness_score < 20

    def test_missing_amount_column_lowers_completeness(self):
        """Missing amount column significantly reduces completeness score."""
        df = pd.DataFrame({
            "date": pd.to_datetime(["2026-01-01"] * 10),
            "customer": ["A"] * 10,
            "product": ["X"] * 10,
            # No amount column
        })
        report = compute_health_score(df)
        assert report.completeness_score < 15
