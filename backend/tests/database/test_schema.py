import os
import secrets
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from schema_contract import COLUMNS, FOREIGN_KEYS, INDEX_COLUMNS, UNIQUE_KEYS
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Numeric,
    func,
    insert,
    inspect,
    select,
    text,
    update,
)
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError, ProgrammingError

from app import models  # noqa: F401
from app.database import Base, MigrationSettings, database_engine
from app.seed import DEMO_ACCOUNTS, HASHER, ORGANIZATION_NAME, seed_demo

pytestmark = pytest.mark.database
NOW = datetime(2026, 1, 1, tzinfo=UTC)


def add(db: Connection, table_name: str, **values: Any) -> UUID:
    table = Base.metadata.tables[table_name]
    key = next(iter(table.primary_key.columns))
    return db.execute(insert(table).values(**values).returning(key)).scalar_one()


@pytest.fixture(scope="session")
def fixture_hash() -> str:
    return HASHER.hash(secrets.token_urlsafe(32))


@pytest.fixture
def graph(db: Connection, fixture_hash: str) -> dict[str, UUID]:
    """Valid synthetic related records, always rolled back; no model is actually trained."""
    g: dict[str, UUID] = {}
    g["organizations"] = add(db, "organizations", name="Isolated synthetic fixture")
    g["users"] = add(
        db,
        "users",
        email=f"{uuid4()}@fixture.invalid",
        password_hash=fixture_hash,
        display_name="Fictional fixture user",
    )
    org, user = g["organizations"], g["users"]
    g["memberships"] = add(db, "memberships", organization_id=org, user_id=user, role="ADMIN")
    g["sessions"] = add(
        db,
        "sessions",
        user_id=user,
        token_hash=secrets.token_hex(32),
        created_at=NOW,
        expires_at=NOW + timedelta(hours=1),
    )
    g["risk_settings"] = add(db, "risk_settings", organization_id=org, updated_by=user)
    g["rule_definitions"] = add(
        db,
        "rule_definitions",
        organization_id=org,
        code="AMOUNT_OUTLIER",
        description="Synthetic constraint fixture only",
        parameters_json={"fixture_only": True},
    )
    g["datasets"] = add(
        db,
        "datasets",
        organization_id=org,
        uploaded_by=user,
        purpose="TRAINING",
        source_kind="SYNTHETIC",
        original_filename="synthetic-fixture.csv",
        object_key="isolated-test/no-object-created",
        sha256="0" * 64,
        size_bytes=100,
        status="VALIDATED",
    )
    g["model_versions"] = add(
        db,
        "model_versions",
        organization_id=org,
        training_dataset_id=g["datasets"],
        version_label="constraint-fixture",
        algorithm="schema fixture, not a trained model",
        artifact_key="isolated-test/no-artifact",
        artifact_sha256="0" * 64,
        feature_schema_json={},
        metrics_json={},
        trained_at=NOW,
    )
    g["jobs"] = add(
        db,
        "jobs",
        organization_id=org,
        requested_by=user,
        dataset_id=g["datasets"],
        model_version_id=g["model_versions"],
        type="MODEL_TRAIN",
        status="QUEUED",
    )
    g["job_errors"] = add(
        db,
        "job_errors",
        job_id=g["jobs"],
        row_number=1,
        code="SYNTHETIC_FIXTURE",
        summary="Constraint test only",
    )
    g["transactions"] = add(
        db,
        "transactions",
        organization_id=org,
        external_id="synthetic-001",
        customer_ref="fictional-customer",
        occurred_at=NOW,
        amount=Decimal("10.25"),
        currency="INR",
        merchant_category="synthetic",
        country_code="IN",
        channel="WEB",
        source="SINGLE",
    )
    g["transaction_labels"] = add(
        db,
        "transaction_labels",
        transaction_id=g["transactions"],
        fraud_label=False,
        label_source="SYNTHETIC",
    )
    g["scoring_results"] = add(
        db,
        "scoring_results",
        transaction_id=g["transactions"],
        model_version_id=g["model_versions"],
        risk_score=50,
        risk_band="MEDIUM",
        supervised_probability=Decimal("0.5"),
        anomaly_percentile=Decimal("0.5"),
        rule_signal=Decimal("0.5"),
        explanation_status="PARTIAL",
        explanation_json={"fixture_only": True},
        settings_snapshot_json={},
        latency_ms=0,
    )
    g["rule_hits"] = add(
        db,
        "rule_hits",
        scoring_result_id=g["scoring_results"],
        rule_definition_id=g["rule_definitions"],
        rule_code_snapshot="AMOUNT_OUTLIER",
        strength=Decimal("0.5"),
        details_json={"fixture_only": True},
    )
    g["alerts"] = add(
        db,
        "alerts",
        organization_id=org,
        scoring_result_id=g["scoring_results"],
        status="NEW",
        reason_summary="Synthetic constraint fixture",
    )
    g["cases"] = add(
        db,
        "cases",
        organization_id=org,
        alert_id=g["alerts"],
        created_by=user,
        assigned_to=user,
        status="OPEN",
    )
    g["case_events"] = add(
        db,
        "case_events",
        case_id=g["cases"],
        actor_user_id=user,
        action="CASE_OPENED",
        new_status="OPEN",
    )
    g["audit_logs"] = add(
        db,
        "audit_logs",
        organization_id=org,
        actor_user_id=user,
        action="SCHEMA_FIXTURE",
        resource_type="CASE",
        metadata_json={"fixture_only": True},
    )
    return g


