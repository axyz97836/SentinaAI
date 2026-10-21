"""Inspect only the supplied synthetic verification job; never print private content."""

import sys
from urllib.error import HTTPError
from urllib.request import urlopen
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import database_engine
from app.ingestion.storage import PrivateStorage
from app.ingestion.validation import InvalidCSV
from app.models import Dataset, Job, Transaction
from app.worker import publish_ingestion


def check() -> None:
    job_id, mode = UUID(sys.argv[1]), sys.argv[2]
    settings = get_settings()
    engine = database_engine(settings.database_url)
    storage = PrivateStorage(settings)
    try:
        with Session(engine) as db:
            job = db.get(Job, job_id)
            if job is None:
                raise RuntimeError("Verification job missing")
            dataset = db.get(Dataset, job.dataset_id)
            if dataset is None or dataset.source_kind != "SYNTHETIC":
                raise RuntimeError("Synthetic dataset required")
            if mode == "redeliver":
                publish_ingestion(str(job.id), str(dataset.id))
                publish_ingestion(str(job.id), str(dataset.id))
                return
            if mode == "absent":
                try:
                    with storage.read(
                        job.organization_id, dataset.id, dataset.size_bytes, dataset.sha256
                    ):
                        raise RuntimeError("Rejected object still present")
                except InvalidCSV as exc:
                    if exc.code != "OBJECT_MISSING":
                        raise
                return
            with storage.read(
                job.organization_id, dataset.id, dataset.size_bytes, dataset.sha256
            ) as file:
                if not file.read(128).startswith(b"external_id,customer_ref,"):
                    raise RuntimeError("Unexpected synthetic object")
            key = storage.key(job.organization_id, dataset.id)
            url = f"{settings.s3_endpoint}/{storage.bucket}/{key}"
            try:
                with urlopen(url, timeout=5):  # noqa: S310 -- configured local storage endpoint
                    raise RuntimeError("Anonymous object access allowed")
            except HTTPError as exc:
                if exc.code not in {401, 403}:
                    raise
            if (
                db.scalar(
                    select(Transaction.id).where(
                        Transaction.organization_id == job.organization_id,
                        Transaction.external_id == "phase4-e2e-fictional-marker",
                    )
                )
                is not None
            ):
                raise RuntimeError("Validation created an operational transaction")
    finally:
        storage.close()
        engine.dispose()


if __name__ == "__main__":
    try:
        check()
    except Exception:
        print("FAIL: private ingestion storage verification", file=sys.stderr)
        sys.exit(1)
    print("PASS: private ingestion storage verification")
