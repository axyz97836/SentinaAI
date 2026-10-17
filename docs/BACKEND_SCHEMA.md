# SentinelAI | Backend Schema, API and Event Contracts

**Version:** 1.1 approved baseline (revised 2026-10-16)  
**Status:** Owner approved; canonical backend contracts retained  
**Database:** PostgreSQL  
**API base:** `/api/v1`  
**Tenant model:** One seeded demo organization in MVP, organization-scoped data throughout.

## 1. General conventions

- Entity identifiers use UUID (`uuid`, generated server-side) unless a PK is explicitly specified as a FK.
- Timestamps use `timestamptz` in UTC; frontend formats local time with timezone shown.
- Money uses `numeric(14,2)` and 3-letter currency code; never floating point for persisted amounts.
- JSON object fields use `jsonb` with validation at API/schema boundaries; do not put ordinary FK relationships in JSON.
- Fields noted `NN` are `NOT NULL`. `PK` primary key, `FK` foreign key, `UQ` unique, `CK` check constraint.
- A soft/deactivated user is `is_active=false`; domain facts, event history and audit log are retained within retention policy.
- Organization ownership is verified in every query; **never** trust `organization_id` from the user input.
- Enum-like fields use checked `varchar` values in MVP to keep migrations explicit. Valid value sets are normative below.

## 2. Entity relationship diagram (text)

```text
organizations (1) --< memberships >-- (1) users
                                users (1) --< sessions
organizations (1) -- (1) risk_settings
organizations (1) --< rule_definitions
organizations (1) --< datasets --< jobs --< job_errors
organizations (1) --< model_versions >-- (0..1) datasets [training]
organizations (1) --< transactions -- (0..1) transaction_labels
                          |       |
                          |       +-- (1) scoring_results >-- (1) model_versions
                          |                          |  |
                          |                          |  +--< rule_hits >-- (0..1) rule_definitions
                          |                          +-- (0..1) alerts -- (0..1) cases --< case_events
                          |
                          +-- unique(organization_id, external_id)
organizations (1) --< audit_logs
users referenced by datasets, jobs, case actor/assignee, admin edits, audit logs
```

**Core uniqueness:** one `scoring_results` row per transaction; at most one alert per scoring result; at most one case per alert. Active model uniqueness is enforced by a partial unique index on `(organization_id) WHERE is_active`.

## 3. Full table specifications

### 3.1 `organizations`

| Column | Type | Constraints / meaning |
|---|---|---|
| `id` | uuid | PK |
| `name` | varchar(120) | NN, human-readable demo organization |
| `created_at` | timestamptz | NN default now() |

**Indexes:** PK `id`. **Relationship:** parent of all organization-scoped objects.

### 3.2 `users`

| Column | Type | Constraints / meaning |
|---|---|---|
| `id` | uuid | PK |
| `email` | varchar(254) | NN, case-insensitive unique |
| `password_hash` | text | NN, Argon2id encoded hash |
| `display_name` | varchar(100) | NN, fictional demo names only |
| `is_active` | boolean | NN default true |
| `created_at` | timestamptz | NN default now() |
| `updated_at` | timestamptz | NN default now() |

**Indexes:** PK; unique functional index on `lower(email)`. **Relationship:** membership, sessions, actions. Never store a plaintext password.

### 3.3 `memberships`

| Column | Type | Constraints / meaning |
|---|---|---|
| `id` | uuid | PK |
| `organization_id` | uuid | NN FK -> `organizations.id` |
| `user_id` | uuid | NN FK -> `users.id` |
| `role` | varchar(20) | NN CK in (`ANALYST`, `RISK_MANAGER`, `ADMIN`) |
| `created_at` | timestamptz | NN default now() |
| `updated_at` | timestamptz | NN default now() |

**Indexes:** UQ(`organization_id`,`user_id`); index (`user_id`). **Invariant:** last active ADMIN in organization cannot be demoted or deactivated; enforce with locked transaction in service layer.

