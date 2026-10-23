# Phase 5 verification: training, evaluation, versioning and activation

Updated: 2026-10-23. **Implementation verified locally; final publication/hosted CI pending.**
Branch: `feat/phase-05-ml-training`.
Base: `e231674d5e6fbaa8167d1d10a9c0c4d59d099f6d` (merged Phase 4).
Only Phase 5 is implemented. No merge, deployment or Phase 6 is authorized.

## Authority, resume and preservation

The owner's Phase 5 handoff and subsequent explicit five-package approval authorize this
work beyond the historical Phase 4 boundary in AGENTS.md. All eleven approved documents
and both installed Ponytail skills were read; approved documents and AGENTS.md are unchanged.
Phase 4 merge ancestry was verified before safely fast-forwarding main and creating this
branch. The data-preparation checkpoint was preserved, not recreated:

- `8ac7cace4470e626be4c3fa4b997612b63677295`: generator, trusted loader, temporal split/tests.
- `201e639a2f72dcd3f20c1c01c9458e47237b202a`: checkpoint report.
- [Checkpoint CI](https://github.com/axyz97836/SentinaAI/actions/runs/39777486158): success.

Existing credentials and volumes were preserved; main seed was not repeated. Real ML
integration used only the guarded `sentinelai-ingestion-tests` project, separate database,
networks/volumes and loopback API port 18004. Existing synthetic credentials were mounted
read-only to provision that disposable database; the harness verifies unchanged file bytes.
Main database: 18 domain tables. Initial migration remains `0001_initial_schema (head)`;
main Alembic comparison reports **No new upgrade operations detected**. No schema migration.
All six main services are healthy after refresh; liveness/readiness return alive/ready.
`shasum -a 256 -c verification/approved-documents.sha256`: **11/11 match**.

## Implemented features and API contracts

- Deterministic synthetic CSV generator with inspectable labels; strict private dataset
  loading rechecks org, TRAINING/VALIDATED, approved source, schema 1, server-derived key,
  byte count, SHA-256, original CSV rules, labels, unique IDs and persisted row count.
- At least 300 samples; each class at least max(30, floor(rows/100)); each chronological
  training class needs 20 examples and each validation/test class needs five.
- Training-only preprocessing, Logistic Regression and Isolation Forest; genuine held-out
  metrics, reproducible reference anomaly percentiles, versioned private artifact.
- `POST /api/v1/admin/models/train`: ADMIN + session/Origin/CSRF, bounded strict JSON,
  validated `training_dataset_id`; durable MODEL_TRAIN admission and documented 202 job ID.
- `GET /api/v1/admin/models`: ADMIN, org-scoped UUID cursor, max 100 results, measured metadata.
- `POST /api/v1/admin/models/{id}/activate`: ADMIN + CSRF; verifies trusted artifact first.
- `GET /api/v1/models/active`: all authenticated roles, organization-scoped metadata;
  409 ACTIVE_MODEL_REQUIRED when absent. No raw object keys, URLs or credentials returned.
- `/jobs/{id}` returns model_version_id and truthful TRAINING phase/output availability.
- Candidates never activate automatically. Organization row lock serializes activation;
  old-active clear, new-active set and audit event commit together. Existing partial unique
  index enforces one active model. Failed verification preserves the previous active model.
- Model metadata is immutable under the restricted application DB identity except approved
  activation columns. Old versions are retained. No operational scores, transactions,
  alerts, cases, frontend screens or Phase 7 rules/SHAP were added.

## Synthetic data, features and methodology

`python -m app.ml.synthetic --rows 2000 --seed 42` emits CSV on stdout and a synthetic
class-count summary on stderr. The actual default run yields **2,000 rows: 1,830 legitimate,
170 suspicious (8.5%)**. IDs/customer/device assignments are independent of the label;
labels are noisy Bernoulli draws from overlapping amount/category/channel/hour scenarios.
All references are fictional; no public or real customer dataset was downloaded.

Numeric features in fixed order: log1p(amount), sin/cos UTC hour, sin/cos weekday.
Categorical order: currency, country_code, channel, merchant_category. External/customer/
device IDs and fraud_label are excluded. Optional device absence therefore cannot change
predictions. No historical behavior or future transaction features are invented.

Rows are chronologically sorted and split approximately 60/20/20; equal timestamps stay
in the same partition. Inadequate temporal class balance fails explicitly. StandardScaler
and OneHotEncoder fit only training rows. Categorical encoding is bounded to 32 output
categories per field and ignores unseen categories. Both models are frozen before test
metrics are calculated; changing test labels/categories/amounts cannot change fitted
coefficients, reference distribution or selected threshold (regression tested).

Logistic Regression: lbfgs, class_weight=balanced, random_state=42, max_iter=1000, tol=1e-8;
convergence warnings fail training. Validation F1 selects one threshold from 0.05–0.95
in steps of 0.05, with highest threshold breaking ties. Final test data is not used for
selection. PR-AUC is trapezoidal area; average precision is separately named and measured.

Isolation Forest: 100 trees, max_samples=256, random_state=42, n_jobs=1, scaled numeric
features only. Sorted negative training score_samples form a 1,200-value reference;
percentile is the fraction of reference scores <= the new score, bounded [0,1]. It is
**not a fraud probability**. Test fixtures verify determinism and extreme-amount ordering.
Native BLAS/OpenMP threads are capped at one. Default composite weights 0.60/0.25/0.15
are frozen as approved metadata; Phase 5 does not calculate a composite operational score.

### Actual measured results from the real Celery integration run

| Partition | Rows | Legitimate | Suspicious | Event-time range (UTC) |
|---|---:|---:|---:|---|
| Train | 1200 | 1105 | 95 | Jan 1 00:09:08 – Jan 13 20:25:58, 2026 |
| Validation | 400 | 361 | 39 | Jan 13 20:39:05 – Jan 18 05:04:38, 2026 |
| Test | 400 | 364 | 36 | Jan 18 05:20:45 – Jan 22 15:41:10, 2026 |

| Metric | Held-out test | Validation |
|---|---:|---:|
| PR-AUC (trapezoidal) | 0.23596279185377103 | 0.326508639052296 |
| Average precision | 0.24144945965216705 | 0.3431842218832559 |
| Precision | 0.1896551724137931 | 0.3188405797101449 |
| Recall | 0.3055555555555556 | 0.5641025641025641 |
| F1 | 0.23404255319148937 | 0.4074074074074074 |
| Class prevalence | 0.09 | 0.0975 |
| Decision threshold | 0.70 | 0.70 |

Test confusion matrix `[[TN=317, FP=47], [FN=25, TP=11]]`.
Validation confusion matrix `[[314,47],[17,22]]`.
Anomaly reference min/max: 0.48807115590319644 / 0.6336154939399796.
These are actual synthetic results, not production fraud accuracy. Performance is limited;
only 36 positive test examples exist. Validation threshold selection can vary on other
samples. Balanced class weights do not establish probability calibration. Nominal amounts
are not FX converted; categories/scenarios are narrow, labels invented and history absent.

## Artifact integrity, provenance and serialization

Server-generated candidate UUIDs determine private organization/model keys. A bounded
16 MiB artifact contains a version-1 envelope, exact dependency versions, provenance,
feature schema/order, fitted pipelines, reference distribution, metrics and frozen weights.
Worker writes are read back and verified before candidate/job/audit records commit.

Loading requires a matching successful MODEL_TRAIN job, candidate ID, org, TRAINING dataset,
server-derived key and immutable model metadata. SHA-256, format, dependency versions,
feature schema and provenance are checked **before pickle deserialization**. Loaded bundle
identity, transformed feature names, finite sorted reference, metrics and weights must match.
No user-supplied artifact/path/import is accepted. Anonymous object access is denied in the
real integration test. Tampered/missing/untrusted/incompatible artifacts are rejected.

Python protocol-5 pickle retains the exact approved fitted sklearn pipelines without an
additional runtime format dependency or a second implementation of forest inference. It is
executable, not a sandbox or signature. Security depends on trusted worker production,
protected DB metadata and private storage; simultaneous compromise is not addressed.
Safer external formats would require an independently reviewed dependency/conversion path;
none was silently installed. Never expose this loader as an uploaded-model API.

## Durable jobs, retries and recovery

PostgreSQL owns job intent/status. Admission serializes on org: one pending training job,
three admissions per 15 minutes. These are bounded demo defaults, not capacity claims.
Celery `models.train_baseline` carries only job_id/training_dataset_id, with late ack,
worker-loss redelivery, 240/300-second soft/hard task limits and at most three started attempts.

The shared dedicated-connection advisory lock spans progress commits and prevents concurrent
processing of the same job. A candidate UUID is persisted at admission and reused on retry.
A row-locked terminal-state recheck immediately precedes object publication after CPU work.
Candidate creation, job SUCCEEDED/model link and MODEL_TRAINED audit commit atomically.
Ambiguous object writes reuse one candidate; final failures retain durable cleanup flags.
Invalid input fails permanently without rejecting/deleting the original validated dataset.

API lifespan recovery dispatches CSV and MODEL_TRAIN independently by type. Each training
pass scans at most 100 jobs; publication cooldown is normally 60 seconds within a 15-second
loop. Broker failure cannot lose admission. Storage retries back off; failed artifacts are
removed with retryable cleanup. Unexpected worker interruptions retain durable state and
are republished; exhaustion ends FAILED/RETRY_EXHAUSTED. Errors/logs are sanitized.

## Dependencies and audit evidence

The owner explicitly approved these exact versions; manifest comparison confirms no other
package version was added/changed. Runtime/development hash locks were regenerated with
pip-tools 7.6.2 and binary-only resolution; Docker installation requires hashes and wheels.

| Package | Installed version | Purpose | License / Python |
|---|---|---|---|
| scikit-learn | 1.7.2 | Approved estimators/preprocessing | BSD-3-Clause; >=3.10 |
| NumPy | 2.3.4 | Arrays/numerics | BSD core + bundled notices; >=3.11 |
| SciPy | 1.16.3 | Numerical solvers | BSD core + bundled notices; >=3.11 |
| joblib | 1.5.2 | sklearn execution support | BSD-3-Clause; >=3.9 |
| threadpoolctl | 3.6.0 | Native thread bounds | BSD-3-Clause; >=3.9 |

Installed NumPy/SciPy notices include OpenBLAS BSD-3-Clause, LAPACK BSD-3-Clause-Open-MPI,
GCC runtime GPL-3.0-or-later WITH GCC-exception-3.1 and libquadmath LGPL-2.1-or-later.
NumPy also records MIT, Zlib and Apache-2.0 bundled components. Wheel notices remain intact.
Python 3.12 runtime imports of FastAPI/Celery/sklearn/NumPy/SciPy passed; pip check passed in
both images. Complete runtime and development lock audits each returned **No known
vulnerabilities found**. This dated advisory check is not a security guarantee.

Executed commands (inside disposable Python 3.12 test image with mounted backend):

    pip-compile --generate-hashes --strip-extras --pip-args=--only-binary=:all: --output-file=requirements.txt requirements.in
    pip-compile --allow-unsafe --generate-hashes --strip-extras --pip-args=--only-binary=:all: --output-file=requirements-dev.txt requirements-dev.in
    pip-audit -r /work/requirements.txt --disable-pip --no-deps
    pip-audit -r /work/requirements-dev.txt --disable-pip --no-deps
    pip check

Sources: [sklearn persistence](https://scikit-learn.org/1.7/model_persistence.html),
[Isolation Forest](https://scikit-learn.org/1.7/modules/generated/sklearn.ensemble.IsolationForest.html),
[average precision](https://scikit-learn.org/1.7/modules/generated/sklearn.metrics.average_precision_score.html).
Exact version metadata was also inspected through PyPI's package/version JSON endpoints.

## Executed final verification

| Check | Actual local result |
|---|---|
| Focused ML unit suite | 12 passed, 3.54 s; included in backend total |
| `make database-check` | **272 passed**, 1 existing warning, 19.95 s |
| `make backend-check` | Ruff PASS, 54 formatted files, strict mypy PASS/34 modules; **128 passed**, 272 deselected, 4 existing warnings, 5.24 s |
| `make frontend-check` | ESLint, Next type generation, strict TypeScript, production build PASS |
| `make infra-check` | PASS, restricted DB/Redis/private S3/worker checks |
| `make outage-check` | PASS, controlled main DB/Redis/storage stop/recovery and port isolation |
| `make browser-check` | **8 passed**, 6.6 s, auth/logout CSRF, five widths, health links and a11y smoke |
| `make model-check` | **8 real integration checks passed**, repeated after publication-race fix |
| `make ingestion-check` | **9 real integration checks passed**; isolated resources removed |
| Main Alembic current/check | Initial head unchanged; no schema differences |
| Approved document hashes | 11/11 matched |
| Main services / health | Six healthy; liveness/readiness pass |

**Distinct automated application tests: 408 = 272 database + 128 backend + 8 browser.**
Focused tests overlap and are not added again. Integration check groups are separate.
The database suite includes 19 new model cases beyond the 253 existing schema/auth/ingestion
cases. Phase 5 adds 33 backend unit cases including the earlier data-preparation checkpoint.

Real model integration proves: authenticated upload -> VALIDATED -> real Celery MODEL_TRAIN
-> measured metrics/private verified artifact -> explicit activation -> active lookup;
no auto-activation, duplicate no-op, both non-admin denials, CSRF denial, broker outage/API
restart recovery, corrupt-candidate rejection preserving old-active, storage retry/recovery,
no raw fixture rows/credentials in logs, unchanged credential file and isolated teardown.
Database tests additionally prove cross-org isolation, concurrent admission/activation,
immutable metadata privileges, missing/untrusted/schema-invalid artifacts, interrupted
training recovery, exhausted retries, original-dataset preservation and ambiguous writes.

Ignored local logs under `.local/`: phase5-runtime-lock.log, phase5-dev-lock.log,
phase5-runtime-build.log, phase5-test-build.log, phase5-runtime-audit.log,
phase5-dev-audit.log, phase5-ml-focused.log, phase5-database.log,
phase5-database-final.log, phase5-backend.log, phase5-final-checks.log,
phase5-model-integration.log, phase5-model-final.log, phase5-stack-regression.log,
phase5-main-up.log, phase5-ingestion-final.log and phase5-marker-verification.log.
The last log confirms both integration modes passed with the workload-marker and
nonempty API/worker capture assertions. They are not public artifacts.

## Ponytail Review and fixes

What this change does: trains two synthetic-data baselines in durable jobs, saves verified
private candidates, and lets an ADMIN explicitly activate one model atomically.
Assumed load: documented local demo, one worker process/thread, concurrent requests and
duplicate deliveries. Review traced all new modules, auth/body limits, ORM constraints and
privileges, storage, worker/recovery, shared CSV lock callers, tests, harness, CI and README.

Resolved findings:

1. **Missing private-loader coverage:** added digest/size argument and row-count rejection
   tests without changing original dataset state. This was fixed in the preserved checkpoint.
2. **Late worker publication:** after long CPU work, stale local job state could allow a
   finalized job to write an artifact. Added row-lock/refresh before publication and terminal
   guards on failure handling. New regression proves no artifact after terminal transition;
   ambiguous PUT retry proves exactly one candidate object remains.
3. **Fixture used excessive privileges implicitly:** schema-tampering test tried to mutate
   immutable metadata through the app identity. The first database run had 269 passes and
   one permission failure. Only fixture sabotage now uses the guarded migrator; app privileges
   remain restricted. Final 272-case run passes.
4. **Integration startup lacked diagnostic evidence:** the first startup failed before any
   ML check, with generic Compose failure under the original three-minute command bound.
   Cause was not proven. Added ignored failure logs and a five-minute startup allowance;
   both subsequent real eight-check runs passed. No earlier startup was counted as a pass.
5. **Model log check used the ingestion fixture marker:** the shared harness originally
   searched for the Phase 4 marker even during generated model data tests. It now searches
   for the generator's fictional customer prefix in model mode, so raw model CSV rows
   would fail the log check. It also asserts that the exact marker occurs in uploaded
   customer data and that captured logs contain actual API requests and worker output.
   Both integration modes were rerun with these non-vacuous assertions.

Formatting findings were corrected before final checks. No material finding remains open.
**Verdict: local Phase 5 implementation is ready for hosted verification and owner review.**
Not checked: production scale/deployment, formal independent security audit, real-world
model performance/calibration, future scoring/SHAP/rule behavior or public-data licensing.

## Exact Phase 5 changed files (including preserved checkpoint)

- `.github/workflows/ci.yml`
- `Makefile`
- `README.md`
- `backend/Dockerfile`
- `backend/app/auth/body_limit.py`
- `backend/app/ingestion/processing.py`
- `backend/app/ingestion/routes.py`
- `backend/app/jobs.py`
- `backend/app/main.py`
- `backend/app/worker.py`
- `backend/app/ml/__init__.py`
- `backend/app/ml/data.py`
- `backend/app/ml/synthetic.py`
- `backend/app/ml/training.py`
- `backend/app/ml/artifacts.py`
- `backend/app/ml/service.py`
- `backend/app/ml/routes.py`
- `backend/app/ml/processing.py`
- `backend/pyproject.toml`
- `backend/requirements.in`
- `backend/requirements.txt`
- `backend/requirements-dev.txt`
- `backend/tests/test_synthetic_training.py`
- `backend/tests/test_training_data.py`
- `backend/tests/test_model_training.py`
- `backend/tests/database/test_ingestion.py`
- `backend/tests/database/test_models.py`
- `infra/scripts/check-ingestion.mjs`
- `infra/scripts/check-models.mjs`
- `infra/scripts/check-model-storage.py`
- `verification/phase-5.md`

## Secret hygiene, publication and remaining limits

Pre-stage scan: **128 tracked/nonignored files and 160 reachable historical blobs**, plus
main API/worker logs, no findings. It compares known local credentials and common token/
private-key patterns; not exhaustive detection/SAST. No generated CSV, model bundle,
credentials, private storage, logs or resolved secret-bearing Compose files are committed.

Exact origin: https://github.com/axyz97836/SentinaAI.
[Phase 5 branch](https://github.com/axyz97836/SentinaAI/tree/feat/phase-05-ml-training).
Implementation commit, remote ref and final hosted evidence will be recorded after execution.
No force push, merge or deployment. Sandbox-only tool access failures were resolved through
approved command execution; no Git authentication/synchronization error is known.

Recovery requires a running API; jobs are not immediately dispatched by the 202 response.
Exhausted jobs remain FAILED; no new retry endpoint. Failed-artifact cleanup retries after
storage recovery; successful-artifact retention/backup/expiry remains later operations work.
The generator cannot establish real-world generalization and syntactic CSV checks cannot
prove fictional provenance. Public datasets remain refused. Existing Starlette/httpx/Redis
warnings remain; no unrelated replacement dependency was added. Model-list pagination
uses immutable UUID order. Phase 6 must reuse verified active bundles consistently and add
prior-only behavioral features/scoring; this phase creates no operational risk scores.

Community source inspected: [Leakage in ML Pipelines: How to build a bulletproof preprocessing architecture](https://dev.to/pasquale_molinaro/leakage-in-ml-pipelines-how-to-build-a-bulletproof-preprocessing-architecture-1ip4)
by Pasquale Molinaro. Split-before-fitting supports this design; its production guarantee
is not adopted. No comments were returned and no extra framework was installed.
