from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "nile_fulfillment",
    broker=settings.broker_url,
    backend=settings.result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    broker_connection_retry_on_startup=False,
    broker_transport_options={"max_retries": 1},
    beat_schedule={
        "check-outreach-sla-every-5-minutes": {
            "task": "app.workers.tasks.check_outreach_sla_timeouts",
            "schedule": 300.0,  # 5 minutes
        },
    },
)

celery_app.set_default()