### 3.4 `sessions`

| Column | Type | Constraints / meaning |
|---|---|---|
| `id` | uuid | PK |
| `user_id` | uuid | NN FK -> `users.id` |
| `token_hash` | char(64) | NN UQ; hash of random session token, not cookie itself |
| `created_at` | timestamptz | NN default now() |
| `expires_at` | timestamptz | NN, after created_at |
| `revoked_at` | timestamptz | nullable |
| `last_seen_at` | timestamptz | nullable |

**Indexes:** UQ `token_hash`; (`user_id`, `expires_at`); cleanup index (`expires_at`). No raw tokens in logs.

### 3.5 `risk_settings`

| Column | Type | Constraints / meaning |
|---|---|---|
| `organization_id` | uuid | PK, FK -> `organizations.id` |
| `medium_threshold` | smallint | NN default 40 |
| `high_threshold` | smallint | NN default 70 |
| `critical_threshold` | smallint | NN default 85 |
| `alert_threshold` | smallint | NN default 70 |
| `updated_by` | uuid | NN FK -> `users.id` |
| `updated_at` | timestamptz | NN default now() |
| `version` | integer | NN default 1, optimistic concurrency |

**Constraints:** CK `0 < medium_threshold < high_threshold < critical_threshold <= 100`; CK `0 <= alert_threshold <= 100`. Alert threshold need not equal `high_threshold`, although the default does. **Indexes:** PK. **History:** all changes captured by `audit_logs`; old scoring results keep their actual evaluated band/score.

### 3.6 `rule_definitions`

| Column | Type | Constraints / meaning |
|---|---|---|
| `id` | uuid | PK |
| `organization_id` | uuid | NN FK -> `organizations.id` |
| `code` | varchar(64) | NN, UQ within organization (`AMOUNT_OUTLIER`, `HIGH_VELOCITY`, `DEVICE_CHANGE`) |
| `description` | text | NN |
| `enabled` | boolean | NN default true |
| `parameters_json` | jsonb | NN, validated numeric/window parameters |
| `version` | integer | NN default 1 |
| `created_at` | timestamptz | NN default now() |
| `updated_at` | timestamptz | NN default now() |

**Indexes:** UQ(`organization_id`,`code`); (`organization_id`,`enabled`). **Past evidence:** `rule_hits` stores the rule code, details and threshold snapshot so later editing does not rewrite history.

### 3.7 `datasets`

| Column | Type | Constraints / meaning |
|---|---|---|
| `id` | uuid | PK |
| `organization_id` | uuid | NN FK -> `organizations.id` |
| `uploaded_by` | uuid | NN FK -> `users.id` |
| `purpose` | varchar(10) | NN CK in (`TRAINING`, `SCORING`) |
| `source_kind` | varchar(20) | NN CK in (`SYNTHETIC`, `PUBLIC_DATASET`) |
| `license_reference` | varchar(500) | nullable for synthetic, required and verified for public dataset |
| `original_filename` | varchar(255) | NN, sanitized for display |
| `object_key` | text | NN, private storage path/key |
| `sha256` | char(64) | NN file digest |
| `size_bytes` | bigint | NN CK 0 < size_bytes <= 10485760 |
| `row_count` | integer | nullable pending validation; <=10000 |
| `schema_version` | varchar(20) | NN default `1` |
| `status` | varchar(20) | NN CK in (`UPLOADED`, `VALIDATED`, `REJECTED`) |
| `created_at` | timestamptz | NN default now() |

**Indexes:** (`organization_id`,`created_at` DESC), (`organization_id`,`purpose`,`status`). **Source policy:** require verified `license_reference` for `PUBLIC_DATASET` uploads; never claim a license without review. Public availability alone is insufficient: do not admit actual person-linked financial transaction records. **Retention:** delete object through managed cleanup, never simply discard DB reference.

### 3.8 `jobs`

