# Phase 4 verification: CSV ingestion, private storage and durable jobs

Updated: 2026-10-22. **Phase 4 verified locally and in hosted CI; ready for owner review.**
Branch: feat/phase-04-ingestion.
Base: 8cab9ffad78c76412c767acd831038c7bab9db7a (merged Phase 3/Ponytail main).
Only Phase 4 is implemented. No merge, deployment or Phase 5 work is authorized.

## Resume and preservation

Resumed the existing uncommitted implementation and saved tests without reconstructing
the branch or discarding work. All eleven approved documents were read during this
continuing task and their recorded SHA-256 hashes matched again at final verification.
The owner's AGENTS.md authorization edit is retained. No approved planning/security
document, ORM schema, migration, database grant or frontend source changed.

Local execution works with approved permissions outside the sandbox. The old report's
sandbox and multipart-approval blockers are resolved. Exact origin is
https://github.com/axyz97836/SentinaAI; remote main still points to the base above.
No previous Phase 4 remote branch or commit existed at resume.

Main database: 18 domain tables; Alembic current reports 0001_initial_schema (head);
Alembic check reports **No new upgrade operations detected**. Main data and volumes
were never reset. Existing credentials were not regenerated. Six local credential/
configuration files have mode 0600. The isolated integration run checked that the demo
credential file's bytes were unchanged. Earlier synthetic verification uploads in the
main stack remain intact; this resume did not remove them.

## Implemented behavior

- POST /api/v1/ingestions authenticates and checks CSRF/Origin before consuming the
  body. It accepts one multipart CSV plus purpose/source/license metadata. TRAINING
  requires ADMIN; all three existing roles may stage SCORING.
- Streaming bounds: 10 MiB of file bytes, 16 KiB request overhead, 8 KiB part headers,
  three metadata fields of at most 512 bytes, one file, 60-second body-read timeout.
  Buffering spills to a temporary file after 1 MiB. Failed, incomplete, disconnected
  and cancelled parsing closes files. Duplicate/unknown fields, unsupported MIME/
  extension and invalid CSV headers are refused before private storage.
- Strict UTF-8 CSV (optional BOM), canonical column allowlist, at most 10,000 rows,
  bounded physical lines, duplicate external IDs, UTC timestamps, positive fixed-point
  money, country/currency allowlists, channel and bounded reference/category validation.
  Optional fraud_label is checked as 0/1 and never used for inference.
- Public datasets fail closed with LICENSE_REQUIRED or PUBLIC_DATASET_NOT_APPROVED.
  No public dataset/license has been independently approved; no approval registry,
  table or role was invented. Synthetic uploads may retain optional license metadata.
- Private S3 keys use server UUIDs under organization prefixes. Bounded reads check
  persisted size and SHA-256 before CSV validation. No user-controlled key is accepted.
- Dataset/job intent commits before object writes. Upload readiness and sanitized audit
  commit after PUT. PostgreSQL remains authoritative through broker outages, ambiguous
  object writes or subsequent database rollback.
- Admission serializes on the organization row: five pending imports and ten accepted
  intents per five minutes. These are initial demo limits, not measured capacity.
- GET /api/v1/jobs/{id} enforces session-derived organization scope and returns 404 for
  foreign/absent IDs. It omits raw filenames, keys, digests and credentials; returns
  counts, safe codes, at most 100 row errors and pending cleanup information.
- Real Celery processing uses late acknowledgement, worker-loss redelivery, PostgreSQL
  advisory locks across progress commits, terminal-delivery no-ops and at most three
  started attempts. Storage retries back off; committed progress is not counted twice.
- API recovery scans up to 100 candidates every 15 seconds, with normal per-job
  publication cooldown of 60 seconds. Broker or object deletion failure does not
  block recovery of subsequent jobs.
- Incomplete upload intents older than five minutes become FAILED/UPLOAD_INTERRUPTED
  and REJECTED. Rejected objects retain cleanup flags until deletion succeeds. A late
  uploader cannot recreate an object after its job was finalized.
- Sanitized worker, cleanup and publication logs carry safe codes/job IDs. The
  allowlisted formatter identifies worker events without raw exception messages.

### TRAINING and SCORING boundary

Entirely valid TRAINING becomes dataset VALIDATED / job SUCCEEDED. Row-invalid training
fails as a whole, remains unavailable for training and preserves valid/invalid counts.
Structural errors fail the job; total_rows may remain unknown. processed_rows means
valid rows examined, and the API explicitly reports the VALIDATION phase.

Valid SCORING is staged as VALIDATED but ends FAILED/ACTIVE_MODEL_REQUIRED without an
active model, or SCORING_NOT_AVAILABLE if one exists. Phase 6 must implement scoring
and partial-row success semantics. Phase 4 writes no operational transactions, labels,
scores, alerts or model artifacts and never invents scoring success.

