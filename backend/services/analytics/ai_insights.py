"""
AI-Powered Business Insights
==============================
Calls Gemini to generate 4 specific, actionable insights from computed analytics.
Business-type-aware — a pharmacy gets different advice than a kirana store.
"""

import json
import logging
from dataclasses import dataclass

from google import genai

from config import settings

logger = logging.getLogger(__name__)
GEMINI_MODEL = "gemini-2.0-flash-lite"


@dataclass
class AiInsight:
    title: str    # Short, max 6 words
    insight: str  # 1-2 sentences, specific and actionable
    type: str     # "opportunity" | "warning" | "celebration" | "action"
    priority: int # 1 = most important


def generate_insights(
    business_type: str,
    period_start: str,
    period_end: str,
    period_label: str,
    current_revenue: float,
    previous_revenue: float,
    change_pct: float | None,
    top_products: list[dict],
    dead_stock: list[dict],
    anomalies: list[dict],
    total_customers: int,
) -> list[AiInsight]:
    """
    Generate 4 business-specific insights via Gemini.
    Returns [] on any failure — non-blocking.
    """
    if not settings.GOOGLE_API_KEY:
        return []
    try:
        return _call_gemini(
            business_type=business_type,
            period_start=period_start,
            period_end=period_end,
            period_label=period_label,
            current_revenue=current_revenue,
            previous_revenue=previous_revenue,
            change_pct=change_pct,
            top_products=top_products,
            dead_stock=dead_stock,
            anomalies=anomalies,
            total_customers=total_customers,
        )
    except Exception as exc:
        logger.warning("AI insight generation failed: %s", exc)
        return []


def _call_gemini(*, business_type, period_start, period_end, period_label,
                 current_revenue, previous_revenue, change_pct,
                 top_products, dead_stock, anomalies, total_customers) -> list[AiInsight]:
    client = genai.Client(api_key=settings.GOOGLE_API_KEY)

    change_str = f"{change_pct:+.1f}%" if change_pct is not None else "first period (no comparison)"
    top_str = ", ".join(f"{p['name']} (₹{p['revenue']:,.0f})" for p in top_products[:5]) or "none"
    dead_str = ", ".join(f"{d['product']} ({d.get('days_since_sale', '?')} days)" for d in dead_stock[:5]) or "none"
    alert_str = "; ".join(f"{a['severity']}: {a['title']}" for a in anomalies[:4]) or "none"

    prompt = f"""You are a senior business analyst advising an Indian {business_type} owner.

Their financial data summary:
- Analysis period: {period_start} to {period_end} ({period_label})
- Revenue this period: ₹{current_revenue:,.0f}
- Revenue previous period: ₹{previous_revenue:,.0f} (change: {change_str})
- Top selling items: {top_str}
- Slow/dead stock (not sold recently): {dead_str}
- Alerts detected: {alert_str}
- Total customers tracked: {total_customers}

Generate exactly 4 insights tailored to a {business_type}. Each must:
1. Reference specific numbers from the data above
2. Be actionable (tell them what to DO)
3. Be written in simple English any shopkeeper can understand
4. Be specific to the {business_type} business context

Return ONLY a valid JSON array, no markdown:
[
  {{
    "title": "<5-6 words max>",
    "insight": "<2 sentences max. First sentence states the observation with numbers. Second sentence tells them what to do.>",
    "type": "<exactly one of: opportunity | warning | celebration | action>",
    "priority": <integer 1-4, 1 is most urgent>
  }}
]"""

    response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    raw = response.text.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    items = json.loads(raw)
    insights = []
    for item in items[:4]:
        insights.append(AiInsight(
            title=item.get("title", "Business Insight"),
            insight=item.get("insight", ""),
            type=item.get("type", "action"),
            priority=int(item.get("priority", len(insights) + 1)),
        ))
    insights.sort(key=lambda x: x.priority)
    logger.info("Generated %d AI insights for business_type=%r", len(insights), business_type)
    return insights
