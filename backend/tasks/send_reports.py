"""
Automated Report Sender
========================
Celery tasks for scheduled WhatsApp report delivery.
Beat schedule (configured in celery_app.py):
  - Weekly:  Monday 08:00 AM IST (02:30 UTC)
  - Monthly: 1st of month 08:00 AM IST (02:30 UTC)

Each task:
  1. Fetches all opted-in users with the relevant notify pref
  2. Gets their latest analysis results
  3. Generates a Hindi/English narrative report via Gemini
  4. Sends it via WhatsApp (Twilio or Meta)
  5. Inserts a row into the reports table
  6. Wraps each user independently — one failure never aborts the batch
"""

import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import create_engine, text

from config import settings
from services.reporter.llm_narrator import generate_report
from services.whatsapp.sender import send_whatsapp_sync
from tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# Skip analyses older than 60 days — don't spam stale data
MAX_ANALYSIS_AGE_DAYS = 60

_sync_engine = None


def _get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
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


def _get_opted_in_users(engine, notify_col: str) -> list:
    """
    Fetch users who have opted in to WhatsApp AND have the specific notify preference enabled.
    notify_col: 'notify_weekly' or 'notify_monthly'
    Falls back to all opted-in users if the column doesn't exist yet (pre-migration).
    """
    with engine.connect() as conn:
        try:
            result = conn.execute(text(f"""
                SELECT id::text, name, phone, language_preference
                FROM users
                WHERE whatsapp_opted_in = TRUE
                  AND phone IS NOT NULL
                  AND phone != ''
                  AND {notify_col} = TRUE
            """))
        except Exception:
            # Column doesn't exist yet (migration not run) — fall back to all opted-in users
            logger.warning("Column %s not found — sending to all opted-in users", notify_col)
            result = conn.execute(text("""
                SELECT id::text, name, phone, language_preference
                FROM users
                WHERE whatsapp_opted_in = TRUE
                  AND phone IS NOT NULL
                  AND phone != ''
            """))
        return result.fetchall()


def _get_latest_analysis(engine, user_id: str):
    """
    Fetch the most recent analysis result for a user.
    Returns None if no analysis exists or if it's older than MAX_ANALYSIS_AGE_DAYS.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_ANALYSIS_AGE_DAYS)
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT id::text, metrics, anomalies, customers, seasonality_context,
                       period_start::text, period_end::text, created_at
                FROM analysis_results
                WHERE user_id = :uid
                  AND created_at > :cutoff
                ORDER BY created_at DESC
                LIMIT 1
            """),
            {"uid": user_id, "cutoff": cutoff},
        )
        return result.fetchone()


def _send_report_for_user(engine, user, report_type: str) -> None:
    """
    Generate and send a WhatsApp report for a single user.
    Inserts the report into the reports table.
    Raises on failure — caller must wrap in try/except.
    """
    analysis = _get_latest_analysis(engine, user.id)
    if not analysis:
        logger.info(
            "Skipping user %s — no recent analysis (>%d days or none)",
            user.id[:8], MAX_ANALYSIS_AGE_DAYS,
        )
        return

    lang = user.language_preference or "hi"
    owner_name = user.name or "Business Owner"

    # metrics/anomalies stored as JSON in DB
    metrics = analysis.metrics if isinstance(analysis.metrics, dict) else {}
    anomalies = analysis.anomalies if isinstance(analysis.anomalies, dict) else {}
    seasonality = analysis.seasonality_context if isinstance(analysis.seasonality_context, dict) else {}

    # Build generate_report inputs from pre-computed JSON stored in the DB.
    # generate_report() expects: metrics_summary (dict), top_anomalies (list),
    # seasonality_context (list), period_start (str), period_end (str).
    top_anomalies = (anomalies.get("anomalies") or [])[:3]
    seasonality_notes = seasonality.get("events", [])
    period_start = analysis.period_start or ""
    period_end = analysis.period_end or ""

    # Generate narrative report
    narrator_result = generate_report(
        owner_name=owner_name,
        language=lang,
        period_start=period_start,
        period_end=period_end,
        metrics_summary=metrics,
        top_anomalies=top_anomalies,
        seasonality_context=seasonality_notes,
    )

    # Send via WhatsApp
    try:
        send_whatsapp_sync(user.phone, narrator_result.content)
    except RuntimeError:
        # WhatsApp not configured — log but don't crash
        logger.warning("WhatsApp not configured — skipping send for user %s", user.id[:8])
        return
    except Exception as exc:
        logger.error("WhatsApp send failed for user %s: %s", user.id[:8], exc)
        raise

    # Store in reports table.
    # id is auto-generated by the DB (UUID default) — do NOT include it in the INSERT.
    # This matches the pattern in routers/reports.py which also omits id and uses RETURNING.
    with engine.connect() as conn:
        conn.execute(
            text("""
                INSERT INTO reports (
                    analysis_id, user_id, report_type, language,
                    content_hindi, content_english
                ) VALUES (
                    :analysis_id, :user_id, :report_type, :lang,
                    :content_hi, :content_en
                )
                ON CONFLICT DO NOTHING
            """),
            {
                "analysis_id": analysis.id,
                "user_id": user.id,
                "report_type": report_type,
                "lang": lang,
                "content_hi": narrator_result.content if lang in ("hi", "hinglish") else None,
                "content_en": narrator_result.content if lang == "en" else None,
            },
        )
        conn.commit()

    logger.info(
        "Report sent | user=%s | type=%s | lang=%s | words=%d | fallback=%s",
        user.id[:8], report_type, lang, narrator_result.word_count, narrator_result.used_fallback,
    )


@celery_app.task(name="tasks.send_reports.send_weekly_reports")
def send_weekly_reports() -> dict:
    """
    Send weekly WhatsApp business reports to all opted-in users.
    Triggered by Beat every Monday at 08:00 AM IST.
    """
    engine = _get_sync_engine()
    users = _get_opted_in_users(engine, "notify_weekly")
    logger.info("Weekly reports — sending to %d users", len(users))

    success, failed, skipped = 0, 0, 0
    for user in users:
        try:
            _send_report_for_user(engine, user, report_type="weekly")
            success += 1
        except Exception as exc:
            logger.error("Weekly report failed for user %s: %s", user.id[:8], exc)
            failed += 1

    logger.info("Weekly reports done — success=%d failed=%d skipped=%d", success, failed, skipped)
    return {"success": success, "failed": failed, "skipped": skipped}


@celery_app.task(name="tasks.send_reports.send_monthly_reports")
def send_monthly_reports() -> dict:
    """
    Send monthly WhatsApp business reports to all opted-in users.
    Triggered by Beat on the 1st of each month at 08:00 AM IST.
    """
    engine = _get_sync_engine()
    users = _get_opted_in_users(engine, "notify_monthly")
    logger.info("Monthly reports — sending to %d users", len(users))

    success, failed, skipped = 0, 0, 0
    for user in users:
        try:
            _send_report_for_user(engine, user, report_type="monthly")
            success += 1
        except Exception as exc:
            logger.error("Monthly report failed for user %s: %s", user.id[:8], exc)
            failed += 1

    logger.info("Monthly reports done — success=%d failed=%d skipped=%d", success, failed, skipped)
    return {"success": success, "failed": failed, "skipped": skipped}
