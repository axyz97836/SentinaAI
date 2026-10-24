"""PYTEST_DONT_REWRITE: synthetic credentials must not appear in assertion diagnostics."""

import secrets
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from io import BytesIO
from threading import Event
from unittest.mock import Mock
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import delete, func, select
from sqlalchemy.orm import sessionmaker

from app.auth.crypto import new_token, token_hash
from app.auth.errors import AuthError
from app.auth.service import HASHER, AuthService, Principal
from app.config import Settings
from app.database import database_engine
from app.ingestion.processing import process_job
from app.ingestion.service import accept_upload, reconcile
from app.ingestion.storage import PrivateStorage, StorageUnavailable
from app.ingestion.validation import UploadMetadata
from app.main import create_app
from app.models import (
    AuditLog,
    Dataset,
    Job,
    JobError,
    Membership,
    ModelVersion,
    Organization,
    SessionRecord,
    Transaction,
    User,
)

pytestmark = pytest.mark.database
HEADER = (
    "external_id,customer_ref,occurred_at,amount,currency,merchant_category,country_code,channel"
)
ROW = "syn-1,customer-demo,2026-10-20T10:00:00Z,12.34,INR,grocery,IN,WEB"
CSV = f"{HEADER}\n{ROW}\n".encode()


class MemoryStorage:
    key = staticmethod(PrivateStorage.key)

    def __init__(self):
        self.objects = {}

    def put(self, organization_id, dataset_id, file, size):
        self.objects[self.key(organization_id, dataset_id)] = file.read()

    def delete(self, organization_id, dataset_id):
        self.objects.pop(self.key(organization_id, dataset_id), None)

    @contextmanager
    def read(self, organization_id, dataset_id, size, digest):
        content = self.objects[self.key(organization_id, dataset_id)]
        assert len(content) == size and sha256(content).hexdigest() == digest
        yield BytesIO(content)


@pytest.fixture(scope="module")
def password_hash():
    return HASHER.hash(secrets.token_urlsafe(32))


@pytest.fixture
def ingestion(migrated_engine, password_hash):
    settings = Settings(
        auth_secret=SecretStr(secrets.token_hex(32)),
        auth_cookie_secure=False,
        auth_allowed_origins="http://testserver",
    )
    engine = database_engine(settings.database_url)
    sessions = sessionmaker(engine, expire_on_commit=False)
    with sessions.begin() as db:
        organization = Organization(name="Fictional ingestion test")
        user = User(
            email=f"{uuid4()}@fixture.invalid",
            display_name="Fictional Uploader",
            password_hash=password_hash,
        )
        db.add_all([organization, user])
        db.flush()
        membership = Membership(organization_id=organization.id, user_id=user.id, role="ADMIN")
        db.add(membership)
        db.flush()
        principal = Principal(
            user.id,
            organization.id,
            membership.id,
            uuid4(),
            "ADMIN",
            user.email,
            user.display_name,
            organization.name,
        )
    storage = MemoryStorage()
    try:
        yield engine, sessions, storage, principal, settings
    finally:
        # Only fixture-owned rows in the guarded disposable DB; audit removal uses migrator.
        with sessionmaker(migrated_engine).begin() as db:
            jobs = select(Job.id).where(Job.organization_id == organization.id)
            db.execute(delete(JobError).where(JobError.job_id.in_(jobs)))
            db.execute(delete(AuditLog).where(AuditLog.organization_id == organization.id))
            db.execute(delete(Job).where(Job.organization_id == organization.id))
            db.execute(delete(ModelVersion).where(ModelVersion.organization_id == organization.id))
            db.execute(delete(Dataset).where(Dataset.organization_id == organization.id))
            db.execute(delete(Membership).where(Membership.organization_id == organization.id))
            db.execute(delete(User).where(User.id == user.id))
            db.execute(delete(Organization).where(Organization.id == organization.id))
        engine.dispose()


def upload(ingestion, content=CSV, purpose="TRAINING"):
    _, sessions, storage, principal, _ = ingestion
    return accept_upload(
        sessions,
        storage,
        principal,
        UploadMetadata(purpose=purpose, source_kind="SYNTHETIC"),
        BytesIO(content),
        "fixture.csv",
        len(content),
        str(uuid4()),
    )


