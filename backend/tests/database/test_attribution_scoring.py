"""PYTEST_DONT_REWRITE: explanation evidence uses fictional fixtures only."""

from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import select
from test_ingestion import client as client
from test_ingestion import ingestion as ingestion
from test_ingestion import password_hash as password_hash
from test_models import ml as ml
from test_risk_configuration import add_rules
from test_transaction_scoring import PAYLOAD, submit
from test_transaction_scoring import scoring as scoring

from app.models import ModelVersion, RuleDefinition, ScoringResult, Transaction

pytestmark = pytest.mark.database


@pytest.mark.parametrize(
    "state,expected",
    [
        ("missing_rules", "PARTIAL"),
        ("missing_history", "PARTIAL"),
        ("evaluated", "COMPLETE"),
        ("disabled", "COMPLETE"),
    ],
)
def test_genuine_attribution_persistence_and_status(scoring, client, state, expected):
    _, sessions, _, principal, _ = scoring
    if state != "missing_rules":
        add_rules(sessions, principal.organization_id)
    if state == "evaluated":
        submit(
            scoring,
            {
                **PAYLOAD,
                "external_id": "prior",
                "occurred_at": "2026-01-23T09:59:00Z",
                "amount": "10",
                "device_ref": "same",
            },
        )
    if state == "disabled":
        with sessions.begin() as db:
            for rule in db.scalars(
                select(RuleDefinition).where(
                    RuleDefinition.organization_id == principal.organization_id
                )
            ):
                rule.enabled = False
    result, _ = submit(scoring, {**PAYLOAD, "device_ref": "same"})
    browser, _ = client
    response = browser.get(f"/api/v1/transactions/{result['transaction_id']}/explanation")
    assert response.status_code == 200
    body = response.json()
    assert body["explanation_status"] == expected
    attribution = body["supervised_attribution"]
    assert attribution["available"] and attribution["method"] == "SHAP_LINEAR_INTERVENTIONAL"
    assert attribution["reference_count"] == 1200 and attribution["units"] == "log_odds"
    assert 0 < len(attribution["top_features"]) <= 5
    assert (
        abs(
            attribution["base_value"]
            + attribution["remaining_features_contribution"]
            + sum(row["contribution"] for row in attribution["top_features"])
            - attribution["model_output"]
        )
        < 1e-10
    )
    with sessions() as db:
        stored = db.get(ScoringResult, result["scoring_result_id"])
        assert stored.explanation_json["supervised_attribution"] == attribution
    assert submit(scoring, {**PAYLOAD, "device_ref": "same"}) == (result, False)
    assert (
        browser.get(f"/api/v1/transactions/{result['transaction_id']}/explanation").json() == body
    )


@pytest.mark.parametrize(
    "failure", ["background_missing", "constructor_failure", "generation_failure"]
)
def test_attribution_failure_preserves_valid_score_and_safe_partial(
    scoring, client, failure, caplog
):
    _, sessions, storage, principal, _ = scoring
    original, _ = submit(scoring)
    with sessions() as db:
        baseline = db.get(ScoringResult, original["scoring_result_id"])
        expected = (
            baseline.risk_score,
            baseline.supervised_probability,
            baseline.anomaly_percentile,
            baseline.rule_signal,
        )
        model = db.get(ModelVersion, original["model_version_id"])
    if failure == "background_missing":
        storage.objects.pop(storage.key(principal.organization_id, model.training_dataset_id))
        result, _ = submit(scoring, {**PAYLOAD, "external_id": "partial"})
    else:
        target = (
            "app.ml.attribution.shap.LinearExplainer"
            if failure == "constructor_failure"
            else "app.ml.attribution.shap.LinearExplainer.shap_values"
        )
        with patch(target, side_effect=RuntimeError("private-attribution-marker")):
            result, _ = submit(scoring, {**PAYLOAD, "external_id": "partial"})
    with sessions() as db:
        score = db.get(ScoringResult, result["scoring_result_id"])
        assert (
            score.risk_score,
            score.supervised_probability,
            score.anomaly_percentile,
            score.rule_signal,
        ) == expected
        assert score.explanation_status == "PARTIAL"
        assert not score.explanation_json["supervised_attribution"]["available"]
        assert score.explanation_json["supervised_attribution"]["top_features"] == []
    browser, _ = client
    response = browser.get(f"/api/v1/transactions/{result['transaction_id']}/explanation")
    assert "private-attribution-marker" not in response.text + caplog.text


def test_explanation_foreign_organization_denial(scoring, client):
    result, _ = submit(scoring)
    browser, _ = client
    from dataclasses import replace

    from app.auth.dependencies import authenticated

    principal = scoring[3]
    browser.app.dependency_overrides[authenticated] = lambda: replace(
        principal, organization_id=uuid4()
    )
    try:
        assert (
            browser.get(f"/api/v1/transactions/{result['transaction_id']}/explanation").status_code
            == 404
        )
    finally:
        browser.app.dependency_overrides.clear()


def test_operational_scoring_refuses_non_authoritative_runtime(scoring, client):
    browser, headers = client
    with patch("app.ml.runtime.platform.system", return_value="Darwin"):
        response = browser.post("/api/v1/transactions", headers=headers, json=PAYLOAD)
    assert (
        response.status_code == 409
        and response.json()["error"]["code"] == "MODEL_RUNTIME_UNSUPPORTED"
    )
    with scoring[1]() as db:
        assert not db.scalar(
            select(Transaction.id).where(Transaction.organization_id == scoring[3].organization_id)
        )


def test_concurrent_replay_retains_one_attribution_snapshot(scoring):
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: submit(scoring), range(4)))
    assert sum(created for _, created in results) == 1
    assert all(result == results[0][0] for result, _ in results)
    with scoring[1]() as db:
        score = db.get(ScoringResult, results[0][0]["scoring_result_id"])
        assert score.explanation_json["supervised_attribution"]["available"]


@pytest.mark.parametrize("kind", ["scoring", "training"])
def test_worker_refuses_unsupported_runtime_without_output(scoring, kind):
    from test_ingestion import upload
    from test_models import submit as request_model
    from test_transaction_scoring import scoring_csv

    from app.ingestion.processing import process_job
    from app.ml.processing import process_training
    from app.models import Job

    engine, sessions, storage, principal, _ = scoring
    if kind == "scoring":
        job_id, dataset_id = upload(scoring, scoring_csv([{}]), purpose="SCORING")
        process = process_job
    else:
        with sessions() as db:
            dataset_id = db.scalars(
                select(ModelVersion.training_dataset_id).where(
                    ModelVersion.organization_id == principal.organization_id
                )
            ).one()
        job_id, dataset_id = request_model(scoring, dataset_id)
        process = process_training
    with patch("app.ml.runtime.platform.system", return_value="Darwin"):
        assert process(engine, storage, job_id, dataset_id) is False
    with sessions() as db:
        job = db.get(Job, job_id)
        assert job.status == "FAILED" and job.error_code == "MODEL_RUNTIME_UNSUPPORTED"
        assert job.processed_rows == 0 and job.model_version_id is None
        assert not db.scalar(
            select(Transaction.id).where(Transaction.organization_id == principal.organization_id)
        )
