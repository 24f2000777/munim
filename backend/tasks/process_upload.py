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

import boto3
from botocore.config import Config
from celery import Task
from sqlalchemy import create_engine, text

from config import settings
from services.ingestor.schema_detector import detect_and_parse
from services.cleaner.deduplicator import deduplicate_products
from services.cleaner.normaliser import normalise
from services.cleaner.health_scorer import compute_health_score, MINIMUM_SCORE_FOR_ANALYSIS
from services.analytics.metrics import compute_metrics
from services.analytics.anomaly import detect_anomalies
from services.analytics.rfm import compute_rfm
from services.analytics.seasonality import get_seasonal_context
from tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# Sync engine for Celery workers (asyncpg not compatible with sync Celery)
_sync_engine = None


def _get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
        sync_url = settings.DATABASE_URL.replace(
            "postgresql+asyncpg://", "postgresql+psycopg2://"
        ).replace("postgresql://", "postgresql+psycopg2://")
        from sqlalchemy import create_engine
        _sync_engine = create_engine(
            sync_url,
            pool_pre_ping=True,
            connect_args={"sslmode": "require"},
        )
    return _sync_engine


def _get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,  # Wait 30s before retry
    name="tasks.process_upload.process_upload_task",
)
def process_upload_task(self: Task, upload_id: str) -> dict:
    """
    Process an uploaded file through the full analytics pipeline.

    Args:
        upload_id: UUID of the upload record in the DB.

    Returns:
        Dict with processing result summary.
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

        # --- 2. Download from R2 ---
        logger.info("Downloading file from R2: %s", upload.file_path)
        r2 = _get_r2_client()
        r2_response = r2.get_object(Bucket=settings.R2_BUCKET_NAME, Key=upload.file_path)
        raw_bytes = r2_response["Body"].read()

        # --- 3. Parse ---
        logger.info("Parsing file: %s (%d bytes)", upload.file_name, len(raw_bytes))
        parsed = detect_and_parse(raw_bytes, upload.file_name)

        # --- 4. Deduplicate product names ---
        df, canonical_map = deduplicate_products(parsed.df)
        if canonical_map:
            logger.info("Deduplication merged %d product name variants", len(canonical_map))

        # --- 5. Normalise ---
        df, normalise_summary = normalise(df)

        # --- 6. Compute health score ---
        health = compute_health_score(df)

        # Store health report
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
                "Upload %s has health score %d — below minimum %d, skipping analysis",
                upload_id, health.score, MINIMUM_SCORE_FOR_ANALYSIS,
            )
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

        # --- 8. Serialize and store results ---
        analysis_id = _store_analysis_results(
            engine=engine,
            upload_id=upload_id,
            user_id=str(upload.user_id),
            metrics=metrics,
            anomaly_report=anomaly_report,
            customer_segments=customer_segments,
            seasonal_ctx=seasonal_ctx,
        )

        # --- 9. Mark done ---
        with engine.connect() as conn:
            conn.execute(
                text("UPDATE uploads SET status = 'done', processed_at = NOW() WHERE id = :id"),
                {"id": upload_id},
            )
            conn.commit()

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

        # Store a safe, generic message for user-facing API — full detail is in server logs only
        safe_msg = _safe_error_message(exc)

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

        # Retry on transient errors
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


def _store_analysis_results(
    engine, upload_id, user_id, metrics, anomaly_report, customer_segments, seasonal_ctx
) -> str:
    """Serialize analytics results to JSON and store in DB."""
    import uuid
    from decimal import Decimal

    analysis_id = str(uuid.uuid4())

    def decimal_serializer(obj):
        if isinstance(obj, Decimal):
            return float(obj)
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    metrics_json = json.dumps(_serialize_metrics(metrics), default=decimal_serializer)
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
                    :metrics::jsonb, :anomalies::jsonb, :products::jsonb,
                    :customers::jsonb, :seasonal::jsonb
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
