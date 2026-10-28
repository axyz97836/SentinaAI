"""PYTEST_DONT_REWRITE: no synthetic session values in assertion diagnostics."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from threading import Event
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import delete, event, select
from sqlalchemy.orm import sessionmaker
from test_ingestion import client as client
from test_ingestion import ingestion as ingestion
from test_ingestion import password_hash as password_hash
from test_models import ml as ml
from test_transaction_scoring import PAYLOAD, submit
from test_transaction_scoring import scoring as scoring

from app.auth.errors import AuthError
from app.models import (
    AuditLog,
    Membership,
    Organization,
    RiskSettings,
    RuleDefinition,
    ScoringResult,
)
from app.scoring.configuration import RuleUpdate, SettingsUpdate, update_rule, update_settings

pytestmark = pytest.mark.database

VALUES = {
    "medium_threshold": 30,
    "high_threshold": 60,
    "critical_threshold": 90,
    "alert_threshold": 0,
    "version": 1,
}


def add_rules(sessions, org):
    with sessions.begin() as db:
        rules = [
            RuleDefinition(
                organization_id=org,
                code=code,
                description="Synthetic rule fixture",
                parameters_json=params,
            )
            for code, params in [
                ("AMOUNT_OUTLIER", {"multiplier": 3, "min_history": 1}),
                ("HIGH_VELOCITY", {"window_minutes": 10, "count_threshold": 2}),
                ("DEVICE_CHANGE", {}),
            ]
        ]
        db.add_all(rules)
        db.flush()
        return {rule.code: rule.id for rule in rules}


@pytest.fixture
def configured(ingestion, migrated_engine):
    _, sessions, _, principal, _ = ingestion
    with sessions.begin() as db:
        db.add(
            RiskSettings(organization_id=principal.organization_id, updated_by=principal.user_id)
        )
    rules = add_rules(sessions, principal.organization_id)
    yield ingestion, rules
    with sessionmaker(migrated_engine).begin() as db:
        db.execute(
            delete(RuleDefinition).where(
                RuleDefinition.organization_id == principal.organization_id
            )
        )
        db.execute(
            delete(RiskSettings).where(RiskSettings.organization_id == principal.organization_id)
        )


@pytest.mark.parametrize("role", ["ADMIN", "ANALYST", "RISK_MANAGER"])
def test_configuration_roles_csrf_strict_body_and_audit(configured, client, role):
    context, rules = configured
    _, sessions, _, principal, _ = context
    browser, headers = client
    with sessions.begin() as db:
        db.get(Membership, principal.membership_id).role = role
    assert browser.get("/api/v1/admin/settings").status_code == (200 if role == "ADMIN" else 403)
    assert browser.patch("/api/v1/admin/settings", json=VALUES).status_code == 403
    assert (
        browser.patch(
            "/api/v1/admin/settings",
            headers={**headers, "Origin": "https://foreign.invalid"},
            json=VALUES,
        ).status_code
        == 403
    )
    result = browser.patch("/api/v1/admin/settings", headers=headers, json=VALUES)
    assert result.status_code == (200 if role == "ADMIN" else 403)
    rule_id = rules["HIGH_VELOCITY"]
    edited = browser.patch(
        f"/api/v1/admin/rules/{rule_id}", headers=headers, json={"enabled": False, "version": 1}
    )
    assert edited.status_code == (200 if role == "ADMIN" else 403)
    if role == "ADMIN":
        assert result.json()["version"] == 2 and result.json()["alert_threshold"] == 0
        assert edited.json()["version"] == 2 and not edited.json()["enabled"]
        assert (
            browser.patch("/api/v1/admin/settings", headers=headers, json=VALUES).status_code == 409
        )
        assert (
            browser.patch(
                f"/api/v1/admin/rules/{rule_id}",
                headers=headers,
                json={"enabled": True, "version": 1},
            ).status_code
            == 409
        )
        assert (
            browser.patch(
                f"/api/v1/admin/rules/{rule_id}",
                headers=headers,
                json={
                    "parameters_json": {"window_minutes": 60, "count_threshold": 1},
                    "version": 2,
                },
            ).status_code
            == 422
        )
        assert (
            browser.patch(
                "/api/v1/admin/settings", headers=headers, json={**VALUES, "role": "ADMIN"}
            ).status_code
            == 422
        )
        assert (
            browser.patch(
                "/api/v1/admin/settings", headers=headers, json={**VALUES, "extra": "x" * 5000}
            ).status_code
            == 413
        )
        current = browser.get("/api/v1/admin/settings").json()
        assert len(current["rules"]) == 3 and len(current["audit_summary"]) == 2
        assert "artifact_key" not in str(current)
        with sessions() as db:
            settings = db.get(RiskSettings, principal.organization_id)
            assert settings.updated_by == principal.user_id and settings.updated_at <= datetime.now(
                UTC
            )
            audit = db.scalars(
                select(AuditLog).where(
                    AuditLog.action == "RISK_SETTINGS_UPDATED",
                    AuditLog.organization_id == principal.organization_id,
                )
            ).one()
            assert audit.metadata_json["before"]["alert_threshold"] == 70
            assert audit.metadata_json["after"]["alert_threshold"] == 0
    browser.cookies.clear()
    assert browser.get("/api/v1/admin/settings").status_code == 401


def test_atomic_audit_failure_restores_settings_and_rule(configured):
    context, rules = configured
    engine, sessions, _, principal, _ = context

    def fail(conn, cursor, statement, parameters, execution, executemany):
        if statement.startswith("INSERT INTO audit_logs"):
            raise RuntimeError("fixture audit failure")

    event.listen(engine, "before_cursor_execute", fail)
    try:
        with pytest.raises(RuntimeError), sessions.begin() as db:
            update_settings(db, principal, SettingsUpdate(**VALUES), "fixture")
        with pytest.raises(RuntimeError), sessions.begin() as db:
            update_rule(
                db,
                principal,
                rules["DEVICE_CHANGE"],
                RuleUpdate(enabled=False, version=1),
                "fixture",
            )
    finally:
        event.remove(engine, "before_cursor_execute", fail)
    with sessions() as db:
        assert db.get(RiskSettings, principal.organization_id).version == 1
        assert db.get(RiskSettings, principal.organization_id).alert_threshold == 70
        assert db.get(RuleDefinition, rules["DEVICE_CHANGE"]).enabled
        assert db.get(RuleDefinition, rules["DEVICE_CHANGE"]).version == 1


@pytest.mark.parametrize("target", ["settings", "rule"])
def test_concurrent_edit_has_one_winner(configured, target):
    context, rules = configured
    _, sessions, _, principal, _ = context

    def edit():
        try:
            with sessions.begin() as db:
                if target == "settings":
                    update_settings(db, principal, SettingsUpdate(**VALUES), "fixture")
                else:
                    update_rule(
                        db,
                        principal,
                        rules["DEVICE_CHANGE"],
                        RuleUpdate(enabled=False, version=1),
                        "fixture",
                    )
            return "updated"
        except AuthError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda _: edit(), range(3)))
    assert sorted(results) == [
        "CONFIGURATION_VERSION_CONFLICT",
        "CONFIGURATION_VERSION_CONFLICT",
        "updated",
    ]


def test_foreign_rule_denied_and_service_checks_admin(configured, migrated_engine):
    context, rules = configured
    _, sessions, _, principal, _ = context
    with sessions.begin() as db:
        foreign = Organization(name="Fictional configuration isolation")
        db.add(foreign)
        db.flush()
        foreign_id = foreign.id
    try:
        with sessions.begin() as db:
            with pytest.raises(AuthError) as error:
                update_rule(
                    db,
                    replace(principal, organization_id=foreign_id),
                    rules["DEVICE_CHANGE"],
                    RuleUpdate(enabled=False, version=1),
                    "fixture",
                )
            assert error.value.status == 404
    finally:
        with sessionmaker(migrated_engine).begin() as db:
            db.execute(delete(Organization).where(Organization.id == foreign_id))
    with sessions.begin() as db:
        with pytest.raises(AuthError) as error:
            update_settings(
                db, replace(principal, role="ANALYST"), SettingsUpdate(**VALUES), "fixture"
            )
        assert error.value.status == 403


def test_configuration_changes_affect_new_scores_only(scoring, client):
    _, sessions, _, principal, _ = scoring
    rules = add_rules(sessions, principal.organization_id)
    submit(
        scoring,
        {
            **PAYLOAD,
            "external_id": "prior",
            "occurred_at": "2026-01-23T09:59:00Z",
            "amount": "10",
            "device_ref": "prior-device",
        },
    )
    first, _ = submit(scoring, {**PAYLOAD, "device_ref": "new-device"})
    browser, headers = client
    before = browser.get(f"/api/v1/transactions/{first['transaction_id']}").json()
    assert before["score"]["rule_signal"] == "1.000000"
    assert browser.patch("/api/v1/admin/settings", headers=headers, json=VALUES).status_code == 200
    for identifier in rules.values():
        assert (
            browser.patch(
                f"/api/v1/admin/rules/{identifier}",
                headers=headers,
                json={"enabled": False, "version": 1},
            ).status_code
            == 200
        )
    assert submit(scoring, {**PAYLOAD, "device_ref": "new-device"}) == (first, False)
    assert browser.get(f"/api/v1/transactions/{first['transaction_id']}").json() == before
    second, _ = submit(scoring, {**PAYLOAD, "external_id": "new", "device_ref": "new-device"})
    after = browser.get(f"/api/v1/transactions/{second['transaction_id']}").json()
    assert after["score"]["rule_signal"] == "0.000000"
    assert after["score"]["settings_snapshot_json"]["version"] == 2
    assert after["alert_id"] is not None


@pytest.mark.parametrize("role", ["ANALYST", "RISK_MANAGER", "ADMIN"])
def test_explanation_reads_original_evidence_without_storage(scoring, client, role):
    _, sessions, storage, principal, _ = scoring

    # Emulate a Phase 6 insertion shape; no already-persisted evidence is rewritten.
    def legacy_insert(mapper, connection, score):
        score.explanation_json = {
            k: v for k, v in score.explanation_json.items() if k != "supervised_attribution"
        }
        score.explanation_status = "PARTIAL"

    event.listen(ScoringResult, "before_insert", legacy_insert)
    try:
        result, _ = submit(scoring)
    finally:
        event.remove(ScoringResult, "before_insert", legacy_insert)
    browser, headers = client
    with sessions.begin() as db:
        db.get(Membership, principal.membership_id).role = role
    storage.objects.clear()
    response = browser.get(f"/api/v1/transactions/{result['transaction_id']}/explanation")
    assert response.status_code == 200
    body = response.json()
    assert body["model_version_id"] == str(result["model_version_id"])
    assert body["risk_score"] == result["risk_score"]
    assert body["explanation_status"] == "PARTIAL"
    assert body["supervised_attribution"]["reason"] == "NOT_RECORDED_AT_SCORING_TIME"
    assert body["supervised_attribution"]["top_features"] == []
    assert (
        body["caveat"]
        == "This score is a screening signal, not proof of fraud or a calibrated fraud probability."
    )
    assert not any(
        key in response.text
        for key in ("artifact_key", "customer_ref", "device_ref", "password_hash")
    )
    assert browser.get(f"/api/v1/transactions/{uuid4()}/explanation").status_code == 404
    browser.cookies.clear()
    assert (
        browser.get(f"/api/v1/transactions/{result['transaction_id']}/explanation").status_code
        == 401
    )


def test_configuration_update_serializes_with_scoring(scoring):
    _, sessions, _, principal, _ = scoring
    entered, release, editing = Event(), Event(), Event()
    from app.ml.training import BaselineBundle

    real = BaselineBundle.components

    def held(self, rows):
        entered.set()
        assert release.wait(3)
        return real(self, rows)

    def edit():
        editing.set()
        with sessions.begin() as db:
            update_settings(db, principal, SettingsUpdate(**VALUES), "fixture")

    with (
        patch.object(BaselineBundle, "components", held),
        ThreadPoolExecutor(max_workers=2) as pool,
    ):
        scoring_future = pool.submit(submit, scoring)
        assert entered.wait(3)
        edit_future = pool.submit(edit)
        assert editing.wait(3)
        release.set()
        first, _ = scoring_future.result()
        edit_future.result()
    with sessions() as db:
        assert (
            db.get(ScoringResult, first["scoring_result_id"]).settings_snapshot_json["version"] == 1
        )
        assert db.get(RiskSettings, principal.organization_id).version == 2
    second, _ = submit(scoring, {**PAYLOAD, "external_id": "after-config"})
    with sessions() as db:
        assert (
            db.get(ScoringResult, second["scoring_result_id"]).settings_snapshot_json["version"]
            == 2
        )


def test_exact_rule_observations_and_currency_grouping(scoring):
    from app.scoring.history import evaluate
    from app.scoring.schema import TransactionInput

    _, sessions, _, principal, _ = scoring
    add_rules(sessions, principal.organization_id)
    for index in range(4):
        submit(
            scoring,
            {
                **PAYLOAD,
                "external_id": f"history-{index}",
                "occurred_at": "2026-01-23T09:59:00Z",
                "amount": "10" if index < 3 else "999999",
                "currency": "INR" if index < 3 else "USD",
            },
        )
    with sessions() as db:
        signal, items = evaluate(
            db, principal.organization_id, TransactionInput.model_validate(PAYLOAD)
        )
        assert signal == 1
        assert items[0]["historical_mean"] == "10.00"
        assert items[0]["observed_amount"] == "100.00" and items[0]["threshold_amount"] == "30.000"
        assert items[0]["history_count"] == 3 and items[0]["currency"] == "INR"
        assert items[1]["prior_count"] == 4 and items[1]["parameters"]["count_threshold"] == 2
        assert items[2]["status"] == "MISSING_HISTORY"


def test_velocity_window_at_minimum_supported_timestamp(configured):
    from app.scoring.history import evaluate
    from app.scoring.schema import TransactionInput

    context, _ = configured
    _, sessions, _, principal, _ = context
    with sessions() as db:
        signal, items = evaluate(
            db,
            principal.organization_id,
            TransactionInput.model_validate({**PAYLOAD, "occurred_at": "0001-01-01T00:00:00Z"}),
        )
        assert signal == 0
        assert all(item["status"] == "MISSING_HISTORY" for item in items)
