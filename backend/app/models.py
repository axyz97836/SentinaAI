"""The 18 approved domain tables. No product operations or implicit delete cascades."""

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from sqlalchemy import (
    CHAR,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

ID = Annotated[UUID, mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))]
Created = Annotated[datetime, mapped_column(DateTime(timezone=True), server_default=text("now()"))]
Timestamp = Annotated[datetime, mapped_column(DateTime(timezone=True))]
JsonObject = Annotated[dict[str, Any], mapped_column(JSONB)]


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[ID]
    name: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[Created]


class User(Base):
    __tablename__ = "users"
    id: Mapped[ID]
    email: Mapped[str] = mapped_column(String(254))
    password_hash: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[Created]
    updated_at: Mapped[Created]
    __table_args__ = (Index("uq_users_email_lower", text("lower(email)"), unique=True),)


class Membership(Base):
    __tablename__ = "memberships"
    id: Mapped[ID]
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[Created]
    updated_at: Mapped[Created]
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id"),
        Index("ix_memberships_user_id", "user_id"),
        CheckConstraint("role IN ('ANALYST', 'RISK_MANAGER', 'ADMIN')", name="role"),
    )


class SessionRecord(Base):
    __tablename__ = "sessions"
    id: Mapped[ID]
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    token_hash: Mapped[str] = mapped_column(CHAR(64), unique=True)
    created_at: Mapped[Created]
    expires_at: Mapped[Timestamp]
    revoked_at: Mapped[Timestamp | None]
    last_seen_at: Mapped[Timestamp | None]
    __table_args__ = (
        CheckConstraint("expires_at > created_at", name="expiry"),
        Index("ix_sessions_user_expiry", "user_id", "expires_at"),
        Index("ix_sessions_expiry", "expires_at"),
    )


class RiskSettings(Base):
    __tablename__ = "risk_settings"
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), primary_key=True)
    medium_threshold: Mapped[int] = mapped_column(SmallInteger, server_default=text("40"))
    high_threshold: Mapped[int] = mapped_column(SmallInteger, server_default=text("70"))
    critical_threshold: Mapped[int] = mapped_column(SmallInteger, server_default=text("85"))
    alert_threshold: Mapped[int] = mapped_column(SmallInteger, server_default=text("70"))
    updated_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[Created]
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    __table_args__ = (
        CheckConstraint(
            "0 < medium_threshold AND medium_threshold < high_threshold "
            "AND high_threshold < critical_threshold AND critical_threshold <= 100",
            name="threshold_order",
        ),
        CheckConstraint("alert_threshold BETWEEN 0 AND 100", name="alert_threshold"),
    )


class RuleDefinition(Base):
    __tablename__ = "rule_definitions"
    id: Mapped[ID]
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    code: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    parameters_json: Mapped[JsonObject]
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    created_at: Mapped[Created]
    updated_at: Mapped[Created]
    __table_args__ = (
        UniqueConstraint("organization_id", "code"),
        CheckConstraint(
            "code IN ('AMOUNT_OUTLIER', 'HIGH_VELOCITY', 'DEVICE_CHANGE')", name="code"
        ),
        Index("ix_rule_definitions_org_enabled", "organization_id", "enabled"),
    )


class Dataset(Base):
    __tablename__ = "datasets"
    id: Mapped[ID]
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    uploaded_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    purpose: Mapped[str] = mapped_column(String(10))
    source_kind: Mapped[str] = mapped_column(String(20))
    license_reference: Mapped[str | None] = mapped_column(String(500))
    original_filename: Mapped[str] = mapped_column(String(255))
    object_key: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(CHAR(64))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    row_count: Mapped[int | None] = mapped_column(Integer)
    schema_version: Mapped[str] = mapped_column(String(20), server_default=text("'1'"))
    status: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[Created]
    __table_args__ = (
        CheckConstraint("purpose IN ('TRAINING', 'SCORING')", name="purpose"),
        CheckConstraint("source_kind IN ('SYNTHETIC', 'PUBLIC_DATASET')", name="source_kind"),
        CheckConstraint("status IN ('UPLOADED', 'VALIDATED', 'REJECTED')", name="status"),
        CheckConstraint("size_bytes > 0 AND size_bytes <= 10485760", name="size_bytes"),
        CheckConstraint("row_count BETWEEN 0 AND 10000", name="row_count"),
        CheckConstraint(
            "source_kind <> 'PUBLIC_DATASET' OR "
            "(license_reference IS NOT NULL AND license_reference ~ '[^[:space:]]')",
            name="public_license_reference",
        ),
        Index("ix_datasets_org_created", "organization_id", text("created_at DESC")),
        Index("ix_datasets_org_purpose_status", "organization_id", "purpose", "status"),
    )