| Column | Type | Constraints / meaning |
|---|---|---|
| `id` | uuid | PK |
| `organization_id` | uuid | NN FK -> `organizations.id` |
| `requested_by` | uuid | NN FK -> `users.id` |
| `dataset_id` | uuid | nullable FK -> `datasets.id` |
| `model_version_id` | uuid | nullable FK -> `model_versions.id` (for relevant jobs) |
| `type` | varchar(30) | NN CK in (`CSV_IMPORT`, `MODEL_TRAIN`, `REPORT_EXPORT`) |
| `status` | varchar(20) | NN CK in (`QUEUED`, `PROCESSING`, `SUCCEEDED`, `FAILED`) |
| `object_key` | text | nullable; completed report export object key |
| `params_json` | jsonb | NN default `{}`, validated request/filter metadata |
| `total_rows` | integer | nullable |
| `processed_rows` | integer | NN default 0 |
| `failed_rows` | integer | NN default 0 |
| `attempt_count` | smallint | NN default 0 |
| `error_code` | varchar(80) | nullable |
| `error_message` | varchar(500) | nullable, safe for display |
| `created_at` | timestamptz | NN default now() |
| `started_at` | timestamptz | nullable |
| `completed_at` | timestamptz | nullable |

**Indexes:** (`organization_id`,`created_at` DESC), (`status`,`created_at`), (`dataset_id`). **Checks:** row counters >=0; completed/failed jobs have `completed_at`; `REPORT_EXPORT` may have no dataset. **Truth:** Postgres owns job status, not Redis queue metadata. For a CSV that finishes with some rejected rows, use `SUCCEEDED` with `failed_rows > 0` and visible “Completed with row errors” text; reserve `FAILED` for job-level failure. Never hide partial failures.

### 3.9 `job_errors`

| Column | Type | Constraints / meaning |
|---|---|---|
| `id` | uuid | PK |
| `job_id` | uuid | NN FK -> `jobs.id` |
| `row_number` | integer | nullable, >=1 if present |
| `code` | varchar(80) | NN machine-readable reason |
| `summary` | varchar(400) | NN sanitized explanation, no raw PII |
| `created_at` | timestamptz | NN default now() |

**Indexes:** (`job_id`,`row_number`). Cap stored detailed row errors per job and still count total failures.

### 3.10 `model_versions`

| Column | Type | Constraints / meaning |
|---|---|---|
| `id` | uuid | PK |
| `organization_id` | uuid | NN FK -> `organizations.id` |
| `training_dataset_id` | uuid | NN FK -> `datasets.id`; must be `TRAINING` |
| `version_label` | varchar(40) | NN, e.g. `baseline-001` |
| `algorithm` | varchar(120) | NN, describes combined Logistic Regression + Isolation Forest bundle |
| `artifact_key` | text | NN, private trusted model bundle |
| `artifact_sha256` | char(64) | NN |
| `feature_schema_json` | jsonb | NN |
| `metrics_json` | jsonb | NN, held-out metrics and class counts |
| `weight_config_json` | jsonb | NN, default `{supervised:0.60,anomaly:0.25,rules:0.15}` as structured object |
| `is_active` | boolean | NN default false |
| `trained_at` | timestamptz | NN |
| `activated_at` | timestamptz | nullable |
| `created_at` | timestamptz | NN default now() |

**Indexes:** UQ(`organization_id`,`version_label`); unique partial index on (`organization_id`) WHERE `is_active = true`; (`organization_id`,`trained_at` DESC). **Activation:** lock organization, deactivate old active, activate new in one transaction; validate artifact/checksum first.

### 3.11 `transactions`

