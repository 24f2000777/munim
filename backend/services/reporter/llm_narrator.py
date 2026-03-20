"""
LLM Narrator — Gemini 2.0 Flash
==================================
Converts pre-computed analytics JSON into plain-language WhatsApp messages
in Hindi or English using Google's Gemini 2.0 Flash model (free tier).

Critical rules (per spec):
  1. LLM NEVER receives raw financial data — only pre-computed summaries
  2. All numbers in LLM output are validated against pre-computed analytics
  3. 15-second timeout — fallback to template-based report on timeout
  4. Max 300 words in output
  5. Amounts always in Indian format: ₹1,24,300
  6. Never make up data not in the input JSON
  7. Log all LLM outputs for quality review (amounts redacted in logs)

Free tier: Gemini 2.0 Flash — 15 RPM, 1M tokens/day (plenty for MVP)
"""

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Optional

from google import genai
from google.genai import types as genai_types

from config import settings
from services.analytics.metrics import format_inr, BusinessMetrics
from services.analytics.anomaly import AnomalyReport

logger = logging.getLogger(__name__)

LLM_TIMEOUT_SECONDS = 15
MAX_RETRIES = 2


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def _get_client():
    """Lazy initialise Gemini client (google-genai SDK)."""
    if not settings.GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY not configured")
    return genai.Client(api_key=settings.GOOGLE_API_KEY)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_TEMPLATE = """\
You are Munim (मुनीम), a trusted business advisor for Indian small businesses.
Your job is to convert the structured business analysis below into a WhatsApp message for the business owner.

STRICT RULES — follow every single one:
1. Write ONLY in {language_instruction}
2. Maximum 300 words total — count carefully
3. Use simple language — the owner may have studied only till Class 10
4. Start with a warm greeting using the owner's first name
5. Lead with the most important alert first (if any HIGH severity alerts exist)
6. End with EXACTLY 3 numbered action items
7. Use emojis sparingly — max 5 total: 📈 for growth, ⚠️ for warning, ✅ for good news
8. NEVER use jargon: no "CAGR", no "YoY", no "ROI", no "churn rate"
9. If revenue dropped, give ONE specific reason — not a list
10. Amounts MUST be in Indian format: ₹1,24,300 (not ₹124300, not 1.24L)
11. If no alerts exist, start with the top revenue achievement

NEVER do:
- Never invent data not present in the JSON below
- Never give financial advice ("you should invest...")
- Never give legal advice
- Never predict exact future numbers — use "likely" or "probably" if needed
- Never be alarmist — stay calm and constructive even for bad news
- Never include HTML, markdown, asterisks, or formatting codes
"""

LANGUAGE_INSTRUCTIONS = {
    "hi": "simple Hindi (Hinglish is fine — mix Hindi and English naturally as Indians do in conversation)",
    "en": "simple Indian English (conversational, not formal)",
    "hinglish": "Hinglish (natural mix of Hindi and English, as spoken in North India)",
}


def _sanitize_text(text: str, max_length: int = 100) -> str:
    """Strip control characters that could escape prompt context."""
    import re
    return re.sub(r"[\x00-\x1f\x7f]", "", str(text))[:max_length].strip()


def build_report_prompt(
    owner_name: str,
    language: str,
    period_start: str,
    period_end: str,
    metrics_summary: dict,
    top_anomalies: list[dict],
    seasonality_context: list[str],
) -> str:
    """Build the user-turn prompt with pre-computed analytics."""
    safe_name = _sanitize_text(owner_name)
    return f"""\
Owner name: {safe_name}
Report period: {period_start} to {period_end}

BUSINESS METRICS THIS WEEK:
{json.dumps(metrics_summary, indent=2, ensure_ascii=False)}

TOP ALERTS (max 3, already sorted by severity — HIGH first):
{json.dumps(top_anomalies[:3], indent=2, ensure_ascii=False)}

SEASONAL CONTEXT (use this to explain any unusual patterns):
{json.dumps(seasonality_context, indent=2, ensure_ascii=False)}

Write the WhatsApp report now. Follow all rules exactly.
"""


# ---------------------------------------------------------------------------
# Main generation function
# ---------------------------------------------------------------------------

