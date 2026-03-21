"""
Async File Processing Task
===========================
Celery task that processes an uploaded file through the full pipeline:
  1. Download from Cloudflare R2
  2. Parse (Tally/Excel/CSV)
  3. Clean data (dedup, normalise)
  4. Compute health score
  5. If score ≥ 40: run analytics (metrics + anomalies + RFM)
  6. Store results in Neon PostgreSQL
  7. Update upload status

Runs async in a Celery worker — decoupled from the HTTP request.
Typical processing time: 15–90 seconds for large Tally files.
"""

import json
import logging
from decimal import Decimal
from pathlib import Path

import boto3
from botocore.config import Config
from celery import Task
from sqlalchemy import create_engine, text

from config import settings
from services.ingestor.schema_detector import detect_and_parse
from services.analytics.ai_insights import generate_insights
from services.cleaner.deduplicator import deduplicate_products
from services.cleaner.normaliser import normalise
from services.cleaner.health_scorer import compute_health_score, MINIMUM_SCORE_FOR_ANALYSIS
from services.analytics.metrics import compute_metrics
from services.analytics.anomaly import detect_anomalies
from services.analytics.rfm import compute_rfm
from services.analytics.seasonality import get_seasonal_context
from tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# Local uploads directory — mirrors what upload.py uses
LOCAL_UPLOADS_DIR = Path(__file__).parent.parent / "uploads"

# Sync engine for Celery workers (asyncpg not compatible with sync Celery)
_sync_engine = None


def _get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
        # Strip asyncpg driver and query params for psycopg2
        sync_url = settings.DATABASE_URL
        sync_url = sync_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
        sync_url = sync_url.replace("postgresql://", "postgresql+psycopg2://")
        if "?" in sync_url:
            sync_url = sync_url.split("?")[0]

        _sync_engine = create_engine(
            sync_url,
            pool_pre_ping=True,
            connect_args={"sslmode": "require"},
        )
    return _sync_engine


def _get_file_bytes(file_path: str) -> bytes:
    """
    Retrieve file bytes — checks local disk first, then falls back to R2.
    This allows the same pipeline to work in dev (local) and prod (R2).
    """
    local_path = LOCAL_UPLOADS_DIR / file_path
    if local_path.exists():
        logger.info("Reading file from local disk: %s", local_path)
        return local_path.read_bytes()

    # Fall back to Cloudflare R2
    logger.info("Reading file from R2: %s", file_path)
    r2 = boto3.client(
        "s3",
        endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )
    response = r2.get_object(Bucket=settings.R2_BUCKET_NAME, Key=file_path)
    return response["Body"].read()


