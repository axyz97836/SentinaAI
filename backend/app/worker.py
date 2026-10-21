from typing import Any
from uuid import UUID

from celery import Celery
from celery.exceptions import Retry

from app.config import get_settings
from app.database import database_engine
from app.ingestion.processing import process_job
from app.ingestion.storage import PrivateStorage
from app.observability import configure_logging

logger = configure_logging()

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
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    broker_transport_options={"visibility_timeout": 120, "socket_timeout": 3},
    task_publish_retry=False,
)


def process_csv(self: Any, job_id: str, dataset_id: str) -> None:
    try:
        identifiers = UUID(job_id), UUID(dataset_id)
    except (ValueError, TypeError, AttributeError):
        return
    configuration = get_settings()
    engine = database_engine(configuration.database_url)
    storage = PrivateStorage(configuration)
    try:
        if process_job(engine, storage, *identifiers):
            raise self.retry(countdown=10 * 2**self.request.retries)
    except Retry:
        raise
    except Exception:
        # Durable reconciliation recovers DB outages and worker crashes; no raw exceptions logged.
        # After three started attempts the job is finalized as RETRY_EXHAUSTED.
        logger.warning(
            "ingestion task interrupted",
            extra={
                "action": "ingestion_process",
                "error_code": "PROCESSING_INTERRUPTED",
                "service": "worker",
                "job_id": str(identifiers[0]),
            },
        )
    finally:
        storage.close()
        engine.dispose()


celery_app.task(bind=True, name="ingestion.process_csv", max_retries=2)(process_csv)


def publish_ingestion(job_id: str, dataset_id: str) -> None:
    celery_app.send_task(
        "ingestion.process_csv", kwargs={"job_id": job_id, "dataset_id": dataset_id}
    )
