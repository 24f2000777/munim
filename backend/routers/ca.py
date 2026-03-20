"""
CA Console Router
==================
CA (Chartered Accountant) firms manage multiple SMB clients through this router.
Each CA firm can have 50–200 clients, each with their own upload history,
analysis results, and WhatsApp report preferences.

Endpoints:
  GET    /api/v1/ca/dashboard                          — portfolio overview
  GET    /api/v1/ca/clients                            — list all clients
  POST   /api/v1/ca/clients                            — add new client
  GET    /api/v1/ca/clients/{client_id}                — client detail
  PUT    /api/v1/ca/clients/{client_id}                — update client
  DELETE /api/v1/ca/clients/{client_id}                — deactivate client
  GET    /api/v1/ca/clients/{client_id}/uploads        — client's upload history

Security:
  - All endpoints require JWT.
  - Enforces user_type = 'ca_firm' — SMB owners cannot use this console.
  - All queries filter by ca_user_id to prevent cross-CA data access.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from auth import AuthenticatedUser, get_current_user
from db.neon_client import get_db_session

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CAClientCreate(BaseModel):
    client_name: str
    client_phone: Optional[str] = None
    client_email: Optional[EmailStr] = None
    white_label_name: Optional[str] = None
    white_label_logo_url: Optional[str] = None
    language_preference: str = "hi"

    @field_validator("language_preference")
    @classmethod
    def validate_language(cls, v: str) -> str:
        if v not in ("hi", "en", "hinglish"):
            raise ValueError("language_preference must be 'hi', 'en', or 'hinglish'")
        return v

    @field_validator("client_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("client_name must be at least 2 characters")
        if len(v) > 200:
            raise ValueError("client_name must be at most 200 characters")
        return v


class CAClientUpdate(BaseModel):
    client_name: Optional[str] = None
    client_phone: Optional[str] = None
    client_email: Optional[EmailStr] = None
    white_label_name: Optional[str] = None
    white_label_logo_url: Optional[str] = None
    language_preference: Optional[str] = None
    whatsapp_opted_in: Optional[bool] = None
    active: Optional[bool] = None

    @field_validator("language_preference")
    @classmethod
    def validate_language(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("hi", "en", "hinglish"):
            raise ValueError("language_preference must be 'hi', 'en', or 'hinglish'")
        return v


# ---------------------------------------------------------------------------
# Dependency: enforce CA-only access
# ---------------------------------------------------------------------------

async def _require_ca(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> AuthenticatedUser:
    """Raises 403 if the authenticated user is not a CA firm."""
    result = await db.execute(
        text("SELECT user_type FROM users WHERE email = :email"),
        {"email": current_user.email},
    )
    row = result.fetchone()
    if not row or row.user_type != "ca_firm":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is only accessible to CA firms.",
        )
    return current_user


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/dashboard")
async def get_dashboard(
    ca_user: AuthenticatedUser = Depends(_require_ca),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Portfolio overview for the CA firm:
    - Total clients, active clients
    - Total uploads across all clients
    - Clients with recent anomalies (HIGH severity)
    - Clients with no uploads in 30+ days (at risk)
    """
    result = await db.execute(
        text("""
            WITH client_stats AS (
                SELECT
                    c.id,
                    c.client_name,
                    c.active,
                    COUNT(u.id) AS upload_count,
                    MAX(u.created_at) AS last_upload_at,
                    AVG(u.data_health_score) AS avg_health_score
                FROM ca_clients c
                LEFT JOIN uploads u ON u.ca_client_id = c.id
                WHERE c.ca_user_id = :ca_id
                GROUP BY c.id, c.client_name, c.active
            )
            SELECT
                COUNT(*) AS total_clients,
                COUNT(*) FILTER (WHERE active) AS active_clients,
                COALESCE(SUM(upload_count), 0) AS total_uploads,
                COUNT(*) FILTER (
                    WHERE last_upload_at < NOW() - INTERVAL '30 days'
                    OR last_upload_at IS NULL
                ) AS clients_at_risk,
                ROUND(AVG(avg_health_score)) AS portfolio_health_score
            FROM client_stats
        """),
        {"ca_id": ca_user.user_id},
    )
    stats = result.fetchone()

    # Clients with recent HIGH anomalies
    alerts_result = await db.execute(
        text("""
            SELECT DISTINCT
                c.id::text,
                c.client_name,
                ar.anomalies->>'high_count' AS high_alerts,
                ar.period_end::text
            FROM ca_clients c
            JOIN uploads u ON u.ca_client_id = c.id
            JOIN analysis_results ar ON ar.upload_id = u.id
            WHERE c.ca_user_id = :ca_id
              AND (ar.anomalies->>'high_count')::int > 0
              AND ar.created_at > NOW() - INTERVAL '7 days'
            ORDER BY high_alerts DESC
            LIMIT 5
        """),
        {"ca_id": ca_user.user_id},
    )
    alert_clients = alerts_result.fetchall()

    return {
        "total_clients": stats.total_clients or 0,
        "active_clients": stats.active_clients or 0,
        "total_uploads": stats.total_uploads or 0,
        "clients_at_risk": stats.clients_at_risk or 0,
        "portfolio_health_score": int(stats.portfolio_health_score or 0),
        "clients_with_high_alerts": [
            {
                "client_id": r.id,
                "client_name": r.client_name,
                "high_alerts": int(r.high_alerts or 0),
                "period_end": r.period_end,
            }
            for r in alert_clients
        ],
    }


