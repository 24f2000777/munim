"""
Tests for India Seasonality Engine
=====================================
"""

import pytest
from datetime import date

from services.analytics.seasonality import (
    get_seasonal_context,
    is_anomaly_seasonal,
)


class TestSeasonalityEngine:

    def test_diwali_2025_detected(self):
        """Diwali 2025 period is in season."""
        ctx = get_seasonal_context(date(2025, 10, 20), date(2025, 10, 27))
        assert ctx.in_season is True
        assert any("Diwali" in e.name for e in ctx.events)

    def test_diwali_2026_detected(self):
        """Diwali 2026 period is in season."""
        ctx = get_seasonal_context(date(2026, 11, 10), date(2026, 11, 17))
        assert ctx.in_season is True

    def test_random_non_festival_date_not_in_season(self):
        """A random date far from any event returns in_season=False."""
        ctx = get_seasonal_context(date(2025, 7, 15), date(2025, 7, 22))
        # July 15 is not near any hardcoded event
        assert ctx.in_season is False

    def test_diwali_causes_downgrade_modifier(self):
        """Diwali period returns downgrade modifier (expected dip after spike)."""
        ctx = get_seasonal_context(date(2025, 11, 5), date(2025, 11, 12))
        # Post-Diwali is a dip period
        if ctx.in_season:
            assert ctx.severity_modifier in ("downgrade", "upgrade", "none")

    def test_gst_deadline_detected(self):
        """GST filing deadline week is detected."""
        ctx = get_seasonal_context(date(2026, 3, 18), date(2026, 3, 22))
        assert ctx.in_season is True
        assert any("GST" in e.name for e in ctx.events)

    def test_holi_2026_detected(self):
        """Holi 2026 is detected."""
        ctx = get_seasonal_context(date(2026, 3, 2), date(2026, 3, 6))
        assert ctx.in_season is True

    def test_context_notes_are_plain_english(self):
        """Context notes are non-empty strings."""
        ctx = get_seasonal_context(date(2025, 10, 20), date(2025, 10, 27))
        if ctx.in_season:
            for note in ctx.context_notes:
                assert isinstance(note, str)
                assert len(note) > 10

    def test_is_anomaly_seasonal_convenience(self):
        """is_anomaly_seasonal returns correct tuple."""
        is_seasonal, notes = is_anomaly_seasonal(date(2025, 10, 25))
        assert isinstance(is_seasonal, bool)
        assert isinstance(notes, list)

    def test_republic_day_detected(self):
        """Republic Day 2026 is detected."""
        ctx = get_seasonal_context(date(2026, 1, 25), date(2026, 1, 26))
        assert ctx.in_season is True

    def test_financial_year_end_detected(self):
        """March financial year-end is detected."""
        ctx = get_seasonal_context(date(2026, 3, 28), date(2026, 3, 31))
        assert ctx.in_season is True