@pytest.mark.parametrize(
    "purpose,status,code",
    [
        ("TRAINING", "SUCCEEDED", None),
        ("SCORING", "FAILED", "ACTIVE_MODEL_REQUIRED"),
    ],
)
def test_durable_validation_and_duplicate_delivery(ingestion, purpose, status, code):
    engine, sessions, storage, principal, _ = ingestion
    job_id, dataset_id = upload(ingestion, purpose=purpose)
    assert process_job(engine, storage, job_id, dataset_id) is False
    assert process_job(engine, storage, job_id, dataset_id) is False
    with sessions() as db:
        job, dataset = db.get(Job, job_id), db.get(Dataset, dataset_id)
        assert (job.status, job.error_code) == (status, code)
        assert job.total_rows == 1 and job.failed_rows == 0
        assert job.processed_rows == (1 if purpose == "TRAINING" else 0)
        assert job.attempt_count == 1 and job.started_at and job.completed_at
        assert dataset.status == "VALIDATED" and dataset.row_count == 1
        assert (
            db.scalar(
                select(func.count())
                .select_from(Transaction)
                .where(Transaction.organization_id == principal.organization_id)
            )
            == 0
        )
        assert (
            db.scalar(
                select(func.count()).select_from(AuditLog).where(AuditLog.resource_id == dataset_id)
            )
            == 1
        )


def test_bounded_row_errors_honest_counts(ingestion):
    engine, sessions, storage, _, _ = ingestion
    content = f"{HEADER}\n{ROW}\n" + (ROW.replace("12.34", "NaN") + "\n") * 150
    job_id, dataset_id = upload(ingestion, content.encode())
    process_job(engine, storage, job_id, dataset_id)
    with sessions() as db:
        job = db.get(Job, job_id)
        assert (job.total_rows, job.processed_rows, job.failed_rows) == (151, 1, 150)
        assert job.status == "FAILED" and job.error_code == "ROW_VALIDATION_FAILED"
        assert db.get(Dataset, dataset_id).status == "REJECTED"
        errors = list(db.scalars(select(JobError).where(JobError.job_id == job_id)))
        assert len(errors) == 100 and errors[0].row_number == 2
        assert all(
            error.code == "INVALID_AMOUNT" and "NaN" not in error.summary for error in errors
        )


def test_worker_infrastructure_retry_and_exhaustion(ingestion):
    engine, sessions, storage, _, _ = ingestion
    job_id, dataset_id = upload(ingestion)
    broken = Mock()
    broken.read.side_effect = StorageUnavailable
    for attempt in range(1, 4):
        assert process_job(engine, broken, job_id, dataset_id) is (attempt < 3)
        with sessions.begin() as db:
            job = db.get(Job, job_id)
            assert job.attempt_count == attempt
            job.params_json = {**job.params_json, "retry_at": 0}
    with sessions() as db:
        job = db.get(Job, job_id)
        assert job.status == "FAILED" and job.completed_at and job.processed_rows == 0
    process_job(engine, storage, job_id, dataset_id)
    with sessions() as db:
        assert db.get(Job, job_id).status == "FAILED"


def test_concurrent_delivery(ingestion):
    engine, sessions, storage, _, _ = ingestion
    job_id, dataset_id = upload(ingestion)
    entered, release = Event(), Event()
    original = storage.read

    @contextmanager
    def slow(*args):
        entered.set()
        assert release.wait(10)
        with original(*args) as file:
            yield file

    storage.read = slow
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(process_job, engine, storage, job_id, dataset_id)
        try:
            assert entered.wait(10)
            assert process_job(engine, storage, job_id, dataset_id) is False
        finally:
            release.set()
        assert first.result(timeout=10) is False
    with sessions() as db:
        job = db.get(Job, job_id)
        assert job.attempt_count == 1 and job.processed_rows == 1


def test_publication_failure_remains_recoverable(ingestion):
    _, sessions, storage, _, _ = ingestion
    job_id, dataset_id = upload(ingestion)
    publisher = Mock(side_effect=ConnectionError("isolated broker unavailable"))
    reconcile(sessions, storage, publisher)
    with sessions() as db:
        assert db.get(Job, job_id).status == "QUEUED"
    publisher.side_effect = None
    reconcile(sessions, storage, publisher)
    publisher.assert_called_with(str(job_id), str(dataset_id))
    reconcile(sessions, storage, publisher)
    assert publisher.call_count == 2  # Failed publish, successful retry; then cooldown.