| Column | Type | Constraints / meaning |
|---|---|---|
| `id` | uuid | PK |
| `organization_id` | uuid | NN FK -> `organizations.id` |
| `external_id` | varchar(100) | NN; synthetic source identifier |
| `customer_ref` | varchar(100) | NN; fictional/pseudonymous |
| `occurred_at` | timestamptz | NN event time |
| `amount` | numeric(14,2) | NN CK >0 |
| `currency` | char(3) | NN |
| `merchant_category` | varchar(80) | NN |
| `country_code` | char(2) | NN |
| `channel` | varchar(8) | NN CK in (`WEB`, `MOBILE`, `POS`) |
| `device_ref` | varchar(100) | nullable synthetic reference |
| `source` | varchar(12) | NN CK in (`SINGLE`, `CSV`) |
| `ingested_at` | timestamptz | NN default now() |

**Indexes:** UQ(`organization_id`,`external_id`); (`organization_id`,`occurred_at` DESC,`id`); (`organization_id`,`customer_ref`,`occurred_at` DESC) for velocity/behavior lookups; (`organization_id`,`source`). **Immutable** after creation. Canonical payload comparison protects replay.

### 3.12 `transaction_labels`

| Column | Type | Constraints / meaning |
|---|---|---|
| `transaction_id` | uuid | PK, FK -> `transactions.id` |
| `fraud_label` | boolean | NN; only if optional label supplied in scoring CSV |
| `label_source` | varchar(16) | NN CK in (`SYNTHETIC`, `PUBLIC_DATASET`) |
| `created_at` | timestamptz | NN default now() |

**Indexes:** PK. **Key safety rule:** No model input/feature generation path can join this table. Case resolutions do not silently overwrite these labels.

### 3.13 `scoring_results`

| Column | Type | Constraints / meaning |
|---|---|---|
| `id` | uuid | PK |
| `transaction_id` | uuid | NN FK -> `transactions.id`, UQ |
| `model_version_id` | uuid | NN FK -> `model_versions.id` |
| `risk_score` | smallint | NN CK 0..100 |
| `risk_band` | varchar(10) | NN CK in (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) |
| `supervised_probability` | numeric(7,6) | NN CK 0..1 |
| `anomaly_percentile` | numeric(7,6) | NN CK 0..1 |
| `rule_signal` | numeric(7,6) | NN CK 0..1 |
| `explanation_status` | varchar(10) | NN CK in (`COMPLETE`, `PARTIAL`) |
| `explanation_json` | jsonb | NN, sanitized top features + model component reasons |
| `settings_snapshot_json` | jsonb | NN, thresholds used at scoring time |
| `latency_ms` | integer | NN >=0, actual measured server-side time |
| `scored_at` | timestamptz | NN default now() |

**Indexes:** UQ(`transaction_id`); (`model_version_id`,`scored_at` DESC); (`risk_band`,`scored_at` DESC). Risk band and score are persisted snapshots, not back-calculated after admin configuration changes.

### 3.14 `rule_hits`

| Column | Type | Constraints / meaning |
|---|---|---|
| `id` | uuid | PK |
| `scoring_result_id` | uuid | NN FK -> `scoring_results.id` |
| `rule_definition_id` | uuid | nullable FK -> `rule_definitions.id`, ON DELETE SET NULL |
| `rule_code_snapshot` | varchar(64) | NN |
| `strength` | numeric(7,6) | NN CK 0..1 |
| `details_json` | jsonb | NN includes bounded parameter snapshot and observed reason |

**Indexes:** UQ(`scoring_result_id`,`rule_code_snapshot`); index (`rule_definition_id`). Keeps historical decisions interpretable after rule editing.

### 3.15 `alerts`

| Column | Type | Constraints / meaning |
|---|---|---|
| `id` | uuid | PK |
| `organization_id` | uuid | NN FK -> `organizations.id` |
| `scoring_result_id` | uuid | NN UQ FK -> `scoring_results.id` |
| `status` | varchar(12) | NN CK in (`NEW`, `IN_CASE`, `DISMISSED`) |
| `reason_summary` | varchar(240) | NN, cautious plain language |
| `dismissal_reason` | varchar(1000) | nullable, required for dismissal |
| `dismissed_by` | uuid | nullable FK -> `users.id` |
| `created_at` | timestamptz | NN default now() |
| `updated_at` | timestamptz | NN default now() |

