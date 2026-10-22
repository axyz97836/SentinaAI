# Phase 5 verification: model training and activation

Updated: 2026-10-22. **IN PROGRESS. Only the data-preparation checkpoint is implemented.**
Branch: `feat/phase-05-ml-training`.
Base: `e231674d5e6fbaa8167d1d10a9c0c4d59d099f6d`, the merged Phase 4 main.

The owner's attached Phase 5 instruction explicitly authorizes this phase and supersedes
the historical Phase 4-only boundary. The root AGENTS.md and all eleven approved planning/
security documents remain unchanged. Phase 6, merging and deployment are not authorized.

## Repository and preservation

- Read the owner handoff, AGENTS.md, both installed Ponytail skills, all eleven approved
  documents, Phase 4 verification, and the existing ingestion/storage/worker/auth/schema code.
- Initial working tree was clean on `feat/phase-04-ingestion` at `af9e4d6`.
- Confirmed exact origin `https://github.com/axyz97836/SentinaAI` before fetching.
- `git fetch origin` succeeded. `git merge-base --is-ancestor af9e4d6 origin/main`
  succeeded; merge `e231674` includes Phase 4 implementation and verification commits.
- Safely fast-forwarded local main from `8cab9ff` and created the dedicated Phase 5 branch.
- All six existing Docker services were healthy. Main schema count: **18 domain tables**.
- Main `alembic current`: **0001_initial_schema (head)**; `alembic check`:
  **No new upgrade operations detected**. No migrations or schema edits made.
- Actual HTTP checks returned `{"status":"alive"}` and `{"status":"ready"}`.
- `shasum -a 256 -c verification/approved-documents.sha256`: **11/11 matched**.
- Credentials were not regenerated, database volumes were not reset, seed was not repeated.
- The sandbox initially blocked attachment access and installed Git/Perl tooling.
  Approved read/verification commands outside the sandbox succeeded. No Git synchronization
  or authentication error occurred.

## Implementation plan and scope

Anticipated additions under `backend/app/ml/`: synthetic generator, trusted data loading,
training/preprocessing, artifact verification, training service/worker processing and API
routes. Tests belong in `backend/tests/` and `backend/tests/database/`. Extend existing
`backend/app/worker.py`, API lifespan/router registration, job response metadata and bounded
JSON-body handling as required. Reuse Phase 4 durable recovery and private storage;
dispatch by job type, never send MODEL_TRAIN through ingestion.process_csv.

Add an isolated real training integration script under `infra/scripts/`, a Makefile
target and CI coverage, then document use in README. No frontend screens or schema edits.

Acceptance: deterministic synthetic inputs; chronological separation; training-fitted
preprocessing; actual held-out metrics; bounded anomaly percentiles; verified private
artifacts; ADMIN/CSRF/org enforcement; duplicate/retry/recovery safety; atomic activation
and old-active preservation; all requested regressions and hosted CI.

Security risks to test: label/time leakage, invalid evaluation, unsafe deserialization,
untrusted storage paths, resource exhaustion, duplicate candidate creation, loss of job
intent, cross-organization access and non-atomic activation.

## Completed checkpoint: synthetic data and trusted input validation

Exact added files:

- `backend/app/ml/__init__.py`
- `backend/app/ml/synthetic.py`
- `backend/app/ml/data.py`
- `backend/tests/test_synthetic_training.py`
- `backend/tests/test_training_data.py`
- `verification/phase-5.md`

The standard-library generator emits canonical UTF-8 CSV, 300–10,000 rows, default
2,000 rows and seed 42. It uses only fictional references and a fixed starting timestamp.
It varies amounts, merchant categories, countries, currencies, channels, time and optional
devices. Identifiers are shuffled independently of labels; no legitimate/fraud ID prefix.
Labels are Bernoulli draws using overlapping amount/category/channel/hour scenarios.
These are invented scenario labels, not actual fraud outcomes. Currency amounts are
fictional nominal values, not converted monetary equivalents. No behavioral history is
inferred from customer/device references.

CLI: `python -m app.ml.synthetic --rows 2000 --seed 42`; CSV goes to stdout and a clear
synthetic label/count summary goes to stderr. Save generated data only under ignored
local paths. Nothing generated is committed or ingested into the main stack here.
The CLI was executed in a disposable container: seed 42 produced **2,000 rows,
1,830 legitimate and 170 suspicious labels (8.5%)**, plus one CSV header. Its temporary
CSV disappeared with that container. These are class counts, not model evaluation metrics.