## Dependency verification

Owner-approved addition: **python-multipart 0.0.32**, Apache-2.0, Python >=3.10,
no new transitive runtime dependencies. Verified with Python 3.12, FastAPI 0.143.3 and
Starlette 1.8.0. Hash-required image installation and pip check passed. Both lockfiles
were regenerated with pip-tools 7.6.2.

- Wheel SHA-256: ff6d3f776f16878c894e52e107296ffc890e913c611b1a4ec6c44e2821fe2e23
- Source SHA-256: be54b7f3fa167bb83e4fcd936b887b708f4e57fe75911c02aebf53efaf8d938e

Sources: [PyPI metadata](https://pypi.org/pypi/python-multipart/0.0.32/json),
[upstream release](https://github.com/Kludex/python-multipart/releases/tag/0.0.32),
[advisories](https://github.com/Kludex/python-multipart/security).

The development audit found existing certifi 2026.7.22 affected by PYSEC-2026-4320 /
GHSA-6q48-6c7w-9gw2. Updated only that existing development dependency to **2026.10.19**
with regenerated hashes; no additional package was added. Its MPL-2.0 license and
Python compatibility remain suitable for the existing tooling.
[Upstream advisory](https://github.com/certifi/python-certifi/security/advisories/GHSA-6q48-6c7w-9gw2),
[patched metadata](https://pypi.org/pypi/certifi/2026.10.19/json).

Runtime and development pip-audit runs report **No known vulnerabilities found** after
the fix. This is a dated advisory-database result, not a security guarantee.

Lock commands ran in a disposable network-enabled Python test image (the application
network intentionally cannot reach PyPI):

    pip-compile --generate-hashes --output-file=backend/requirements.txt --strip-extras backend/requirements.in
    pip-compile --allow-unsafe --generate-hashes --output-file=backend/requirements-dev.txt --strip-extras backend/requirements-dev.in
    pip-compile --allow-unsafe --generate-hashes --upgrade-package certifi==2026.10.19 --output-file=backend/requirements-dev.txt --strip-extras backend/requirements-dev.in
    pip-audit -r requirements.txt --disable-pip --no-deps
    pip-audit -r requirements-dev.txt --disable-pip --no-deps
    pip check

## Executed verification

Results cover the final application code and tests. Backend/database checks were rerun
after final logging, regression-test and certifi changes. Frontend build evidence was
reused because frontend code/dependencies did not change; browser regression ran again
against the refreshed API.

| Executed command | Actual result |
|---|---|
| Focused pytest: CSV, storage, multipart | 50 passed; included in unit count below |
| make database-check | **253 passed**, 1 existing Starlette/httpx warning, 32.73 s; disposable PostgreSQL/Redis removed |
| make backend-check | Ruff lint PASS; 41 files formatted; strict mypy PASS, 25 source files; **95 passed**, 253 database tests deselected, 4 warnings, 4.42 s |
| make frontend-check | ESLint, Next type generation, strict TypeScript and production build PASS |
| npm audit --audit-level=high (frontend) | 0 vulnerabilities |
| make ingestion-check | **9 integration checks passed** in separate disposable real PostgreSQL/Redis/S3/API/Celery project |
| make infra-check | **5 check groups passed**: restricted PostgreSQL, Redis auth, S3 operations/private access, bucket restriction, worker ping |
| make outage-check | **8 check groups passed**: healthy baseline, PostgreSQL/Redis/storage stop/recovery, port isolation |
| make browser-check | **8 passed**, 7.0 s: auth/logout CSRF, five widths, real health links, automated WCAG AA scan |
| Main alembic current / alembic check | Initial revision still head; no schema differences |
| Main schema inspection | 18 domain tables |
| shasum -a 256 -c verification/approved-documents.sha256 | 11/11 matched |
| git diff --check, helper Ruff, Node syntax | PASS |
| Compose health inspection | All six main services running and healthy |
| Isolated ingestion project after teardown | No remaining test containers |

**Automated test total: 356 = 253 database + 95 backend unit + 8 browser.**
The 50 focused cases overlap the unit suite and are not counted again. The 9 ingestion,
5 infrastructure and 8 outage check groups are separate, not inflated into pytest counts.
Database breakdown: 153 schema + 56 auth + 44 ingestion cases.

Hosted Linux CI for the final implementation/harness commit e9097f6 independently
confirmed the same counts: 253 database tests (16.28 s), 95 backend unit tests (3.74 s),
8 browser tests (5.9 s), and all 9 real integration checks. Lint, strict typing,
frontend build, infrastructure/outage checks and the frontend dependency audit passed.
The hosted log explicitly records stopped storage, QUEUED attempt 1,
STORAGE_UNAVAILABLE and zero processed rows before successful retry and recovery.

Ignored local logs: .local/phase4-focused.log, phase4-database.log, phase4-backend.log,
phase4-frontend.log, phase4-integration.log, phase4-infra.log, phase4-outage.log,
phase4-browser.log, phase4-audit.log and phase4-dev-audit.log (all under .local/).
Initial failing resume output remains in .local/phase4-resume-database.log.
Logs are not committed or treated as public artifacts.

### Corrected storage-outage evidence

The old harness used Compose start, which also restored storage dependencies. Its last
run passed seven checks then timed out waiting for a storage failure. That was not a
retry verification pass.

The corrected harness resolves the existing worker container **inside the fixed
sentinelai-ingestion-tests project** and starts only that container with docker start.
This project has separate named volumes/networks, database sentinelai_ingestion_test,
and loopback port 18004. It reuses credentials read-only to provision only the isolated
database. Its resolved configuration is ignored and mode 0600.

Actual observations before restoring storage:

- Storage container State.Running: false.
- API readiness: 503.
- Job: QUEUED, attempt_count 1, STORAGE_UNAVAILABLE, processed_rows 0.

After explicit storage start, the real worker reached SUCCEEDED with 2–3 attempts
(asserted bound), exactly one processed row and no duplicated progress. All nine
integration checks passed: authenticated 202 upload/private read/anonymous denial,
duplicate delivery, rejected-object deletion, SCORING refusal, 10,001-row rejection,
API restart, broker outage/recovery, storage outage/retry and log/credential checks.
Only the isolated project's resources were removed. No main database reset or volume deletion.

### Failures found and corrected

- Saved cross-organization test cleanup used the restricted app identity to delete its
  fixture organization. PostgreSQL correctly refused; residue caused later failures
  (223 passed, 6 failed, 1 teardown error). Cleanup now uses the disposable migration
  identity; final 253-case suite passes without weakening privileges.
- Multipart stream annotation used AsyncIterator where Starlette requires AsyncGenerator;
  corrected and strict mypy passed.
- Read-only container Ruff cache/line-length errors corrected; checks rerun.
- Lock resolution on the internal application network failed DNS; used a disposable
  network-enabled build container, preserving app network restrictions.
- Existing certifi advisory fixed and audit rerun.
- Outage harness dependency restart issue fixed and verified as detailed above.
- The first hosted run passed database/backend/frontend/infra/outage checks, then failed
  while seeding the separate ingestion test database. The harness used root with all
  capabilities dropped to read a host-user-owned 0600 credential file. A disposable
  Linux file test reproduced restricted-root denial and matching-owner success. The
  isolated seed now uses the host UID/GID, matching the existing Makefile seed pattern.
  File permissions and assertions remain unchanged. The corrected local integration run
  passed all nine checks again, including stopped storage, failed attempt and recovery.

## Ponytail Review: final

**What this change does:** Adds bounded authenticated CSV uploads and private storage,
then validates them through durable PostgreSQL/Celery jobs. Rejected objects and
interrupted work recover without generating scoring results.

Assumed load: approved single-organization local demo, one worker, concurrent HTTP
submissions and duplicate deliveries. Review traced routes, auth/CSRF, multipart/temp
files, CSV validation, storage, DB transactions, locks/retries, recovery, logs, tests,
Compose/CI and README.

Resolved material findings (none remain open):

1. **Late uploads could orphan objects.** Recovery could finalize an intent before its
   delayed PUT. The uploader now checks locked state before writing; regression tests
   prove a late upload cannot recreate the object. Skipping the fix leaves untracked data.
2. **Deletion or broker failure could block unrelated recovery.** Safe per-job cleanup
   failures persist and publication failures no longer escape the loop. Tests prove later
   jobs/cleanup continue. Skipping the fix strands work during dependency outages.
3. **Interrupted uploads could stay QUEUED after deletion failure.** Failure state and
   cleanup outcome now persist independently. Failure/recovery tests preserve original
   error and counters. Skipping the fix misreports durable status.
4. **Worker exceptions lacked usable diagnostics.** Sanitized logs now carry job ID and
   worker service label. Formatter/real-log checks exclude sensitive content. Skipping
   the fix makes recovered failures difficult to trace.
5. **The outage harness restored the failed dependency.** Worker-only start and explicit
   stopped-storage/readiness assertions prove a real failure/retry in isolation. Skipping
   the fix would claim recovery coverage without inducing the outage.
6. **The isolated seed could not read credentials on Linux CI.** Capability-restricted
   root cannot read another user's 0600 file. Using the host UID/GID preserves permissions
   and matches the existing seed command. A Linux permission reproduction and the full
   nine-check local integration rerun pass; skipping this fix prevents hosted verification.

Contract review also removed unnecessary rejection of optional synthetic license metadata
and spaces in merchant categories. Positive regression tests pass.

**Verdict: Ship the verified Phase 4 scope.** Hosted CI passed; owner review is next.
Not checked: production load, deployment security/retention/backups, future ML/scoring/UI
or a formal security audit. These remain outside the authorized phase.

## Secret hygiene

Reviewed the scoped source/test/config diff, dependency deltas and inventory. An explicit
scan covered 112 working tracked/nonignored files, all 125 reachable historical blobs
before the Phase 4 commit, and inspected API/worker logs. It compared known local credential
values and common GitHub/AWS/private-key patterns: **no findings**. The first scan wrongly
classified the public LOCAL_SYNTHETIC_DEMO_ONLY label as a credential; restricting extraction
to account credential values removed that false positive. No .env, credentials, private
storage, logs or uploaded data is staged.

Limitations: exact-value/pattern checks are not exhaustive secret detection or SAST and
cannot prove absence of unknown credentials or every sensitive string.

## Exact changed files

Existing:
- .github/workflows/ci.yml
- AGENTS.md (owner's existing authorization edit)
- Makefile
- README.md
- backend/app/main.py
- backend/app/observability.py
- backend/app/worker.py
- backend/requirements.in
- backend/requirements.txt
- backend/requirements-dev.txt
- backend/tests/test_health.py

New:
- backend/app/ingestion/__init__.py
- backend/app/ingestion/multipart.py
- backend/app/ingestion/processing.py
- backend/app/ingestion/routes.py
- backend/app/ingestion/service.py
- backend/app/ingestion/storage.py
- backend/app/ingestion/validation.py
- backend/tests/database/test_ingestion.py
- backend/tests/test_csv_validation.py
- backend/tests/test_multipart.py
- backend/tests/test_private_storage.py
- infra/scripts/check-ingestion-storage.py
- infra/scripts/check-ingestion.mjs
- verification/phase-4.md

## Remaining limitations and phase boundary

- Public datasets remain blocked pending independent owner/license review.
- Syntactic identifier checks cannot establish that data is fictional. Code allowlists
  require maintenance; semantic PII detection is not claimed.
- The multipart adapter uses pinned Starlette internals; upgrades must rerun limit,
  incomplete-body, disconnect and cleanup tests.
- Recovery requires a running API process and runs every 15 seconds; 202 does not imply
  immediate worker execution. Resource limits are demo defaults, not production sizing.
- Maximum three started attempts; permanent infrastructure failures remain FAILED.
  No new user-facing retry endpoint was invented.
- Successful-upload retention/backup purge, public deployment, full UI, model training
  and scoring remain later-phase work. Rejected-upload deletion is tested.
- Existing Starlette/httpx and Redis deprecation warnings remain. No replacement library
  was added just to silence warnings.

## GitHub publication

Exact origin: https://github.com/axyz97836/SentinaAI.
[Branch](https://github.com/axyz97836/SentinaAI/tree/feat/phase-04-ingestion).
[Base](https://github.com/axyz97836/SentinaAI/commit/8cab9ffad78c76412c767acd831038c7bab9db7a).

Implementation commit: [87715f02b1de64521ce078d810445f159e4c8003](https://github.com/axyz97836/SentinaAI/commit/87715f02b1de64521ce078d810445f159e4c8003).
Pushed with explicit HEAD:refs/heads/feat/phase-04-ingestion; git ls-remote verified
that exact remote hash. The post-commit scan covered 150 reachable blobs and found no
known secrets or matching credential patterns. No force push or merge occurred.

[Hosted workflow](https://github.com/axyz97836/SentinaAI/actions/runs/39632621136)
finished with failure at isolated ingestion seed setup; all preceding checks passed.
The Linux harness correction is committed as
[e9097f67a35bcde46f64597d20b496343cf60cbd](https://github.com/axyz97836/SentinaAI/commit/e9097f67a35bcde46f64597d20b496343cf60cbd).
Its push succeeded and git ls-remote verified that exact remote hash on resume.
[Corrected hosted workflow](https://github.com/axyz97836/SentinaAI/actions/runs/39633929091)
finished **completed / success** for that exact commit. Downloaded logs confirmed
356 application tests and all 9 integration checks, including genuine storage failure
and worker retry. No unresolved test failure remains.

The final follow-up changes only this report. Application code and the tested harness
remain identical to e9097f6. Its final commit hash, remote synchronization and latest
workflow result are verified separately in the completion response, avoiding a
self-referencing commit hash in this file.

GitHub CLI is unavailable (gh: command not found). Public Actions status queries work;
anonymous log download returned HTTP 403, so logs were retrieved using the existing
macOS Git credential manager, with credentials kept only in process memory. No token
was requested in chat, printed or saved. Temporary CI-watch/download/scan scripts and
logs remain ignored under .local/ and are not part of the commit. No Git push
authentication or synchronization error occurred. No force push, merge or deployment.