**Indexes:** UQ(`scoring_result_id`); (`organization_id`,`status`,`created_at` DESC). `alerts` joins its transaction through `scoring_results`, not an extra denormalized transaction FK.

### 3.16 `cases`

| Column | Type | Constraints / meaning |
|---|---|---|
| `id` | uuid | PK |
| `organization_id` | uuid | NN FK -> `organizations.id` |
| `alert_id` | uuid | NN UQ FK -> `alerts.id` |
| `created_by` | uuid | NN FK -> `users.id` |
| `assigned_to` | uuid | nullable FK -> `users.id` |
| `status` | varchar(12) | NN CK in (`OPEN`, `IN_REVIEW`, `CLOSED`) |
| `resolution` | varchar(20) | nullable CK in (`CONFIRMED_FRAUD`, `FALSE_POSITIVE`, `INCONCLUSIVE`) |
| `resolution_note` | varchar(2000) | nullable |
| `created_at` | timestamptz | NN default now() |
| `updated_at` | timestamptz | NN default now() |
| `closed_at` | timestamptz | nullable |
| `version` | integer | NN default 1, optimistic concurrency |

**Indexes:** UQ(`alert_id`); (`organization_id`,`status`,`updated_at` DESC); (`assigned_to`,`status`). **Checks:** If `status='CLOSED'`, resolution, nonblank note and `closed_at` must be present; if open/in review, resolution and close time absent. No reopen in MVP.

### 3.17 `case_events`

| Column | Type | Constraints / meaning |
|---|---|---|
| `id` | uuid | PK |
| `case_id` | uuid | NN FK -> `cases.id` |
| `actor_user_id` | uuid | NN FK -> `users.id` |
| `action` | varchar(40) | NN e.g. `CASE_OPENED`, `NOTE_ADDED`, `STATUS_CHANGED`, `CASE_CLOSED` |
| `previous_status` | varchar(12) | nullable |
| `new_status` | varchar(12) | nullable |
| `note` | varchar(2000) | nullable; required for `NOTE_ADDED` |
| `created_at` | timestamptz | NN default now() |

**Indexes:** (`case_id`,`created_at`,`id`). Append-only application policy. Prevent normal update/delete through role permissions.

### 3.18 `audit_logs`

| Column | Type | Constraints / meaning |
|---|---|---|
| `id` | uuid | PK |
| `organization_id` | uuid | NN FK -> `organizations.id` |
| `actor_user_id` | uuid | nullable FK -> `users.id` for system jobs |
| `action` | varchar(80) | NN machine-readable operation |
| `resource_type` | varchar(60) | NN, e.g. `CASE`, `RULE`, `MODEL`, `USER` |
| `resource_id` | uuid | nullable for organization-level events |
| `metadata_json` | jsonb | NN, redacted diff/reference, no secrets |
| `request_id` | varchar(64) | nullable tracing ID |
| `created_at` | timestamptz | NN default now() |

**Indexes:** (`organization_id`,`created_at` DESC), (`resource_type`,`resource_id`,`created_at` DESC), (`actor_user_id`,`created_at` DESC). Append-only application policy and restricted DB privileges.

## 4. API shape and authentication

### Shared response conventions

- All routes below are relative to `/api/v1`; except sign-in, health and session state, routes require a valid HttpOnly cookie session plus organization membership.
- `ANALYST`, `RISK_MANAGER`, `ADMIN` abbreviated A, M, D in the permission column. **Admin-only** is D.
- For every unsafe method under cookie auth, send CSRF token per the chosen double-submit or synchronized-token implementation. Do not put tokens in URLs.
- Successful single transaction (`201`) summary shape: `{transaction_id, scoring_result_id, risk_score, risk_band, model_version_id, alert_id|null}`.
- Async response (`202`): `{job_id, dataset_id?, status:"QUEUED"}`.
- List response: `{items:[...], next_cursor:string|null}`; limit max 100.
- Error response: `{error:{code,message,request_id,field_errors?}}`, with appropriate 4xx/5xx.
- Auth cookies are not returned in JSON; login uses Set-Cookie. Cross-org requested IDs resolve as 404 to avoid information disclosure.

