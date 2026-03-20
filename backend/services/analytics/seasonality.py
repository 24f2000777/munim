"""
India Seasonality Engine
=========================
Hardcoded Indian business calendar for contextualising revenue changes.

Before flagging any revenue dip as a HIGH anomaly, the anomaly detector
calls this engine to check if the period falls within ±N days of a known
seasonal event. If yes, severity is downgraded from HIGH → MEDIUM with
a context note explaining the expected seasonal pattern.

Events covered:
  - Major Hindu festivals (Diwali, Holi, Navratri, Dussehra, etc.)
  - School calendar (admissions, reopening, exams)
  - Agricultural cycles (harvest, sowing)
  - Government/GST deadlines
  - National holidays with payment delays

Date calculation:
  - Fixed-date events: hardcoded (Republic Day, Independence Day)
  - Lunar calendar events: approximate Gregorian dates per year
    (We hardcode 2024–2027 which covers our operational horizon)
"""

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

CONTEXT_WINDOW_DAYS = 14  # ± days around event to consider "in season"


@dataclass
class SeasonalEvent:
    name: str
    name_hindi: str
    date_range: tuple[date, date]          # (start, end) inclusive
    expected_impact: str                   # "spike" | "dip" | "mixed"
    affected_industries: list[str]         # Empty = all industries
    context_note: str                      # Plain English explanation for report


@dataclass
class SeasonalContext:
    """Result of checking a date/period against the calendar."""
    in_season: bool
    events: list[SeasonalEvent]
    severity_modifier: str    # "downgrade" | "upgrade" | "none"
    context_notes: list[str]  # Ready to include in LLM prompt


# ---------------------------------------------------------------------------
# Festival calendar — 2024 to 2027
# Approximate Gregorian dates for lunar events.
# Source: widely published Indian festival calendars.
# ---------------------------------------------------------------------------