def test_interrupted_upload_reconciliation(ingestion):
    _, sessions, storage, _, _ = ingestion
    job_id, dataset_id = upload(ingestion)
    with sessions.begin() as db:
        job = db.get(Job, job_id)
        job.params_json = {"upload_ready": False}
        job.created_at = datetime.now(UTC) - timedelta(minutes=6)
    publisher = Mock()
    reconcile(sessions, storage, publisher)
    assert not storage.objects and publisher.call_count == 0
    with sessions() as db:
        assert db.get(Job, job_id).error_code == "UPLOAD_INTERRUPTED"
        assert db.get(Dataset, dataset_id).status == "REJECTED"


@pytest.fixture
def client(ingestion):
    engine, sessions, storage, principal, settings = ingestion
    auth = AuthService(settings, engine)
    token = new_token()
    with sessions.begin() as db:
        db.add(
            SessionRecord(
                id=principal.session_id,
                user_id=principal.user_id,
                token_hash=token_hash(token),
                expires_at=datetime.now(UTC) + timedelta(hours=1),
            )
        )
    app = create_app(settings, Mock(), auth)
    try:
        with TestClient(app) as client:
            app.state.storage = storage
            client.cookies.set(settings.session_cookie, token)
            yield (
                client,
                {
                    "Origin": "http://testserver",
                    "X-CSRF-Token": auth.csrf.proof("session-header", token),
                },
            )
    finally:
        with sessions.begin() as db:
            db.execute(delete(SessionRecord).where(SessionRecord.user_id == principal.user_id))
        auth.limiter.close()