### Endpoint inventory

| Method | Path | Request | Response | Auth |
|---|---|---|---|---|
| POST | `/auth/login` | `{email,password}` | 200 `{user,role}` + session cookie | Public + CSRF/login origin protection |
| GET | `/auth/me` | none | 200 `{user,role,organization}` | A/M/D |
| POST | `/auth/logout` | none | 204 + session revoked | A/M/D + CSRF |
| GET | `/dashboard/summary` | `date_from,date_to` | 200 counts, band distribution, recent alerts, timestamps | A/M/D |
| POST | `/ingestions` | multipart CSV, `purpose=TRAINING|SCORING`, `source_kind`, `license_reference` if public | 202 `{job_id,dataset_id,status}` | SCORING A/M/D; TRAINING D |
| GET | `/jobs/{id}` | none | 200 type, status, counts, safe errors, output flag | A/M/D, own organization |
| GET | `/transactions` | cursor, limit, search, band, dates | 200 paginated rows | A/M/D |
| POST | `/transactions` | canonical transaction JSON | 201 score result; same replay 200; conflict 409 | A/M/D |
| GET | `/transactions/{id}` | none | 200 transaction + score + alert/case links | A/M/D |
| GET | `/transactions/{id}/explanation` | none | 200 component contributions, rule hits, SHAP features, caveat | A/M/D |
| GET | `/alerts` | cursor, status, risk band, date | 200 paginated alert rows | A/M/D |
| POST | `/alerts/{id}/dismiss` | `{reason}` | 200 updated alert | A/M/D + CSRF |
| POST | `/alerts/{id}/cases` | optional `{note}` | 201 case ID, alert `IN_CASE`; duplicate same existing case returns 200 | A/M/D + CSRF |
| GET | `/cases` | cursor, status, date | 200 paginated case rows | A/M/D |
| GET | `/cases/{id}` | none | 200 case, linked evidence, timeline | A/M/D |
| PATCH | `/cases/{id}` | `{status:"IN_REVIEW",version,note?}` | 200 updated case | A/M/D + CSRF |
| POST | `/cases/{id}/events` | `{note}` | 201 append-only case event | A/M/D + CSRF |
| POST | `/cases/{id}/resolve` | `{resolution,resolution_note,version}` | 200 closed case + event | A/M/D + CSRF |
| GET | `/reports/summary` | `date_from,date_to` | 200 observed counts/outcomes | A/M/D |
| POST | `/reports/exports` | `{date_from,date_to}` | 202 `{job_id,status}` | A/M/D + CSRF |
| GET | `/reports/exports/{job_id}/download` | none | 200 CSV attachment, 404 if wrong org/expired | A/M/D |
| GET | `/models/active` | none | 200 active version, metrics, training data provenance | A/M/D |
| GET | `/admin/settings` | none | 200 thresholds, rules, versions, audit summary | D |
| PATCH | `/admin/settings` | `{medium_threshold,high_threshold,critical_threshold,alert_threshold,version}` | 200 new settings + version | D + CSRF |
| PATCH | `/admin/rules/{id}` | `{enabled,parameters_json,version}` | 200 updated version | D + CSRF |
| GET | `/admin/models` | cursor | 200 model versions + held-out metrics | D |
| POST | `/admin/models/train` | `{training_dataset_id}` | 202 `{job_id,status}` | D + CSRF |
| POST | `/admin/models/{id}/activate` | `{}` | 200 active model version | D + CSRF |
| GET | `/admin/users` | none | 200 demo users and roles | D |
| PATCH | `/admin/users/{id}/role` | `{role}` | 200 updated role; guard last admin | D + CSRF |
| GET | `/health/live` | none | 200 process running | Public, no sensitive details |
| GET | `/health/ready` | none | 200 ready / 503 dependency error | Internal/protected in deployed environment |

