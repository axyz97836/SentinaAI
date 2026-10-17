"""Initial approved 18-table schema, frozen from the reviewed Phase 2 model definitions.

Revision: 0001_initial_schema
The SQL is deliberately stored here, not imported from evolving application metadata.
"""

import os
import re

import sqlalchemy as sa
from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None

TABLES = (
    "organizations",
    "users",
    "audit_logs",
    "datasets",
    "memberships",
    "risk_settings",
    "rule_definitions",
    "sessions",
    "transactions",
    "model_versions",
    "transaction_labels",
    "jobs",
    "scoring_results",
    "alerts",
    "job_errors",
    "rule_hits",
    "cases",
    "case_events",
)

DDL = (
    """CREATE TABLE organizations (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	name VARCHAR(120) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_organizations PRIMARY KEY (id)
)""",
    """CREATE TABLE users (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	email VARCHAR(254) NOT NULL,
	password_hash TEXT NOT NULL,
	display_name VARCHAR(100) NOT NULL,
	is_active BOOLEAN DEFAULT true NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_users PRIMARY KEY (id)
)""",
    """CREATE UNIQUE INDEX uq_users_email_lower ON users (lower(email))""",
    """CREATE TABLE audit_logs (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	organization_id UUID NOT NULL,
	actor_user_id UUID,
	action VARCHAR(80) NOT NULL,
	resource_type VARCHAR(60) NOT NULL,
	resource_id UUID,
	metadata_json JSONB NOT NULL,
	request_id VARCHAR(64),
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_audit_logs PRIMARY KEY (id),
	CONSTRAINT fk_audit_logs_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id),
	CONSTRAINT fk_audit_logs_actor_user_id_users FOREIGN KEY(actor_user_id) REFERENCES users (id)
)""",
    """CREATE INDEX ix_audit_logs_actor_created ON audit_logs (actor_user_id, created_at DESC)""",
    """CREATE INDEX ix_audit_logs_org_created ON audit_logs (organization_id, created_at DESC)""",
    """CREATE INDEX ix_audit_logs_resource_created ON audit_logs (resource_type, resource_id, created_at DESC)""",
    """CREATE TABLE datasets (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	organization_id UUID NOT NULL,
	uploaded_by UUID NOT NULL,
	purpose VARCHAR(10) NOT NULL,
	source_kind VARCHAR(20) NOT NULL,
	license_reference VARCHAR(500),
	original_filename VARCHAR(255) NOT NULL,
	object_key TEXT NOT NULL,
	sha256 CHAR(64) NOT NULL,
	size_bytes BIGINT NOT NULL,
	row_count INTEGER,
	schema_version VARCHAR(20) DEFAULT '1' NOT NULL,
	status VARCHAR(20) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_datasets PRIMARY KEY (id),
	CONSTRAINT ck_datasets_purpose CHECK (purpose IN ('TRAINING', 'SCORING')),
	CONSTRAINT ck_datasets_source_kind CHECK (source_kind IN ('SYNTHETIC', 'PUBLIC_DATASET')),
	CONSTRAINT ck_datasets_status CHECK (status IN ('UPLOADED', 'VALIDATED', 'REJECTED')),
	CONSTRAINT ck_datasets_size_bytes CHECK (size_bytes > 0 AND size_bytes <= 10485760),
	CONSTRAINT ck_datasets_row_count CHECK (row_count BETWEEN 0 AND 10000),
	CONSTRAINT ck_datasets_public_license_reference CHECK (source_kind <> 'PUBLIC_DATASET' OR (license_reference IS NOT NULL AND license_reference ~ '[^[:space:]]')),
	CONSTRAINT fk_datasets_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id),
	CONSTRAINT fk_datasets_uploaded_by_users FOREIGN KEY(uploaded_by) REFERENCES users (id)
)""",
    """CREATE INDEX ix_datasets_org_created ON datasets (organization_id, created_at DESC)""",
    """CREATE INDEX ix_datasets_org_purpose_status ON datasets (organization_id, purpose, status)""",
    """CREATE TABLE memberships (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	organization_id UUID NOT NULL,
	user_id UUID NOT NULL,
	role VARCHAR(20) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_memberships PRIMARY KEY (id),
	CONSTRAINT uq_memberships_organization_id_user_id UNIQUE (organization_id, user_id),
	CONSTRAINT ck_memberships_role CHECK (role IN ('ANALYST', 'RISK_MANAGER', 'ADMIN')),
	CONSTRAINT fk_memberships_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id),
	CONSTRAINT fk_memberships_user_id_users FOREIGN KEY(user_id) REFERENCES users (id)
)""",
    """CREATE INDEX ix_memberships_user_id ON memberships (user_id)""",
    """CREATE TABLE risk_settings (
	organization_id UUID NOT NULL,
	medium_threshold SMALLINT DEFAULT 40 NOT NULL,
	high_threshold SMALLINT DEFAULT 70 NOT NULL,
	critical_threshold SMALLINT DEFAULT 85 NOT NULL,
	alert_threshold SMALLINT DEFAULT 70 NOT NULL,
	updated_by UUID NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	version INTEGER DEFAULT 1 NOT NULL,
	CONSTRAINT pk_risk_settings PRIMARY KEY (organization_id),
	CONSTRAINT ck_risk_settings_threshold_order CHECK (0 < medium_threshold AND medium_threshold < high_threshold AND high_threshold < critical_threshold AND critical_threshold <= 100),
	CONSTRAINT ck_risk_settings_alert_threshold CHECK (alert_threshold BETWEEN 0 AND 100),
	CONSTRAINT fk_risk_settings_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id),
	CONSTRAINT fk_risk_settings_updated_by_users FOREIGN KEY(updated_by) REFERENCES users (id)
)""",
    """CREATE TABLE rule_definitions (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	organization_id UUID NOT NULL,
	code VARCHAR(64) NOT NULL,
	description TEXT NOT NULL,
	enabled BOOLEAN DEFAULT true NOT NULL,
	parameters_json JSONB NOT NULL,
	version INTEGER DEFAULT 1 NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_rule_definitions PRIMARY KEY (id),
	CONSTRAINT uq_rule_definitions_organization_id_code UNIQUE (organization_id, code),
	CONSTRAINT ck_rule_definitions_code CHECK (code IN ('AMOUNT_OUTLIER', 'HIGH_VELOCITY', 'DEVICE_CHANGE')),
	CONSTRAINT fk_rule_definitions_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id)
)""",
    """CREATE INDEX ix_rule_definitions_org_enabled ON rule_definitions (organization_id, enabled)""",
    """CREATE TABLE sessions (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	user_id UUID NOT NULL,
	token_hash CHAR(64) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
	revoked_at TIMESTAMP WITH TIME ZONE,
	last_seen_at TIMESTAMP WITH TIME ZONE,
	CONSTRAINT pk_sessions PRIMARY KEY (id),
	CONSTRAINT ck_sessions_expiry CHECK (expires_at > created_at),
	CONSTRAINT fk_sessions_user_id_users FOREIGN KEY(user_id) REFERENCES users (id),
	CONSTRAINT uq_sessions_token_hash UNIQUE (token_hash)
)""",
    """CREATE INDEX ix_sessions_expiry ON sessions (expires_at)""",
    """CREATE INDEX ix_sessions_user_expiry ON sessions (user_id, expires_at)""",
    """CREATE TABLE transactions (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	organization_id UUID NOT NULL,
	external_id VARCHAR(100) NOT NULL,
	customer_ref VARCHAR(100) NOT NULL,
	occurred_at TIMESTAMP WITH TIME ZONE NOT NULL,
	amount NUMERIC(14, 2) NOT NULL,
	currency CHAR(3) NOT NULL,
	merchant_category VARCHAR(80) NOT NULL,
	country_code CHAR(2) NOT NULL,
	channel VARCHAR(8) NOT NULL,
	device_ref VARCHAR(100),
	source VARCHAR(12) NOT NULL,
	ingested_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_transactions PRIMARY KEY (id),
	CONSTRAINT uq_transactions_organization_id_external_id UNIQUE (organization_id, external_id),
	CONSTRAINT ck_transactions_positive_amount CHECK (amount > 0 AND amount <> 'NaN'::numeric),
	CONSTRAINT ck_transactions_channel CHECK (channel IN ('WEB', 'MOBILE', 'POS')),
	CONSTRAINT ck_transactions_source CHECK (source IN ('SINGLE', 'CSV')),
	CONSTRAINT fk_transactions_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id)
)""",
    """CREATE INDEX ix_transactions_org_customer_occurred ON transactions (organization_id, customer_ref, occurred_at DESC)""",
    """CREATE INDEX ix_transactions_org_occurred_id ON transactions (organization_id, occurred_at DESC, id)""",
    """CREATE INDEX ix_transactions_org_source ON transactions (organization_id, source)""",
    """CREATE TABLE model_versions (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	organization_id UUID NOT NULL,
	training_dataset_id UUID NOT NULL,
	version_label VARCHAR(40) NOT NULL,
	algorithm VARCHAR(120) NOT NULL,
	artifact_key TEXT NOT NULL,
	artifact_sha256 CHAR(64) NOT NULL,
	feature_schema_json JSONB NOT NULL,
	metrics_json JSONB NOT NULL,
	weight_config_json JSONB DEFAULT '{"supervised": 0.60, "anomaly": 0.25, "rules": 0.15}'::jsonb NOT NULL,
	is_active BOOLEAN DEFAULT false NOT NULL,
	trained_at TIMESTAMP WITH TIME ZONE NOT NULL,
	activated_at TIMESTAMP WITH TIME ZONE,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_model_versions PRIMARY KEY (id),
	CONSTRAINT uq_model_versions_organization_id_version_label UNIQUE (organization_id, version_label),
	CONSTRAINT fk_model_versions_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id),
	CONSTRAINT fk_model_versions_training_dataset_id_datasets FOREIGN KEY(training_dataset_id) REFERENCES datasets (id)
)""",
    """CREATE INDEX ix_model_versions_org_trained ON model_versions (organization_id, trained_at DESC)""",
    """CREATE UNIQUE INDEX uq_model_versions_active_org ON model_versions (organization_id) WHERE is_active = true""",
    """CREATE TABLE transaction_labels (
	transaction_id UUID NOT NULL,
	fraud_label BOOLEAN NOT NULL,
	label_source VARCHAR(16) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_transaction_labels PRIMARY KEY (transaction_id),
	CONSTRAINT ck_transaction_labels_label_source CHECK (label_source IN ('SYNTHETIC', 'PUBLIC_DATASET')),
	CONSTRAINT fk_transaction_labels_transaction_id_transactions FOREIGN KEY(transaction_id) REFERENCES transactions (id)
)""",
    """CREATE TABLE jobs (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	organization_id UUID NOT NULL,
	requested_by UUID NOT NULL,
	dataset_id UUID,
	model_version_id UUID,
	type VARCHAR(30) NOT NULL,
	status VARCHAR(20) NOT NULL,
	object_key TEXT,
	params_json JSONB DEFAULT '{}'::jsonb NOT NULL,
	total_rows INTEGER,
	processed_rows INTEGER DEFAULT 0 NOT NULL,
	failed_rows INTEGER DEFAULT 0 NOT NULL,
	attempt_count SMALLINT DEFAULT 0 NOT NULL,
	error_code VARCHAR(80),
	error_message VARCHAR(500),
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	started_at TIMESTAMP WITH TIME ZONE,
	completed_at TIMESTAMP WITH TIME ZONE,
	CONSTRAINT pk_jobs PRIMARY KEY (id),
	CONSTRAINT ck_jobs_type CHECK (type IN ('CSV_IMPORT', 'MODEL_TRAIN', 'REPORT_EXPORT')),
	CONSTRAINT ck_jobs_status CHECK (status IN ('QUEUED', 'PROCESSING', 'SUCCEEDED', 'FAILED')),
	CONSTRAINT ck_jobs_counters CHECK (total_rows >= 0 AND processed_rows >= 0 AND failed_rows >= 0 AND attempt_count >= 0),
	CONSTRAINT ck_jobs_completed_at CHECK (status NOT IN ('SUCCEEDED', 'FAILED') OR completed_at IS NOT NULL),
	CONSTRAINT fk_jobs_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id),
	CONSTRAINT fk_jobs_requested_by_users FOREIGN KEY(requested_by) REFERENCES users (id),
	CONSTRAINT fk_jobs_dataset_id_datasets FOREIGN KEY(dataset_id) REFERENCES datasets (id),
	CONSTRAINT fk_jobs_model_version_id_model_versions FOREIGN KEY(model_version_id) REFERENCES model_versions (id)
)""",
    """CREATE INDEX ix_jobs_dataset ON jobs (dataset_id)""",
    """CREATE INDEX ix_jobs_org_created ON jobs (organization_id, created_at DESC)""",
    """CREATE INDEX ix_jobs_status_created ON jobs (status, created_at)""",
    """CREATE TABLE scoring_results (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	transaction_id UUID NOT NULL,
	model_version_id UUID NOT NULL,
	risk_score SMALLINT NOT NULL,
	risk_band VARCHAR(10) NOT NULL,
	supervised_probability NUMERIC(7, 6) NOT NULL,
	anomaly_percentile NUMERIC(7, 6) NOT NULL,
	rule_signal NUMERIC(7, 6) NOT NULL,
	explanation_status VARCHAR(10) NOT NULL,
	explanation_json JSONB NOT NULL,
	settings_snapshot_json JSONB NOT NULL,
	latency_ms INTEGER NOT NULL,
	scored_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_scoring_results PRIMARY KEY (id),
	CONSTRAINT ck_scoring_results_risk_score CHECK (risk_score BETWEEN 0 AND 100),
	CONSTRAINT ck_scoring_results_risk_band CHECK (risk_band IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
	CONSTRAINT ck_scoring_results_supervised_probability CHECK (supervised_probability BETWEEN 0 AND 1),
	CONSTRAINT ck_scoring_results_anomaly_percentile CHECK (anomaly_percentile BETWEEN 0 AND 1),
	CONSTRAINT ck_scoring_results_rule_signal CHECK (rule_signal BETWEEN 0 AND 1),
	CONSTRAINT ck_scoring_results_explanation_status CHECK (explanation_status IN ('COMPLETE', 'PARTIAL')),
	CONSTRAINT ck_scoring_results_latency_ms CHECK (latency_ms >= 0),
	CONSTRAINT uq_scoring_results_transaction_id UNIQUE (transaction_id),
	CONSTRAINT fk_scoring_results_transaction_id_transactions FOREIGN KEY(transaction_id) REFERENCES transactions (id),
	CONSTRAINT fk_scoring_results_model_version_id_model_versions FOREIGN KEY(model_version_id) REFERENCES model_versions (id)
)""",
    """CREATE INDEX ix_scoring_results_band_scored ON scoring_results (risk_band, scored_at DESC)""",
    """CREATE INDEX ix_scoring_results_model_scored ON scoring_results (model_version_id, scored_at DESC)""",
    """CREATE TABLE alerts (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	organization_id UUID NOT NULL,
	scoring_result_id UUID NOT NULL,
	status VARCHAR(12) NOT NULL,
	reason_summary VARCHAR(240) NOT NULL,
	dismissal_reason VARCHAR(1000),
	dismissed_by UUID,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_alerts PRIMARY KEY (id),
	CONSTRAINT ck_alerts_status CHECK (status IN ('NEW', 'IN_CASE', 'DISMISSED')),
	CONSTRAINT ck_alerts_dismissal_reason CHECK (status <> 'DISMISSED' OR (dismissal_reason IS NOT NULL AND dismissal_reason ~ '[^[:space:]]')),
	CONSTRAINT fk_alerts_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id),
	CONSTRAINT uq_alerts_scoring_result_id UNIQUE (scoring_result_id),
	CONSTRAINT fk_alerts_scoring_result_id_scoring_results FOREIGN KEY(scoring_result_id) REFERENCES scoring_results (id),
	CONSTRAINT fk_alerts_dismissed_by_users FOREIGN KEY(dismissed_by) REFERENCES users (id)
)""",
    """CREATE INDEX ix_alerts_org_status_created ON alerts (organization_id, status, created_at DESC)""",
    """CREATE TABLE job_errors (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	job_id UUID NOT NULL,
	row_number INTEGER,
	code VARCHAR(80) NOT NULL,
	summary VARCHAR(400) NOT NULL,
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_job_errors PRIMARY KEY (id),
	CONSTRAINT ck_job_errors_row_number CHECK (row_number >= 1),
	CONSTRAINT fk_job_errors_job_id_jobs FOREIGN KEY(job_id) REFERENCES jobs (id)
)""",
    """CREATE INDEX ix_job_errors_job_row ON job_errors (job_id, row_number)""",
    """CREATE TABLE rule_hits (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	scoring_result_id UUID NOT NULL,
	rule_definition_id UUID,
	rule_code_snapshot VARCHAR(64) NOT NULL,
	strength NUMERIC(7, 6) NOT NULL,
	details_json JSONB NOT NULL,
	CONSTRAINT pk_rule_hits PRIMARY KEY (id),
	CONSTRAINT uq_rule_hits_scoring_result_id_rule_code_snapshot UNIQUE (scoring_result_id, rule_code_snapshot),
	CONSTRAINT ck_rule_hits_strength CHECK (strength BETWEEN 0 AND 1),
	CONSTRAINT fk_rule_hits_scoring_result_id_scoring_results FOREIGN KEY(scoring_result_id) REFERENCES scoring_results (id),
	CONSTRAINT fk_rule_hits_rule_definition_id_rule_definitions FOREIGN KEY(rule_definition_id) REFERENCES rule_definitions (id) ON DELETE SET NULL
)""",
    """CREATE INDEX ix_rule_hits_definition ON rule_hits (rule_definition_id)""",
    """CREATE TABLE cases (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	organization_id UUID NOT NULL,
	alert_id UUID NOT NULL,
	created_by UUID NOT NULL,
	assigned_to UUID,
	status VARCHAR(12) NOT NULL,
	resolution VARCHAR(20),
	resolution_note VARCHAR(2000),
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	closed_at TIMESTAMP WITH TIME ZONE,
	version INTEGER DEFAULT 1 NOT NULL,
	CONSTRAINT pk_cases PRIMARY KEY (id),
	CONSTRAINT ck_cases_status CHECK (status IN ('OPEN', 'IN_REVIEW', 'CLOSED')),
	CONSTRAINT ck_cases_resolution CHECK (resolution IN ('CONFIRMED_FRAUD', 'FALSE_POSITIVE', 'INCONCLUSIVE')),
	CONSTRAINT ck_cases_resolution_state CHECK ((status = 'CLOSED' AND resolution IS NOT NULL AND resolution_note IS NOT NULL AND resolution_note ~ '[^[:space:]]' AND closed_at IS NOT NULL) OR (status IN ('OPEN', 'IN_REVIEW') AND resolution IS NULL AND closed_at IS NULL)),
	CONSTRAINT fk_cases_organization_id_organizations FOREIGN KEY(organization_id) REFERENCES organizations (id),
	CONSTRAINT uq_cases_alert_id UNIQUE (alert_id),
	CONSTRAINT fk_cases_alert_id_alerts FOREIGN KEY(alert_id) REFERENCES alerts (id),
	CONSTRAINT fk_cases_created_by_users FOREIGN KEY(created_by) REFERENCES users (id),
	CONSTRAINT fk_cases_assigned_to_users FOREIGN KEY(assigned_to) REFERENCES users (id)
)""",
    """CREATE INDEX ix_cases_assignee_status ON cases (assigned_to, status)""",
    """CREATE INDEX ix_cases_org_status_updated ON cases (organization_id, status, updated_at DESC)""",
    """CREATE TABLE case_events (
	id UUID DEFAULT gen_random_uuid() NOT NULL,
	case_id UUID NOT NULL,
	actor_user_id UUID NOT NULL,
	action VARCHAR(40) NOT NULL,
	previous_status VARCHAR(12),
	new_status VARCHAR(12),
	note VARCHAR(2000),
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
	CONSTRAINT pk_case_events PRIMARY KEY (id),
	CONSTRAINT ck_case_events_previous_status CHECK (previous_status IN ('OPEN', 'IN_REVIEW', 'CLOSED')),
	CONSTRAINT ck_case_events_new_status CHECK (new_status IN ('OPEN', 'IN_REVIEW', 'CLOSED')),
	CONSTRAINT ck_case_events_note CHECK (action <> 'NOTE_ADDED' OR (note IS NOT NULL AND note ~ '[^[:space:]]')),
	CONSTRAINT fk_case_events_case_id_cases FOREIGN KEY(case_id) REFERENCES cases (id),
	CONSTRAINT fk_case_events_actor_user_id_users FOREIGN KEY(actor_user_id) REFERENCES users (id)
)""",
    """CREATE INDEX ix_case_events_case_created_id ON case_events (case_id, created_at, id)""",
)


