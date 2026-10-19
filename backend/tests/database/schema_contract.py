"""Independent column/FK inventory transcribed from approved BACKEND_SCHEMA.md."""

COLUMNS = {
    "organizations": "id name created_at",
    "users": "id email password_hash display_name is_active created_at updated_at",
    "memberships": "id organization_id user_id role created_at updated_at",
    "sessions": "id user_id token_hash created_at expires_at revoked_at last_seen_at",
    "risk_settings": "organization_id medium_threshold high_threshold critical_threshold alert_threshold updated_by updated_at version",
    "rule_definitions": "id organization_id code description enabled parameters_json version created_at updated_at",
    "datasets": "id organization_id uploaded_by purpose source_kind license_reference original_filename object_key sha256 size_bytes row_count schema_version status created_at",
    "jobs": "id organization_id requested_by dataset_id model_version_id type status object_key params_json total_rows processed_rows failed_rows attempt_count error_code error_message created_at started_at completed_at",
    "job_errors": "id job_id row_number code summary created_at",
    "model_versions": "id organization_id training_dataset_id version_label algorithm artifact_key artifact_sha256 feature_schema_json metrics_json weight_config_json is_active trained_at activated_at created_at",
    "transactions": "id organization_id external_id customer_ref occurred_at amount currency merchant_category country_code channel device_ref source ingested_at",
    "transaction_labels": "transaction_id fraud_label label_source created_at",
    "scoring_results": "id transaction_id model_version_id risk_score risk_band supervised_probability anomaly_percentile rule_signal explanation_status explanation_json settings_snapshot_json latency_ms scored_at",
    "rule_hits": "id scoring_result_id rule_definition_id rule_code_snapshot strength details_json",
    "alerts": "id organization_id scoring_result_id status reason_summary dismissal_reason dismissed_by created_at updated_at",
    "cases": "id organization_id alert_id created_by assigned_to status resolution resolution_note created_at updated_at closed_at version",
    "case_events": "id case_id actor_user_id action previous_status new_status note created_at",
    "audit_logs": "id organization_id actor_user_id action resource_type resource_id metadata_json request_id created_at",
}

FOREIGN_KEYS = {
    "memberships": {"organization_id": "organizations", "user_id": "users"},
    "sessions": {"user_id": "users"},
    "risk_settings": {"organization_id": "organizations", "updated_by": "users"},
    "rule_definitions": {"organization_id": "organizations"},
    "datasets": {"organization_id": "organizations", "uploaded_by": "users"},
    "jobs": {
        "organization_id": "organizations",
        "requested_by": "users",
        "dataset_id": "datasets",
        "model_version_id": "model_versions",
    },
    "job_errors": {"job_id": "jobs"},
    "model_versions": {"organization_id": "organizations", "training_dataset_id": "datasets"},
    "transactions": {"organization_id": "organizations"},
    "transaction_labels": {"transaction_id": "transactions"},
    "scoring_results": {"transaction_id": "transactions", "model_version_id": "model_versions"},
    "rule_hits": {"scoring_result_id": "scoring_results", "rule_definition_id": "rule_definitions"},
    "alerts": {
        "organization_id": "organizations",
        "scoring_result_id": "scoring_results",
        "dismissed_by": "users",
    },
    "cases": {
        "organization_id": "organizations",
        "alert_id": "alerts",
        "created_by": "users",
        "assigned_to": "users",
    },
    "case_events": {"case_id": "cases", "actor_user_id": "users"},
    "audit_logs": {"organization_id": "organizations", "actor_user_id": "users"},
}

UNIQUE_KEYS = {
    "memberships": [("organization_id", "user_id")],
    "sessions": [("token_hash",)],
    "rule_definitions": [("organization_id", "code")],
    "model_versions": [("organization_id", "version_label")],
    "transactions": [("organization_id", "external_id")],
    "scoring_results": [("transaction_id",)],
    "rule_hits": [("scoring_result_id", "rule_code_snapshot")],
    "alerts": [("scoring_result_id",)],
    "cases": [("alert_id",)],
}

# Expected non-constraint indexes, including direction. Uniqueness is tested separately.
INDEX_COLUMNS = {
    "memberships": [("user_id",)],
    "sessions": [("user_id", "expires_at"), ("expires_at",)],
    "rule_definitions": [("organization_id", "enabled")],
    "datasets": [("organization_id", "created_at DESC"), ("organization_id", "purpose", "status")],
    "jobs": [("organization_id", "created_at DESC"), ("status", "created_at"), ("dataset_id",)],
    "job_errors": [("job_id", "row_number")],
    "model_versions": [("organization_id", "trained_at DESC")],
    "transactions": [
        ("organization_id", "occurred_at DESC", "id"),
        ("organization_id", "customer_ref", "occurred_at DESC"),
        ("organization_id", "source"),
    ],
    "scoring_results": [("model_version_id", "scored_at DESC"), ("risk_band", "scored_at DESC")],
    "rule_hits": [("rule_definition_id",)],
    "alerts": [("organization_id", "status", "created_at DESC")],
    "cases": [("organization_id", "status", "updated_at DESC"), ("assigned_to", "status")],
    "case_events": [("case_id", "created_at", "id")],
    "audit_logs": [
        ("organization_id", "created_at DESC"),
        ("resource_type", "resource_id", "created_at DESC"),
        ("actor_user_id", "created_at DESC"),
    ],
}
