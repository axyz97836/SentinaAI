"""PYTEST_DONT_REWRITE: keep synthetic session values out of assertion diagnostics."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from io import BytesIO
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from botocore.exceptions import ClientError
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker
from test_ingestion import client as client
from test_ingestion import ingestion as ingestion
from test_ingestion import password_hash as password_hash
from test_ingestion import upload

from app.auth.errors import AuthError
from app.ingestion.processing import process_job
from app.ingestion.service import reconcile
from app.ingestion.storage import StorageUnavailable
from app.ingestion.validation import InvalidCSV
from app.ml import artifacts
from app.ml.processing import process_training, reconcile_training
from app.ml.service import activate, load_bundle, request_training
from app.ml.synthetic import generate_csv
from app.models import AuditLog, Dataset, Job, Membership, ModelVersion, Organization

pytestmark = pytest.mark.database


@pytest.fixture
def ml(ingestion):
    engine, sessions, storage, principal, settings = ingestion

    class S3:
        def put_object(self, **kwargs):
            storage.objects[kwargs["Key"]] = kwargs["Body"]

        def get_object(self, **kwargs):
            if kwargs["Key"] not in storage.objects:
                raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
            content = storage.objects[kwargs["Key"]]
            return {"Body": BytesIO(content), "ContentLength": len(content)}

        def delete_object(self, **kwargs):
            storage.objects.pop(kwargs["Key"], None)

    storage.client, storage.bucket = S3(), "private-fixtures"
    return ingestion


def validated(ml):
    engine, _, storage, _, _ = ml
    job, dataset = upload(ml, generate_csv())
    process_job(engine, storage, job, dataset)
    return dataset


def submit(ml, dataset=None):
    _, sessions, _, principal, _ = ml
    dataset = dataset or validated(ml)
    with sessions.begin() as db:
        job = request_training(db, principal, dataset, "fixture")
    return job.id, dataset


def trained(ml, dataset=None):
    engine, sessions, storage, _, _ = ml
    job_id, dataset_id = submit(ml, dataset)
    process_training(engine, storage, job_id, dataset_id)
    with sessions() as db:
        job = db.get(Job, job_id)
        assert job.status == "SUCCEEDED"
        return job.model_version_id


def test_real_training_candidate_provenance_and_duplicate_delivery(ml):
    engine, sessions, storage, principal, _ = ml
    job_id, dataset_id = submit(ml)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda _: process_training(engine, storage, job_id, dataset_id), range(2))
        )
    assert results == [False, False]
    assert not process_training(engine, storage, job_id, dataset_id)
    with sessions() as db:
        job = db.get(Job, job_id)
        assert job.attempt_count == 1 and job.status == "SUCCEEDED" and job.processed_rows == 2000
        model = db.get(ModelVersion, job.model_version_id)
        assert not model.is_active and model.activated_at is None
        bundle = load_bundle(db, storage, model)
        assert bundle.provenance["job_id"] == str(job_id)
        assert model.metrics_json["sample_count"] == 400
        assert (
            db.scalar(
                select(func.count())
                .select_from(ModelVersion)
                .where(ModelVersion.organization_id == principal.organization_id)
            )
            == 1
        )


@pytest.mark.parametrize("role", ["ANALYST", "RISK_MANAGER", "ADMIN"])
def test_model_api_roles_csrf_and_active_metadata(ml, client, role):
    engine, sessions, storage, principal, _ = ml
    dataset = validated(ml)
    browser, headers = client
    with sessions.begin() as db:
        db.get(Membership, principal.membership_id).role = role
    response = browser.post(
        "/api/v1/admin/models/train", headers=headers, json={"training_dataset_id": str(dataset)}
    )
    assert response.status_code == (202 if role == "ADMIN" else 403)
    assert browser.get("/api/v1/admin/models").status_code == (200 if role == "ADMIN" else 403)
    assert browser.post(
        f"/api/v1/admin/models/{uuid4()}/activate", headers=headers, json={}
    ).status_code == (404 if role == "ADMIN" else 403)
    assert (
        browser.post(
            "/api/v1/admin/models/train", json={"training_dataset_id": str(dataset)}
        ).status_code
        == 403
    )
    assert (
        browser.post(
            "/api/v1/admin/models/train",
            headers={**headers, "Origin": "https://foreign.invalid"},
            json={"training_dataset_id": str(dataset)},
        ).status_code
        == 403
    )
    if role == "ADMIN":
        job_id = UUID(response.json()["job_id"])
        assert response.json()["status"] == "QUEUED"
        process_training(engine, storage, job_id, dataset)
        identifier = browser.get(f"/api/v1/jobs/{job_id}").json()["model_version_id"]
        assert (
            browser.post(f"/api/v1/admin/models/{identifier}/activate", json={}).status_code == 403
        )
        assert (
            browser.post(
                f"/api/v1/admin/models/{identifier}/activate", headers=headers, json={}
            ).status_code
            == 200
        )
        result = browser.get("/api/v1/models/active")
        assert result.status_code == 200 and result.json()["id"] == identifier
        assert "artifact_key" not in result.text and "sha256" not in result.text
        for allowed in ("ANALYST", "RISK_MANAGER"):
            with sessions.begin() as db:
                db.get(Membership, principal.membership_id).role = allowed
            assert browser.get("/api/v1/models/active").status_code == 200
    browser.cookies.clear()
    assert browser.get("/api/v1/models/active").status_code == 401
    assert browser.get("/api/v1/admin/models").status_code == 401
    assert (
        browser.post(
            "/api/v1/admin/models/train",
            headers=headers,
            json={"training_dataset_id": str(dataset)},
        ).status_code
        == 401
    )


def test_foreign_dataset_model_and_active_are_isolated(ml, client, migrated_engine):
    _, sessions, _, principal, _ = ml
    identifier = trained(ml)
    with sessions.begin() as db:
        dataset = db.get(ModelVersion, identifier).training_dataset_id
        other = Organization(name="Fictional foreign model organization")
        db.add(other)
        db.flush()
        db.get(Membership, principal.membership_id).organization_id = other.id
    browser, headers = client
    try:
        assert (
            browser.post(
                "/api/v1/admin/models/train",
                headers=headers,
                json={"training_dataset_id": str(dataset)},
            ).status_code
            == 404
        )
        assert (
            browser.post(
                f"/api/v1/admin/models/{identifier}/activate", headers=headers, json={}
            ).status_code
            == 404
        )
        assert browser.get("/api/v1/admin/models").json()["items"] == []
        assert browser.get("/api/v1/models/active").status_code == 409
    finally:
        with sessionmaker(migrated_engine).begin() as db:
            db.get(Membership, principal.membership_id).organization_id = principal.organization_id
            db.delete(db.get(Organization, other.id))


def test_admission_concurrency_and_input_limits(ml, client):
    _, sessions, _, principal, _ = ml
    dataset = validated(ml)

    def admit(_):
        try:
            with sessions.begin() as db:
                request_training(db, principal, dataset, "concurrent")
            return 202
        except AuthError as error:
            return error.status

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(admit, range(2))) == [202, 429]
    browser, headers = client
    assert browser.get("/api/v1/admin/models?limit=101").status_code == 422
    assert browser.get("/api/v1/admin/models?cursor=invalid").status_code == 422
    assert (
        browser.post(
            "/api/v1/admin/models/train",
            headers=headers,
            json={"training_dataset_id": str(dataset), "object_key": "untrusted"},
        ).status_code
        == 422
    )
    assert (
        browser.post(
            "/api/v1/admin/models/train",
            headers={**headers, "Content-Type": "application/json"},
            content=b" " * 4097,
        ).status_code
        == 413
    )


def test_atomic_concurrent_activation_and_audit(ml):
    _, sessions, storage, principal, _ = ml
    first = trained(ml)
    second = trained(ml)

    def promote(identifier):
        with sessions.begin() as db:
            activate(db, storage, principal, identifier, "concurrent")

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(promote, (first, second)))
    with sessions() as db:
        active = list(
            db.scalars(
                select(ModelVersion).where(
                    ModelVersion.organization_id == principal.organization_id,
                    ModelVersion.is_active.is_(True),
                )
            )
        )
        assert len(active) == 1 and active[0].id in {first, second}
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(
                    AuditLog.organization_id == principal.organization_id,
                    AuditLog.action == "MODEL_ACTIVATED",
                )
            )
            == 2
        )


@pytest.mark.parametrize("failure", ["corrupt", "missing", "schema", "untrusted", "storage"])
def test_failed_activation_preserves_previous_active(ml, failure, migrated_engine):
    _, sessions, storage, principal, _ = ml
    first, second = trained(ml), trained(ml)
    with sessions.begin() as db:
        activate(db, storage, principal, first, "activate-first")
        model = db.get(ModelVersion, second)
        if failure == "untrusted":
            job = db.scalars(select(Job).where(Job.model_version_id == second)).one()
            job.type = "CSV_IMPORT"
    if failure == "schema":
        # Immutable model metadata is tampered only by the disposable fixture's migrator.
        with sessionmaker(migrated_engine).begin() as db:
            model = db.get(ModelVersion, second)
            model.feature_schema_json = {**model.feature_schema_json, "version": "unsupported"}
    key = artifacts.key(principal.organization_id, second)
    if failure == "corrupt":
        storage.objects[key] = b"untrusted arbitrary serialized bytes"
    elif failure == "missing":
        del storage.objects[key]
    elif failure == "storage":
        storage.client.get_object = Mock(side_effect=StorageUnavailable())
    with pytest.raises((InvalidCSV, StorageUnavailable)):
        with sessions.begin() as db:
            activate(db, storage, principal, second, "bad-activate")
    with sessions() as db:
        assert db.get(ModelVersion, first).is_active
        assert not db.get(ModelVersion, second).is_active


def test_worker_crash_retry_and_typed_recovery(ml, monkeypatch):
    engine, sessions, storage, _, _ = ml
    job_id, dataset = submit(ml)
    from app.ml import processing

    original = processing.train
    monkeypatch.setattr(processing, "train", Mock(side_effect=RuntimeError("PRIVATE_MARKER")))
    with pytest.raises(RuntimeError):
        process_training(engine, storage, job_id, dataset)
    ingestion_publish, training_publish = Mock(), Mock()
    reconcile(sessions, storage, ingestion_publish)
    reconcile_training(sessions, storage, training_publish)
    ingestion_publish.assert_not_called()
    training_publish.assert_called_once_with(str(job_id), str(dataset))
    monkeypatch.setattr(processing, "train", original)
    assert not process_training(engine, storage, job_id, dataset)
    with sessions() as db:
        job = db.get(Job, job_id)
        assert job.status == "SUCCEEDED" and job.attempt_count == 2


def test_storage_retries_bounded_and_cleanup_durable(ml, monkeypatch):
    engine, sessions, storage, _, _ = ml
    job_id, dataset = submit(ml)
    monkeypatch.setattr(artifacts, "put", Mock(side_effect=StorageUnavailable()))
    for attempt in range(1, 4):
        assert process_training(engine, storage, job_id, dataset) == (attempt < 3)
        with sessions.begin() as db:
            job = db.get(Job, job_id)
            assert job.attempt_count == attempt
            job.params_json = {**job.params_json, "retry_at": 0}
    with sessions() as db:
        job = db.get(Job, job_id)
        assert job.status == "FAILED" and job.error_code == "STORAGE_UNAVAILABLE"
        assert job.params_json["artifact_cleanup_pending"]
    reconcile_training(sessions, storage, Mock())
    with sessions() as db:
        assert not db.get(Job, job_id).params_json["artifact_cleanup_pending"]
        assert db.get(Dataset, dataset).status == "VALIDATED"


@pytest.mark.parametrize(
    "change,code",
    [
        ("purpose", "VALIDATED_TRAINING_REQUIRED"),
        ("schema_version", "DATASET_SCHEMA_UNSUPPORTED"),
        ("row_count", "DATASET_ROW_COUNT_MISMATCH"),
    ],
)
def test_worker_revalidates_dataset_and_fails_permanently(ml, change, code):
    engine, sessions, storage, _, _ = ml
    job_id, dataset = submit(ml)
    with sessions.begin() as db:
        setattr(
            db.get(Dataset, dataset),
            change,
            {"purpose": "SCORING", "schema_version": "2", "row_count": 1}[change],
        )
    assert not process_training(engine, storage, job_id, dataset)
    with sessions() as db:
        job = db.get(Job, job_id)
        assert job.status == "FAILED" and job.error_code == code and job.attempt_count == 1


def test_late_training_cannot_publish_after_terminal_transition(ml, monkeypatch):
    from app.ml import processing

    engine, sessions, storage, _, _ = ml
    job_id, dataset = submit(ml)
    original = processing.train

    def interrupted(rows, provenance):
        bundle = original(rows, provenance)
        with sessions.begin() as db:
            job = db.get(Job, job_id)
            job.status = "FAILED"
            job.completed_at = datetime.now(UTC)
            job.error_code = "RETRY_EXHAUSTED"
        return bundle

    monkeypatch.setattr(processing, "train", interrupted)
    assert not process_training(engine, storage, job_id, dataset)
    assert all("/models/" not in key for key in storage.objects)
    with sessions() as db:
        assert db.get(Job, job_id).status == "FAILED"


def test_ambiguous_object_write_reuses_one_candidate(ml, monkeypatch):
    engine, sessions, storage, _, _ = ml
    job_id, dataset = submit(ml)
    original = artifacts.put

    def ambiguous(*args):
        original(*args)
        raise StorageUnavailable()

    monkeypatch.setattr(artifacts, "put", ambiguous)
    assert process_training(engine, storage, job_id, dataset)
    with sessions.begin() as db:
        job = db.get(Job, job_id)
        job.params_json = {**job.params_json, "retry_at": 0}
    monkeypatch.setattr(artifacts, "put", original)
    assert not process_training(engine, storage, job_id, dataset)
    assert len([key for key in storage.objects if "/models/" in key]) == 1
    with sessions() as db:
        assert db.get(Job, job_id).status == "SUCCEEDED"
