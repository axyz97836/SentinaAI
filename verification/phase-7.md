# Phase 7 verification: rules, explanations and risk configuration

Updated: 2026-10-25. **Configuration and stored-explanation checkpoint verified locally.
Phase 7 remains incomplete; supervised attribution awaits owner dependency approval.**
Branch: `feat/phase-07-explainability`; base `f57eeae` (Phase 6 merge, PR #6).

## Authorization and preservation

The owner's Phase 7 attachment and resume instruction authorize only rules, supervised
explanation, the explanation API and ADMIN risk configuration. The eleven approved documents
and prior Phase 5/6 evidence were reviewed; their SHA-256 hashes match the approved baseline.
AGENTS.md and both installed Ponytail skills were read. No uncommitted Phase 7 work existed.
Origin was inspected and remains exactly https://github.com/axyz97836/SentinaAI. Fetch verified
Phase 6 implementation/report ancestry in main; local main fast-forwarded safely and this
dedicated branch was created. No reset, seed, credential regeneration or main-data mutation.

Initial live baseline: six healthy services, API alive/ready, 18 domain tables,
`0001_initial_schema (head)`, Alembic check reports no new upgrade operations. No migration.

## First implementation unit

- Strict shared validation preserves Phase 6 parameter shapes: AMOUNT_OUTLIER multiplier
  >1 and <=100, min_history 1–100; HIGH_VELOCITY window_minutes exactly 10 and count_threshold
  1–1000; DEVICE_CHANGE empty parameters. Unknown keys/codes, booleans as numbers, nonfinite
  multipliers and unsupported windows are refused. No rule creation API or seed change.
- Existing amount/history/device decisions and binary max aggregation remain. Amount
  evidence now records observed amount/currency, same-currency historical mean and threshold.
  Velocity uses an indexed, bounded ten-minute aggregate to record the exact observed count
  instead of the Phase 6 threshold-capped count; the firing decision is unchanged.
- GET/PATCH /api/v1/admin/settings and PATCH /api/v1/admin/rules/{id}: ADMIN guard,
  session-derived org, CSRF/Origin on writes, bounded body, strict fields, expected version,
  same org lock as scoring, version increment and atomic sanitized audit. No-op edits retain
  version/audit state; stale edits return 409. Alert threshold is independent of band thresholds.
- GET /api/v1/transactions/{id}/explanation reads only immutable persisted evidence and
  never loads artifacts or recalculates an old score. All roles within the org are allowed;
  missing/foreign IDs are 404. Old absent attribution is explicitly NOT_RECORDED_AT_SCORING_TIME.

## Dependency review and owner approval pending

SHAP is not installed. The owner was asked through the asynchronous input tool to approve
exactly five additions: shap 0.54.1, pandas 3.1.0, tqdm 4.70.1, slicer 0.0.8, cloudpickle 3.1.2.
The alternative offered is an explicitly labeled native linear fallback with no new packages.
No answer has been assumed and no dependency manifest or lockfile has changed.

PyPI metadata and a pip `--dry-run --only-binary=:all:` resolution on the existing Python
3.12 test image confirm those five additions with all existing runtime versions constrained
unchanged. Python requirements fit 3.12; SHAP supplies non-yanked Linux ARM/x86 wheels.
Licenses: SHAP/slicer MIT, pandas/cloudpickle BSD-3-Clause, tqdm MPL-2.0 AND MIT.
`pip-audit -r /evidence/phase7-shap-proposed.txt --disable-pip --no-deps --cache-dir /tmp/pip-audit`
reports **No known vulnerabilities found** for the five exact versions. This is a dated
advisory check, not a security guarantee or runtime compatibility pass.

First dry run correctly rejected a mixed hashed/unhashed request. A temporary version-only
constraint list was then used solely for resolution; installation remains unapproved.
Ignored evidence: `.local/phase7-shap-resolution.json`, `phase7-shap-resolution.log`,
`phase7-shap-proposed.txt`, `phase7-shap-audit.log`, `phase7-existing-constraints.txt`.

Sources: [SHAP package](https://pypi.org/project/shap/0.54.1/),
[LinearExplainer](https://shap.readthedocs.io/en/latest/generated/shap.LinearExplainer.html),
[versioned implementation](https://github.com/shap/shap/blob/v0.54.1/shap/explainers/_linear.py).
The proposed bounded interventional explanation uses the exact transformed training-fold
mean from verified private training bytes, not a fabricated zero baseline or holdout data.
It explains classifier log odds only; at most five features plus the omitted contribution
sum and base value will preserve additivity. No existing model will be retrained or rewritten.

## Executed evidence to date

| Check | Completed result |
|---|---|
| `make database-check` | **310 passed**, one existing warning, 54.64 s; guarded resources removed |
| `make backend-check` | Ruff PASS, 69 formatted files, strict mypy PASS/45 modules; **198 passed**, 310 deselected, four existing warnings, 5.69 s |
| `make frontend-check` | ESLint, type generation, strict TypeScript and production build PASS |
| `make infra-check` | Restricted database, authenticated Redis, private S3 and worker checks PASS |
| `make outage-check` | All eight controlled outage/recovery/port-isolation groups PASS |
| `make browser-check` | **8 passed**, 5.0 s |
| `make ingestion-check` | **9 integration checks passed**, isolated teardown completed |
| `make model-check` | **8 integration checks passed**, original synthetic metrics reproduced |
| `make scoring-check` | **9 integration checks passed**, including SIGKILL and storage recovery |
| `make explanation-check` | **7 integration checks passed**, isolated teardown completed |
| Focused parameter/scoring pytest | 70 passed, overlapping the backend total |

**516 distinct automated tests = 310 database + 198 backend + 8 browser.** Integration
groups are separate; focused and earlier runs are not counted twice. Earlier 304/309-case
database runs were incremental checks before the final timestamp-boundary test.

The real explanation integration generated/ingested synthetic training data, trained and
activated a model, provisioned three rule definitions only in the guarded disposable DB,
and scored genuine historical fixtures. It verified all three hits, observed amount/reference
and exact velocity counts, persisted component reconciliation, ADMIN edits and stale conflicts,
unchanged replay/evidence, non-admin/CSRF denials, SCORING CSV and foreign explanation denial.
Attribution is explicitly unavailable; this test does not claim to have exercised SHAP.

The checkpoint scoring integration reproduced 805 transactions/scores/alerts/audits and
803 separate labels, with no log markers/credentials leaked. Existing seed credentials
and main volumes/models are preserved. No main database seed was repeated.

## Resume diagnosis and corrected failures

The latest resume inspected all four requested logs and recovered the original tool-session
exit codes. `phase7-checkpoint-database.log`, `phase7-checkpoint-up.log`,
`phase7-checkpoint-regression.log` and `phase7-checkpoint-pipelines.log` all ended successfully
(exit zero). The startup log ends with six healthy services; no Docker startup failure or
pytest assertion failure remains in those logs. Completed unchanged checks were reused.

Earlier visible command failures were distinct:

- Initial dependency dry-run: existing hashed constraints triggered pip's require-hashes
  protection for the unapproved SHAP requirement. Temporary version-only constraints fixed
  metadata resolution; no packages were installed and real locks remain unchanged.
- Ruff identified formatting/import/line-length issues. These were fixed; final lint/format
  and strict typing passed. One new test module initially lacked its database marker, causing
  skips in the unit command; the marker now correctly deselects all 310 database cases.
- A patch referenced a pre-formatting import line and was refused without changing files.
  The current file was reread and the intended test additions applied successfully.
- Sandbox access blocked the attachment and a Node/OpenSSL metadata read; approved external
  execution resolved those tool restrictions. They were not application test failures.
- Review found subtraction underflow for a valid year-0001 event with velocity enabled.
  The lower window endpoint now clamps to the minimum supported timestamp; its real database
  regression passes, without changing the ordinary inclusive-lower/exclusive-upper window.

Evidence is in ignored `.local/phase7-checkpoint-{database,up,regression,pipelines}.log`,
`.local/phase7-configuration-integration.log` and earlier configuration/focused logs.

## Checkpoint Ponytail Review

What this change does: makes the existing rules strictly configurable, persists fuller factual
rule observations, and exposes existing immutable explanations. Configuration updates and
audit share a transaction and the same org lock as scoring.

Review traced auth/body limits, all new configuration/read routes, rule validation/evaluation,
immutable ORM grants, scoring/CSV callers, audit contents, integration helpers and CI. Expected
load remains the bounded single-worker demo. Database tests prove concurrent edit conflicts,
score/configuration serialization, audit failure rollback, historical score/alert/evidence
preservation, role/CSRF denial and actual history/currency boundaries. No new schema/role or
rule defaults are introduced. The timestamp underflow finding was fixed and verified.

Verdict: ship this independently verified checkpoint; do not claim Phase 7 complete.
Not checked yet: supervised attribution runtime, COMPLETE attribution behavior, final
Phase 7 hosted CI and the complete attribution-related review.

## Checkpoint changed files

- `.github/workflows/ci.yml`
- `Makefile`
- `backend/app/auth/body_limit.py`
- `backend/app/main.py`
- `backend/app/scoring/history.py`
- `backend/app/scoring/routes.py`
- `backend/app/scoring/config_routes.py`
- `backend/app/scoring/configuration.py`
- `backend/app/scoring/explanations.py`
- `backend/app/scoring/rules.py`
- `backend/tests/database/test_risk_configuration.py`
- `backend/tests/test_rule_parameters.py`
- `infra/scripts/check-ingestion.mjs`
- `infra/scripts/check-scoring-db.py`
- `infra/scripts/check-explanations.mjs`
- `verification/phase-7.md`

## Planned approved-dependency changes (not executed)

If the owner approves, add the five exact pins to `backend/requirements.in` and regenerate
`backend/requirements.txt` plus `backend/requirements-dev.txt` using pip-tools, binary-only
resolution and hashes. Preserve every existing runtime version, including sklearn 1.7.2,
NumPy 2.3.4, SciPy 1.16.3, joblib 1.5.2 and threadpoolctl 3.6.0. Review both complete lock
deltas and audit both resolved environments. No new hosted service is needed.

Existing artifact compatibility is expected, not yet runtime-proven with SHAP: the artifact
loader records exactly those five ML dependency versions, which will remain unchanged.
Neither the pickle class layout nor the feature schema/order will change. A previously
generated trusted bundle must load and produce identical component outputs after installation;
existing artifacts/historical scores must not be retrained or rewritten.

## Checkpoint publication hygiene

Pre-stage scan: 148 tracked/nonignored files and 213 reachable historical blobs plus
API/worker logs, no findings. Scope is known local secret values and common token/private-key
patterns, not exhaustive secret detection or SAST. No env files, private CSV/model bytes,
credentials, logs or resolved secret-bearing Compose files are included in this checkpoint.
All eleven approved document hashes match and all six main services remain healthy.
Origin is unchanged; main is still `f57eeae`. Checkpoint commit and hosted CI verification
will be recorded after publishing to `feat/phase-07-explainability`.

## Outstanding

Owner decision on the five packages, attribution computation/persistence and COMPLETE/PARTIAL
semantics, attribution integration tests, affected final regression targets, final Ponytail
Review, secret scan, verified commits/push, remote HEAD and hosted CI evidence. No Phase 7 completion
or production accuracy is claimed. No Phase 8, frontend, new tables or new roles.
