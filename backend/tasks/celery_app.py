"""Celery application configuration — Upstash Redis broker."""

from celery import Celery
from celery.schedules import crontab

from config import settings

celery_app = Celery(
    "munim",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["tasks.process_upload", "tasks.send_reports"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_acks_late=True,            # Re-queue on worker crash
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,   # Process one task at a time per worker
    task_soft_time_limit=120,       # Soft limit: 2 min (sends SIGTERM)
    task_time_limit=180,            # Hard limit: 3 min (sends SIGKILL)
    result_expires=3600,            # Results expire after 1 hour
    broker_transport_options={
        "visibility_timeout": 3600,
        "fanout_prefix": True,
        "fanout_patterns": True,
    },
)

# Beat schedule for weekly reports (Monday 8 AM IST = 02:30 UTC)
celery_app.conf.beat_schedule = {
    "send-weekly-reports": {
        "task": "tasks.send_reports.send_weekly_reports",
        "schedule": crontab(hour=2, minute=30, day_of_week=1),
    },
    "send-monthly-reports": {
        "task": "tasks.send_reports.send_monthly_reports",
        "schedule": crontab(hour=2, minute=30, day_of_month=1),
    },
}