def _dispatch_anomaly_alert(engine, user_id: str, anomaly_report, owner_name: str) -> None:
    """
    Send an automatic WhatsApp alert when HIGH severity anomalies are detected.
    Only sends if:
    - User has whatsapp_opted_in = TRUE
    - User has a phone number
    - notify_on_anomaly = TRUE (defaults to TRUE if column not yet added)
    Fast: uses template message only (no LLM call).
    """
    from services.whatsapp.sender import send_whatsapp_sync
    import uuid

    # Fetch user's WhatsApp preferences
    with engine.connect() as conn:
        try:
            result = conn.execute(
                text("""
                    SELECT name, phone, language_preference,
                           whatsapp_opted_in,
                           COALESCE(notify_on_anomaly, TRUE) AS notify_on_anomaly
                    FROM users WHERE id = :uid
                """),
                {"uid": user_id},
            )
        except Exception:
            # notify_on_anomaly column not yet added — use simpler query
            result = conn.execute(
                text("""
                    SELECT name, phone, language_preference, whatsapp_opted_in
                    FROM users WHERE id = :uid
                """),
                {"uid": user_id},
            )
        user = result.fetchone()

    if not user:
        return
    if not user.whatsapp_opted_in:
        return
    if not user.phone:
        return
    if hasattr(user, 'notify_on_anomaly') and not user.notify_on_anomaly:
        return

    # Build alert message from the top HIGH anomaly
    top_anomalies = []
    if hasattr(anomaly_report, 'anomalies'):
        top_anomalies = [a for a in anomaly_report.anomalies if getattr(a, 'severity', '') == 'HIGH'][:2]

    owner = user.name or "Business Owner"

    if top_anomalies:
        anomaly = top_anomalies[0]
        title = getattr(anomaly, 'title', 'Business Alert')
        explanation = getattr(anomaly, 'explanation', '')[:120]
        action = getattr(anomaly, 'action', 'Please review your data.')

        message = (
            f"🚨 *{owner} जी — Business Alert!*\n\n"
            f"⚠️ *{title}*\n"
            f"{explanation}\n\n"
            f"💡 क्या करें: {action}\n\n"
            f"Full details: munim.app\n"
            f"— Munim (आपका digital मुनीम)"
        )
        if len(top_anomalies) > 1:
            message += f"\n\n_(और {len(top_anomalies) - 1} alerts हैं — munim.app पर देखें)_"
    else:
        message = (
            f"🚨 *{owner} जी — Business Alert!*\n\n"
            f"आपके नए data में HIGH severity issues मिले हैं।\n"
            f"Full details देखें: munim.app\n\n"
            f"— Munim"
        )

    # Send WhatsApp alert
    try:
        send_whatsapp_sync(user.phone, message)
        logger.info("Anomaly alert sent to user %s", user_id[:8])
    except RuntimeError:
        logger.info("WhatsApp not configured — anomaly alert skipped")
        return
    except Exception as exc:
        logger.warning("Failed to send anomaly alert: %s", exc)
        return

    # Store in reports table
    # Need latest analysis_id
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT id::text FROM analysis_results WHERE upload_id = (SELECT id FROM uploads WHERE user_id = :uid ORDER BY created_at DESC LIMIT 1) LIMIT 1"),
            {"uid": user_id},
        )
        analysis_row = result.fetchone()
        analysis_id = analysis_row.id if analysis_row else None

    if analysis_id:
        with engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO reports (
                        analysis_id, user_id, report_type, language,
                        content_hindi, content_english
                    ) VALUES (
                        :aid, :uid, 'alert', :lang, :content_hi, :content_en
                    )
                """),
                {
                    "aid": analysis_id,
                    "uid": user_id,
                    "lang": user.language_preference or "hi",
                    "content_hi": message if (user.language_preference or "hi") in ("hi", "hinglish") else None,
                    "content_en": message if user.language_preference == "en" else None,
                },
            )
            conn.commit()


def run_pipeline(upload_id: str) -> dict:
    """
    Core processing pipeline — runs the full analytics stack for an upload.
    Called by the Celery task OR directly as a FastAPI background task.
    """
    logger.info("Starting processing for upload: %s", upload_id)
    engine = _get_sync_engine()

    with engine.connect() as conn:
        _update_status(conn, upload_id, "processing")

    try:
        # --- 1. Fetch upload record ---
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT * FROM uploads WHERE id = :id"),
                {"id": upload_id},
            )
            upload = result.fetchone()

        if not upload:
            raise ValueError(f"Upload {upload_id} not found in database")

        # --- 2. Get file bytes (local or R2) ---
        raw_bytes = _get_file_bytes(upload.file_path)

        # --- 3. Parse ---
        logger.info("Parsing file: %s (%d bytes)", upload.file_name, len(raw_bytes))
        parsed = detect_and_parse(raw_bytes, upload.file_name)
        business_type = getattr(parsed, 'business_type', 'business')

        # --- 4. Deduplicate product names ---
        df, canonical_map = deduplicate_products(parsed.df)
        if canonical_map:
            logger.info("Deduplication merged %d product name variants", len(canonical_map))

        # --- 5. Normalise ---
        df, normalise_summary = normalise(df)

        # --- 6. Compute health score ---
        health = compute_health_score(df)

        health_report_json = {
            "score": health.score,
            "grade": health.grade,
            "completeness_score": health.completeness_score,
            "consistency_score": health.consistency_score,
            "validity_score": health.validity_score,
            "uniqueness_score": health.uniqueness_score,
            "total_rows": health.total_rows,
            "usable_rows": health.usable_rows,
            "issues": health.issues,
            "suggestions": health.suggestions,
            "can_analyze": health.can_analyze,
        }

        with engine.connect() as conn:
            conn.execute(
                text("""
                    UPDATE uploads SET
                        data_health_score = :score,
                        health_report = :report
                    WHERE id = :id
                """),
                {
                    "id": upload_id,
                    "score": health.score,
                    "report": json.dumps(health_report_json),
                },
            )
            conn.commit()

        if not health.can_analyze:
            logger.warning(
                "Upload %s health score %d below minimum %d — skipping analysis",
                upload_id, health.score, MINIMUM_SCORE_FOR_ANALYSIS,
            )
            with engine.connect() as conn:
                _update_status(conn, upload_id, "done")
            return {"status": "done", "score": health.score, "analyzed": False}

        # --- 7. Analytics ---
        logger.info("Running analytics for upload: %s", upload_id)
        metrics = compute_metrics(df)
        anomaly_report = detect_anomalies(df)
        customer_segments = compute_rfm(df)
        seasonal_ctx = get_seasonal_context(
            metrics.period_start or df["date"].min(),
            metrics.period_end or df["date"].max(),
        )

        # --- 7b. Generate AI insights ---
        ai_insights = []
        try:
            m = _serialize_metrics(metrics)
            ai_insights = generate_insights(
                business_type=business_type,
                period_start=str(metrics.period_start.date()) if metrics.period_start else "",
                period_end=str(metrics.period_end.date()) if metrics.period_end else "",
                period_label=metrics.revenue.period_label,
                current_revenue=float(m["current_revenue"]),
                previous_revenue=float(m["previous_revenue"]),
                change_pct=float(m["change_pct"]) if m["change_pct"] is not None else None,
                top_products=m["top_products"],
                dead_stock=m["dead_stock"],
                anomalies=_serialize_anomalies(anomaly_report)["anomalies"],
                total_customers=len(customer_segments),
            )
        except Exception as exc:
            logger.warning("AI insights generation failed (non-critical): %s", exc)

        revenue_trend = _compute_revenue_trend(df)

        # --- 8. Store results ---
        analysis_id = _store_analysis_results(
            engine=engine,
            upload_id=upload_id,
            user_id=str(upload.user_id),
            metrics=metrics,
            anomaly_report=anomaly_report,
            customer_segments=customer_segments,
            seasonal_ctx=seasonal_ctx,
            business_type=business_type,
            ai_insights=ai_insights,
            revenue_trend=revenue_trend,
        )

        # --- 9. Mark done ---
        with engine.connect() as conn:
            conn.execute(
                text("UPDATE uploads SET status = 'done', processed_at = NOW() WHERE id = :id"),
                {"id": upload_id},
            )
            conn.commit()

        # --- 10. Auto-alert if HIGH anomalies detected ---
        if anomaly_report.high_count > 0:
            try:
                _dispatch_anomaly_alert(
                    engine=engine,
                    user_id=str(upload.user_id),
                    anomaly_report=anomaly_report,
                    owner_name=str(getattr(upload, 'user_id', 'Unknown')),
                )
            except Exception as alert_exc:
                # Never let alert dispatch break the main pipeline
                logger.warning("Anomaly alert dispatch failed (non-critical): %s", alert_exc)

        logger.info(
            "Processing complete for upload: %s | health: %d | analysis_id: %s",
            upload_id, health.score, analysis_id,
        )
        return {
            "status": "done",
            "upload_id": upload_id,
            "analysis_id": analysis_id,
            "health_score": health.score,
            "analyzed": True,
        }

    except Exception as exc:
        logger.error("Processing failed for upload %s: %s", upload_id, exc, exc_info=True)
        safe_msg = _safe_error_message(exc)
        try:
            with engine.connect() as conn:
                conn.execute(
                    text("""
                        UPDATE uploads SET
                            status = 'error',
                            error_message = :msg,
                            processed_at = NOW()
                        WHERE id = :id
                    """),
                    {"id": upload_id, "msg": safe_msg},
                )
                conn.commit()
        except Exception as db_err:
            logger.error("Failed to update error status: %s", db_err)
        raise


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="tasks.process_upload.process_upload_task",
)
def process_upload_task(self: Task, upload_id: str) -> dict:
    """Celery wrapper around run_pipeline with retry logic."""
    try:
        return run_pipeline(upload_id)
    except Exception as exc:
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        raise


def _safe_error_message(exc: Exception) -> str:
    """
    Return a user-safe error message. Only specific, expected errors get descriptive text.
    All unexpected exceptions return a generic message so internal details are never exposed.
    """
    from services.ingestor.tally_parser import TallyParseError

    if isinstance(exc, TallyParseError):
        return "Could not parse the Tally XML file. Please check the file format and try again."
    if isinstance(exc, ValueError) and len(str(exc)) < 200:
        # ValueError messages are typically safe (our own validation messages)
        return str(exc)
    return "Processing failed. Our team has been notified. Please try again later."


def _update_status(conn, upload_id: str, status: str) -> None:
    conn.execute(
        text("UPDATE uploads SET status = :status WHERE id = :id"),
        {"id": upload_id, "status": status},
    )
    conn.commit()


def _compute_revenue_trend(df) -> list[dict]:
    """Daily revenue aggregation for the trend chart."""
    from decimal import Decimal
    sales_df = df[df["amount"].apply(lambda x: isinstance(x, Decimal) and x > Decimal(0))].copy()
    if sales_df.empty:
        return []
    daily = (
        sales_df.groupby(sales_df["date"].dt.date)["amount"]
        .apply(lambda s: float(sum(x for x in s if isinstance(x, Decimal))))
        .reset_index()
    )
    daily.columns = ["date", "revenue"]
    daily["date"] = daily["date"].astype(str)
    return daily.to_dict(orient="records")


def _store_analysis_results(
    engine, upload_id, user_id, metrics, anomaly_report, customer_segments, seasonal_ctx,
    business_type="business", ai_insights=None, revenue_trend=None,
) -> str:
    """Serialize analytics results to JSON and store in DB."""
    import uuid
    from decimal import Decimal

    analysis_id = str(uuid.uuid4())

    def decimal_serializer(obj):
        if isinstance(obj, Decimal):
            return float(obj)
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    serialized_metrics = _serialize_metrics(metrics)
    serialized_metrics["business_type"] = business_type
    serialized_metrics["period_label"] = metrics.revenue.period_label
    serialized_metrics["revenue_trend"] = revenue_trend or []
    serialized_metrics["ai_insights"] = [
        {"title": i.title, "insight": i.insight, "type": i.type, "priority": i.priority}
        for i in (ai_insights or [])
    ]
    metrics_json = json.dumps(serialized_metrics, default=decimal_serializer)
    anomalies_json = json.dumps(_serialize_anomalies(anomaly_report), default=decimal_serializer)
    customers_json = json.dumps(_serialize_customers(customer_segments), default=decimal_serializer)
    seasonal_json = json.dumps(
        {"events": [e.name for e in seasonal_ctx.events], "notes": seasonal_ctx.context_notes},
        default=decimal_serializer,
    )

    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO analysis_results (
                    id, upload_id, user_id, period_start, period_end,
                    metrics, anomalies, products, customers, seasonality_context
                ) VALUES (
                    :id, :upload_id, :user_id, :period_start, :period_end,
                    :metrics, :anomalies, :products,
                    :customers, :seasonal
                )
            """),
            {
                "id": analysis_id,
                "upload_id": upload_id,
                "user_id": user_id,
                "period_start": metrics.period_start.date() if metrics.period_start else None,
                "period_end": metrics.period_end.date() if metrics.period_end else None,
                "metrics": metrics_json,
                "anomalies": anomalies_json,
                "products": json.dumps([], default=decimal_serializer),
                "customers": customers_json,
                "seasonal": seasonal_json,
            },
        )
        conn.commit()

    return analysis_id