def upgrade() -> None:
    for statement in DDL:
        # Escape SQLAlchemy bind markers inside literal JSON and PostgreSQL casts.
        op.execute(sa.text(statement.replace(":", r"\:")))
    role = os.environ.get("APP_DB_USER", "sentinel_app")
    if not re.fullmatch(r"[a-z][a-z0-9_]*", role) or role == "sentinel_migrator":
        raise RuntimeError("Invalid application role for migration grants")
    immutable = {
        "transactions",
        "transaction_labels",
        "scoring_results",
        "rule_hits",
        "case_events",
        "audit_logs",
        "model_versions",
    }
    for table in TABLES:
        op.execute(f'GRANT SELECT, INSERT ON TABLE "{table}" TO "{role}"')
        if table not in immutable:
            op.execute(f'GRANT UPDATE ON TABLE "{table}" TO "{role}"')
    op.execute(f'GRANT UPDATE (is_active, activated_at) ON model_versions TO "{role}"')
    op.execute(f'GRANT DELETE ON sessions, rule_definitions TO "{role}"')
    op.execute(f'GRANT SELECT ON alembic_version TO "{role}"')


def downgrade() -> None:
    # Destructive rollback is deliberately supported only by the isolated test runner.
    if (
        os.environ.get("APP_ENV") != "test"
        or os.environ.get("DB_HOST") != "database-test"
        or os.environ.get("POSTGRES_DB") != "sentinelai_schema_test"
    ):
        raise RuntimeError("Downgrade refused: only the disposable schema test database is allowed")
    if op.get_bind().scalar(sa.text("SELECT current_database()")) != "sentinelai_schema_test":
        raise RuntimeError("Downgrade refused: connected database is not the test database")
    for table in reversed(TABLES):
        op.drop_table(table)
