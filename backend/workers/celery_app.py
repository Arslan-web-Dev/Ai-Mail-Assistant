"""
Celery application instance. Task modules (email sync, AI analysis,
automation) are added starting Module 3 — this is foundation wiring only.

Run a worker with:
    celery -A workers.celery_app worker --loglevel=info
"""
from celery import Celery

from app.config import settings

celery_app = Celery(
    "ai_mail_assistant",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "renew-gmail-watches-every-6-hours": {
            "task": "renew_gmail_watches",
            "schedule": 6 * 60 * 60,  # seconds
        },
    },
)

# Import task modules so Celery registers them.
celery_app.autodiscover_tasks(["workers"], related_name="tasks")