Trusted loading checks organization, TRAINING purpose, VALIDATED state, schema version 1,
server-derived key, size and approved provenance. Existing bounded storage reads verify
SHA-256 and byte count. Original CSV validation runs again; duplicate IDs, malformed rows,
unknown columns and invalid/missing labels are refused. Persisted row count must match.
Minimum 300 rows, both classes at least max(30, floor(rows / 100)).

Chronological split sorts by UTC event time, aims at 60% train / 20% validation / 20% test,
and keeps equal timestamps together. Each class needs at least 20 training examples and
five in each holdout. Inadequate temporal splits fail explicitly rather than silently
switching methodology. No transformer or model is fitted in this checkpoint.

## Dependency review and pending owner decision

Current runtime locks contain no scikit-learn/numerical stack. Proposed compatible set:

| Package | Version | Purpose / runtime dependencies | License |
|---|---|---|---|
| scikit-learn | 1.7.2 | Approved Logistic Regression, Isolation Forest, preprocessing; requires the four packages below | BSD-3-Clause |
| NumPy | 2.3.4 | Arrays and numerical operations; no Python runtime dependency | BSD, bundled numerical-library notices |
| SciPy | 1.16.3 | Numerical solvers; NumPy >=1.25.2,<2.6 | BSD, bundled numerical-library notices |
| joblib | 1.5.2 | Required scikit-learn execution support; no Python runtime dependency | BSD-3-Clause |
| threadpoolctl | 3.6.0 | Required scikit-learn native thread controls; no Python runtime dependency | BSD-3-Clause |

PyPI version metadata queried on 2026-10-22: all support Python 3.12 and supply compatible
wheels; each returned an empty vulnerabilities list. This is not a completed dependency
audit or guarantee. Sources: `https://pypi.org/pypi/{package}/{version}/json` for each row.
Latest releases were inspected too: scikit-learn 1.9.1 adds narwhals and joblib 1.6.0 adds
cloudpickle. The proposed compatible set avoids those additional runtime packages.

`pip-audit -r /tmp/proposed.txt --disable-pip --no-deps`, executed in the existing test
image with only the proposed five pinned versions mounted read-only, returned **No known
vulnerabilities found**. No packages were installed by this audit. Output is in ignored
`.local/phase5-proposed-ml-audit.log`. Full resolved/hash-locked audits remain necessary.

Owner approval was requested for supporting packages not individually named in the
planning documents. **No package installed and no dependency manifest/lock changed.**
After approval: regenerate hash-required runtime/development locks, run pip check and
pip-audit, inspect licenses/notices of actual resolved wheels, test both target platforms
through local Docker and hosted Linux CI. Audit failures must be resolved before publishing
the dependency checkpoint. Serialization choice remains to be implemented/reviewed;
no arbitrary pickle/joblib loading has been introduced.

## Executed checkpoint verification

- Existing test image, isolated `--network none`, runtime user, all capabilities dropped,
  backend mounted: Ruff check and format for new source/tests **PASS**.
- Focused pytest: **20 passed in 1.06 s** (4 generator + 16 trusted-input/split tests).
- Strict mypy over `app`: **PASS, 28 source files**.
- Editor diagnostics for added source/tests: no errors reported.
- Initial `make backend-check`: Ruff lint/format and strict mypy PASS;
  **115 passed, 253 database tests deselected, 4 existing warnings, 3.66 s**.
  A subsequent loader regression was added after this image's test copy.
  Final `make backend-check`: **116 passed, 253 deselected, 4 existing warnings, 4.28 s**;
  Ruff lint PASS, 46 files formatted, strict mypy PASS across 28 modules. This includes
  all **21 new checkpoint tests** and the previous 95 backend unit tests.
  Output saved to ignored `.local/phase5-backend-checkpoint.log`.
- Resume-requested focused rerun:
  `docker compose --env-file .env -f infra/compose.yaml --profile checks run --rm --no-deps backend-checks pytest -p no:cacheprovider tests/test_training_data.py tests/test_private_storage.py`
  — **25 passed in 1.84 s**, including missing/corrupted storage objects and loader
  size/digest arguments/row-count rejection. These overlap the 116 backend tests.