def _serialize_metrics(metrics) -> dict:
    from decimal import Decimal
    r = metrics.revenue
    return {
        "current_revenue": float(r.current_period),
        "previous_revenue": float(r.previous_period),
        "change_amount": float(r.change_amount),
        "change_pct": float(r.change_pct) if r.change_pct is not None else None,
        "trend": r.trend,
        "top_products": [
            {"rank": p.rank, "name": p.name, "revenue": float(p.revenue), "trend": p.trend}
            for p in metrics.top_products
        ],
        "dead_stock_count": len(metrics.dead_stock),
        "dead_stock": [
            {"product": d.product, "days_since_sale": d.days_since_last_sale}
            for d in metrics.dead_stock[:5]
        ],
    }


def _serialize_anomalies(report) -> dict:
    return {
        "total": report.total_detected,
        "high_count": report.high_count,
        "medium_count": report.medium_count,
        "low_count": report.low_count,
        "anomalies": [
            {
                "type": a.anomaly_type,
                "severity": a.severity,
                "confidence": a.confidence,
                "title": a.title,
                "explanation": a.explanation,
                "action": a.action,
            }
            for a in report.anomalies[:10]
        ],
    }


def _serialize_customers(segments) -> dict:
    return {
        "total": len(segments),
        "segments": {
            seg: sum(1 for s in segments if s.segment == seg)
            for seg in ["Champion", "Loyal", "Potential", "At Risk", "Lost", "New", "Average"]
        },
        "top_customers": [
            {"name": s.customer, "segment": s.segment, "rfm_score": s.rfm_score}
            for s in segments[:10]
        ],
    }
