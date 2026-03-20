"""
Analysis Router
================
Returns analytics results for a processed upload.
All data was computed by the Celery pipeline and stored in analysis_results.

Endpoints:
  GET /api/v1/analysis/{upload_id}           — full analysis bundle
  GET /api/v1/analysis/{upload_id}/metrics   — revenue, top products, dead stock
  GET /api/v1/analysis/{upload_id}/anomalies — alerts sorted by severity
  GET /api/v1/analysis/{upload_id}/customers — RFM segments + top customers
  GET /api/v1/analysis/history               — paginated list of past analyses

Security:
  - Every query filters by user_id — users can never see each other's data.
  - RLS on Neon also enforces this at the DB level as a second layer.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from auth import AuthenticatedUser, get_current_user
from db.neon_client import get_db_session

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/{upload_id}")
async def get_full_analysis(
    upload_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Full analysis bundle — metrics + anomalies + customers + seasonality."""
    row = await _fetch_analysis(upload_id, current_user.user_id, db)
    return {
        "upload_id": upload_id,
        "analysis_id": str(row.id),
        "period_start": str(row.period_start),
        "period_end": str(row.period_end),
        "metrics": row.metrics,
        "anomalies": row.anomalies,
        "customers": row.customers,
        "seasonality_context": row.seasonality_context,
        "created_at": str(row.created_at),
    }


@router.get("/{upload_id}/metrics")
async def get_metrics(
    upload_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Revenue metrics, top products by revenue, and dead stock items."""
    row = await _fetch_analysis(upload_id, current_user.user_id, db)
    m = row.metrics or {}
    return {
        "upload_id": upload_id,
        "period_start": str(row.period_start),
        "period_end": str(row.period_end),
        "revenue": {
            "current": m.get("current_revenue", 0),
            "previous": m.get("previous_revenue", 0),
            "change_amount": m.get("change_amount", 0),
            "change_pct": m.get("change_pct"),
            "trend": m.get("trend", "flat"),
        },
        "top_products": m.get("top_products", []),
        "dead_stock": m.get("dead_stock", []),
        "dead_stock_count": m.get("dead_stock_count", 0),
    }


@router.get("/{upload_id}/anomalies")
async def get_anomalies(
    upload_id: str,
    severity: Optional[str] = Query(None, description="Filter by severity: HIGH, MEDIUM, LOW"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Anomaly alerts sorted by severity (HIGH first)."""
    if severity and severity not in ("HIGH", "MEDIUM", "LOW"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="severity must be HIGH, MEDIUM, or LOW",
        )

    row = await _fetch_analysis(upload_id, current_user.user_id, db)
    a = row.anomalies or {}
    alerts = a.get("anomalies", [])

    if severity:
        alerts = [x for x in alerts if x.get("severity") == severity]

    return {
        "upload_id": upload_id,
        "total_detected": a.get("total", len(alerts)),
        "high_count": a.get("high_count", 0),
        "medium_count": a.get("medium_count", 0),
        "low_count": a.get("low_count", 0),
        "anomalies": alerts,
    }


@router.get("/{upload_id}/customers")
async def get_customers(
    upload_id: str,
    segment: Optional[str] = Query(None, description="Filter by segment name"),
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """RFM customer segments and top customers by revenue."""
    row = await _fetch_analysis(upload_id, current_user.user_id, db)
    c = row.customers or {}
    top = c.get("top_customers", [])

    if segment:
        top = [x for x in top if x.get("segment", "").lower() == segment.lower()]

    return {
        "upload_id": upload_id,
        "total_customers": c.get("total", 0),
        "segments": c.get("segments", {}),
        "top_customers": top,
    }


@router.get("/history/list")
async def get_analysis_history(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Paginated list of past analyses for the authenticated user."""
    result = await db.execute(
        text("""
            SELECT
                ar.id::text,
                ar.upload_id::text,
                u.file_name,
                u.file_type,
                u.data_health_score,
                ar.period_start::text,
                ar.period_end::text,
                ar.created_at::text,
                (ar.metrics->>'current_revenue')::numeric AS current_revenue,
                (ar.metrics->>'trend') AS trend,
                (ar.anomalies->>'total')::int AS anomaly_count
            FROM analysis_results ar
            JOIN uploads u ON u.id = ar.upload_id
            WHERE ar.user_id = :user_id
            ORDER BY ar.created_at DESC
            LIMIT :limit OFFSET :offset
        """),
        {"user_id": current_user.user_id, "limit": limit, "offset": offset},
    )
    rows = result.fetchall()

    count_result = await db.execute(
        text("SELECT COUNT(*) FROM analysis_results WHERE user_id = :user_id"),
        {"user_id": current_user.user_id},
    )
    total = count_result.scalar()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "analysis_id": r.id,
                "upload_id": r.upload_id,
                "file_name": r.file_name,
                "file_type": r.file_type,
                "health_score": r.data_health_score,
                "period_start": r.period_start,
                "period_end": r.period_end,
                "current_revenue": float(r.current_revenue) if r.current_revenue else None,
                "trend": r.trend,
                "anomaly_count": r.anomaly_count or 0,
                "created_at": r.created_at,
            }
            for r in rows
        ],
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _fetch_analysis(upload_id: str, user_id: str, db: AsyncSession):
    """Fetch analysis_results row, ensuring it belongs to user_id."""
    result = await db.execute(
        text("""
            SELECT
                ar.id, ar.period_start, ar.period_end,
                ar.metrics, ar.anomalies, ar.customers,
                ar.seasonality_context, ar.created_at
            FROM analysis_results ar
            JOIN uploads u ON u.id = ar.upload_id
            WHERE ar.upload_id = :upload_id
              AND ar.user_id = :user_id
        """),
        {"upload_id": upload_id, "user_id": user_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not found. The file may still be processing.",
        )
    return row
