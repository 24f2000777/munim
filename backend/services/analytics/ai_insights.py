"""
AI-Powered Business Insights
==============================
Calls Gemini to generate 4 specific, actionable insights from computed analytics.
Business-type-aware — a pharmacy gets different advice than a kirana store.
"""

import json
import logging
from dataclasses import dataclass

from config import settings

logger = logging.getLogger(__name__)


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
    Generate 4 business-specific insights via AI model router.
    Returns [] on any failure — non-blocking.
    """
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
    from services.ai.model_router import router as _router

    change_str = f"{change_pct:+.1f}%" if change_pct is not None else "first period (no comparison)"
    top_str = ", ".join(f"{p['name']} (₹{p['revenue']:,.0f})" for p in top_products[:5]) or "none"
    dead_str = ", ".join(f"{d['product']} ({d.get('days_since_sale', '?')} days)" for d in dead_stock[:5]) or "none"
    alert_str = "; ".join(f"{a['severity']}: {a['title']}" for a in anomalies[:4]) or "none"

    # Priority logic: warnings first if revenue dropped, celebrations first if growing
    revenue_dropped = change_pct is not None and change_pct < -10
    revenue_grew = change_pct is not None and change_pct > 15
    priority_guidance = ""
    if revenue_dropped:
        priority_guidance = "PRIORITY: Revenue dropped >10% — priority 1 MUST be a 'warning' insight."
    elif revenue_grew:
        priority_guidance = "PRIORITY: Revenue grew >15% — priority 1 MUST be a 'celebration' insight."
    if dead_stock:
        priority_guidance += " Include one 'action' insight about dead stock."

    prompt = f"""ROLE: You are a seasoned business consultant who has advised 1,000+ Indian small businesses — kirana stores, medical shops, restaurants, hardware shops, textile traders.

TASK: Generate exactly 4 actionable business insights from this sales data.

BUSINESS DATA:
Type: {business_type}
Period: {period_start} to {period_end} ({period_label})
Revenue now: ₹{current_revenue:,.0f}
Revenue before: ₹{previous_revenue:,.0f} | Change: {change_str}
Best sellers: {top_str}
Not selling: {dead_str}
Alerts found: {alert_str}
Customer count: {total_customers}

INSIGHT QUALITY CRITERIA (non-negotiable):
1. SPECIFIC — must reference actual numbers ("Atta revenue up ₹12,000 = 34% growth" not "revenue increased")
2. ACTIONABLE — must say exactly what to DO ("Reorder Atta this week — stock for 2 weeks", not "manage inventory")
3. SIMPLE — Class 8 English. No: CAGR, YoY, ROI, churn, cohort, elasticity, penetration
4. RELEVANT — specific to {business_type} context (a kirana insight ≠ a restaurant insight)

INSIGHT TYPES:
"opportunity" — specific growth action available RIGHT NOW
"warning"     — specific risk needing action within 7 days
"celebration" — genuine achievement worth acknowledging (boosts morale)
"action"      — concrete operational task: reorder, call customer, adjust price

{priority_guidance}

Return ONLY valid JSON array, no markdown, no explanation:
[
  {{"title": "Max 6 words", "insight": "2 sentences. Specific numbers. Tell them what to DO.", "type": "opportunity|warning|celebration|action", "priority": 1}},
  {{"title": "...", "insight": "...", "type": "...", "priority": 2}},
  {{"title": "...", "insight": "...", "type": "...", "priority": 3}},
  {{"title": "...", "insight": "...", "type": "...", "priority": 4}}
]"""

    raw = _router.call_text(prompt, max_tokens=800, temperature=0.3)
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