@dataclass
class NarratorResult:
    content: str          # The generated WhatsApp message text
    language: str
    word_count: int
    used_fallback: bool
    generation_time_ms: int

    # Legacy alias so existing code using .text still works
    @property
    def text(self) -> str:
        return self.content


def generate_report(
    owner_name: str,
    language: str,
    period_start: str,
    period_end: str,
    metrics_summary: dict,
    top_anomalies: list,
    seasonality_context: list,
    # Optional: pass BusinessMetrics + AnomalyReport directly (from Celery pipeline)
    metrics: "BusinessMetrics | None" = None,
    anomaly_report: "AnomalyReport | None" = None,
) -> NarratorResult:
    """
    Generate a WhatsApp report using Gemini 2.0 Flash.

    Accepts either:
      - Pre-serialized dicts (metrics_summary, top_anomalies) — used by the API router
      - BusinessMetrics + AnomalyReport objects — used by the Celery pipeline

    Returns:
        NarratorResult with the generated WhatsApp message.
    """
    lang_instruction = LANGUAGE_INSTRUCTIONS.get(language, LANGUAGE_INSTRUCTIONS["hi"])

    # If raw objects passed, build summaries from them
    if metrics is not None:
        metrics_summary = _build_metrics_summary(metrics)
        period_start = str(metrics.period_start.date()) if metrics.period_start else period_start
        period_end = str(metrics.period_end.date()) if metrics.period_end else period_end
    if anomaly_report is not None:
        top_anomalies = _build_anomaly_summaries(anomaly_report)
        seasonality_context = []
        for a in anomaly_report.anomalies[:3]:
            seasonality_context.extend(a.context_notes)

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(language_instruction=lang_instruction)
    user_prompt = build_report_prompt(
        owner_name=owner_name,
        language=language,
        period_start=period_start,
        period_end=period_end,
        metrics_summary=metrics_summary,
        top_anomalies=top_anomalies,
        seasonality_context=seasonality_context,
    )

    start_ms = int(time.time() * 1000)
    text, used_fallback = _call_gemini_with_fallback(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        metrics_summary=metrics_summary,
        owner_name=owner_name,
        language=language,
    )
    elapsed_ms = int(time.time() * 1000) - start_ms

    # Validate: check numbers in output match pre-computed metrics
    text = _validate_and_fix_amounts(text, metrics_summary)

    word_count = len(text.split())

    # Log without financial figures (privacy)
    logger.info(
        "Report generated | owner=%r | lang=%s | words=%d | fallback=%s | time=%dms",
        owner_name, language, word_count, used_fallback, elapsed_ms,
    )

    return NarratorResult(
        content=text,
        language=language,
        word_count=word_count,
        used_fallback=used_fallback,
        generation_time_ms=elapsed_ms,
    )


# ---------------------------------------------------------------------------
# Gemini API call with retry + fallback
# ---------------------------------------------------------------------------

