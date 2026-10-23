"""Inspect/tamper ONLY the disposable ingestion test stack's synthetic candidate."""

import json
import sys
from uuid import UUID

import boto3
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import ClientError
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import database_engine
from app.ingestion.storage import PrivateStorage
from app.ml import artifacts
from app.ml.service import load_bundle
from app.models import Job, ModelVersion
from app.worker import publish_training

settings = get_settings()
assert settings.postgres_db == "sentinelai_ingestion_test" and settings.app_env == "local"
engine = database_engine(settings.database_url)
storage = PrivateStorage(settings)
try:
    with Session(engine) as db:
        assert db.scalar(text("SELECT current_database()")) == "sentinelai_ingestion_test"
        job = db.get(Job, UUID(sys.argv[1]))
        assert job is not None and job.type == "MODEL_TRAIN" and job.status == "SUCCEEDED"
        model = db.scalars(
            select(ModelVersion).where(
                ModelVersion.id == job.model_version_id,
                ModelVersion.organization_id == job.organization_id,
            )
        ).one()
        mode = sys.argv[2]
        if mode == "redeliver":
            publish_training(str(job.id), str(job.dataset_id))
        elif mode == "tamper":
            assert not model.is_active
            artifacts.put(
                storage, model.organization_id, model.id, b"corrupted synthetic test artifact"
            )
        else:
            assert mode == "verify"
            bundle = load_bundle(db, storage, model)
            anonymous = boto3.client(
                "s3",
                endpoint_url=settings.s3_endpoint,
                region_name=settings.s3_region,
                config=Config(signature_version=UNSIGNED),
            )
            try:
                anonymous.get_object(Bucket=storage.bucket, Key=model.artifact_key)
            except ClientError as exc:
                assert exc.response["ResponseMetadata"]["HTTPStatusCode"] == 403
            else:
                raise AssertionError("Anonymous model access was permitted")
            finally:
                anonymous.close()
            print(json.dumps({"private": True, "metrics": bundle.metrics}))
finally:
    storage.close()
    engine.dispose()