Tests exercise reproducibility, different seeds, canonical ingestion compatibility,
class overlap, sample limits, chronological boundaries, identical timestamps,
one-class holdout, missing/invalid labels, duplicate IDs, unsupported columns,
purpose/status/schema/key/size/organization/provenance rejection.

No model metrics, artifact equivalence, training API, Celery training job or activation
has been executed. The existing full regression workflow passed for this checkpoint
as detailed below; real ML integration and all affected regressions remain required
after the complete implementation. Main read-only health/schema checks above are
not substitutes for those tests.

## Review and publication

Ponytail checkpoint self-review traced generator -> canonical validation -> private
dataset loading -> temporal split. No new runtime dependency, table or API in this unit.
Checkpoint review added a missing loader test proving that the org/id/size/digest are
passed to private storage, persisted row-count mismatch is rejected, and the original
dataset remains VALIDATED after that failure. Whole-phase review remains outstanding.

Pre-commit secret scan covered **118 tracked/nonignored working files, 153 reachable
historical blobs**, and main API/worker logs: no findings. It compares known local
credential values and common GitHub/AWS/private-key patterns; it is not exhaustive
secret detection, SAST or evidence of absence of unknown credentials. No private data,
generated CSV/model object, credentials or logs are staged. Commit/ref verification
and hosted CI evidence follow below.
**Phase 5 is not complete or ready to merge.**

### Published checkpoint

Commit [8ac7cace4470e626be4c3fa4b997612b63677295](https://github.com/axyz97836/SentinaAI/commit/8ac7cace4470e626be4c3fa4b997612b63677295)
contains the completed data-preparation unit and its evidence. A second scan before push
covered **118 files and 159 reachable historical blobs**, plus main API/worker logs,
with no findings under the same limited detection method.

Pushed with `git push -u origin HEAD:refs/heads/feat/phase-05-ml-training`.
`git ls-remote origin refs/heads/feat/phase-05-ml-training` returned the exact commit above.
[Branch](https://github.com/axyz97836/SentinaAI/tree/feat/phase-05-ml-training).
[Checkpoint workflow](https://github.com/axyz97836/SentinaAI/actions/runs/39776428892)
finished **completed / success** for that exact SHA. Downloaded hosted logs confirm:

| Hosted check | Actual result |
|---|---|
| `make database-check` | **253 passed**, 1 existing warning, 16.68 s |
| `make backend-check` | Ruff lint/format and strict mypy PASS; **116 passed**, 253 deselected, 4 existing warnings, 5.15 s |
| `make frontend-check` | PASS |
| `make infra-check` | PASS |
| `make outage-check` | PASS |
| `make ingestion-check` | **9 integration checks passed**, isolated resources removed |
| Browser `npm test` | **8 passed**, 5.4 s |
| Frontend dependency audit | PASS |

Total distinct automated application tests: **377 = 253 database + 116 backend + 8 browser**.
Focused tests overlap these totals and are not counted again. Logs were retrieved using
the existing macOS Git credential manager with credentials held only in process memory;
no token was requested, printed or saved. The downloaded archive is ignored local evidence.

The follow-up report-only commit records this checkpoint's hosted results. Its exact
remote hash and final workflow outcome are verified separately in the completion response
to avoid a self-referencing report commit. No application/test changes followed the
successful checkpoint workflow.
No force push, merge, deployment, authentication error or synchronization conflict occurred.

Community source inspected: Pasquale Molinaro,
[Leakage in ML Pipelines: How to build a bulletproof preprocessing architecture](https://dev.to/pasquale_molinaro/leakage-in-ml-pipelines-how-to-build-a-bulletproof-preprocessing-architecture-1ip4).
Useful point: split before fitting transformations. Its production-performance guarantee
is not adopted; leakage prevention does not establish generalization. No comments were
returned. No SMOTE, imbalanced-learn or other suggested extra framework was added.

## Resume next

Inspect current branch/status and this report first. Preserve completed data-preparation
code and tests. Resolve the pending package decision, then implement preprocessing/models,
artifact provenance/integrity, durable MODEL_TRAIN jobs and model management APIs.
Complete all requested integration, negative/concurrency tests, regression checks, review,
secret hygiene, verified commits/pushes and hosted CI. Do not start Phase 6.