class ModelVersion(Base):
    __tablename__ = "model_versions"
    id: Mapped[ID]
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    training_dataset_id: Mapped[UUID] = mapped_column(ForeignKey("datasets.id"))
    version_label: Mapped[str] = mapped_column(String(40))
    algorithm: Mapped[str] = mapped_column(String(120))
    artifact_key: Mapped[str] = mapped_column(Text)
    artifact_sha256: Mapped[str] = mapped_column(CHAR(64))
    feature_schema_json: Mapped[JsonObject]
    metrics_json: Mapped[JsonObject]
    weight_config_json: Mapped[JsonObject] = mapped_column(
        JSONB,
        server_default=text('\'{"supervised": 0.60, "anomaly": 0.25, "rules": 0.15}\'::jsonb'),
    )
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    trained_at: Mapped[Timestamp]
    activated_at: Mapped[Timestamp | None]
    created_at: Mapped[Created]
    __table_args__ = (
        UniqueConstraint("organization_id", "version_label"),
        Index(
            "uq_model_versions_active_org",
            "organization_id",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
        Index("ix_model_versions_org_trained", "organization_id", text("trained_at DESC")),
    )


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[ID]
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    requested_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    dataset_id: Mapped[UUID | None] = mapped_column(ForeignKey("datasets.id"))
    model_version_id: Mapped[UUID | None] = mapped_column(ForeignKey("model_versions.id"))
    type: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20))
    object_key: Mapped[str | None] = mapped_column(Text)
    params_json: Mapped[JsonObject] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    total_rows: Mapped[int | None] = mapped_column(Integer)
    processed_rows: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    failed_rows: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    attempt_count: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[Created]
    started_at: Mapped[Timestamp | None]
    completed_at: Mapped[Timestamp | None]
    __table_args__ = (
        CheckConstraint("type IN ('CSV_IMPORT', 'MODEL_TRAIN', 'REPORT_EXPORT')", name="type"),
        CheckConstraint("status IN ('QUEUED', 'PROCESSING', 'SUCCEEDED', 'FAILED')", name="status"),
        CheckConstraint(
            "total_rows >= 0 AND processed_rows >= 0 AND failed_rows >= 0 AND attempt_count >= 0",
            name="counters",
        ),
        CheckConstraint(
            "status NOT IN ('SUCCEEDED', 'FAILED') OR completed_at IS NOT NULL", name="completed_at"
        ),
        Index("ix_jobs_org_created", "organization_id", text("created_at DESC")),
        Index("ix_jobs_status_created", "status", "created_at"),
        Index("ix_jobs_dataset", "dataset_id"),
    )


class JobError(Base):
    __tablename__ = "job_errors"
    id: Mapped[ID]
    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id"))
    row_number: Mapped[int | None] = mapped_column(Integer)
    code: Mapped[str] = mapped_column(String(80))
    summary: Mapped[str] = mapped_column(String(400))
    created_at: Mapped[Created]
    __table_args__ = (
        CheckConstraint("row_number >= 1", name="row_number"),
        Index("ix_job_errors_job_row", "job_id", "row_number"),
    )