@pytest.mark.parametrize("role", ["ANALYST", "RISK_MANAGER", "ADMIN"])
def test_job_api_auth_and_no_private_metadata(ingestion, client, role):
    _, sessions, storage, principal, _ = ingestion
    job_id, _ = upload(ingestion)
    with sessions.begin() as db:
        db.get(Membership, principal.membership_id).role = role
    browser, _ = client
    response = browser.get(f"/api/v1/jobs/{job_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "QUEUED"
    assert all(key not in response.text for key in storage.objects)
    assert "sha256" not in response.text and "original_filename" not in response.text
    assert browser.get(f"/api/v1/jobs/{uuid4()}").status_code == 404
    browser.cookies.clear()
    assert browser.get(f"/api/v1/jobs/{job_id}").status_code == 401


def test_cross_organization_job(ingestion, client, migrated_engine):
    _, sessions, _, principal, _ = ingestion
    job_id, _ = upload(ingestion)
    with sessions.begin() as db:
        other = Organization(name="Other fictional organization")
        db.add(other)
        db.flush()
        db.get(Membership, principal.membership_id).organization_id = other.id
    try:
        assert client[0].get(f"/api/v1/jobs/{job_id}").status_code == 404
    finally:
        with sessionmaker(migrated_engine).begin() as db:
            db.get(Membership, principal.membership_id).organization_id = principal.organization_id
            db.delete(db.get(Organization, other.id))


def test_retry_preserves_committed_progress(ingestion):
    engine, sessions, storage, _, _ = ingestion
    job_id, dataset_id = upload(ingestion)
    original = storage.read

    @contextmanager
    def interrupted(*args):
        with original(*args) as file:
            yield file
        raise StorageUnavailable()

    storage.read = interrupted
    assert process_job(engine, storage, job_id, dataset_id)
    with sessions.begin() as db:
        job = db.get(Job, job_id)
        assert job.processed_rows == 1
        job.params_json = {**job.params_json, "retry_at": 0}
    storage.read = original
    assert not process_job(engine, storage, job_id, dataset_id)
    with sessions() as db:
        job = db.get(Job, job_id)
        assert (job.status, job.attempt_count, job.processed_rows) == ("SUCCEEDED", 2, 1)


def test_failed_put_has_recoverable_intent(ingestion):
    _, sessions, storage, _, _ = ingestion
    original = storage.put

    def ambiguous(*args):
        original(*args)
        raise StorageUnavailable()

    storage.put = ambiguous
    with pytest.raises(AuthError) as exc:
        upload(ingestion)
    assert exc.value.status == 503 and len(storage.objects) == 1
    with sessions.begin() as db:
        job = db.scalars(
            select(Job).where(Job.organization_id == ingestion[3].organization_id)
        ).one()
        assert not job.params_json["upload_ready"]
        job.created_at = datetime.now(UTC) - timedelta(minutes=6)
    reconcile(sessions, storage, Mock())
    assert not storage.objects


def test_rejected_object_cleanup_retries(ingestion, client):
    engine, sessions, storage, _, _ = ingestion
    job_id, dataset_id = upload(ingestion, CSV.replace(b"12.34", b"NaN"))
    process_job(engine, storage, job_id, dataset_id)
    original = storage.delete
    storage.delete = Mock(side_effect=StorageUnavailable)
    reconcile(sessions, storage, Mock())
    with sessions() as db:
        job = db.get(Job, job_id)
        assert job.params_json["cleanup_pending"]
        assert job.params_json["cleanup_error_code"] == "STORAGE_DELETE_UNAVAILABLE"
        assert job.status == "FAILED" and job.completed_at
        assert job.error_code == "ROW_VALIDATION_FAILED"
    response = client[0].get(f"/api/v1/jobs/{job_id}")
    assert response.status_code == 200 and response.json()["cleanup_pending"]
    assert response.json()["cleanup_error_code"] == "STORAGE_DELETE_UNAVAILABLE"
    assert storage.objects
    storage.delete = original
    reconcile(sessions, storage, Mock())
    assert not storage.objects
    with sessions() as db:
        job = db.get(Job, job_id)
        assert not job.params_json["cleanup_pending"]
        assert job.params_json["cleanup_error_code"] is None
        assert job.failed_rows == 1 and job.attempt_count == 1
    reconcile(sessions, storage, Mock())
    process_job(engine, storage, job_id, dataset_id)
    with sessions() as db:
        job = db.get(Job, job_id)
        assert job.attempt_count == 1 and job.failed_rows == 1
        assert (
            db.scalar(select(func.count()).select_from(JobError).where(JobError.job_id == job_id))
            == 1
        )


def test_worker_rejects_mismatched_ids(ingestion):
    engine, sessions, storage, _, _ = ingestion
    job_id, _ = upload(ingestion)
    assert not process_job(engine, storage, job_id, uuid4())
    with sessions() as db:
        assert db.get(Job, job_id).attempt_count == 0


def test_admission_quota_cannot_be_bypassed(ingestion):
    for _ in range(5):
        upload(ingestion)
    with pytest.raises(AuthError) as exc:
        upload(ingestion)
    assert exc.value.code == "INGESTION_LIMIT"
    assert len(ingestion[2].objects) == 5


def test_cleanup_failure_does_not_block_other_jobs(ingestion):
    engine, sessions, storage, _, _ = ingestion
    rejected_job, rejected_dataset = upload(ingestion, CSV.replace(b"12.34", b"NaN"))
    process_job(engine, storage, rejected_job, rejected_dataset)
    queued_job, queued_dataset = upload(ingestion)
    storage.delete = Mock(side_effect=StorageUnavailable)
    publisher = Mock()
    reconcile(sessions, storage, publisher)
    publisher.assert_called_once_with(str(queued_job), str(queued_dataset))
    with sessions() as db:
        job = db.get(Job, rejected_job)
        assert job.status == "FAILED" and job.params_json["cleanup_pending"]


def test_interrupted_upload_cleanup_failure_is_durable(ingestion):
    _, sessions, storage, _, _ = ingestion
    job_id, dataset_id = upload(ingestion)
    with sessions.begin() as db:
        job = db.get(Job, job_id)
        job.params_json = {"upload_ready": False}
        job.created_at = datetime.now(UTC) - timedelta(minutes=6)
    original = storage.delete
    storage.delete = Mock(side_effect=StorageUnavailable)
    publisher = Mock()
    reconcile(sessions, storage, publisher)
    with sessions() as db:
        job = db.get(Job, job_id)
        assert job.status == "FAILED" and job.error_code == "UPLOAD_INTERRUPTED"
        assert job.completed_at and job.params_json["cleanup_pending"]
        assert job.params_json["cleanup_error_code"] == "STORAGE_DELETE_UNAVAILABLE"
        assert db.get(Dataset, dataset_id).status == "REJECTED"
    storage.delete = original
    reconcile(sessions, storage, publisher)
    assert not storage.objects and publisher.call_count == 0


def test_delayed_upload_cannot_write_after_reconciliation(ingestion):
    _, sessions, storage, principal, _ = ingestion

    class DelayedSessions:
        calls = 0

        @contextmanager
        def begin(self):
            self.calls += 1
            if self.calls == 2:
                with sessions.begin() as db:
                    job = db.scalars(
                        select(Job).where(Job.organization_id == principal.organization_id)
                    ).one()
                    job.created_at = datetime.now(UTC) - timedelta(minutes=6)
                reconcile(sessions, storage, Mock())
            with sessions.begin() as db:
                yield db

    with pytest.raises(AuthError) as exc:
        accept_upload(
            DelayedSessions(),
            storage,
            principal,
            UploadMetadata(purpose="TRAINING", source_kind="SYNTHETIC"),
            BytesIO(CSV),
            "fixture.csv",
            len(CSV),
            str(uuid4()),
        )
    assert exc.value.code == "UPLOAD_INTERRUPTED" and not storage.objects
    with sessions() as db:
        job = db.scalars(select(Job).where(Job.organization_id == principal.organization_id)).one()
        assert job.status == "FAILED" and not job.params_json["upload_ready"]
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.resource_id == job.dataset_id)
            )
            == 0
        )


