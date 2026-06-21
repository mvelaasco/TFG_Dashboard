from celery import Celery

from core.config import settings

celery_app = Celery(
    "tfg_worker",
    broker=f"redis://{settings.redis_host}:{settings.redis_port}/0",
    backend=f"redis://{settings.redis_host}:{settings.redis_port}/0",
    include=["infrastructure.workers.ingestion_task"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

celery_app.conf.beat_schedule = {
    "hourly-intelligent-ingestion": {
        "task": "infrastructure.workers.ingestion_task.hourly_ingestion",
        "schedule": 3600.0,
    },
}
