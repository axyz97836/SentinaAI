"""PYTEST_DONT_REWRITE: synthetic session values stay out of assertion diagnostics."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch
from uuid import UUID, uuid4

import numpy as np
import pytest
from sqlalchemy import delete, event, func, select
from sqlalchemy.orm import sessionmaker
from test_ingestion import client as client
from test_ingestion import ingestion as ingestion
from test_ingestion import password_hash as password_hash
from test_models import ml as ml
from test_models import trained

from app.auth.errors import AuthError
from app.ml import artifacts
from app.ml.service import activate
from app.models import (
    Alert,
    AuditLog,
    Membership,
    ModelVersion,
    RiskSettings,
    RuleDefinition,
    RuleHit,
    ScoringResult,
    SessionRecord,
    Transaction,
    TransactionLabel,
)
from app.scoring.calculation import composite
from app.scoring.history import evaluate
from app.scoring.schema import TransactionInput
from app.scoring.service import score_transaction

pytestmark = pytest.mark.database
PAYLOAD = {
    "external_id": "syn-single",
    "customer_ref": "customer-fictional",
    "occurred_at": "2026-01-23T10:00:00Z",
    "amount": "100.00",
    "currency": "INR",
    "merchant_category": "grocery",
    "country_code": "IN",
    "channel": "WEB",
}


@pytest.fixture
def scoring(ml, migrated_engine):
    _, sessions, storage, principal, _ = ml
    model = trained(ml)
    with sessions.begin() as db:
        activate(db, storage, principal, model, "fixture")
        db.add(
            RiskSettings(organization_id=principal.organization_id, updated_by=principal.user_id)
        )
    try:
        yield ml
    finally:
        with sessionmaker(migrated_engine).begin() as db:
            txs = select(Transaction.id).where(
                Transaction.organization_id == principal.organization_id
            )
            scores = select(ScoringResult.id).where(ScoringResult.transaction_id.in_(txs))
            db.execute(delete(Alert).where(Alert.scoring_result_id.in_(scores)))
            db.execute(delete(RuleHit).where(RuleHit.scoring_result_id.in_(scores)))
            db.execute(delete(ScoringResult).where(ScoringResult.transaction_id.in_(txs)))
            db.execute(delete(TransactionLabel).where(TransactionLabel.transaction_id.in_(txs)))
            db.execute(
                delete(Transaction).where(Transaction.organization_id == principal.organization_id)
            )
            db.execute(
                delete(RuleDefinition).where(
                    RuleDefinition.organization_id == principal.organization_id
                )
            )
            db.execute(
                delete(RiskSettings).where(
                    RiskSettings.organization_id == principal.organization_id
                )
            )


def submit(scoring, payload=None):
    _, sessions, storage, principal, _ = scoring
    with sessions.begin() as db:
        return score_transaction(
            db,
            storage,
            principal.organization_id,
            principal.user_id,
            TransactionInput.model_validate(payload or PAYLOAD),
            source="SINGLE",
        )


def test_real_score_replay_and_threshold_snapshot(scoring, client):
    browser, headers = client
    _, sessions, _, principal, _ = scoring
    first = browser.post("/api/v1/transactions", headers=headers, json=PAYLOAD)
    assert first.status_code == 201
    result = first.json()
    detail = browser.get(f"/api/v1/transactions/{result['transaction_id']}")
    assert detail.status_code == 200
    score = detail.json()["score"]
    assert 0 <= score["risk_score"] <= 100 and score["latency_ms"] >= 0
    assert score["explanation_status"] == "PARTIAL"
    assert {item["status"] for item in score["explanation_json"]["rules"]} == {"NOT_CONFIGURED"}
    assert score["risk_score"] == composite(
        Decimal(score["supervised_probability"]),
        Decimal(score["anomaly_percentile"]),
        Decimal(score["rule_signal"]),
        score["explanation_json"]["weights"],
    )
    assert not any(word in detail.text for word in ("artifact_key", "token_hash", "password_hash"))
    with sessions.begin() as db:
        db.get(ModelVersion, UUID(result["model_version_id"])).is_active = False
        settings = db.get(RiskSettings, principal.organization_id)
        settings.alert_threshold = 0
        settings.version += 1
    replay = browser.post(
        "/api/v1/transactions", headers=headers, json={**PAYLOAD, "amount": 100, "device_ref": ""}
    )
    assert replay.status_code == 200 and replay.json() == result
    assert browser.get(f"/api/v1/transactions/{result['transaction_id']}").json()["score"] == score
    conflict = browser.post(
        "/api/v1/transactions", headers=headers, json={**PAYLOAD, "amount": "101"}
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "DUPLICATE_TRANSACTION_CONFLICT"
    assert (
        browser.post(
            "/api/v1/transactions", headers=headers, json={**PAYLOAD, "external_id": "new"}
        ).json()["error"]["code"]
        == "ACTIVE_MODEL_REQUIRED"
    )


@pytest.mark.parametrize("role", ["ADMIN", "ANALYST", "RISK_MANAGER"])
def test_roles_csrf_validation_and_missing_session(scoring, client, role):
    browser, headers = client
    _, sessions, _, principal, _ = scoring
    with sessions.begin() as db:
        db.get(Membership, principal.membership_id).role = role
    assert browser.post("/api/v1/transactions", json=PAYLOAD).status_code == 403
    assert (
        browser.post(
            "/api/v1/transactions",
            headers={**headers, "Origin": "https://foreign.invalid"},
            json=PAYLOAD,
        ).status_code
        == 403
    )
    assert (
        browser.post(
            "/api/v1/transactions", headers=headers, json={**PAYLOAD, "fraud_label": 1}
        ).status_code
        == 422
    )
    assert (
        browser.post(
            "/api/v1/transactions", headers=headers, json={**PAYLOAD, "extra": "x" * 5000}
        ).status_code
        == 413
    )
    assert browser.post("/api/v1/transactions", headers=headers, json=PAYLOAD).status_code == 201
    browser.cookies.clear()
    assert browser.post("/api/v1/transactions", headers=headers, json=PAYLOAD).status_code == 401
    assert browser.get("/api/v1/transactions").status_code == 401


@pytest.mark.parametrize("mode", ["expired", "revoked"])
def test_expired_revoked_session(scoring, client, mode):
    browser, headers = client
    _, sessions, _, principal, _ = scoring
    with sessions.begin() as db:
        token = db.scalars(
            select(SessionRecord).where(SessionRecord.user_id == principal.user_id)
        ).one()
        if mode == "revoked":
            token.revoked_at = datetime.now(UTC)
        else:
            token.created_at = datetime.now(UTC) - timedelta(days=2)
            token.expires_at = datetime.now(UTC) - timedelta(days=1)
    assert browser.post("/api/v1/transactions", headers=headers, json=PAYLOAD).status_code == 401


@pytest.mark.parametrize("mode", ["missing", "corrupt", "schema"])
def test_bad_artifact_no_partial_transaction(scoring, client, migrated_engine, mode):
    browser, headers = client
    _, sessions, storage, principal, _ = scoring
    with sessions() as db:
        model = db.scalars(
            select(ModelVersion).where(ModelVersion.organization_id == principal.organization_id)
        ).one()
        key = artifacts.key(principal.organization_id, model.id)
    if mode == "missing":
        storage.objects.pop(key)
    elif mode == "corrupt":
        storage.objects[key] = b"corrupt"
    else:
        with sessionmaker(migrated_engine).begin() as db:
            db.get(ModelVersion, model.id).feature_schema_json = {"version": "incompatible"}
    response = browser.post("/api/v1/transactions", headers=headers, json=PAYLOAD)
    assert response.status_code == 409
    with sessions() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(Transaction)
                .where(Transaction.organization_id == principal.organization_id)
            )
            == 0
        )


@pytest.mark.parametrize("threshold,expected", [(69, 1), (70, 1), (71, 0)])
def test_configured_alert_boundaries_and_exactly_one(scoring, threshold, expected):
    _, sessions, _, principal, _ = scoring
    with sessions.begin() as db:
        db.get(RiskSettings, principal.organization_id).alert_threshold = threshold
    with patch(
        "app.ml.training.BaselineBundle.components", return_value=(np.array([1.0]), np.array([0.4]))
    ):
        first, created = submit(scoring)
        replay, created_again = submit(scoring)
    assert created and not created_again and first == replay and first["risk_score"] == 70
    with sessions() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(Alert)
                .where(Alert.organization_id == principal.organization_id)
            )
            == expected
        )


def test_concurrent_matching_and_conflicting_submissions(scoring):
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda _: submit(scoring), range(6)))
    assert sum(created for _, created in results) == 1
    assert all(result == results[0][0] for result, _ in results)

    def conflict():
        try:
            submit(scoring, {**PAYLOAD, "amount": "999"})
        except AuthError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=3) as pool:
        assert (
            list(pool.map(lambda _: conflict(), range(3))) == ["DUPLICATE_TRANSACTION_CONFLICT"] * 3
        )


def test_atomic_audit_failure_rolls_back_every_write(scoring):
    engine, sessions, _, principal, _ = scoring

    def fail_audit(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO audit_logs"):
            raise RuntimeError("injected persistence failure")

    event.listen(engine, "before_cursor_execute", fail_audit)
    try:
        with pytest.raises(RuntimeError, match="injected"):
            submit(scoring)
    finally:
        event.remove(engine, "before_cursor_execute", fail_audit)
    with sessions() as db:
        assert not db.scalar(
            select(Transaction.id).where(Transaction.organization_id == principal.organization_id)
        )
        assert not db.scalar(
            select(Alert.id).where(Alert.organization_id == principal.organization_id)
        )
        assert not db.scalar(
            select(AuditLog.id).where(
                AuditLog.organization_id == principal.organization_id,
                AuditLog.action == "TRANSACTION_SCORED",
            )
        )


def test_pagination_filters_and_foreign_ids(scoring, client, migrated_engine):
    browser, headers = client
    _, sessions, _, principal, _ = scoring
    identifiers = []
    for i in range(3):
        response = browser.post(
            "/api/v1/transactions", headers=headers, json={**PAYLOAD, "external_id": f"page-{i}"}
        )
        assert response.status_code == 201
        identifiers.append(response.json()["transaction_id"])
    first = browser.get("/api/v1/transactions", params={"limit": 2}).json()
    second = browser.get(
        "/api/v1/transactions", params={"limit": 2, "cursor": first["next_cursor"]}
    ).json()
    assert {row["id"] for row in first["items"] + second["items"]} == set(identifiers)
    assert second["next_cursor"] is None
    chosen = first["items"][0]["risk_band"]
    assert (
        browser.get("/api/v1/transactions", params={"risk_band": chosen}).json()
        == browser.get("/api/v1/transactions", params={"band": chosen}).json()
    )
    assert (
        len(browser.get("/api/v1/transactions", params={"search": "page-1"}).json()["items"]) == 1
    )
    assert (
        browser.get("/api/v1/transactions", params={"date_to": "2026-01-23T10:00:00Z"}).json()[
            "items"
        ]
        == []
    )
    for query in (
        {"limit": 101},
        {"cursor": "bad"},
        {"search": "%' OR 1=1"},
        {"band": "INVALID"},
        {"date_from": "2026-01-23T10:00:00"},
    ):
        assert browser.get("/api/v1/transactions", params=query).status_code == 422
    assert browser.get(f"/api/v1/transactions/{uuid4()}").status_code == 404
    # Move only the test membership to a fixture organization; genuine auth resolves it afresh.
    from app.models import Organization

    with sessionmaker(migrated_engine).begin() as db:
        foreign = Organization(name="Fictional isolation")
        db.add(foreign)
        db.flush()
        foreign_id = foreign.id
        db.get(Membership, principal.membership_id).organization_id = foreign_id
    try:
        assert browser.get("/api/v1/transactions").json()["items"] == []
        assert browser.get(f"/api/v1/transactions/{identifiers[0]}").status_code == 404
    finally:
        with sessionmaker(migrated_engine).begin() as db:
            db.get(Membership, principal.membership_id).organization_id = principal.organization_id
            db.execute(delete(Organization).where(Organization.id == foreign_id))


def test_prior_only_history_missing_context_and_actual_hits(scoring, migrated_engine):
    _, sessions, _, principal, _ = scoring
    with sessions.begin() as db:
        for code, params in [
            ("AMOUNT_OUTLIER", {"multiplier": 3, "min_history": 1}),
            ("HIGH_VELOCITY", {"window_minutes": 10, "count_threshold": 1}),
            ("DEVICE_CHANGE", {}),
        ]:
            db.add(
                RuleDefinition(
                    organization_id=principal.organization_id,
                    code=code,
                    description="Synthetic fixture",
                    parameters_json=params,
                )
            )
    payload = TransactionInput.model_validate({**PAYLOAD, "device_ref": "device-new"})
    with sessions.begin() as db:
        signal, evidence = evaluate(db, principal.organization_id, payload)
        assert signal == 0 and {row["status"] for row in evidence} == {"MISSING_HISTORY"}
    # Same-time and future rows must not influence any rule.
    submit(
        scoring,
        {
            **PAYLOAD,
            "external_id": "future",
            "occurred_at": "2026-01-23T11:00:00Z",
            "amount": "1",
            "device_ref": "old",
        },
    )
    submit(scoring, {**PAYLOAD, "external_id": "equal", "amount": "1", "device_ref": "old"})
    with sessions.begin() as db:
        assert evaluate(db, principal.organization_id, payload)[0] == 0
    submit(
        scoring,
        {
            **PAYLOAD,
            "external_id": "prior",
            "occurred_at": "2026-01-23T09:50:00Z",
            "amount": "10",
            "device_ref": "old",
        },
    )
    result, _ = submit(scoring, {**PAYLOAD, "device_ref": "device-new"})
    with sessions() as db:
        score = db.get(ScoringResult, result["scoring_result_id"])
        assert score.rule_signal == 1 and score.explanation_status == "PARTIAL"
        hits = list(db.scalars(select(RuleHit).where(RuleHit.scoring_result_id == score.id)))
        assert len(hits) == 3 and all(hit.strength == 1 for hit in hits)
        assert all("'old'" not in str(hit.details_json) for hit in hits)


def scoring_csv(rows):
    import csv
    from io import StringIO

    output = StringIO()
    fields = list(PAYLOAD) + ["device_ref", "fraud_label"]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    writer.writerows({**PAYLOAD, "device_ref": "", "fraud_label": "0", **row} for row in rows)
    return output.getvalue().encode()


def test_csv_partial_rows_replay_label_separation_and_duplicate_delivery(scoring, client):
    from test_ingestion import upload

    from app.ingestion.processing import process_job
    from app.models import Job, JobError

    engine, sessions, storage, principal, _ = scoring
    rows = [
        {"external_id": "csv-first"},
        {"external_id": "csv-first"},
        {"external_id": "csv-first", "amount": "101"},
        {"external_id": "invalid", "amount": "NaN"},
        {"external_id": "csv-second", "fraud_label": "1"},
    ]
    job_id, dataset_id = upload(scoring, scoring_csv(rows), purpose="SCORING")
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(
            pool.map(lambda _: process_job(engine, storage, job_id, dataset_id), range(2))
        ) == [False, False]
    process_job(engine, storage, job_id, dataset_id)
    with sessions() as db:
        job = db.get(Job, job_id)
        assert (
            job.status,
            job.total_rows,
            job.processed_rows,
            job.failed_rows,
            job.attempt_count,
        ) == ("SUCCEEDED", 5, 3, 2, 1)
        assert job.error_message == "Completed with row errors."
        txs = list(
            db.scalars(
                select(Transaction).where(Transaction.organization_id == principal.organization_id)
            )
        )
        assert len(txs) == 2
        assert (
            db.scalar(
                select(func.count())
                .select_from(ScoringResult)
                .where(ScoringResult.transaction_id.in_([t.id for t in txs]))
            )
            == 2
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(TransactionLabel)
                .where(TransactionLabel.transaction_id.in_([t.id for t in txs]))
            )
            == 2
        )
        assert {e.code for e in db.scalars(select(JobError).where(JobError.job_id == job_id))} == {
            "INVALID_AMOUNT",
            "DUPLICATE_TRANSACTION_CONFLICT",
        }
    browser, _ = client
    status = browser.get(f"/api/v1/jobs/{job_id}").json()
    assert (
        status["progress_phase"] == "SCORING"
        and status["has_output"]
        and status["completed_with_row_errors"]
    )
    # Direct replay ignores CSV-only ground truth and retains the same result.
    result, created = submit(scoring, {**PAYLOAD, "external_id": "csv-first"})
    assert not created
    original = browser.get(f"/api/v1/transactions/{result['transaction_id']}").json()["score"]
    second_job, second_data = upload(
        scoring, scoring_csv([{"external_id": "csv-first", "fraud_label": "1"}]), purpose="SCORING"
    )
    process_job(engine, storage, second_job, second_data)
    with sessions() as db:
        assert db.get(Job, second_job).failed_rows == 1
        assert db.get(TransactionLabel, result["transaction_id"]).fraud_label is False
    assert (
        browser.get(f"/api/v1/transactions/{result['transaction_id']}").json()["score"] == original
    )


def test_csv_crash_retry_has_atomic_progress_and_pinned_model(scoring):
    from test_ingestion import upload

    from app.ingestion.processing import process_job
    from app.models import Job

    engine, sessions, storage, principal, _ = scoring
    job_id, dataset_id = upload(
        scoring, scoring_csv([{"external_id": f"retry-{i}"} for i in range(4)]), purpose="SCORING"
    )
    from app.scoring.service import score_transaction as real_score

    calls = 0

    def interrupt(*args, **kwargs):
        nonlocal calls
        calls += 1
        result = real_score(*args, **kwargs)
        if calls == 2:
            raise RuntimeError("simulated worker loss before progress commit")
        return result

    with patch("app.scoring.processing.score_transaction", side_effect=interrupt):
        with pytest.raises(RuntimeError, match="simulated"):
            process_job(engine, storage, job_id, dataset_id)
    with sessions.begin() as db:
        job = db.get(Job, job_id)
        assert job.processed_rows == 1 and job.status == "PROCESSING"
        pinned = job.model_version_id
        db.get(ModelVersion, pinned).is_active = False
        assert (
            db.scalar(
                select(func.count())
                .select_from(Transaction)
                .where(Transaction.organization_id == principal.organization_id)
            )
            == 1
        )
    assert process_job(engine, storage, job_id, dataset_id) is False
    with sessions() as db:
        job = db.get(Job, job_id)
        assert (job.status, job.processed_rows, job.failed_rows, job.attempt_count) == (
            "SUCCEEDED",
            4,
            0,
            2,
        )
        assert job.model_version_id == pinned
        scores = list(
            db.scalars(
                select(ScoringResult)
                .join(Transaction)
                .where(Transaction.organization_id == principal.organization_id)
            )
        )
        assert len(scores) == 4 and all(score.model_version_id == pinned for score in scores)


def test_csv_storage_retry_and_model_failure_preserves_valid_source(scoring):
    from test_ingestion import upload

    from app.ingestion.processing import process_job
    from app.ingestion.storage import StorageUnavailable
    from app.models import Dataset, Job

    engine, sessions, storage, principal, _ = scoring
    job_id, dataset_id = upload(
        scoring, scoring_csv([{"external_id": "storage-retry"}]), purpose="SCORING"
    )
    with patch("app.ml.artifacts.read", side_effect=StorageUnavailable):
        assert process_job(engine, storage, job_id, dataset_id)
    with sessions.begin() as db:
        job = db.get(Job, job_id)
        assert job.processed_rows == 0 and job.error_code == "STORAGE_UNAVAILABLE"
        job.params_json = {**job.params_json, "retry_at": 0}
    assert process_job(engine, storage, job_id, dataset_id) is False
    with sessions() as db:
        assert db.get(Job, job_id).status == "SUCCEEDED"
    job_id, dataset_id = upload(
        scoring, scoring_csv([{"external_id": "corrupt-model"}]), purpose="SCORING"
    )
    with sessions() as db:
        model = db.scalars(
            select(ModelVersion).where(ModelVersion.organization_id == principal.organization_id)
        ).one()
    storage.objects[artifacts.key(principal.organization_id, model.id)] = b"corrupt"
    process_job(engine, storage, job_id, dataset_id)
    with sessions() as db:
        job = db.get(Job, job_id)
        assert job.status == "FAILED" and job.processed_rows == 0
        assert job.error_code == "ARTIFACT_INTEGRITY_FAILED"
        assert db.get(Dataset, dataset_id).status == "VALIDATED"
        assert storage.key(principal.organization_id, dataset_id) in storage.objects


def test_csv_errors_bounded_and_no_labels_in_inference(scoring):
    from test_ingestion import upload

    from app.ingestion.processing import process_job
    from app.models import Job, JobError

    engine, sessions, storage, _, _ = scoring
    rows = [{"external_id": f"bad-{i}", "amount": "NaN"} for i in range(105)]
    rows += [{"external_id": "truthful", "fraud_label": "1"}]
    job_id, dataset_id = upload(scoring, scoring_csv(rows), purpose="SCORING")
    from app.ml.training import BaselineBundle

    real = BaselineBundle.components

    def inspect(self, values):
        assert len(values) == 1 and "fraud_label" not in values[0]
        return real(self, values)

    with patch.object(BaselineBundle, "components", inspect):
        process_job(engine, storage, job_id, dataset_id)
    with sessions() as db:
        job = db.get(Job, job_id)
        assert (job.total_rows, job.processed_rows, job.failed_rows) == (106, 1, 105)
        assert (
            db.scalar(select(func.count()).select_from(JobError).where(JobError.job_id == job_id))
            == 100
        )


def test_rule_states_disabled_unsupported_and_evaluated_no_hit(scoring):
    _, sessions, _, principal, _ = scoring
    submit(
        scoring,
        {
            **PAYLOAD,
            "external_id": "prior",
            "occurred_at": "2026-01-23T09:59:00Z",
            "device_ref": "same",
        },
    )
    with sessions.begin() as db:
        db.add_all(
            [
                RuleDefinition(
                    organization_id=principal.organization_id,
                    code="AMOUNT_OUTLIER",
                    description="Fixture",
                    enabled=False,
                    parameters_json={},
                ),
                RuleDefinition(
                    organization_id=principal.organization_id,
                    code="HIGH_VELOCITY",
                    description="Fixture",
                    parameters_json={"window_minutes": 60, "count_threshold": 1},
                ),
                RuleDefinition(
                    organization_id=principal.organization_id,
                    code="DEVICE_CHANGE",
                    description="Fixture",
                    parameters_json={},
                ),
            ]
        )
    with sessions.begin() as db:
        signal, evidence = evaluate(
            db,
            principal.organization_id,
            TransactionInput.model_validate({**PAYLOAD, "device_ref": "same"}),
        )
        assert signal == 0
        assert [row["status"] for row in evidence] == [
            "DISABLED",
            "UNSUPPORTED_PARAMETERS",
            "NOT_HIT",
        ]
        # The same existing history is absent from a different organization context.
        assert evaluate(db, uuid4(), TransactionInput.model_validate(PAYLOAD))[0] == 0


def test_changed_active_model_only_affects_new_transaction(scoring):
    _, sessions, storage, principal, _ = scoring
    first, _ = submit(scoring)
    with sessions() as db:
        dataset_id = db.get(ModelVersion, first["model_version_id"]).training_dataset_id
    second = trained(scoring, dataset_id)
    with sessions.begin() as db:
        activate(db, storage, principal, second, "fixture")
    assert submit(scoring)[0] == first
    new, _ = submit(scoring, {**PAYLOAD, "external_id": "after-activation"})
    assert new["model_version_id"] == second and second != first["model_version_id"]


def test_two_csv_jobs_and_direct_request_share_one_idempotency_boundary(scoring):
    from test_ingestion import upload

    from app.ingestion.processing import process_job
    from app.models import Job

    engine, sessions, storage, principal, _ = scoring
    first = upload(scoring, scoring_csv([{}]), purpose="SCORING")
    second = upload(scoring, scoring_csv([{}]), purpose="SCORING")
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [
            pool.submit(process_job, engine, storage, *first),
            pool.submit(process_job, engine, storage, *second),
            pool.submit(submit, scoring),
        ]
        for future in futures:
            future.result()
    with sessions() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(Transaction)
                .where(Transaction.organization_id == principal.organization_id)
            )
            == 1
        )
        for job_id, _ in (first, second):
            job = db.get(Job, job_id)
            assert job.status == "SUCCEEDED" and job.processed_rows == 1 and job.failed_rows == 0


def test_foreign_history_and_same_external_id_are_independent(scoring, migrated_engine):
    from app.models import Organization

    _, sessions, _, principal, _ = scoring
    with sessions.begin() as db:
        foreign = Organization(name="Fictional foreign history")
        db.add(foreign)
        db.flush()
        foreign_id = foreign.id
        db.add(
            Transaction(
                organization_id=foreign_id,
                source="SINGLE",
                **TransactionInput.model_validate(
                    {
                        **PAYLOAD,
                        "occurred_at": "2026-01-23T09:59:00Z",
                        "amount": "1",
                        "device_ref": "old",
                    }
                ).values(),
            )
        )
        db.add(
            RuleDefinition(
                organization_id=principal.organization_id,
                code="DEVICE_CHANGE",
                description="Fixture",
                parameters_json={},
            )
        )
    try:
        result, created = submit(scoring, {**PAYLOAD, "device_ref": "new"})
        assert created
        with sessions() as db:
            score = db.get(ScoringResult, result["scoring_result_id"])
            assert score.rule_signal == 0
            assert score.explanation_json["rules"][2]["status"] == "MISSING_HISTORY"
    finally:
        with sessionmaker(migrated_engine).begin() as db:
            db.execute(delete(Transaction).where(Transaction.organization_id == foreign_id))
            db.execute(delete(Organization).where(Organization.id == foreign_id))