def test_object_write_followed_by_database_rollback_is_cleaned(ingestion):
    _, sessions, storage, principal, _ = ingestion

    class InterruptedSessions:
        calls = 0

        @contextmanager
        def begin(self):
            self.calls += 1
            with sessions.begin() as db:
                yield db
                if self.calls == 2:
                    raise RuntimeError("isolated transaction failure")

    with pytest.raises(RuntimeError, match="isolated transaction failure"):
        accept_upload(
            InterruptedSessions(),
            storage,
            principal,
            UploadMetadata(purpose="TRAINING", source_kind="SYNTHETIC"),
            BytesIO(CSV),
            "fixture.csv",
            len(CSV),
            str(uuid4()),
        )
    assert len(storage.objects) == 1
    with sessions.begin() as db:
        job = db.scalars(select(Job).where(Job.organization_id == principal.organization_id)).one()
        assert not job.params_json["upload_ready"]
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.resource_id == job.dataset_id)
            )
            == 0
        )
        job.created_at = datetime.now(UTC) - timedelta(minutes=6)
    reconcile(sessions, storage, Mock())
    assert not storage.objects


@pytest.mark.parametrize("role", ["ANALYST", "RISK_MANAGER", "ADMIN"])
@pytest.mark.parametrize("purpose", ["TRAINING", "SCORING"])
def test_multipart_upload_role_matrix(ingestion, client, role, purpose):
    engine, sessions, storage, principal, _ = ingestion
    with sessions.begin() as db:
        db.get(Membership, principal.membership_id).role = role
    browser, headers = client
    response = browser.post(
        "/api/v1/ingestions",
        headers=headers,
        data={"purpose": purpose, "source_kind": "SYNTHETIC"},
        files={"file": ("../../fictional.csv", CSV, "text/csv")},
    )
    allowed = purpose == "SCORING" or role == "ADMIN"
    assert response.status_code == (202 if allowed else 403)
    if not allowed:
        assert not storage.objects
        return
    result = response.json()
    assert result["status"] == "QUEUED"
    job_id, dataset_id = UUID(result["job_id"]), UUID(result["dataset_id"])
    with sessions() as db:
        assert db.get(Job, job_id).status == "QUEUED"
        dataset = db.get(Dataset, dataset_id)
        assert dataset.organization_id == principal.organization_id
        assert dataset.original_filename == "fictional.csv"
        assert dataset.size_bytes == len(CSV) and dataset.sha256 == sha256(CSV).hexdigest()
    process_job(engine, storage, job_id, dataset_id)
    status = browser.get(f"/api/v1/jobs/{job_id}").json()
    assert status["status"] == ("SUCCEEDED" if purpose == "TRAINING" else "FAILED")
    assert status["processed_rows"] == (1 if purpose == "TRAINING" else 0)