@router.get("/clients")
async def list_clients(
    active_only: bool = Query(True),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    ca_user: AuthenticatedUser = Depends(_require_ca),
    db: AsyncSession = Depends(get_db_session),
):
    """List all clients for this CA firm, with upload counts."""
    where_active = "AND c.active = TRUE" if active_only else ""

    result = await db.execute(
        text(f"""
            SELECT
                c.id::text,
                c.client_name,
                c.client_phone,
                c.client_email,
                c.white_label_name,
                c.language_preference,
                c.whatsapp_opted_in,
                c.active,
                c.created_at::text,
                COUNT(u.id) AS upload_count,
                MAX(u.created_at)::text AS last_upload_at,
                MAX(u.data_health_score) AS latest_health_score
            FROM ca_clients c
            LEFT JOIN uploads u ON u.ca_client_id = c.id
            WHERE c.ca_user_id = :ca_id {where_active}
            GROUP BY c.id, c.client_name, c.client_phone, c.client_email,
                     c.white_label_name, c.language_preference,
                     c.whatsapp_opted_in, c.active, c.created_at
            ORDER BY c.client_name
            LIMIT :limit OFFSET :offset
        """),
        {"ca_id": ca_user.user_id, "limit": limit, "offset": offset},
    )
    rows = result.fetchall()

    count_result = await db.execute(
        text(f"""
            SELECT COUNT(*) FROM ca_clients
            WHERE ca_user_id = :ca_id {where_active}
        """),
        {"ca_id": ca_user.user_id},
    )
    total = count_result.scalar()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "client_id": r.id,
                "client_name": r.client_name,
                "client_phone": r.client_phone,
                "client_email": r.client_email,
                "white_label_name": r.white_label_name,
                "language_preference": r.language_preference,
                "whatsapp_opted_in": r.whatsapp_opted_in,
                "active": r.active,
                "upload_count": r.upload_count,
                "last_upload_at": r.last_upload_at,
                "latest_health_score": r.latest_health_score,
                "created_at": r.created_at,
            }
            for r in rows
        ],
    }


@router.post("/clients", status_code=status.HTTP_201_CREATED)
async def create_client(
    payload: CAClientCreate,
    ca_user: AuthenticatedUser = Depends(_require_ca),
    db: AsyncSession = Depends(get_db_session),
):
    """Add a new SMB client to the CA firm's portfolio."""
    result = await db.execute(
        text("""
            INSERT INTO ca_clients (
                ca_user_id, client_name, client_phone, client_email,
                white_label_name, white_label_logo_url, language_preference
            ) VALUES (
                :ca_id, :name, :phone, :email,
                :wl_name, :wl_logo, :lang
            )
            RETURNING id::text, client_name, client_phone, client_email,
                      white_label_name, language_preference,
                      whatsapp_opted_in, active, created_at::text
        """),
        {
            "ca_id": ca_user.user_id,
            "name": payload.client_name,
            "phone": payload.client_phone,
            "email": str(payload.client_email) if payload.client_email else None,
            "wl_name": payload.white_label_name,
            "wl_logo": payload.white_label_logo_url,
            "lang": payload.language_preference,
        },
    )
    await db.commit()
    row = result.fetchone()

    return {
        "client_id": row.id,
        "client_name": row.client_name,
        "client_phone": row.client_phone,
        "client_email": row.client_email,
        "white_label_name": row.white_label_name,
        "language_preference": row.language_preference,
        "whatsapp_opted_in": row.whatsapp_opted_in,
        "active": row.active,
        "created_at": row.created_at,
    }