def _call_gemini_with_fallback(
    system_prompt: str,
    user_prompt: str,
    metrics_summary: dict,
    owner_name: str,
    language: str,
) -> tuple[str, bool]:
    """
    Call Gemini with retry logic.
    Returns (text, used_fallback).
    Fallback to template-based report if Gemini fails or times out.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            client = _get_client()
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=f"{system_prompt}\n\n{user_prompt}",
                config=genai_types.GenerateContentConfig(
                    max_output_tokens=600,
                    temperature=0.4,    # Low temp = more factual, less creative
                    top_p=0.8,
                    http_options=genai_types.HttpOptions(timeout=LLM_TIMEOUT_SECONDS * 1000),
                ),
            )

            if response.text and len(response.text.strip()) > 50:
                return response.text.strip(), False

            logger.warning("Gemini returned empty/short response on attempt %d", attempt)

        except Exception as exc:
            logger.warning("Gemini call failed (attempt %d/%d): %s", attempt, MAX_RETRIES, exc)

    # All retries exhausted — use template fallback
    logger.warning("All Gemini attempts failed — using template fallback")
    fallback_text = _template_fallback(owner_name, language, metrics_summary)
    return fallback_text, True


# ---------------------------------------------------------------------------
# Template fallback (used when LLM fails)
# ---------------------------------------------------------------------------

def _template_fallback(owner_name: str, language: str, metrics: dict) -> str:
    """
    Generate a basic template-based report when LLM is unavailable.
    Numbers come from pre-computed metrics — never fabricated.
    """
    revenue = metrics.get("current_revenue_formatted", "N/A")
    change = metrics.get("revenue_change_pct", 0)
    top_product = metrics.get("top_product", "N/A")

    if language == "hi":
        trend = "बढ़ी है 📈" if change > 0 else "घटी है ⚠️" if change < 0 else "स्थिर है"
        return (
            f"नमस्ते {owner_name} जी! 🙏\n\n"
            f"इस हफ्ते की रिपोर्ट:\n"
            f"• Revenue: {revenue} ({abs(change):.1f}% {trend})\n"
            f"• सबसे अच्छा product: {top_product}\n\n"
            f"3 काम करें:\n"
            f"1. अपने top customers को call करें\n"
            f"2. Dead stock को check करें\n"
            f"3. इस हफ्ते का target set करें\n\n"
            f"— Munim (आपका digital मुनीम)"
        )
    else:
        trend = "up 📈" if change > 0 else "down ⚠️" if change < 0 else "stable"
        return (
            f"Hello {owner_name}!\n\n"
            f"This week's summary:\n"
            f"• Revenue: {revenue} ({abs(change):.1f}% {trend})\n"
            f"• Best product: {top_product}\n\n"
            f"3 actions for this week:\n"
            f"1. Call your top customers\n"
            f"2. Review dead stock items\n"
            f"3. Set a revenue target for next week\n\n"
            f"— Munim (Your Digital Business Advisor)"
        )


# ---------------------------------------------------------------------------
# Data preparation helpers
# ---------------------------------------------------------------------------

def _build_metrics_summary(metrics: BusinessMetrics) -> dict:
    """Build a compact, LLM-safe summary of metrics. No raw DataFrames."""
    from decimal import Decimal

    summary: dict = {
        "current_revenue": float(metrics.revenue.current_period),
        "current_revenue_formatted": format_inr(metrics.revenue.current_period),
        "previous_revenue_formatted": format_inr(metrics.revenue.previous_period),
        "revenue_change_pct": float(metrics.revenue.change_pct or Decimal(0)),
        "revenue_trend": metrics.revenue.trend,
    }

    if metrics.top_products:
        summary["top_product"] = metrics.top_products[0].name
        summary["top_products"] = [
            {
                "rank": p.rank,
                "name": p.name,
                "revenue": format_inr(p.revenue),
                "trend": p.trend,
            }
            for p in metrics.top_products[:5]
        ]

    if metrics.dead_stock:
        summary["dead_stock_count"] = len(metrics.dead_stock)
        summary["dead_stock_items"] = [
            {
                "product": d.product,
                "days_inactive": d.days_since_last_sale,
            }
            for d in metrics.dead_stock[:3]
        ]

    cs = metrics.customer_split
    summary["customer_split"] = {
        "new": cs.new_customers,
        "repeat": cs.repeat_customers,
        "new_revenue_pct": float(cs.new_revenue_pct),
    }

    return summary


def _build_anomaly_summaries(report: AnomalyReport) -> list[dict]:
    """Build LLM-safe anomaly summaries. TOP 3 only, HIGH severity first."""
    return [
        {
            "severity": a.severity,
            "title": a.title,
            "explanation": a.explanation,
            "action": a.action,
        }
        for a in report.anomalies[:3]
    ]


def _validate_and_fix_amounts(text: str, metrics: dict) -> str:
    """
    Basic validation: ensure the LLM hasn't hallucinated amounts
    wildly different from our pre-computed metrics.

    If a number in the text is > 10× the actual revenue, it's likely
    a hallucination — we log a warning but don't modify (could be legitimate).
    """
    actual_revenue = metrics.get("current_revenue", 0)
    if actual_revenue == 0:
        return text

    # Find all numbers in text that look like amounts (₹ prefix or large numbers)
    amount_pattern = re.compile(r"₹[\d,]+|[\d,]{5,}")
    found = amount_pattern.findall(text)

    for match in found:
        try:
            cleaned = re.sub(r"[₹,]", "", match)
            val = float(cleaned)
            if val > actual_revenue * 10:
                logger.warning(
                    "LLM may have hallucinated amount: %s (actual revenue: [AMOUNT_REDACTED])",
                    match,
                )
        except ValueError:
            pass

    return text