@pytest.mark.parametrize("failure", ["anonymous", "csrf", "origin", "cross-site"])
def test_upload_auth_before_reading_body(client, failure):
    browser, headers = client
    if failure == "anonymous":
        browser.cookies.clear()
    elif failure == "csrf":
        headers.pop("X-CSRF-Token")
    elif failure == "origin":
        headers["Origin"] = "https://hostile.invalid"
    else:
        headers["Sec-Fetch-Site"] = "cross-site"
    response = browser.post("/api/v1/ingestions", headers=headers, content=b"not multipart")
    assert response.status_code == (401 if failure == "anonymous" else 403)


@pytest.mark.parametrize(
    "data,filename,mime,content,expected",
    [
        (
            {"purpose": "TRAINING", "source_kind": "SYNTHETIC", "organization_id": "fake"},
            "test.csv",
            "text/csv",
            CSV,
            422,
        ),
        (
            {"purpose": "TRAINING", "source_kind": "PUBLIC_DATASET"},
            "test.csv",
            "text/csv",
            CSV,
            422,
        ),
        (
            {
                "purpose": "TRAINING",
                "source_kind": "PUBLIC_DATASET",
                "license_reference": "unreviewed",
            },
            "test.csv",
            "text/csv",
            CSV,
            422,
        ),
        ({"purpose": "OTHER", "source_kind": "SYNTHETIC"}, "test.csv", "text/csv", CSV, 422),
        ({"purpose": "TRAINING", "source_kind": "SYNTHETIC"}, "test.exe", "text/csv", CSV, 422),
        (
            {"purpose": "TRAINING", "source_kind": "SYNTHETIC"},
            "test.csv",
            "application/pdf",
            CSV,
            415,
        ),
        ({"purpose": "TRAINING", "source_kind": "SYNTHETIC"}, "test.csv", "text/csv", b"", 422),
        (
            {"purpose": "TRAINING", "source_kind": "SYNTHETIC"},
            "test.csv",
            "text/csv",
            b"email\n",
            422,
        ),
    ],
)
def test_upload_rejections_leave_no_objects_or_jobs(
    ingestion, client, data, filename, mime, content, expected
):
    _, sessions, storage, principal, _ = ingestion
    browser, headers = client
    response = browser.post(
        "/api/v1/ingestions", headers=headers, data=data, files={"file": (filename, content, mime)}
    )
    assert response.status_code == expected
    assert not storage.objects
    with sessions() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(Job)
                .where(Job.organization_id == principal.organization_id)
            )
            == 0
        )


def test_broker_failure_does_not_block_rejected_cleanup(ingestion):
    engine, sessions, storage, _, _ = ingestion
    queued, _ = upload(ingestion)
    rejected, dataset = upload(ingestion, CSV.replace(b"12.34", b"NaN"))
    process_job(engine, storage, rejected, dataset)
    reconcile(sessions, storage, Mock(side_effect=ConnectionError("private exception marker")))
    with sessions() as db:
        assert db.get(Job, queued).status == "QUEUED"
        assert not db.get(Job, rejected).params_json["cleanup_pending"]
    assert len(storage.objects) == 1


@pytest.mark.parametrize("case", ["two_files", "duplicate_field", "oversized", "field_limit"])
def test_multipart_resource_limits_at_endpoint(ingestion, client, case):
    from app.ingestion.validation import MAX_BYTES

    browser, headers = client
    fields = [("purpose", (None, "TRAINING")), ("source_kind", (None, "SYNTHETIC"))]
    content = CSV
    expected = 400
    if case == "two_files":
        fields.append(("file", ("other.csv", CSV, "text/csv")))
    elif case == "duplicate_field":
        fields.append(("purpose", (None, "SCORING")))
        expected = 422
    elif case == "oversized":
        content = CSV + b"x" * MAX_BYTES
        expected = 413
    else:
        fields.append(("license_reference", (None, "x" * 513)))
    fields.append(("file", ("test.csv", content, "text/csv")))
    response = browser.post("/api/v1/ingestions", headers=headers, files=fields)
    assert response.status_code == expected
    assert response.json()["error"]["request_id"]
    assert not ingestion[2].objects


def test_parallel_admissions_obey_pending_limit(ingestion):
    for _ in range(4):
        upload(ingestion)

    def attempt():
        try:
            upload(ingestion)
            return 202
        except AuthError as exc:
            return exc.status

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(lambda _: attempt(), range(2))) == [202, 429]
    assert len(ingestion[2].objects) == 5