@router.get("/clients/{client_id}")
async def get_client(
    client_id: str,
    ca_user: AuthenticatedUser = Depends(_require_ca),
    db: AsyncSession = Depends(get_db_session),
):
    """Get detailed info for a specific client including recent uploads."""
    result = await db.execute(
        text("""
            SELECT
                c.id::text, c.client_name, c.client_phone, c.client_email,
                c.white_label_name, c.white_label_logo_url, c.language_preference,
                c.whatsapp_opted_in, c.active, c.created_at::text,
                COUNT(u.id) AS upload_count,
                MAX(u.data_health_score) AS latest_health_score,
                MAX(u.created_at)::text AS last_upload_at
            FROM ca_clients c
            LEFT JOIN uploads u ON u.ca_client_id = c.id
            WHERE c.id = :client_id AND c.ca_user_id = :ca_id
            GROUP BY c.id, c.client_name, c.client_phone, c.client_email,
                     c.white_label_name, c.white_label_logo_url, c.language_preference,
                     c.whatsapp_opted_in, c.active, c.created_at
        """),
        {"client_id": client_id, "ca_id": ca_user.user_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found.")

    return {
        "client_id": row.id,
        "client_name": row.client_name,
        "client_phone": row.client_phone,
        "client_email": row.client_email,
        "white_label_name": row.white_label_name,
        "white_label_logo_url": row.white_label_logo_url,
        "language_preference": row.language_preference,
        "whatsapp_opted_in": row.whatsapp_opted_in,
        "active": row.active,
        "upload_count": row.upload_count,
        "latest_health_score": row.latest_health_score,
        "last_upload_at": row.last_upload_at,
        "created_at": row.created_at,
    }


@router.put("/clients/{client_id}")
async def update_client(
    client_id: str,
    payload: CAClientUpdate,
    ca_user: AuthenticatedUser = Depends(_require_ca),
    db: AsyncSession = Depends(get_db_session),
):
    """Update a client's details."""
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update.",
        )

    # Map field names to DB column names
    col_map = {
        "client_name": "client_name",
        "client_phone": "client_phone",
        "client_email": "client_email",
        "white_label_name": "white_label_name",
        "white_label_logo_url": "white_label_logo_url",
        "language_preference": "language_preference",
        "whatsapp_opted_in": "whatsapp_opted_in",
        "active": "active",
    }
    set_clauses = ", ".join(f"{col_map[k]} = :{k}" for k in updates)
    updates["client_id"] = client_id
    updates["ca_id"] = ca_user.user_id

    result = await db.execute(
        text(f"""
            UPDATE ca_clients SET {set_clauses}, updated_at = NOW()
            WHERE id = :client_id AND ca_user_id = :ca_id
            RETURNING id::text, client_name, active
        """),
        updates,
    )
    await db.commit()
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found.")

    return {"client_id": row.id, "client_name": row.client_name, "active": row.active}


@router.delete("/clients/{client_id}", status_code=status.HTTP_200_OK)
async def deactivate_client(
    client_id: str,
    ca_user: AuthenticatedUser = Depends(_require_ca),
    db: AsyncSession = Depends(get_db_session),
):
    """Deactivate a client (soft delete — data is preserved)."""
    result = await db.execute(
        text("""
            UPDATE ca_clients SET active = FALSE, updated_at = NOW()
            WHERE id = :client_id AND ca_user_id = :ca_id
            RETURNING id::text, client_name
        """),
        {"client_id": client_id, "ca_id": ca_user.user_id},
    )
    await db.commit()
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found.")

    return {"client_id": row.id, "client_name": row.client_name, "status": "deactivated"}


@router.get("/clients/{client_id}/uploads")
async def get_client_uploads(
    client_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    ca_user: AuthenticatedUser = Depends(_require_ca),
    db: AsyncSession = Depends(get_db_session),
):
    """List upload history for a specific client."""
    # Verify client belongs to this CA
    check = await db.execute(
        text("SELECT id FROM ca_clients WHERE id = :id AND ca_user_id = :ca_id"),
        {"id": client_id, "ca_id": ca_user.user_id},
    )
    if not check.fetchone():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found.")

    result = await db.execute(
        text("""
            SELECT
                u.id::text, u.file_name, u.file_type,
                u.file_size_bytes, u.status,
                u.data_health_score, u.error_message,
                u.created_at::text, u.processed_at::text,
                ar.id::text AS analysis_id,
                ar.metrics->>'current_revenue' AS revenue,
                ar.metrics->>'trend' AS trend
            FROM uploads u
            LEFT JOIN analysis_results ar ON ar.upload_id = u.id
            WHERE u.ca_client_id = :client_id
            ORDER BY u.created_at DESC
            LIMIT :limit OFFSET :offset
        """),
        {"client_id": client_id, "limit": limit, "offset": offset},
    )
    rows = result.fetchall()

    return {
        "client_id": client_id,
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "upload_id": r.id,
                "file_name": r.file_name,
                "file_type": r.file_type,
                "file_size_bytes": r.file_size_bytes,
                "status": r.status,
                "health_score": r.data_health_score,
                "error_message": r.error_message,
                "analysis_id": r.analysis_id,
                "revenue": float(r.revenue) if r.revenue else None,
                "trend": r.trend,
                "created_at": r.created_at,
                "processed_at": r.processed_at,
            }
            for r in rows
        ],
    }
