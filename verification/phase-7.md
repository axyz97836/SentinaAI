# Phase 7 verification: rules, explanations and risk configuration

Updated: 2026-10-28. **Final implementation, approved dependency remediation, local regression
and Ponytail Review pass. Phase 7 awaits publication and final hosted ARM64 CI verification.
The earlier hosted checkpoint does not cover these uncommitted changes.**
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

## Dependency review before approval (historical checkpoint)

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

## Dependency plan at the earlier checkpoint

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
Origin is unchanged; main is still `f57eeae`.

Checkpoint implementation:
[e194ba144dcc3c7a5e5410be633f80182fd91468](https://github.com/axyz97836/SentinaAI/commit/e194ba144dcc3c7a5e5410be633f80182fd91468).
Pushed with explicit `HEAD:refs/heads/feat/phase-07-explainability`; `git ls-remote`
verified the exact same SHA. The working tree was clean after publication.
[Hosted checkpoint workflow](https://github.com/axyz97836/SentinaAI/actions/runs/40218856634)
finished completed/success. No Git authentication/synchronization error occurred.
This is a verified checkpoint, not final Phase 7 completion. This report-only follow-up
does not change application code or tests; its remote commit/workflow is checked separately.

Community cross-check: [Shapley Addictive Explanation](https://dev.to/saksham780/shapley-addictive-explanation-1i3e)
by [@saksham780](https://dev.to/saksham780) distinguishes raw log-odds attribution from
probability and cautions that reference data matters. No comments were returned. The primary
SHAP documentation and future numerical/runtime tests govern the implementation; this
introductory article is not evidence that our pending SHAP functionality works.

## Outstanding at the earlier checkpoint

Owner decision on the five packages, attribution computation/persistence and COMPLETE/PARTIAL
semantics, attribution integration tests, affected final regression targets, final Ponytail
Review, secret scan, verified commits/push, remote HEAD and hosted CI evidence. No Phase 7 completion
or production accuracy is claimed. No Phase 8, frontend, new tables or new roles.

## 2026-10-26 approved installation and critical stop

This section supersedes the earlier pending-approval/install status above. The owner explicitly
approved shap 0.54.1, pandas 3.1.0, tqdm 4.70.1, slicer 0.0.8 and cloudpickle 3.1.2. Their pins
were added to requirements.in and both hash locks regenerated. Comparison confirms exactly
those five additions, with no removals or version changes: all 53 existing runtime pins and
98 development pins remain unchanged. Temporary constraint references were removed only
from generated comments. Installation in backend/.venv succeeded through the Python
environment tool using `--require-hashes --only-binary=:all: -r requirements-dev.txt`.
The venv previously contained build tooling only, so the existing locked stack was installed
alongside the approved additions. The pre-existing report-only edit remains preserved.

Read-only main database inspection found zero model versions and zero active models. A
protected compatibility fixture was serialized once with the pre-installation Linux/Docker
runtime and the existing deterministic baseline test generator. Files remain ignored under
`.local/phase7-compat/` with restrictive permissions. No existing development model was
retrained, and no historical model artifact or scoring record was rewritten.

Critical command:

    PYTHONPATH=<repo>/backend backend/.venv/bin/python .local/phase7-check-compat.py .local/phase7-compat

**FAILED, exit 1.** Imports and verified deserialization completed. Supervised outputs passed
the `rtol=1e-12, atol=1e-12` comparison. Exact anomaly percentiles differed for **1 of 2,000
rows**, maximum absolute delta **0.0008333333 (1/1200)**. This is a Linux/Docker-to-macOS
comparison; the cause has not been isolated. It is not yet evidence that SHAP itself changes
inference, and the discrepancy has not been accepted as harmless. No tolerance was relaxed.

The failure precedes explainer construction and generation/additivity assertions, so genuine
SHAP generation has **not** been verified. The new attribution module and scoring integration
are saved but unverified. Per the owner's explicit critical-failure stop instruction, work
stopped; only this failure record was updated. No new commit or push was made.

Evidence: `.local/phase7-native-compat.log`, `.local/phase7-runtime-lock.log`,
`.local/phase7-dev-lock.log`. Existing passing checkpoint evidence applies to e194ba1 only,
not these uncommitted additions. Compatibility investigation, attribution/COMPLETE/PARTIAL
tests, full regression/security checks, final review and publication remain outstanding.

## 2026-10-27 focused compatibility investigation

### Build and environment recovery

The requested `.local/phase7-compat-image.log` contains no failed Docker build. It records
successful hash-verified installation of exactly the five approved packages, layer export,
tagging and unpacking. The resulting image exists and executed the trace successfully.
No Dockerfile or approved dependency version needed a build repair; the completed image
was reused instead of rebuilding it.

- Original Linux comparison image: `sha256:86248781742106b70d5a4bd25ff7f1f584655b0e111ee8c7a8ba71e0c36c5b33`.
- Linux image with approved additions: `sha256:96417effe0ef0b07339fab7c7538ce9aba725e3ce8216fc0373e9a0a7e132313`.
- Original image has none of shap/pandas/tqdm/slicer/cloudpickle; the second has exactly
  the approved versions. Both retain NumPy 2.3.4, sklearn 1.7.2 and SciPy 1.16.3.

The separate `.local/phase7-macos-baseline` initially failed before comparison with
`ModuleNotFoundError: numpy`, despite the environment package tool's success message.
It was populated through that environment's explicit interpreter using the original
e194ba1 runtime lock with `--require-hashes --only-binary=:all:`. The main venv was not
uninstalled or downgraded. The completed baseline confirms all five additions absent,
while the primary venv retains all five approved versions. The primary project interpreter
was restored after setup. This was an isolated comparison-environment repair, not a model fix.

### Fixed inputs and controlled matrix

No fitting/training command ran during this focused investigation. All controls read the
same pre-existing serialized fixture and CSV; each verifies their hashes and leaves bytes unchanged.

- Artifact SHA-256: `82c1111a189286e53ec6e78e877c28469b2e4d79ca81864c5e96a31cfe2074ce`.
- CSV SHA-256: `709d1095cde9ec483ae90ecfefc7fcd93ff8e618f3323fa0da71c24cd49fd678`.
- Stored reference-array SHA-256: `d04947918bc2db60a59b2817c50bc46a37da9e699b97af5148af9b2663a099c4`.
- Forest: seed 42, 100 trees, max_samples 256, n_jobs 1; immutable 1,200-score reference.
- Installed sklearn IsolationForest Python source SHA-256 matches in both operating systems:
  `2d61f09b0ebba2a1ce36d5955cb49678e46adbba5d56e40a8f24f9ce784f9a85`.

| Environment | Runtime | Percentile mismatches against frozen Linux fixture | Within-platform dependency comparison |
|---|---|---:|---|
| Linux original dependencies | Python 3.12.15, Linux/glibc 2.36, aarch64 | 0 / 2000 | Baseline |
| Linux approved additions | Same Python/OS/architecture | 0 / 2000 | Every captured array exactly equal |
| macOS original dependencies, five additions absent | Python 3.12.6, macOS 26.6.2, arm64 | 1 / 2000 | Baseline |
| macOS approved additions | Same Python/OS/architecture | 1 / 2000 | Every captured array exactly equal |
| macOS approved, Docker thread settings | OMP/OPENBLAS/MKL_NUM_THREADS all 1 | 1 / 2000 | Same mismatch; threading does not remove it |

Both architectures are ARM64; this is not an x86-versus-ARM comparison. NumPy links
OpenBLAS 0.3.30 on Linux and Accelerate on macOS. Native default OpenMP reported eight
threads versus one in Docker; matching the thread limits changed none of the findings.
The isolated scalar C-library power reproduction below does not invoke BLAS or a model.

An additional import-side-effect control explicitly imports shap, pandas, tqdm, slicer and
cloudpickle before inference on both approved environments. The `linux-approved-imported`
and `macos-approved-imported` traces are each exactly equal, across every captured array,
to their respective original-dependency baseline. This verifies more than installed-package
metadata: importing the additions also leaves the observed inference results unchanged.

### Exact failing row and numerical cause

Data row **25** (header excluded) is identified without publishing customer/device references.
Its canonical payload hash is `fda25d39e710e315f2ef11b22e60a64181326723632785fabcc33a7e710fdfd6`;
the original full row remains only in the protected unchanged CSV. Input, feature and ranking
evidence is saved privately in `.local/phase7-anomaly-investigation/`.

Row 25 numerical features (log_amount, hour_sin, hour_cos, weekday_sin, weekday_cos):

    [4.647079589065301, 0.9411760152563707, -0.3379167180033268,
     0.43388373911755823, -0.900968867902419]

Scaled values, identical for this row in every environment:

    [0.40454918157697173, 1.3040534608997065, -0.48511731331788654,
     0.7761373756647656, -1.2360158087460535]

Across all 2,000 rows, cross-platform float64 feature/scaler values have tiny differences
(231 raw numeric entries and 167 scaled entries, maximum 8.881784197001252e-16), but the
forest's float32 input is **exactly identical for all 10,000 entries**. All 200,000 leaf
indices, all per-tree depth terms, all summed depths and all score exponents are identical.
Thus those earlier feature differences cannot explain this anomaly mismatch.

For row 25:

- Depth sum: `1035.8774783053657`.
- Denominator: `1024.4770920119918` (`0x1.001e88acef2c0p+10`).
- Identical exponent: `-1.0111280050889029` (`-0x1.02d948f1ed330p+0`).
- sklearn computes the positive anomaly score as `2 ** exponent`.

| Result | Linux | macOS |
|---|---:|---:|
| Raw positive anomaly score | 0.4961581630788771 | 0.49615816307887706 |
| Float64 hexadecimal | `0x1.fc10e2b044d33p-2` | `0x1.fc10e2b044d32p-2` |
| Left rank in stored reference | 50 | 50 |
| Right rank in stored reference | 51 | 50 |
| Percentile | 51/1200 = 0.0425 | 50/1200 = 0.041666666666666664 |

The score delta is **one ULP, 5.551115123125783e-17**. Stored reference index 50 equals
the Linux score exactly; neighboring values are 0.4961343232399823 and 0.4961828785939972.
The macOS result falls immediately below the frozen tie. Exact `searchsorted(side="right")`
therefore loses one counted value. The rank implementation is behaving according to its
existing contract; it is not a change in tie-side selection, reference bytes or serialization.

Replaying the exact saved exponent vector, without feature processing or model inference,
reproduces the one difference using NumPy power, Python scalar power and math.pow. Direct
ctypes calls to Linux `libm.so.6` versus macOS `/usr/lib/libm.dylib` reproduce the respective
hex values. This isolates the cause to **platform math-library power rounding**, subsequently
amplified by the exact empirical-CDF boundary. It is not caused by the five approved additions.

Independent standard-library Decimal ln/exp evaluation at 80, 160 and 240 digits consistently
rounds this exponent's result to the lower/macOS float. Its distance is about 2.7707564e-17
versus 2.7803587e-17 to the Linux float. This diagnostic does not authorize replacing the
approved Linux output or changing a golden fixture. Replacing pow with exp2 also does not
preserve parity: macOS exp2 differs from the Linux vector at five entries, including row 25.

### Observed decision and persistence impact

- Linux original versus Linux approved: raw scores, classifier outputs, percentiles, features
  and all captured intermediates are bit-for-bit identical.
- macOS original versus macOS approved: the same full-array exact equality holds.
- Cross-platform classifier differences max at 2.220446049250313e-16; all stored six-place
  supervised components are identical. Row 25 supervised value is 0.46843808936469866.
- The six-place stored anomaly component would differ for one row: **0.042500 vs 0.041667**.
- With rule signal 0, row 25 remains risk 29 / LOW / no alert at 70 on both platforms.
  With rule signal 1, it remains risk 44 / MEDIUM / no alert at 70 on both platforms.
- Evaluating both supported binary rule-signal values across all 2,000 rows yields **zero
  integer risk-score differences**, hence zero band/alert differences for any unchanged
  integer threshold configuration in this fixture. This is not a guarantee for future inputs.
- The investigation performs no database writes. No existing persisted result was changed;
  the differing component above describes what a new native score would persist.

### Reproduction and remaining decision

The reusable ignored scripts are `.local/phase7-trace-anomaly.py`, `phase7-compare-traces.py`,
`phase7-trace-power.py` and `phase7-power-rounding.py`. The trace takes fixture directory,
output directory and environment label. Run it with the original image ID, the approved
comparison image, `.local/phase7-macos-baseline/bin/python`, and `backend/.venv/bin/python`.
Native runs set `PYTHONPATH=<repo>/backend`; container runs set `PYTHONPATH=/app` and mount
the ignored evidence directory at `/evidence`. The single-thread control sets all three
OMP/OPENBLAS/MKL thread environment variables to 1 before Python starts.

Evidence files include the four `<environment>.json/.npz` traces, the threads1 trace,
`trace-comparison.json`, both `*-power.json` and `*-rounding.json` records and
`persisted-impact.json`. The latter contains no customer/device identifiers. Fixture hashes
and original exact compatibility assertions are unchanged; no tolerance or golden was altered.

**Dependency compatibility is established within each platform. Exact cross-platform
artifact-output portability is not established and the original native assertion still fails.**
There is no demonstrated numeric/ranking code change that both removes the mismatch and
preserves the frozen behavior of both platforms. Rounding scores, adding approximate ties,
rebuilding references or switching power algorithms would be behavioral changes.

Recommended owner decision: retain the existing exact score/rank algorithm and designate the
matching pinned artifact-producing Docker runtime (including architecture) as authoritative
for operational scoring and its golden checks. Native macOS can retain approved dependencies
for tooling/attribution checks, with this portability limit explicit. If identical operational
native scoring is mandatory, a separately approved versioned numeric/reference policy is
needed; it must not rewrite historical results or artifacts.

Work stops for that runtime/behavior decision rather than silently accepting the component
change. SHAP generation, full Phase 7 regression and publication remain pending. No commit,
push, reset, retraining, model/artifact rewrite or application numerical change occurred in
this focused investigation; e194ba1 remains the last verified published checkpoint.

## Approved ARM64 implementation and verification (2026-10-27)

The owner explicitly approved the matching pinned Linux ARM64 artifact-producing environment
as authoritative. This supersedes the earlier runtime-policy stop above. No scoring formula,
anomaly power calculation, percentile tie rule, stored reference or golden assertion changed.
The previous investigation and native mismatch remain documented rather than suppressed.

### Runtime identity and enforcement

The comparison image was inspected as Linux/arm64 with local image reference
`sha256:96417effe0ef0b07339fab7c7538ce9aba725e3ce8216fc0373e9a0a7e132313` and local tag
`sentinelai-phase7-compat-approved:latest`. Docker also reports that digest associated with
the local repository name. This is **not evidence of a published Docker Hub registry image**;
the local comparison image must not be treated as a public pullable base dependency.

Reproducible application builds retain the existing public Python base index digest:
`docker.io/library/python@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258`.
The registry manifest was read: its linux/arm64/v8 child digest is
`sha256:739ba32ae445e8d58f3d90feb85f83bebc8346f8dd280fa1eb5848f4ff1ed163`.
API, worker, migration and backend test services now explicitly select `linux/arm64`.
Hosted CI is configured for the documented `ubuntu-24.04-arm` runner; this updated workflow
has not been published or run yet. Source/lock changes naturally produce new local image IDs.

`make model-runtime-check` passed for both rebuilt operational API and worker:
Python 3.12.15, Linux/aarch64, glibc 2.36, OMP/OPENBLAS/MKL thread limits 1, exact approved
ML/SHAP versions and the original Linux power-boundary result. Operational model selection
and training fail closed with MODEL_RUNTIME_UNSUPPORTED outside this boundary. Historical
reads/replay do not recalculate scores. The check is not cryptographic container attestation;
the pinned base, hash locks, image inspection and compatibility tests establish the recipe.

### Genuine SHAP and unchanged artifact results

The original compatibility script ran in the exact approved comparison image with current
application source mounted read-only. **2,000 rows passed**: supervised maximum absolute delta
0.0, exact anomaly percentiles, unchanged artifact bytes, actual SHAP generation and additive
reconciliation. The reference has 1,200 training rows and 19 transformed features. No existing
model was retrained. `.local/phase7-arm64-shap-compat.log` records the completed result.

SHAP LinearExplainer uses an Independent masker containing the exact transformed training-fold
mean. It reports classifier log odds, base value, at most five nonzero signed features with
original transformed names and readable fitted labels, and the omitted contribution sum.
Additivity checks retain relative/absolute 1e-10; the displayed sum check retains absolute
1e-10. The classifier probability reconciliation retains relative 1e-9 / absolute 1e-12.
Anomaly mathematics/reference ranking and composite rounding are unchanged.

The same scoring transaction persists attribution. COMPLETE requires valid attribution and
known evaluated/disabled states for all three rules. Missing rules/history, unsupported
parameters, missing optional training background or explainer failure produce explicit PARTIAL
evidence. Mandatory artifact verification remains a hard failure. Old Phase 6 insertion shapes
are tested without rewriting any persisted row; GET remains read-only and never invokes SHAP.

### Completed local checks for the current implementation

| Check | Actual result |
|---|---|
| Preserved Docker artifact and SHAP check | 2,000 rows PASS; exact inference/reference compatibility; bytes unchanged |
| Focused SHAP/model/scoring tests | 68 passed, 3.12 s; overlaps backend total |
| `make database-check` final | **322 passed**, one existing warning, 42.16 s |
| `make backend-check` final | Ruff/format PASS; mypy PASS/47 modules; **217 passed**, 322 deselected, four existing warnings, 7.58 s |
| `make model-runtime-check` | API and worker approved fingerprints PASS |
| `make frontend-check` | Lint, types, production build PASS |
| `make infra-check` / `make outage-check` | Restricted dependencies and all controlled recovery checks PASS |
| `make browser-check` | **8 passed**, 7.7 s |
| `make explanation-check` | **7 genuine integration checks passed**, including SHAP/COMPLETE and CSV persistence |
| `make ingestion-check` | **9 integration checks passed** |
| `make model-check` | **8 integration checks passed** |
| `make scoring-check` | **9 integration checks passed**, 805 transaction/score/alert/audit rows and 803 labels reconciled |
| Full runtime-lock audit | No known vulnerabilities found |
| Full development-lock audit | **FAILED: seven advisories in two pre-existing packages**, below |

**547 distinct automated application tests = 322 database + 217 backend + 8 browser.**
Focused runs and prior 320-case DB run are not counted again. The final two DB cases exercise
CSV and model-worker refusal outside the authoritative runtime. Integration projects were
removed by their harnesses; existing credentials and main volumes/data are preserved.

Ruff preflight found import order, line length and an empty optional-fallback branch; these
were corrected without changing scoring mathematics. Mypy then reported only SHAP's missing
stubs/py.typed marker. A scoped import override matching the existing sklearn treatment fixed
that integration issue; strict checking of application code remains enabled. No new stubs
dependency or numerical assertion waiver was introduced.

### Security gate failure and stop

The Docker audit initially hit PyPI TLS/read timeouts. Those runs are **incomplete**, not
vulnerability passes. The runtime-lock retry completed successfully. A native metadata-only
development-lock scan with a persistent cache completed and returned exit 1:

| Pre-existing development package | Advisory IDs | Reported fixed version |
|---|---|---|
| filelock 4.2.0 (via cachecontrol) | CVE-2026-112906, CVE-2026-112940, CVE-2026-112914, CVE-2026-112913, CVE-2026-112937, CVE-2026-112907 | 4.2.1 |
| setuptools 84.0.0 (via pip-tools) | GHSA-xmj3-9gf7-h52w | 84.1.0 |

Both versions are confirmed in published checkpoint e194ba1; neither was added/upgraded by
the five-package SHAP change. The filelock advisories concern local shared-directory lock,
symlink/path and cleanup races (platform-specific conditions vary). The setuptools advisory
concerns its legacy Windows wheel-installation path and attacker-controlled namespace metadata.
These are reported dependency vulnerabilities, **not a demonstrated exploit of SentinelAI**.
They still fail the requested full development dependency security gate; no waiver was assumed.

Advisory details were cross-checked through the versioned PyPI JSON metadata. Examples:
[filelock GHSA-2g95-wg33-c5x2](https://osv.dev/vulnerability/GHSA-2g95-wg33-c5x2),
[setuptools GHSA-xmj3-9gf7-h52w](https://osv.dev/vulnerability/GHSA-xmj3-9gf7-h52w).

Per the owner's failure policy, further implementation/publication stopped. Already-running
isolated verification completed and cleaned up; no new model behavior change or dependency
upgrade was made in response. Proposed minimum remediation, **not applied**: approve
development-only filelock 4.2.1 and setuptools 84.1.0, verify resolution/licenses, regenerate
the development hash lock while retaining all runtime/ML pins, then rerun the complete audit
and affected checks. No unverified changes have been committed or pushed.

Evidence: `.local/phase7-attribution-types.log` (initial typing failure),
`phase7-attribution-types-fixed.log`, `phase7-shap-focused.log`, `phase7-shap-database.log`,
`phase7-database-final.log`, `phase7-backend-final.log`, `phase7-final-up.log`,
`phase7-operational-runtime.log`, `phase7-stack-final.log`,
`phase7-genuine-explanation-integration.log`, `phase7-pipelines-final.log`,
`phase7-runtime-audit-final.log` (network failure), `phase7-runtime-audit-retry.log` (pass),
`phase7-dev-audit-retry.log` (network failure), `phase7-dev-audit-native.log` (seven findings).

The current attribution/runtime changes remain uncommitted. The last verified published
checkpoint is e194ba1. Final security remediation, complete Ponytail sign-off, final secret
scan, checkpoint publication and updated hosted ARM64 CI are still required for Phase 7
completion. The earlier hosted checkpoint CI must not be represented as verifying these
new uncommitted changes.

## Approved development security remediation (2026-10-27)

The owner explicitly approved only filelock 4.2.0 → 4.2.1 and setuptools 84.0.0 → 84.1.0.
Both are development-only: filelock is required through cachecontrol/pip-audit and setuptools
through pip-tools. Neither is in `backend/requirements.in` or `backend/requirements.txt`.
Explicit pins were added to `backend/requirements-dev.in`; only their package/version/hash
blocks changed in `backend/requirements-dev.txt` relative to the saved pre-remediation lock.
All other **101 development package blocks** retain their exact versions and hashes. The
runtime lock is byte-identical to its pre-remediation snapshot; the five approved SHAP pins,
original ML dependencies, Docker base, artifact bytes and numerical code are unchanged.

Official versioned PyPI metadata reports both packages as MIT, with Python >=3.11 for
[filelock 4.2.1](https://pypi.org/project/filelock/4.2.1/) and >=3.10 for
[setuptools 84.1.0](https://pypi.org/project/setuptools/84.1.0/). Both support Python 3.12.
Neither requires an additional package for the selected installation (setuptools optional
test/doc/core extras are not selected). No additional dependency approval is needed.
The binary-only lock records their universal wheel SHA-256 values:

- filelock: `7be2662e9e826b9bba28afc0f843a123280d799a2ea44bb5d35ccec67905ae44`
- setuptools: `5231689c6ac8156cd155cfb98c3fd6fb252c3e7e9bd3d78b64d3c55f132624c9`

Executed from `backend/`:

```sh
.venv/bin/python -m piptools compile --allow-unsafe --generate-hashes --strip-extras \
  --pip-args=--only-binary=:all: \
  --constraint=../.local/phase7-security-preserved-pins.txt \
  --output-file=requirements-dev.txt requirements-dev.in
```

The ignored constraints freeze the other 101 current packages. Temporary constraint-path
comments were removed from the generated lock; no package data was altered. A parser compared
all package/version/hash blocks and asserted exactly the two approved changes, no additions
or removals, and a byte-identical runtime lock. An initial shell-quoting error in the local
constraint-generation command made no dependency change and was corrected before compilation.

The project virtual environment installed the complete lock with `--require-hashes
--only-binary=:all:`. `backend/.venv/bin/python -m pip check` reports **No broken requirements
found**. Installed metadata confirms the two approved versions and unchanged ML/SHAP versions.
The complete metadata-only advisory command completed with exit 0:

```sh
backend/.venv/bin/python -m pip_audit -r backend/requirements-dev.txt \
  --disable-pip --no-deps --cache-dir .local/phase7-audit-cache --timeout 45
```

Result: **No known vulnerabilities found**, covering all 103 locked development packages,
including the runtime subset. All seven earlier findings are cleared without ignoring any
advisory. This is a dated dependency audit, not a guarantee against unknown vulnerabilities.
Evidence: `.local/phase7-security-lock-compile.log`, `phase7-security-dev-audit.log`, and the
ignored before/after lock snapshots. Remaining application/build/CI checks are recorded below
only after they complete.

## Final local verification after security updates (2026-10-28)

The interrupted `make backend-check` was confirmed **failed**, not still running. Its
`backend/Dockerfile:19` hash-verified development install timed out at `files.pythonhosted.org`
while downloading the unchanged mypy 2.4.0 ARM64 wheel (3.7/14.5 MB); pip exited 2 at 832.6 s.
This was a network/download failure before application checks. The exact same `make
backend-check` retry succeeded without any Dockerfile, package, hash, network-security or
test-assertion change. The rebuilt local test image is Linux/ARM64,
`sha256:17a7e0fc27664a6cd702581c4befce90c8e9137750057a3dfd3b7df5df4bffc4`.
This is a local image identity, not a published registry digest.

| Final check | Completed result |
|---|---|
| `make backend-check` | Ruff PASS; **73 files** formatted; strict mypy **47 modules** PASS; **217 passed**, 322 deselected, four existing warnings, 6.64 s |
| `make database-check` | **322 passed**, one existing warning, 50.25 s; disposable DB/Redis/network removed |
| Frozen 2,000-row artifact/SHAP check in rebuilt image | Supervised max absolute delta **0.0**; anomaly percentiles exact; artifact bytes unchanged; genuine SHAP additivity PASS |
| Rebuilt image `python -m pip check` | No broken requirements found |
| Rebuilt image `python -m app.ml.runtime` | Approved Linux/aarch64, Python 3.12.15, glibc 2.36, all ten ML/SHAP pins, three thread limits and power probe PASS |
| `make explanation-check` | **7 integration checks passed**, isolated resources removed |
| `make model-runtime-check infra-check` | API/worker fingerprints and all five infrastructure groups PASS |
| Main `alembic current` / `alembic check` / read-only table inspection | `0001_initial_schema (head)`, no new upgrade operations, **18 domain tables** |
| `npm audit --audit-level=high` | **0 vulnerabilities**, exit 0 |
| Full 103-package development lock audit | **No known vulnerabilities**, exit 0; runtime subset included |
| Approved document SHA-256 verification | **11/11 unchanged** |

Frozen compatibility invocation (no network and read-only evidence):

```sh
docker run --rm --platform linux/arm64 --network none \
  --user "$(id -u):$(id -g)" -e PYTHONPATH=/app \
  -v "$PWD/.local:/evidence:ro" sentinelai-backend-checks \
  python /evidence/phase7-check-compat.py /evidence/phase7-compat
```

The first invocation omitted `PYTHONPATH=/app`, so the external script could not import `app`
and exited before loading artifacts. Correcting only the invocation resolved it; the original
script, fixtures and assertions remain unchanged. The successful check used the original
1,200-row training-fold background and 19 transformed features, and verified actual SHAP on
all 2,000 rows. No model was refitted for compatibility and no historical artifact was changed.

Previously completed frontend build/lint/types, eight browser tests, all eight outage groups,
9 ingestion + 8 model + 9 scoring integration groups remain applicable: their application code,
runtime lock, fixtures and harnesses did not change during the development security updates.
These results are reused explicitly, not represented as new executions. Hosted CI will rerun
the complete workflow against the published tree. The genuine explanation integration was
rerun and again covers real worker training in its disposable synthetic fixture only; it does
not retrain or overwrite any existing/main model.

Final distinct local application count remains **547 passed, 0 failed = 322 database +
217 backend + 8 browser**. Focused runs and repeated suites are not additional tests.
Integration groups are reported separately. Existing Starlette/httpx and Redis deprecation
warnings are unchanged; no unapproved replacement dependency was installed.

Evidence: `.local/phase7-security-backend.log` (failed download),
`phase7-security-backend-retry.log`, `phase7-security-database.log`,
`phase7-security-arm64-compat.log` (invocation error),
`phase7-security-arm64-compat-retry.log` (pass), `phase7-security-explanation.log`,
`phase7-security-runtime-infra.log`, `phase7-security-dev-audit.log`,
`phase7-final-npm-audit.log`, and `phase7-security-secrets.log`.

## Final Ponytail Review

What this change does: generates real supervised SHAP contributions in log-odds units and
persists them atomically with each new score. It enforces the approved Linux ARM64 runtime,
retains immutable historical evidence, and fixes the two approved development advisories.

Looks good. Ship the verified checkpoint. Review traced the complete Phase 7 diff and connected
rule validators/history, ADMIN routes/service, authentication/CSRF/body limits, org-scoped
artifact provenance and private dataset checks, direct/CSV scoring, job recovery, model
activation, explanation reads, tests, Make/Compose/CI and README. Expected load remains the
documented bounded demo with one worker and serialized scoring per organization.

The reference is revalidated against private dataset hashes and trusted artifact provenance;
only the chronological training fold contributes to its mean. SHAP shape/order/finite-value,
log-odds additivity and probability reconciliation failures produce explicit PARTIAL evidence.
They cannot bypass mandatory artifact checks or change the score. Tests cover real attribution,
missing background/constructor/generation failures, replay, old evidence, concurrent duplicate
requests, unsupported runtime, org denial and atomic rollback. Configuration concurrency,
optimistic versions and atomic audit remain covered. No material finding remains open.

Verdict: Ship after publication checks. Not checked: production throughput, external penetration
testing or predictive calibration; this review does not claim them. The bounded demo lock and
per-request trusted-background loading remain documented limitations, not production scale
claims. SHAP's interventional independence assumption (including one-hot features) remains
explicit in evidence; native macOS scoring is not bit-for-bit authoritative.

## Final checkpoint file scope and publication gate

Changed/new since e194ba1:

- ML: `backend/app/ml/{attribution.py,runtime.py,processing.py}` and
  `backend/app/scoring/service.py`.
- Dependencies/types: `backend/{requirements.in,requirements.txt,requirements-dev.in,
  requirements-dev.txt,pyproject.toml}`.
- Tests: `backend/tests/test_shap_attribution.py` and
  `backend/tests/database/{test_attribution_scoring.py,test_risk_configuration.py,
  test_transaction_scoring.py}`.
- Runtime/verification: `.github/workflows/ci.yml`, `Makefile`,
  `infra/{compose.yaml,compose.database.yaml,compose.database-tests.yaml}`,
  `infra/scripts/{check-ingestion.mjs,check-explanations.mjs}`.
- Usage/evidence: `README.md`, `verification/phase-7.md` (all previous report-only edits retained).

No schema, protected planning/security document, scoring formula, weight, threshold, golden
fixture, credential, private dataset or historical model file is changed. The secret scan
checked 152 tracked/nonignored working files, 229 reachable historical blobs and API/worker
logs with no findings. Its scope is known local secret values and common key/token patterns,
not exhaustive SAST. Staged scope/whitespace and remote ancestry must also pass before commit.
Current remote checkpoint remains e194ba1 and main f57eeae; no merge/deployment is authorized.