_EVENTS: list[SeasonalEvent] = [

    # === DIWALI (Oct–Nov) ===
    # Retail, FMCG spike; electronics, clothing, gifts surge
    SeasonalEvent(
        name="Diwali Season",
        name_hindi="दीवाली",
        date_range=(date(2024, 10, 29), date(2024, 11, 15)),
        expected_impact="spike",
        affected_industries=["retail", "fmcg", "electronics", "clothing", "sweets"],
        context_note="Diwali season — expect 30–50% revenue spike in retail/FMCG. "
                     "B2B collections may slow as businesses are in festival mode.",
    ),
    SeasonalEvent(
        name="Diwali Season",
        name_hindi="दीवाली",
        date_range=(date(2025, 10, 18), date(2025, 11, 3)),
        expected_impact="spike",
        affected_industries=["retail", "fmcg", "electronics", "clothing", "sweets"],
        context_note="Diwali season — expect 30–50% revenue spike in retail/FMCG.",
    ),
    SeasonalEvent(
        name="Diwali Season",
        name_hindi="दीवाली",
        date_range=(date(2026, 11, 7), date(2026, 11, 22)),
        expected_impact="spike",
        affected_industries=["retail", "fmcg", "electronics", "clothing", "sweets"],
        context_note="Diwali season — expect 30–50% revenue spike in retail/FMCG.",
    ),

    # === POST-DIWALI DIP ===
    SeasonalEvent(
        name="Post-Diwali Slowdown",
        name_hindi="दीवाली के बाद",
        date_range=(date(2024, 11, 16), date(2024, 11, 30)),
        expected_impact="dip",
        affected_industries=[],
        context_note="Post-Diwali period — consumer spending typically drops sharply "
                     "as budgets are exhausted. A revenue dip here is normal.",
    ),
    SeasonalEvent(
        name="Post-Diwali Slowdown",
        name_hindi="दीवाली के बाद",
        date_range=(date(2025, 11, 4), date(2025, 11, 20)),
        expected_impact="dip",
        affected_industries=[],
        context_note="Post-Diwali period — consumer spending typically drops sharply.",
    ),
    SeasonalEvent(
        name="Post-Diwali Slowdown",
        name_hindi="दीवाली के बाद",
        date_range=(date(2026, 11, 23), date(2026, 12, 7)),
        expected_impact="dip",
        affected_industries=[],
        context_note="Post-Diwali period — consumer spending typically drops sharply.",
    ),

    # === NAVRATRI (Sep–Oct, North India) ===
    # Fasting impacts food/restaurant; clothing, jewellery spike
    SeasonalEvent(
        name="Navratri",
        name_hindi="नवरात्रि",
        date_range=(date(2024, 10, 3), date(2024, 10, 12)),
        expected_impact="mixed",
        affected_industries=["food", "fmcg", "clothing", "jewellery"],
        context_note="Navratri — fasting reduces certain food sales in North India. "
                     "Clothing and jewellery see a spike.",
    ),
    SeasonalEvent(
        name="Navratri",
        name_hindi="नवरात्रि",
        date_range=(date(2025, 9, 22), date(2025, 10, 1)),
        expected_impact="mixed",
        affected_industries=["food", "fmcg", "clothing", "jewellery"],
        context_note="Navratri — fasting reduces certain food sales in North India.",
    ),
    SeasonalEvent(
        name="Navratri",
        name_hindi="नवरात्रि",
        date_range=(date(2026, 10, 11), date(2026, 10, 20)),
        expected_impact="mixed",
        affected_industries=["food", "fmcg", "clothing", "jewellery"],
        context_note="Navratri — fasting reduces certain food sales in North India.",
    ),

    # === HOLI (Mar) ===
    SeasonalEvent(
        name="Holi",
        name_hindi="होली",
        date_range=(date(2025, 3, 13), date(2025, 3, 17)),
        expected_impact="spike",
        affected_industries=["retail", "fmcg", "clothing", "sweets"],
        context_note="Holi festival — spike in colors, sweets, clothing. "
                     "Business activity pauses for 2–3 days around the main day.",
    ),
    SeasonalEvent(
        name="Holi",
        name_hindi="होली",
        date_range=(date(2026, 3, 2), date(2026, 3, 6)),
        expected_impact="spike",
        affected_industries=["retail", "fmcg", "clothing", "sweets"],
        context_note="Holi festival — spike in colors, sweets, clothing.",
    ),

    # === SCHOOL REOPENING — JUNE ===
    SeasonalEvent(
        name="School Reopening (Summer)",
        name_hindi="स्कूल खुलना (गर्मी)",
        date_range=(date(2025, 6, 1), date(2025, 6, 20)),
        expected_impact="spike",
        affected_industries=["stationery", "bags", "shoes", "clothing", "books"],
        context_note="Schools reopen after summer break — spike in stationery, "
                     "school bags, shoes, and uniforms.",
    ),
    SeasonalEvent(
        name="School Reopening (Summer)",
        name_hindi="स्कूल खुलना (गर्मी)",
        date_range=(date(2026, 6, 1), date(2026, 6, 20)),
        expected_impact="spike",
        affected_industries=["stationery", "bags", "shoes", "clothing", "books"],
        context_note="Schools reopen after summer break — spike in stationery and school supplies.",
    ),

    # === SCHOOL REOPENING — JANUARY ===
    SeasonalEvent(
        name="School Reopening (Winter)",
        name_hindi="स्कूल खुलना (सर्दी)",
        date_range=(date(2025, 1, 2), date(2025, 1, 15)),
        expected_impact="spike",
        affected_industries=["stationery", "books", "clothing"],
        context_note="New academic semester — stationery and book sales spike.",
    ),
    SeasonalEvent(
        name="School Reopening (Winter)",
        name_hindi="स्कूल खुलना (सर्दी)",
        date_range=(date(2026, 1, 2), date(2026, 1, 15)),
        expected_impact="spike",
        affected_industries=["stationery", "books", "clothing"],
        context_note="New academic semester — stationery and book sales spike.",
    ),

    # === GST FILING DEADLINES (20th of each month) ===
    # CA clients are distracted; B2B payments may be delayed
    *[
        SeasonalEvent(
            name=f"GST Filing Deadline ({month} {year})",
            name_hindi="GST भरने का समय",
            date_range=(date(year, month, 18), date(year, month, 22)),
            expected_impact="dip",
            affected_industries=[],
            context_note=f"GST filing deadline week — CA firms and businesses are occupied with compliance. "
                         f"B2B payment collections often slow by 15–20% this week.",
        )
        for year in (2025, 2026)
        for month in range(1, 13)
    ],

    # === YEAR-END (March) ===
    SeasonalEvent(
        name="Financial Year End",
        name_hindi="वित्तीय वर्ष समाप्ति",
        date_range=(date(2025, 3, 20), date(2025, 3, 31)),
        expected_impact="spike",
        affected_industries=[],
        context_note="Indian financial year closes on March 31 — many businesses "
                     "rush to complete purchases and clear invoices. Revenue spike is common.",
    ),
    SeasonalEvent(
        name="Financial Year End",
        name_hindi="वित्तीय वर्ष समाप्ति",
        date_range=(date(2026, 3, 20), date(2026, 3, 31)),
        expected_impact="spike",
        affected_industries=[],
        context_note="Indian financial year closes on March 31 — revenue spike common.",
    ),

    # === REPUBLIC DAY (Jan 26) ===
    SeasonalEvent(
        name="Republic Day",
        name_hindi="गणतंत्र दिवस",
        date_range=(date(2025, 1, 24), date(2025, 1, 28)),
        expected_impact="dip",
        affected_industries=[],
        context_note="Republic Day holiday — government offices and many businesses closed. "
                     "Government contractor payments often delayed.",
    ),
    SeasonalEvent(
        name="Republic Day",
        name_hindi="गणतंत्र दिवस",
        date_range=(date(2026, 1, 23), date(2026, 1, 27)),
        expected_impact="dip",
        affected_industries=[],
        context_note="Republic Day holiday — business activity pauses for 2–3 days.",
    ),

    # === INDEPENDENCE DAY (Aug 15) ===
    SeasonalEvent(
        name="Independence Day",
        name_hindi="स्वतंत्रता दिवस",
        date_range=(date(2025, 8, 13), date(2025, 8, 17)),
        expected_impact="dip",
        affected_industries=[],
        context_note="Independence Day holiday — business activity dip expected.",
    ),
    SeasonalEvent(
        name="Independence Day",
        name_hindi="स्वतंत्रता दिवस",
        date_range=(date(2026, 8, 13), date(2026, 8, 17)),
        expected_impact="dip",
        affected_industries=[],
        context_note="Independence Day holiday — business activity dip expected.",
    ),

    # === HARVEST SEASON (Rabi — Nov–Jan, Kharif — Jul–Sep) ===
    SeasonalEvent(
        name="Rabi Harvest Season",
        name_hindi="रबी फसल",
        date_range=(date(2025, 11, 1), date(2026, 1, 31)),
        expected_impact="spike",
        affected_industries=["agricultural inputs", "hardware", "wholesale"],
        context_note="Rabi harvest season — farmers have cash. Agricultural input "
                     "demand and rural retail spending typically spike.",
    ),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_seasonal_context(
    period_start: date | pd.Timestamp,
    period_end: date | pd.Timestamp,
    industry: Optional[str] = None,
) -> SeasonalContext:
    """
    Check if a given date range overlaps with any known seasonal events.

    Args:
        period_start: Start of the analysis period.
        period_end:   End of the analysis period.
        industry:     Optional industry tag to filter relevant events.
                      None = return all events.

    Returns:
        SeasonalContext with matching events and severity modifier.
    """
    # Normalise to date objects
    if isinstance(period_start, pd.Timestamp):
        period_start = period_start.date()
    if isinstance(period_end, pd.Timestamp):
        period_end = period_end.date()

    matching_events: list[SeasonalEvent] = []

    for event in _EVENTS:
        event_start, event_end = event.date_range

        # Check overlap: periods overlap if start1 <= end2 AND start2 <= end1
        if period_start <= event_end and event_start <= period_end:
            # Industry filter
            if industry and event.affected_industries:
                if not any(industry.lower() in ind.lower() or ind.lower() in industry.lower()
                           for ind in event.affected_industries):
                    continue
            matching_events.append(event)

    context_notes = [e.context_note for e in matching_events]

    # Determine severity modifier
    if not matching_events:
        modifier = "none"
    elif any(e.expected_impact == "dip" for e in matching_events):
        modifier = "downgrade"   # Revenue dip near a known dip event → not alarming
    elif any(e.expected_impact == "spike" for e in matching_events):
        modifier = "upgrade"     # Revenue spike near spike event → expected, raise bar
    else:
        modifier = "downgrade"   # Mixed events → be conservative

    return SeasonalContext(
        in_season=len(matching_events) > 0,
        events=matching_events,
        severity_modifier=modifier,
        context_notes=context_notes,
    )


def is_anomaly_seasonal(
    anomaly_date: date | pd.Timestamp,
    anomaly_type: str = "revenue_dip",
    industry: Optional[str] = None,
) -> tuple[bool, list[str]]:
    """
    Convenience function: check if a specific anomaly date is seasonal.

    Returns:
        (is_seasonal: bool, context_notes: list[str])
    """
    window_start = anomaly_date - timedelta(days=CONTEXT_WINDOW_DAYS)
    window_end = anomaly_date + timedelta(days=CONTEXT_WINDOW_DAYS)

    ctx = get_seasonal_context(window_start, window_end, industry)
    return ctx.in_season, ctx.context_notes