def reject_update(
    db: Connection, table_name: str, values: dict[str, Any], code: str = "23514"
) -> None:
    with pytest.raises(IntegrityError) as failure, db.begin_nested():
        db.execute(update(Base.metadata.tables[table_name]).values(**values))
    assert failure.value.orig.sqlstate == code


def test_migration_round_trip_and_exact_tables(db: Connection) -> None:
    # The session fixture already upgraded, downgraded to empty and upgraded again.
    assert set(inspect(db).get_table_names()) == set(COLUMNS) | {"alembic_version"}
    assert db.scalar(text("SELECT version_num FROM alembic_version")) == "0001_initial_schema"


def test_downgrade_refuses_local_environment(
    migrated_engine: Engine, migration_config: Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The connection still targets the disposable DB; exercise the main-environment guard safely.
    monkeypatch.setenv("APP_ENV", "local")
    with pytest.raises(RuntimeError, match="Downgrade refused"):
        command.downgrade(migration_config, "base")
    with migrated_engine.connect() as connection:
        assert set(inspect(connection).get_table_names()) == set(COLUMNS) | {"alembic_version"}


@pytest.mark.parametrize("name", COLUMNS)
def test_documented_columns_keys_types_and_defaults(db: Connection, name: str) -> None:
    inspector = inspect(db)
    columns = {column["name"]: column for column in inspector.get_columns(name)}
    assert set(columns) == set(COLUMNS[name].split())
    expected_pk = {"risk_settings": "organization_id", "transaction_labels": "transaction_id"}.get(
        name, "id"
    )
    assert inspector.get_pk_constraint(name)["constrained_columns"] == [expected_pk]
    actual_fks = {
        fk["constrained_columns"][0]: fk["referred_table"]
        for fk in inspector.get_foreign_keys(name)
    }
    assert actual_fks == FOREIGN_KEYS.get(name, {})
    for fk in inspector.get_foreign_keys(name):
        assert fk["referred_columns"] == ["id"]
        expected_delete = (
            "SET NULL"
            if (name, fk["constrained_columns"][0]) == ("rule_hits", "rule_definition_id")
            else None
        )
        assert fk["options"].get("ondelete") == expected_delete
    for column in Base.metadata.tables[name].columns:
        actual = columns[column.name]
        assert actual["nullable"] == column.nullable
        if isinstance(column.type, DateTime):
            assert actual["type"].timezone is True
        if isinstance(column.type, Numeric):
            assert (actual["type"].precision, actual["type"].scale) == (
                column.type.precision,
                column.type.scale,
            )
        if column.name == "id":
            assert "gen_random_uuid()" in actual["default"]
    checks = {item["name"] for item in inspector.get_check_constraints(name)}
    assert checks == {
        constraint.name
        for constraint in Base.metadata.tables[name].constraints
        if isinstance(constraint, CheckConstraint)
    }
    uniques = {tuple(item["column_names"]) for item in inspector.get_unique_constraints(name)}
    assert uniques == set(UNIQUE_KEYS.get(name, []))


def test_documented_indexes_and_model_schema_match(db: Connection) -> None:
    context = MigrationContext.configure(
        db, opts={"compare_type": True, "compare_server_default": True}
    )
    assert compare_metadata(context, Base.metadata) == []
    for table, indexes in INDEX_COLUMNS.items():
        definitions = (
            db.execute(
                text(
                    "SELECT indexdef FROM pg_indexes WHERE schemaname='public' AND tablename=:name"
                ),
                {"name": table},
            )
            .scalars()
            .all()
        )
        for columns in indexes:
            assert any(f"({', '.join(columns)})" in definition for definition in definitions)
    assert db.scalar(text("SELECT indexdef FROM pg_indexes WHERE indexname='uq_users_email_lower'"))
    active = db.scalar(
        text("SELECT indexdef FROM pg_indexes WHERE indexname='uq_model_versions_active_org'")
    )
    assert "UNIQUE INDEX" in active and "WHERE (is_active = true)" in active


@pytest.mark.parametrize("table_name", UNIQUE_KEYS)
def test_documented_uniqueness_rejects_duplicates(
    db: Connection, graph: dict[str, UUID], table_name: str
) -> None:
    table = Base.metadata.tables[table_name]
    row = dict(db.execute(select(table)).mappings().one())
    row.pop("id")
    with pytest.raises(IntegrityError) as failure, db.begin_nested():
        db.execute(insert(table).values(**row))
    assert failure.value.orig.sqlstate == "23505"


def test_external_id_is_scoped_to_organization(db: Connection, graph: dict[str, UUID]) -> None:
    table = Base.metadata.tables["transactions"]
    row = dict(db.execute(select(table)).mappings().one())
    row.pop("id")
    row["organization_id"] = add(db, "organizations", name="Second fictional organization")
    assert (
        db.execute(insert(table).values(**row).returning(table.c.id)).scalar_one()
        != graph["transactions"]
    )


def test_email_uniqueness_is_case_insensitive(db: Connection, graph: dict[str, UUID]) -> None:
    row = dict(db.execute(select(Base.metadata.tables["users"])).mappings().one())
    row.pop("id")
    row["email"] = row["email"].upper()
    with pytest.raises(IntegrityError) as failure, db.begin_nested():
        db.execute(insert(Base.metadata.tables["users"]).values(**row))
    assert failure.value.orig.sqlstate == "23505"


INVALID_VALUES = [
    ("memberships", "role", "OWNER"),
    ("rule_definitions", "code", "UNKNOWN"),
    ("datasets", "purpose", "TESTING"),
    ("datasets", "source_kind", "REAL"),
    ("datasets", "status", "COMPLETE"),
    ("datasets", "size_bytes", 0),
    ("datasets", "size_bytes", 10485761),
    ("datasets", "row_count", -1),
    ("datasets", "row_count", 10001),
    ("datasets", "source_kind", "PUBLIC_DATASET"),
    ("jobs", "type", "UNKNOWN"),
    ("jobs", "status", "COMPLETE"),
    ("jobs", "status", "SUCCEEDED"),
    ("jobs", "status", "FAILED"),
    ("jobs", "total_rows", -1),
    ("jobs", "processed_rows", -1),
    ("jobs", "failed_rows", -1),
    ("jobs", "attempt_count", -1),
    ("job_errors", "row_number", 0),
    ("sessions", "expires_at", NOW),
    ("transactions", "channel", "ATM"),
    ("transactions", "source", "LIVE"),
    ("transactions", "amount", Decimal("0")),
    ("transactions", "amount", Decimal("-1")),
    ("transactions", "amount", Decimal("NaN")),
    ("transaction_labels", "label_source", "REAL"),
    ("scoring_results", "risk_score", -1),
    ("scoring_results", "risk_score", 101),
    ("scoring_results", "risk_band", "SEVERE"),
    ("scoring_results", "explanation_status", "FAILED"),
    ("scoring_results", "supervised_probability", Decimal("-0.000001")),
    ("scoring_results", "supervised_probability", Decimal("1.000001")),
    ("scoring_results", "anomaly_percentile", Decimal("-0.000001")),
    ("scoring_results", "anomaly_percentile", Decimal("1.000001")),
    ("scoring_results", "rule_signal", Decimal("-0.000001")),
    ("scoring_results", "rule_signal", Decimal("1.000001")),
    ("scoring_results", "latency_ms", -1),
    ("rule_hits", "strength", Decimal("-0.000001")),
    ("rule_hits", "strength", Decimal("1.000001")),
    ("alerts", "status", "OPEN"),
    ("alerts", "status", "DISMISSED"),
    ("cases", "status", "REOPENED"),
    ("cases", "resolution", "UNKNOWN"),
    ("case_events", "previous_status", "REOPENED"),
    ("case_events", "new_status", "REOPENED"),
    ("case_events", "action", "NOTE_ADDED"),
    ("risk_settings", "medium_threshold", 0),
    ("risk_settings", "medium_threshold", 70),
    ("risk_settings", "high_threshold", 39),
    ("risk_settings", "high_threshold", 85),
    ("risk_settings", "critical_threshold", 101),
    ("risk_settings", "alert_threshold", -1),
    ("risk_settings", "alert_threshold", 101),
]


@pytest.mark.parametrize("table,column,value", INVALID_VALUES)
def test_invalid_values_are_rejected(
    db: Connection, graph: dict[str, UUID], table: str, column: str, value: Any
) -> None:
    reject_update(db, table, {column: value})


@pytest.mark.parametrize(
    "values",
    [
        {"status": "CLOSED"},
        {"status": "CLOSED", "resolution": "INCONCLUSIVE", "closed_at": NOW},
        {"status": "CLOSED", "resolution": "INCONCLUSIVE", "closed_at": NOW, "resolution_note": ""},
        {
            "status": "CLOSED",
            "resolution": "INCONCLUSIVE",
            "closed_at": NOW,
            "resolution_note": " \n\t",
        },
        {"status": "CLOSED", "resolution": "INCONCLUSIVE", "resolution_note": "Synthetic note"},
        {"resolution": "FALSE_POSITIVE"},
        {"closed_at": NOW},
        {"status": "IN_REVIEW", "resolution": "CONFIRMED_FRAUD"},
    ],
)
def test_invalid_case_resolution_state(
    db: Connection, graph: dict[str, UUID], values: dict[str, Any]
) -> None:
    reject_update(db, "cases", values)


@pytest.mark.parametrize("resolution", ["CONFIRMED_FRAUD", "FALSE_POSITIVE", "INCONCLUSIVE"])
def test_valid_case_resolution(db: Connection, graph: dict[str, UUID], resolution: str) -> None:
    db.execute(
        update(Base.metadata.tables["cases"]).values(
            status="CLOSED",
            resolution=resolution,
            resolution_note="Synthetic database test conclusion",
            closed_at=NOW,
        )
    )


@pytest.mark.parametrize(
    "table,column", [(table, column) for table, fks in FOREIGN_KEYS.items() for column in fks]
)
def test_every_foreign_key_rejects_unknown_reference(
    db: Connection, graph: dict[str, UUID], table: str, column: str
) -> None:
    reject_update(db, table, {column: uuid4()}, code="23503")


def test_one_active_model_per_org_and_inactive_history(
    db: Connection, graph: dict[str, UUID]
) -> None:
    table = Base.metadata.tables["model_versions"]
    db.execute(update(table).values(is_active=True))
    row = dict(db.execute(select(table)).mappings().one())
    row.pop("id")
    row["version_label"] = "second-constraint-fixture"
    with pytest.raises(IntegrityError) as failure, db.begin_nested():
        db.execute(insert(table).values(**row))
    assert failure.value.orig.sqlstate == "23505"
    row["is_active"] = False
    db.execute(insert(table).values(**row))
    row["organization_id"] = add(db, "organizations", name="Other synthetic model organization")
    dataset = dict(db.execute(select(Base.metadata.tables["datasets"])).mappings().one())
    dataset.pop("id")
    dataset["organization_id"] = row["organization_id"]
    row["training_dataset_id"] = add(db, "datasets", **dataset)
    row["is_active"] = True
    db.execute(insert(table).values(**row))


def test_history_survives_rule_edits_and_delete(db: Connection, graph: dict[str, UUID]) -> None:
    table = Base.metadata.tables["rule_hits"]
    before = db.execute(select(table)).mappings().one()
    db.execute(
        update(Base.metadata.tables["rule_definitions"]).values(parameters_json={"changed": True})
    )
    after = db.execute(select(table)).mappings().one()
    assert dict(before) == dict(after)
    db.execute(Base.metadata.tables["rule_definitions"].delete())
    after = db.execute(select(table)).mappings().one()
    assert after["rule_definition_id"] is None
    assert after["details_json"] == before["details_json"]
    assert after["rule_code_snapshot"] == before["rule_code_snapshot"]
    with pytest.raises(IntegrityError) as failure, db.begin_nested():
        db.execute(Base.metadata.tables["model_versions"].delete())
    assert failure.value.orig.sqlstate == "23503"


def test_valid_boundaries_defaults_money_and_utc(db: Connection, graph: dict[str, UUID]) -> None:
    risk = Base.metadata.tables["risk_settings"]
    row = db.execute(select(risk)).mappings().one()
    assert (
        row["medium_threshold"],
        row["high_threshold"],
        row["critical_threshold"],
        row["alert_threshold"],
        row["version"],
    ) == (40, 70, 85, 70, 1)
    for threshold in (0, 100):
        db.execute(update(risk).values(alert_threshold=threshold))
    for boundary in (0, 1):
        db.execute(
            update(Base.metadata.tables["scoring_results"]).values(
                supervised_probability=boundary,
                anomaly_percentile=boundary,
                rule_signal=boundary,
                risk_score=boundary * 100,
            )
        )
    db.execute(update(Base.metadata.tables["jobs"]).values(status="SUCCEEDED", completed_at=NOW))
    transaction = db.execute(select(Base.metadata.tables["transactions"])).mappings().one()
    assert transaction["amount"] == Decimal("10.25")
    assert transaction["occurred_at"].utcoffset() == timedelta(0)
    assert db.scalar(select(Base.metadata.tables["model_versions"].c.weight_config_json)) == {
        "supervised": 0.60,
        "anomaly": 0.25,
        "rules": 0.15,
    }


@pytest.fixture
def app_engine(migrated_engine: Engine) -> Iterator[Engine]:
    settings = MigrationSettings()
    url = settings.database_url.set(
        username=settings.app_db_user, password=os.environ["APP_DB_PASSWORD"]
    )
    engine = database_engine(url)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE TABLE forbidden_ddl(id integer)",
        "CREATE SCHEMA forbidden_ddl",
        "ALTER TABLE organizations ADD COLUMN forbidden integer",
        "DROP TABLE organizations",
        "TRUNCATE organizations",
        "SET ROLE sentinel_migrator",
        "UPDATE alembic_version SET version_num = 'wrong'",
    ]
    + [
        f"{operation} {table} {suffix}"
        for table in [
            "case_events",
            "audit_logs",
            "transactions",
            "transaction_labels",
            "scoring_results",
            "rule_hits",
        ]
        for operation, suffix in [("UPDATE", "SET created_at = now() WHERE false")]
        if table not in {"transactions", "scoring_results", "rule_hits"}
    ]
    + [
        "UPDATE transactions SET amount=1 WHERE false",
        "UPDATE scoring_results SET risk_score=1 WHERE false",
        "UPDATE rule_hits SET strength=1 WHERE false",
        "UPDATE model_versions SET metrics_json='{}' WHERE false",
    ]
    + [
        f"DELETE FROM {table} WHERE false"  # noqa: S608 -- fixed test table names below
        for table in [
            "case_events",
            "audit_logs",
            "transactions",
            "scoring_results",
            "rule_hits",
            "model_versions",
        ]
    ],
)
def test_application_cannot_change_schema_or_history(app_engine: Engine, sql: str) -> None:
    with app_engine.connect() as connection, connection.begin():
        with pytest.raises(ProgrammingError) as failure, connection.begin_nested():
            connection.execute(text(sql))
        assert failure.value.orig.sqlstate == "42501"