**Frontend-only routes:** `/login`, `/dashboard`, `/transactions`, `/transactions/upload`, `/transactions/[id]`, `/alerts`, `/cases`, `/cases/[id]`, `/reports`, `/admin/settings`, `/admin/users`, `/privacy`, `/terms`, custom 404. The server endpoints are **not** substitute frontend pages.

## 5. Event and queue contracts

Use **Celery tasks via Redis**, not a new Kafka cluster. Job state and row errors persist in PostgreSQL. Queue names/task IDs are internal, not public messaging APIs.

| Queue/task name | Trigger | Payload (IDs only, no raw CSV) | Worker effects | Retry behavior |
|---|---|---|---|---|
| `ingestion.process_csv` | `POST /ingestions` | `{job_id,dataset_id}` | Validate dataset; if SCORING create transactions/scores/alerts in per-row transactions; update counts | 3 attempts with exponential backoff for transient infra issues; validation errors permanent |
| `models.train_baseline` | `POST /admin/models/train` | `{job_id,training_dataset_id}` | Build validated model, measure hold-out, save trusted artifact, record candidate model | Up to 2 infra retries; do not retry bad dataset indefinitely |
| `reports.create_csv` | `POST /reports/exports` | `{job_id}` | Read frozen date bounds from `jobs.params_json`, generate private CSV | 3 transient retries with backoff |
| `jobs.cleanup_expired` | scheduled maintenance | no user data in payload | Apply retention policy to expired exports/uploads/job errors and expired sessions | Idempotent and logged |

Task IDs and jobs are independent; use one `jobs.id` as durable key. Ensure duplicate task deliveries cannot create duplicate transaction/alert/case data. Local Redis/Celery is enough for MVP; Kafka, stream processors and WebSocket push are excluded.

## 6. Transactions, locks, and consistency rules

- **Single direct transaction:** one ACID transaction for `transactions`, `scoring_results`, optional `rule_hits`, optional `alerts`, and an audit event. Feature reads must use prior event times, never post-event facts.
- **Alert to case:** row-lock alert, verify `NEW`, insert one `cases` row, update alert to `IN_CASE`, append event/audit, commit. Unique `cases.alert_id` protects retries/races.
- **Dismiss alert:** row-lock, accept only `NEW`, require reason, update alert + audit atomically.
- **Close case:** optimistic `cases.version` or row lock, verify open state, require resolution and nonblank note, append `case_events` and `audit_logs` atomically.
- **Model activation:** serialize per-organization activation; clear one active model and activate next inside transaction, reload cache after success. Avoid active-model gap visible to callers by transaction isolation and cache-version checking.
- **Role changes:** protect last active admin under locked membership set; revoke or recheck sessions to make changed role effective on subsequent requests.
- **Duplicate requests:** `(organization_id, external_id)` uniqueness is authoritative; exact payload replay returns current result, changed payload returns 409; don't double-generate alerts.

## 7. Data retention and privacy

| Data | Proposed retention | Deletion / access rule |
|---|---|---|
| Synthetic transactions, scores, alerts and cases | 90 days after ingest for deployed demo | Scheduled organization-scoped purge, after demo backup/export where appropriate |
| Training/scoring uploaded CSV objects | 30 days from upload | Private bucket; cleanup job removes object and metadata carefully |
| Export files | 24 hours | Authenticated download, then delete object; 404 or 410 policy explained |
| Jobs and sanitized row error details | Jobs 30 days; detailed job errors 7 days | Aggregate stats can be retained within jobs until expiry |
| Server-side sessions | Until expiry or logout; expired rows purged daily | Cookie only in browser, hash in DB |
| `case_events` / `audit_logs` | 90 days in demo, then archived/purged under a declared policy | Append-only until retention cleanup; admin-scoped access |
| Logs | 14 days or host-limited setting | Redacted structured logs only |
| Model artifacts and metadata | Keep active and previous two versions; expire older inactive after 90 days if unreferenced | Never delete artifacts still referenced by scores unless historical explanation policy is addressed |

