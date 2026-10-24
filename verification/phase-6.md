# Phase 6 verification: direct and asynchronous CSV scoring

Updated: 2026-10-24. **Locally verified; GitHub publication/hosted verification pending.**
Branch: `feat/phase-06-scoring`.
Base: `6b54665` (merged Phase 5, PR #5). No Phase 6 commit or push yet.

## Authority and recovery

The owner's Phase 6 attachment and explicit resume instruction authorize only direct
transaction and CSV scoring. All eleven approved documents, Phase 4/5 reports and both
Ponytail skills were read. The obsolete current-phase paragraph in AGENTS.md alone was
replaced with the owner-authorized durable authorization rule.

Origin is exactly https://github.com/axyz97836/SentinaAI. Initial fetch confirmed Phase 5
and both Ponytail skills in origin/main; clean main was fast-forwarded and the Phase 6
branch created. Resume preserved four complete, syntactically valid untracked scoring
modules. No prior Phase 6 commits exist to reconstruct.

Before interruption: six services healthy; 18 domain tables; `0001_initial_schema (head)`;
Alembic check: `No new upgrade operations detected`; all eleven approved document hashes
matched. On resume Docker Desktop was stopped; it was started without resetting volumes
or credentials. No main database seed or destructive test was run.

## Implemented behavior

- POST /api/v1/transactions, GET /api/v1/transactions and GET /api/v1/transactions/{id}.
  Existing session/Origin/CSRF and org guards; strict extra-field rejection; body bound.
  Lists cap at 100 with event-time descending/UUID ascending keyset pagination; bounded
  reference search, band/risk_band aliases and inclusive-from/exclusive-to date filters.
  Detail exposes authorized persisted evidence and alert/case IDs, never artifact keys.
- Trusted Phase 5 bundle loader checks successful training provenance, private server key,
  digest, size limit/ContentLength, format, dependency/schema versions and reference.
  Static feature order/preprocessing is unchanged. Inference checks dimensions, class
  ordering, finite raw outputs and [0,1] classifier values before percentile calculation.
- Stored six-decimal components use decimal half-even rounding. Composite uses the stored
  model weights and decimal integer half-even rounding, so persisted components reproduce
  the score. Default weights remain 0.60/0.25/0.15; never redistributed for missing rules.
  Formula: `round_half_even(100 * (w_supervised*p + w_anomaly*a + w_rules*r))`.
- Risk settings supply band and alert thresholds; every result retains the actual settings
  version/threshold snapshot, immutable model ID and PARTIAL explanation. No SHAP invented.
  Default bands remain LOW 0–39, MEDIUM 40–69, HIGH 70–84, CRITICAL 85–100; alert 70.
  The implementation reads configured values, not permanent hardcoded replacements.
- Org row lock serializes direct/CSV scoring and model activation for the bounded demo.
  INSERT ON CONFLICT plus DB uniqueness owns idempotency. Matching normalized replay returns
  original result before loading a model; changed payload returns 409. Source and label are
  excluded from canonical payload equivalence.
- Transaction, score, actual rule hits, qualifying NEW alert and redacted audit share one
  transaction. Latency is measured through lock/model/history work and transaction insertion,
  before immutable score insertion; excludes final result writes, commit and HTTP transport.
- CSV structure/limits are preflighted before scoring. Rows stream one at a time (bounded
  chunk size 1), with row outcome and progress in the same transaction. First verified active
  model is pinned on the job and reused across rows/retries. Thresholds/rules are read for
  each new row; old replay evidence is retained. Completed row errors use SUCCEEDED and an
  explicit partial warning. At most 100 sanitized row errors; every failure still counted.
- Labels persist separately after transaction creation; conflicting existing labels reject
  that row without rewriting evidence. Labels are never included in model input.
- Missing/corrupt model fails truthfully without pretending rows were processed; valid CSV
  sources are retained. Existing advisory job lock, late acknowledgement, recovery and
  three-attempt storage backoff remain authoritative. Historical terminal jobs stay terminal.

## Minimal rule contract and limits

Approved documents name three rules but do not define exact parameter keys, defaults or
aggregation. The seed explicitly creates no rules. No definitions/defaults are installed.
Absent, disabled, unsupported and missing-history states remain explicit and distinct from
an evaluated non-hit. Zero contribution is absence of a demonstrated hit, not proof of safety.

The narrowly supported internal parameter shapes are tested with synthetic fixtures:
AMOUNT_OUTLIER `{multiplier,min_history}` compares to the mean of at most 100 latest same-
currency prior rows; HIGH_VELOCITY `{window_minutes:10,count_threshold}` counts prior rows in
the inclusive lower/exclusive upper ten-minute window, capped at the decision threshold;
DEVICE_CHANGE `{}` compares the immediately preceding row only when both devices exist.
Binary hit strengths aggregate by maximum (any actual hit => 1); no hit => 0. This is an
explicit Phase 6 interpretation, not a fully configurable rule engine or calibrated model.
All queries scope org/customer, exclude current/future/equal candidate timestamps and use
UUID tie ordering for historical rows with equal timestamps. Late-arriving events never
rewrite existing scores. No fictional history or FX conversion is introduced.

## Executed final local checks

| Command/check | Actual result |
|---|---|
| Four interrupted scoring modules, Python AST parse | PASS |
| Focused scoring + ML / scoring + CSV + ML | 49 / 84 passed; overlapping backend cases, not added again |
| `make database-check` (final corrected source) | **296 passed**, 1 existing warning, 26.76 s |
| `make backend-check` (final corrected source) | Ruff PASS, 63 formatted files, strict mypy PASS/41 modules; **165 passed**, 296 deselected, 4 existing warnings, 4.59 s |
| `make frontend-check` | ESLint, Next type generation, strict TypeScript and production build PASS |
| `make infra-check` | Restricted PostgreSQL, Redis, private S3 and worker checks PASS |
| `make outage-check` | Eight health/outage/recovery/port-isolation groups PASS |
| `make browser-check` | **8 passed**, 7.4 s, auth/logout CSRF, five widths, health links and accessibility smoke |
| `make scoring-check` | **9 genuine integration checks passed**; isolated resources removed |
| `make ingestion-check` | **9 genuine integration checks passed**, including stopped-storage retry |
| `make model-check` | **8 genuine integration checks passed**, including tampered candidate and storage retry |
| Node syntax checks, scoped diff whitespace, editor diagnostics | PASS |
| Approved document hashes | 11/11 match |
| Final main schema/readiness | 18 domain tables; initial migration head; no schema differences; alive/ready |

**Distinct automated application tests: 469 = 296 database + 165 backend + 8 browser.**
Phase 6 adds 24 database cases and 37 backend cases. Focused runs overlap these counts.
Integration groups are listed separately. Final database/backend runs were already in
flight at the last resume; their exit codes were confirmed as zero rather than rerunning
unchanged code merely because the conversation resumed.

Database evidence covers all three roles, missing/expired/revoked sessions, CSRF/Origin,
unknown authority/label fields, missing/corrupt/incompatible model, exact alert boundaries,
atomic audit failure rollback, six concurrent identical submissions, conflicting requests,
two competing CSV jobs plus a direct request, model changes, replay snapshot preservation,
foreign history/IDs, current/equal/future exclusion, genuine rule hits/non-hits/missing states,
CSV partial success, immutable label conflicts, capped errors and interrupted row recovery.

The isolated real scoring workflow generated a synthetic TRAINING file, validated it,
trained through Celery, explicitly activated a model, posted/read/replayed/conflicted direct
transactions, and sent competing HTTP submissions. It then scored CSV partial rows,
redelivered tasks, stopped storage and observed QUEUED/STORAGE_UNAVAILABLE with zero processed
rows, restored storage, and killed the actual worker with SIGKILL during an 800-row job.
Restart recovered durable progress within the three-attempt bound without double counting.

Final isolated reconciliation: **805 transactions = 805 scores = 805 alerts = 805 scoring
audit events; 803 separate labels.** The test intentionally configures alert threshold zero
only in its disposable organization so every score qualifies; separate DB tests prove
below/at/above threshold behavior. Every composite and band reproduces from persisted
components/settings. Cross-org reads return 404, absent model refuses scoring, corrupted
active artifact leaves counts unchanged, and prior direct replay survives corruption.
API/worker log captures are nonempty and omit fictional customer markers and credentials.
Existing credential-file bytes remain identical. No main model/data is changed by this test.

These are synthetic functional results, not observed real-world fraud performance. The
Phase 5 held-out metrics reproduce unchanged; no retraining feature/schema change was made.

Initial diagnostic command used a nonexistent `create_database_engine` name; corrected to
the existing `database_engine`, then schema/readiness checks passed. Sandbox blocked Git,
Docker, Python runtime and shasum; approved external execution resolved those restrictions.
A nested Docker file mount was refused; a single repository mount works for formatting.
The first database run had 287 passes and one failing assertion; the expanded build already
in progress captured that same old assertion and had 295 passes/one failure. The check used
the substring `old` as a fictional device marker, which also matched `count_threshold`.
Checking the quoted complete value fixes the test without changing evidence or application
behavior. The final 296-case run passes. No failed run is counted as success.

Slow test-image builds were traced to runtime source COPY invalidating development package
installation. Docker stages now share the pinned runtime dependencies and install test
dependencies before copying source. Runtime remains non-root and has no added packages;
all dependency manifests/locks are unchanged. This avoids repeated network downloads on
later source-only verification builds. No schema, grant, migration or frontend source change.

## Ponytail Review

**What this change does:** Creates one persisted composite score and optional alert for a
canonical transaction, and uses the same service for durable CSV rows. Replays preserve
their original scoring evidence; partial CSV errors remain visible.

Assumed load: the approved local demo, one worker and bounded concurrent clients. Review
traced all new modules and their auth, schema/privilege, artifact, CSV, worker/recovery and
test/harness callers, plus build/CI/docs. Existing constraints and function-scoped commits
remain authoritative. The explicit org scoring lock favors simple consistency at demo load;
there is no production throughput claim.

Resolved findings and safeguards:

1. Nonfinite raw anomaly output could become a finite percentile through searchsorted.
   Validate raw scores and dimensions before percentile mapping; negative tests pass.
2. Stored numeric precision must reproduce integer composite risk. Quantize components to
   the DB's six decimal places before half-even composite rounding; math and persisted
   reconciliation tests pass without changing model weights.
3. Scoring results cannot be updated by the restricted app identity. Measure latency before
   initial result insertion; never weaken immutable-table grants for a timing update.
4. CSV result/counter commits must not separate. Row writes, optional label and counters
   now share a transaction; injected loss and genuine SIGKILL tests prove retry correctness.
5. Missing history and evaluated non-hits must remain distinct. Rule states are stored
   separately; zero recent velocity with older history is an evaluated non-hit. No default
   rule definitions, nonzero placeholder contribution or SHAP attribution is invented.
6. Redaction assertion matched a schema key; corrected as described above and rerun.

**Verdict: Ship the locally verified Phase 6 scope for hosted verification and owner review.**
Not checked: production scale, deployment, formal security audit, calibrated real-world
accuracy, complete configurable rules/SHAP, frontend transaction screens or case workflows.

## Exact changed files

- `.github/workflows/ci.yml`
- `AGENTS.md` (obsolete boundary paragraph only, explicitly authorized)
- `Makefile`
- `README.md`
- `backend/Dockerfile`
- `backend/app/auth/body_limit.py`
- `backend/app/ingestion/processing.py`
- `backend/app/ingestion/routes.py`
- `backend/app/ingestion/validation.py`
- `backend/app/main.py`
- `backend/app/ml/training.py`
- `backend/app/scoring/__init__.py`
- `backend/app/scoring/calculation.py`
- `backend/app/scoring/history.py`
- `backend/app/scoring/processing.py`
- `backend/app/scoring/routes.py`
- `backend/app/scoring/schema.py`
- `backend/app/scoring/service.py`
- `backend/tests/database/test_ingestion.py`
- `backend/tests/database/test_transaction_scoring.py`
- `backend/tests/test_scoring.py`
- `infra/scripts/check-ingestion.mjs`
- `infra/scripts/check-scoring-db.py`
- `infra/scripts/check-scoring.mjs`
- `verification/phase-6.md`

Ignored logs: `.local/phase6-database-direct.log`, `phase6-database-final.log` (failed
pre-correction runs), `phase6-database-verified.log`, `phase6-backend.log`,
`phase6-backend-verified.log`, `phase6-stack-regression.log`, `phase6-scoring-integration.log`,
`phase6-ingestion-model-regression.log`, `phase6-main-up.log`, `phase6-final-up.log`.

## Secret hygiene and publication

Pre-stage scan examined **140 tracked/nonignored files and 187 reachable historical blobs**,
plus API/worker logs, with **no findings**. It matches known local credentials and common
token/private-key patterns; this is not exhaustive secret detection or SAST. No env file,
private CSV, artifact, credential, storage object or log belongs in this change set.

Origin: https://github.com/axyz97836/SentinaAI.
[Phase 6 branch](https://github.com/axyz97836/SentinaAI/tree/feat/phase-06-scoring).
Implementation commit, verified remote SHA and hosted Actions URL/status will be recorded
after publication. No force push, merge or deployment is authorized or performed.

## Remaining limitations

No dependencies were added or upgraded. No schema change. Public datasets remain blocked
pending independent review; syntactic reference checks cannot establish fictional provenance.
Direct requests reload verified bundles; a CSV attempt reuses its loaded bundle and reloads
the pinned version on retry. Org serialization and per-row commits are deliberate demo limits.
New CSV jobs require a verified model even if all valid rows ultimately replay old results.
Model failures leave valid sources retained; durable recovery still requires the API process.
Exhausted jobs remain FAILED; no retry endpoint or historical-job replay was introduced.
Partial explanations, missing rule definitions and synthetic model limitations remain explicit.
Phase 7 must finish configurable rules, settings editors and detailed attribution separately.