def test_application_allowed_writes_and_migration_role_restrictions(
    app_engine: Engine, migrated_engine: Engine
) -> None:
    with app_engine.connect() as connection, connection.begin():
        org = add(connection, "organizations", name="Synthetic permission test")
        add(
            connection,
            "audit_logs",
            organization_id=org,
            action="TEST",
            resource_type="ORGANIZATION",
            metadata_json={},
        )
        assert connection.scalar(text("SELECT count(*) FROM audit_logs")) == 1
        connection.rollback()
    with migrated_engine.connect() as connection:
        assert tuple(
            connection.execute(
                text(
                    "SELECT rolsuper, rolcreatedb, rolcreaterole "
                    "FROM pg_roles WHERE rolname=current_user"
                )
            ).one()
        ) == (False, False, False)


def test_seed_roles_argon2_idempotency_and_refusal(
    app_engine: Engine, migrated_engine: Engine, tmp_path: Path
) -> None:
    import json

    credential_file = tmp_path / "demo.json"
    try:
        seed_demo(app_engine, credential_file, "local")
        content = credential_file.read_bytes()
        assert credential_file.stat().st_mode & 0o777 == 0o600
        with migrated_engine.connect() as connection:
            before = connection.execute(
                text("SELECT id, password_hash, created_at, updated_at FROM users ORDER BY email")
            ).all()
            roles = connection.execute(
                text(
                    "SELECT u.email, m.role FROM users u "
                    "JOIN memberships m ON m.user_id=u.id ORDER BY u.email"
                )
            ).all()
            assert set(roles) == {(email, role) for email, _, role in DEMO_ACCOUNTS}
            assert connection.scalar(text("SELECT count(*) FROM organizations")) == 1
            assert connection.scalar(text("SELECT count(*) FROM risk_settings")) == 1
            assert connection.scalar(text("SELECT count(*) FROM rule_definitions")) == 0
            for table in ["transactions", "alerts", "cases", "model_versions", "jobs", "datasets"]:
                assert (
                    connection.scalar(select(func.count()).select_from(Base.metadata.tables[table]))
                    == 0
                )
            accounts = json.loads(content)["accounts"]
            for email, hashed in connection.execute(text("SELECT email, password_hash FROM users")):
                assert hashed.startswith("$argon2id$")
                assert HASHER.verify(hashed, accounts[email])
        seed_demo(app_engine, credential_file, "local")
        assert credential_file.read_bytes() == content
        with migrated_engine.connect() as connection:
            after = connection.execute(
                text("SELECT id, password_hash, created_at, updated_at FROM users ORDER BY email")
            ).all()
            assert before == after
            assert connection.scalar(text("SELECT count(*) FROM memberships")) == 3
        for environment in ("production", "staging", "test", ""):
            with pytest.raises(ValueError):
                seed_demo(app_engine, credential_file, environment)
        missing = tmp_path / "missing.json"
        with pytest.raises(ValueError):
            seed_demo(app_engine, missing, "local")
        assert not missing.exists()
        credential_file.chmod(0o644)
        with pytest.raises(ValueError):
            seed_demo(app_engine, credential_file, "local")
        credential_file.chmod(0o600)
        assert credential_file.read_bytes() == content
    finally:
        # This fixture only ever connects to the guarded disposable database.
        with migrated_engine.begin() as connection:
            connection.execute(text("DELETE FROM risk_settings"))
            connection.execute(text("DELETE FROM memberships"))
            connection.execute(text("DELETE FROM users"))
            connection.execute(
                text("DELETE FROM organizations WHERE name=:name"), {"name": ORGANIZATION_NAME}
            )