class Transaction(Base):
    __tablename__ = "transactions"
    id: Mapped[ID]
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    external_id: Mapped[str] = mapped_column(String(100))
    customer_ref: Mapped[str] = mapped_column(String(100))
    occurred_at: Mapped[Timestamp]
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(CHAR(3))
    merchant_category: Mapped[str] = mapped_column(String(80))
    country_code: Mapped[str] = mapped_column(CHAR(2))
    channel: Mapped[str] = mapped_column(String(8))
    device_ref: Mapped[str | None] = mapped_column(String(100))
    source: Mapped[str] = mapped_column(String(12))
    ingested_at: Mapped[Created]
    __table_args__ = (
        UniqueConstraint("organization_id", "external_id"),
        CheckConstraint("amount > 0 AND amount <> 'NaN'::numeric", name="positive_amount"),
        CheckConstraint("channel IN ('WEB', 'MOBILE', 'POS')", name="channel"),
        CheckConstraint("source IN ('SINGLE', 'CSV')", name="source"),
        Index("ix_transactions_org_occurred_id", "organization_id", text("occurred_at DESC"), "id"),
        Index(
            "ix_transactions_org_customer_occurred",
            "organization_id",
            "customer_ref",
            text("occurred_at DESC"),
        ),
        Index("ix_transactions_org_source", "organization_id", "source"),
    )


class TransactionLabel(Base):
    __tablename__ = "transaction_labels"
    transaction_id: Mapped[UUID] = mapped_column(ForeignKey("transactions.id"), primary_key=True)
    fraud_label: Mapped[bool] = mapped_column(Boolean)
    label_source: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[Created]
    __table_args__ = (
        CheckConstraint("label_source IN ('SYNTHETIC', 'PUBLIC_DATASET')", name="label_source"),
    )


class ScoringResult(Base):
    __tablename__ = "scoring_results"
    id: Mapped[ID]
    transaction_id: Mapped[UUID] = mapped_column(ForeignKey("transactions.id"), unique=True)
    model_version_id: Mapped[UUID] = mapped_column(ForeignKey("model_versions.id"))
    risk_score: Mapped[int] = mapped_column(SmallInteger)
    risk_band: Mapped[str] = mapped_column(String(10))
    supervised_probability: Mapped[Decimal] = mapped_column(Numeric(7, 6))
    anomaly_percentile: Mapped[Decimal] = mapped_column(Numeric(7, 6))
    rule_signal: Mapped[Decimal] = mapped_column(Numeric(7, 6))
    explanation_status: Mapped[str] = mapped_column(String(10))
    explanation_json: Mapped[JsonObject]
    settings_snapshot_json: Mapped[JsonObject]
    latency_ms: Mapped[int] = mapped_column(Integer)
    scored_at: Mapped[Created]
    __table_args__ = (
        CheckConstraint("risk_score BETWEEN 0 AND 100", name="risk_score"),
        CheckConstraint("risk_band IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')", name="risk_band"),
        CheckConstraint("supervised_probability BETWEEN 0 AND 1", name="supervised_probability"),
        CheckConstraint("anomaly_percentile BETWEEN 0 AND 1", name="anomaly_percentile"),
        CheckConstraint("rule_signal BETWEEN 0 AND 1", name="rule_signal"),
        CheckConstraint("explanation_status IN ('COMPLETE', 'PARTIAL')", name="explanation_status"),
        CheckConstraint("latency_ms >= 0", name="latency_ms"),
        Index("ix_scoring_results_model_scored", "model_version_id", text("scored_at DESC")),
        Index("ix_scoring_results_band_scored", "risk_band", text("scored_at DESC")),
    )