**Important:** Since results reference historical model versions, preserve the metadata and explanation snapshots even if an old artifact is eventually removed. Use demo-only policy in published Privacy/Terms. Never ingest actual payment cards, names, addresses, phone numbers, bank accounts or real user browsing histories.

### Audit design

Audit at minimum: login/logout failures in security logs (avoid raw credentials), dataset upload, admin rule/threshold/role edits, training/activation, alert dismissal/case creation, case status and resolution, report export. Every audit event includes `actor_user_id` or system actor, organization, action, resource ID, redacted before/after change summary, request ID, and timestamp. No silent update/delete via app role. If a retention purge runs, log its aggregate counts without leaking row contents.

## 8. Performance-related indexing and query review

- List: `transactions(organization_id,occurred_at DESC,id)`, `alerts(organization_id,status,created_at DESC)`, `cases(organization_id,status,updated_at DESC)` with keyset cursors.
- Velocity feature: `transactions(organization_id,customer_ref,occurred_at DESC)`, time window `[occurred_at-10m, occurred_at)`; no future lookups.
- Model lookup: partial unique active index on `model_versions(organization_id)`.
- Background status: `jobs(organization_id,created_at DESC)` and queue status index.
- Audit inspection: `audit_logs(organization_id,created_at DESC)`.
- Limit table/query sizes in API; inspect `EXPLAIN ANALYZE` for slow queries. Do not invent throughput claims.

## 9. DBMS syllabus demonstrations

| Concept | Where it appears |
|---|---|
| Normalization | Separate organizations/users/memberships, transactions/scores, alerts/cases/events, rule definitions/hits |
| Referential integrity | Foreign keys for every relationship and restricted deletion of investigation evidence |
| Uniqueness | Transactions external ID, one score/alert/case constraints, one active model per organization |
| Indexes | Time-ordered operational lists, velocity lookup, status queues, audit filtering |
| ACID transactions | Score plus alert persistence; case opening/closing; role and model activation |
| Isolation and concurrency | Row locking, optimistic case versioning, idempotent CSV retries |
| Query optimization | Aggregation and cursor pagination; observed SQL plans |
| Structured vs. unstructured storage | Relational rows in Postgres, file objects in private object storage |

### Frontend contract, agent/tooling and release consistency (revision 1.1)

The project is planned for **VS Code using the owner's GPT-6 Astra agent** rather than the earlier Google Antigravity workflow. This change does **not** create new tables, statuses or API endpoints. Every UI screen in `UIUX_BRIEF.md` and `APP_FLOW.md` must consume the endpoints and role permissions documented here; UI component examples or design skills must not invent API data, statuses, scores or record counts.

Any Bklit UI chart (or alternative) gets its data from authorized aggregate/list endpoints computed from `transactions`, `scoring_results`, `alerts`, `cases` or `case_events`. Do not generate fake KPI values or imply synthetic evaluation metrics reflect real fraud detection performance. Risk score and supervised fraud probability remain distinct. UI motion libraries have no authority to change event ordering or persisted state.

API contract tests and browser E2E checks must exercise validation errors, 401/403/404/409 states, async job progress and failures, role-gated navigation, and authoritative success confirmation. The database remains the durable authority for counts, case status and job status. Audit logs exclude credentials and sensitive payloads; demo data only. No new persistence entity is required for the selected visual reference sites.

## 10. Policy and resource placeholders

[Dataset source/license: to be added]  
[Hosting/database/Redis/object-storage providers: to be added]  
[Optional external APIs: to be added, no MVP dependency]  
[System monitoring provider: to be added, optional]  
[Custom domain: to be added]

**No executable migrations or application source are created by this document.** Implement only after explicit owner approval and according to `IMPLEMENTATION_PLAN.md`.
