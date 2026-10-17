from celery import Celery

from app.config import get_settings

celery_app = Celery("sentinelai", broker=get_settings().broker_url)
celery_app.conf.update(
    accept_content=["json"],
    task_serializer="json",
    result_serializer="json",
    task_ignore_result=True,
    broker_connection_retry_on_startup=True,
    broker_connection_timeout=3,
    worker_prefetch_multiplier=1,
    worker_concurrency=1,
    task_default_queue="sentinelai",
    timezone="UTC",
    enable_utc=True,
)
# No product tasks or business job status in Redis. Those belong to later phases.