class RuleHit(Base):
    __tablename__ = "rule_hits"
    id: Mapped[ID]
    scoring_result_id: Mapped[UUID] = mapped_column(ForeignKey("scoring_results.id"))
    rule_definition_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("rule_definitions.id", ondelete="SET NULL")
    )
    rule_code_snapshot: Mapped[str] = mapped_column(String(64))
    strength: Mapped[Decimal] = mapped_column(Numeric(7, 6))
    details_json: Mapped[JsonObject]
    __table_args__ = (
        UniqueConstraint("scoring_result_id", "rule_code_snapshot"),
        CheckConstraint("strength BETWEEN 0 AND 1", name="strength"),
        Index("ix_rule_hits_definition", "rule_definition_id"),
    )


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[ID]
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    scoring_result_id: Mapped[UUID] = mapped_column(ForeignKey("scoring_results.id"), unique=True)
    status: Mapped[str] = mapped_column(String(12))
    reason_summary: Mapped[str] = mapped_column(String(240))
    dismissal_reason: Mapped[str | None] = mapped_column(String(1000))
    dismissed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[Created]
    updated_at: Mapped[Created]
    __table_args__ = (
        CheckConstraint("status IN ('NEW', 'IN_CASE', 'DISMISSED')", name="status"),
        CheckConstraint(
            "status <> 'DISMISSED' OR "
            "(dismissal_reason IS NOT NULL AND dismissal_reason ~ '[^[:space:]]')",
            name="dismissal_reason",
        ),
        Index("ix_alerts_org_status_created", "organization_id", "status", text("created_at DESC")),
    )


class Case(Base):
    __tablename__ = "cases"
    id: Mapped[ID]
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    alert_id: Mapped[UUID] = mapped_column(ForeignKey("alerts.id"), unique=True)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    assigned_to: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(12))
    resolution: Mapped[str | None] = mapped_column(String(20))
    resolution_note: Mapped[str | None] = mapped_column(String(2000))
    created_at: Mapped[Created]
    updated_at: Mapped[Created]
    closed_at: Mapped[Timestamp | None]
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    __table_args__ = (
        CheckConstraint("status IN ('OPEN', 'IN_REVIEW', 'CLOSED')", name="status"),
        CheckConstraint(
            "resolution IN ('CONFIRMED_FRAUD', 'FALSE_POSITIVE', 'INCONCLUSIVE')", name="resolution"
        ),
        CheckConstraint(
            "(status = 'CLOSED' AND resolution IS NOT NULL "
            "AND resolution_note IS NOT NULL AND resolution_note ~ '[^[:space:]]' "
            "AND closed_at IS NOT NULL) OR (status IN ('OPEN', 'IN_REVIEW') "
            "AND resolution IS NULL AND closed_at IS NULL)",
            name="resolution_state",
        ),
        Index("ix_cases_org_status_updated", "organization_id", "status", text("updated_at DESC")),
        Index("ix_cases_assignee_status", "assigned_to", "status"),
    )


class CaseEvent(Base):
    __tablename__ = "case_events"
    id: Mapped[ID]
    case_id: Mapped[UUID] = mapped_column(ForeignKey("cases.id"))
    actor_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(40))
    previous_status: Mapped[str | None] = mapped_column(String(12))
    new_status: Mapped[str | None] = mapped_column(String(12))
    note: Mapped[str | None] = mapped_column(String(2000))
    created_at: Mapped[Created]
    __table_args__ = (
        CheckConstraint(
            "previous_status IN ('OPEN', 'IN_REVIEW', 'CLOSED')", name="previous_status"
        ),
        CheckConstraint("new_status IN ('OPEN', 'IN_REVIEW', 'CLOSED')", name="new_status"),
        CheckConstraint(
            "action <> 'NOTE_ADDED' OR (note IS NOT NULL AND note ~ '[^[:space:]]')", name="note"
        ),
        Index("ix_case_events_case_created_id", "case_id", "created_at", "id"),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[ID]
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    actor_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(80))
    resource_type: Mapped[str] = mapped_column(String(60))
    resource_id: Mapped[UUID | None]
    metadata_json: Mapped[JsonObject]
    request_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[Created]
    __table_args__ = (
        Index("ix_audit_logs_org_created", "organization_id", text("created_at DESC")),
        Index(
            "ix_audit_logs_resource_created",
            "resource_type",
            "resource_id",
            text("created_at DESC"),
        ),
        Index("ix_audit_logs_actor_created", "actor_user_id", text("created_at DESC")),
    )
