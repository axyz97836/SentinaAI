# Phase 8 verification: alerts and case management backend

Updated: 2026-10-29. **Phase 8 implementation, local regression, security/concurrency checks,
Ponytail Review and hosted ARM64 CI are complete. Implementation commit 377d5c4 is published
and its remote hash is verified. Phase 8 is ready for owner PR review; the final report-only
commit and its hosted run are identified in the owner handoff. No merge or deployment.**

## Authorization and base

The owner's Phase 8 attachment authorizes only the eight alert/case endpoints, existing state
transitions, append-only investigation evidence and associated verification. AGENTS.md, all
eleven approved documents, Phase 7 evidence and the Ponytail/Ponytail Review instructions were
read. Python fact-grounded coding was used for interpreter/typing/test evidence. No dependency,
schema, enum, role, UI, service or architecture addition is authorized or introduced.

The first fetch still showed the Phase 6 merge. A direct remote check then showed the newer
Phase 7 merge; an explicit main fetch verified that `8216711b4f2dee946295323073210f3c2ad093d1`
is an ancestor of `0ad65b44c8747632724b1f57e3aa5f0c79fa27ad` (PR #7).
[Merge CI](https://github.com/axyz97836/SentinaAI/actions/runs/40679200600) completed successfully.
The clean local main fast-forwarded to that merge, then `feat/phase-08-alerts-cases` was created.
Origin remains `https://github.com/axyz97836/SentinaAI`. No reset, force push, main data reset,
credential regeneration or seed rerun occurred. All eleven approved document hashes match.

## Implemented contract

| Endpoint under `/api/v1` | Implemented behavior |
|---|---|
| `GET /alerts` | Org-scoped status/risk-band/date filters and bounded keyset pagination |
| `POST /alerts/{id}/dismiss` | NEW only, required reason <=1,000 characters, actor/time and redacted audit |
| `POST /alerts/{id}/cases` | Optional note; one OPEN case, alert IN_CASE, CASE_OPENED + audit; 201 first/200 exact retry |
| `GET /cases` | Org-scoped status/activity-date filters and bounded keyset pagination |
| `GET /cases/{id}` | Case, linked alert/transaction, immutable score and explanation, bounded chronological events |
| `PATCH /cases/{id}` | OPEN to IN_REVIEW only with current version and optional note |
| `POST /cases/{id}/events` | Required note <=2,000 characters, NOTE_ADDED + audit; CLOSED refused |
| `POST /cases/{id}/resolve` | IN_REVIEW to CLOSED with supported resolution, mandatory note and current version |

Alert states remain NEW/IN_CASE/DISMISSED. Case states remain OPEN/IN_REVIEW/CLOSED.
Resolutions remain CONFIRMED_FRAUD/FALSE_POSITIVE/INCONCLUSIVE. All three existing roles have
the same investigation permissions. Session/Origin/CSRF, error envelopes and commit-before-HTTP
success are reused. No client organization/actor/assignee field is accepted. Lists, details
and mutations validate the complete org-owned case/alert/score/transaction/model chain;
inconsistent cross-org references resolve as unavailable instead of exposing linked evidence.

Reasons/notes are bounded plain text, trimmed with CRLF normalization; blank required values,
invalid control/encoding and extra fields are rejected. JSON remains inert text, with no HTML
interpretation. Note/reason content is excluded from audit metadata and infrastructure logs.
The investigation body limit is 32 KiB for worst-case JSON-escaped Unicode; existing auth,
scoring and CSV limits are unchanged. Notes remain in the authorized append-only timeline.

List limits are 1–100 (default 20), ordered timestamp descending/UUID ascending. Alert dates
use created_at; case dates use updated_at; bounds are inclusive lower/exclusive upper with
required timezone. Timeline uses ascending created_at/UUID, `events_limit` 1–100 (default 50),
`events_cursor` and `next_events_cursor` on the same documented detail endpoint. No new route.
Pagination is deterministic for a fixed data set, not a frozen export during concurrent edits.

## Atomicity, history and retries

- Alert row FOR UPDATE serializes dismissal versus opening. The existing unique case-per-alert
  constraint remains. Domain state, CASE_OPENED and audit commit together.
- Case row FOR UPDATE serializes notes/review/closure. Detail holds FOR SHARE while reading
  state and timeline. Timestamps are assigned after acquiring the lock, avoiding transaction-
  start timestamps putting a delayed event before an earlier committed event.
- Review and closure each increment version once. Notes update activity time but not the state
  version. An exact open retry compares the normalized original opening note and adds no event.
- Closure replay requires the same normalized outcome/note and original expected version
  (stored version = submitted version + 1); it adds no closure/audit event. Different payloads,
  stale edits, direct OPEN-to-CLOSED and reopening fail with 409 (invalid request fields 422).
- Scores, weights, thresholds, model artifacts, SHAP calculations and transaction_labels are
  never changed by an investigation. Detail reads persisted explanation evidence only.

## Verification executed so far

| Command/check | Actual result |
|---|---|
| Native focused schema/cursor pytest | **30 passed**, 4.10 s; validation only, not authoritative inference |
| Initial `make database-check` | **349 passed, 5 failed**, 83.66 s; forged-header fixture defect diagnosed below |
| Corrected `make database-check` | **354 passed**, one existing warning, 52.62 s; disposable resources removed |
| `make backend-check` on Linux ARM64 | Ruff PASS, **80 files** formatted, mypy **52 modules** PASS; **247 passed**, 354 deselected, four existing warnings, 7.91 s |
| `make case-check` | **11 genuine integration checks passed**, isolated resources removed |
| Full Python dependency audit | No known vulnerabilities, exit 0; unchanged 103-package development lock includes runtime subset |
| Protected-document hashes | **11/11 unchanged** |

The new database tests cover all three roles, exact retry/conflict behavior, CSRF and missing
session denial, foreign organizations, deliberately inconsistent parent FKs, Unicode/body
bounds, fixed query budgets and stable pagination. Six real PostgreSQL races cover duplicate
opening, dismissal/opening, competing review, matching closure, conflicting closure, and note
versus closure. Nine injected event/audit insert failures verify rollback of state, version,
activity timestamps and every partial event/audit. They use the guarded disposable database
and migration identity for fixture cleanup only. No SQLite/mocked transaction substitute.

The new real HTTP workflow trains/activates a trusted model only inside its disposable
synthetic project, configures that project's alert threshold through the ADMIN API, then
scores actual transactions. All three roles complete opening, review, note and closure plus
independent dismissal. It exercises concurrent HTTP actions, real foreign-org sessions,
idempotent retries, forbidden inputs, SQL case/event/audit reconciliation and exact unchanged
historical score/explanation payloads. Main credentials/volumes/artifacts are untouched.

### Diagnosed development checks

- Ruff preflight found initial formatting/import order; fixed without changing behavior.
- Mypy reported SQLAlchemy's installed variadic Select type expects `Select[Alert]` and
  `Select[Case]`, not tuple-wrapped arguments. The annotations were corrected; all 52 modules pass.
- Five new forged-origin tests constructed `{...headers, origin: hostile}` alongside the
  existing capitalized Origin key. HTTPX emitted both original and hostile Origin values;
  the server received the still-valid first value. A controlled HTTPX reproduction confirmed
  the two-value list. Replacing the exact Origin/X-CSRF-Token keys produced the intended
  single invalid header; all original 403 assertions passed. No auth implementation was weakened.
- Failed pytest fixture representations exposed short-lived synthetic CSRF proofs in the local
  diagnostic output. The shared fixture now uses a dict subclass with a redacted repr; request
  mapping behavior is unchanged. Original evidence is preserved in ignored restrictive storage;
  the disposable sessions/database were removed. Runtime HTTP logs contained no raw notes/tokens.
- Sandbox-only Python framework and Node OpenSSL access failures were retried through approved
  execution outside the sandbox; no dependency or system configuration workaround was installed.

Ignored evidence: `.local/phase8-database-initial.log`, `phase8-database-corrected.log`,
`phase8-backend.log`, `phase8-case-integration.log`, `phase8-dependency-audit.log`, `phase8-up.log`.
Final regression and publication results will be appended only after completion.

## Changed files

- `backend/app/investigations/{__init__.py,schema.py,service.py,views.py,routes.py}`.
- `backend/app/main.py`, `backend/app/auth/body_limit.py`.
- `backend/tests/test_investigation_validation.py`, `backend/tests/database/test_investigations.py`,
  `backend/tests/database/test_ingestion.py` (fixture diagnostic redaction only).
- `infra/scripts/check-cases.mjs`, `infra/scripts/check-cases-db.py`,
  `infra/scripts/check-ingestion.mjs`, `Makefile`, `.github/workflows/ci.yml`.
- `README.md` and this separate verification report. All eleven approved documents unchanged.
- `frontend/playwright.config.ts`: local browser worker bound only; CI keeps its default.

No migration revision or new dependency. The authoritative Linux ARM64 policy and all
approved ML/runtime/development pins remain unchanged. Final review and publication pending.

## Browser regression investigation and environment correction

The initial full browser run had **4 passed, 4 failed** in 1.4 minutes. Authentication and
320/375/768px tests failed in `page.goto("/")`, waiting for the document **load** event under
the original 30,000 ms test timeout. They did not reach auth/layout assertions. The other four
tests passed. No failure was ignored or reclassified as a pass.

Preserved evidence: `.local/phase8-stack-regression.log`, the original Playwright results copied
to `.local/phase8-browser-initial-results/` with restrictive permissions, and correlated frontend
logs in `.local/phase8-browser-frontend-window.log`. The root page is static and makes no backend
data/auth request during rendering. The frontend had been serving HTTP 200 health requests for
minutes before the failure; incomplete startup is not supported by the evidence.

The exact timeout mechanism is delayed browser/page setup and document/asset delivery consuming
the test deadline. The saved 320px trace reports:

| Same 320px test | Failed original | Passing comparison |
|---|---:|---:|
| Browser `newPage` | 8,115.868 ms | 661.675 ms |
| Main document status | 200 | 200 |
| Main document response wait | 17,021.802 ms | 2,377.694 ms |
| `page.goto` completion | No completed load before deadline | 3,863.671 ms |
| Resource state | 15 CSS/JS requests unfinished at cancellation | Document load completed and assertions passed |

The failed trace's final captured screenshot is blank while its later error-context DOM snapshot
contains the foundation content. The passing screenshot shows the styled page and keyboard focus.
Frontend logs independently show concurrent root responses taking **17.6–19.0 seconds** during
the failure window, compared with earlier tens/hundreds of milliseconds. This is delayed loading,
not an observed layout, CSRF or case-API assertion failure.

At the time, multiple verification jobs shared the local Docker/host resources; Docker reported
a 3.825 GiB VM. The saved resource sample was taken after the failure, so it cannot identify the
exact process responsible for the original scheduling/I/O delay. Resource contention is the
supported environmental explanation, not an invented per-process diagnosis. Controlled checks
after completing the competing pipeline work confirmed healthy frontend/API and all six services;
the root returned 200 in 0.182026 s before rerunning browsers.

Executed comparisons, without changing assertions or timeouts:

- `npx playwright test tests/foundation.spec.ts --trace=on --output=../.local/phase8-browser-comparison`:
  **7 passed**, 10.1 s. Only non-authentication tests were traced; auth credentials are not recorded.
- Original `make browser-check`, four workers: **8 passed**, 54.1 s. The slowest auth test was 26.7 s.
- `npm test -- --workers=1`: **8 passed**, 27.7 s. Auth was 6.1 s; other tests 0.595–3.8 s.

The minimal reproducible correction bounds **local** Playwright workers to one alongside the
six-service Docker stack. CI retains its previous default worker selection. README instructs
`make -j1 check` without overlapping independent build/integration jobs. Test timeout, retries=0,
all assertions, all eight tests and frontend product code are unchanged. This addresses measured
local contention without hiding application failures or changing the approved runtime policy.
The final configuration was checked through `make -j1 frontend-check browser-check`; the
recurrence and completed isolated retest are recorded below rather than omitted.

Sanitized trace comparison: `.local/phase8-browser-trace-comparison.json`; diagnostic logs:
`phase8-browser-comparison.log`, `phase8-browser-final.log`, `phase8-browser-single-worker.log`,
and `phase8-browser-harness-verification.log`. Repeated/diagnostic runs count as the same eight
browser tests, not additional coverage.

## Completed remaining regression and security checks

- `make -j1 ingestion-check model-check scoring-check explanation-check`: **9 + 8 + 9 + 7**
  checks passed, exit 0, each isolated project removed. Scoring again reconciled 805 transactions,
  results, alerts and scoring audits with 803 labels. No main data changes.
- New `make case-check`: **11 passed**. Total integration groups: **44**, including the unchanged
  Phase 7 baseline of 33. These are separate from pytest/browser test totals.
- Frozen Phase 7 compatibility script against the current ARM64 backend-checks image:
  **2,000 rows**, supervised maximum absolute delta **0.0**, exact anomaly percentiles, unchanged
  artifact bytes, genuine SHAP additivity PASS with 1,200 background rows and 19 features.
- `make model-runtime-check frontend-check infra-check outage-check` passed before the browser
  failure: API/worker fingerprints, frontend lint/types/build, all five infrastructure groups
  and all eight controlled outage/recovery groups. The later frontend harness edit is rechecked.
- Full unchanged 103-package Python development lock audit: **No known vulnerabilities**.
  `npm audit --audit-level=high`: **0 vulnerabilities**. No dependency upgrades or audit waivers.
- Secret scan: **162 working files, 252 reachable historical blobs**, plus API/worker logs,
  no matches. Scope is known local credentials and common key/token patterns, not exhaustive
  secret detection or penetration testing. Disposable workflow logs also reject raw note/data
  markers and current credentials. No private artifacts or diagnostic logs will be committed.

Evidence: `.local/phase8-pipeline-regression.log`, `phase8-arm64-compat.log`,
`phase8-dependency-audit.log`, `phase8-npm-audit.log`, `phase8-secret-scan.log`.

## Ponytail Review

What this change does: adds authenticated alert triage and a complete case investigation
backend using the existing schema. State changes, immutable timeline events and redacted audit
records commit together; scoring and historical evidence remain unchanged.

Review followed all eight routes through session/Origin/CSRF checks, strict input validation,
tenant/parent-chain filters, SQL locks, expected versions, retry decisions, audit writes and
response serialization. It traced direct scoring/alert links and existing explanation readers,
checked case/alert/event grants and constraints, bounded cursor queries, body limits, fixture
redaction, integration helpers, Make/CI and the documented local browser correction. Expected
load is the existing bounded demo and one worker, not an unmeasured production workload.

Confirmed issues during development were corrected and verified: SQLAlchemy annotation shape,
forged-header fixture construction, sensitive fixture repr, and environmental browser concurrency.
No material application logic, authorization, race, rollback or unnecessary-abstraction finding
remains open. Real PostgreSQL races and injected failures support the transactional conclusions;
query-budget tests and bounded lists/timelines support the scope's resource limits.

Verdict: Ship after staged/publication checks. Not checked:
production throughput, external penetration testing or the future investigation frontend.
None is claimed as completed by this backend-only phase. Public release, deployment, assignment,
reopening, new roles/statuses and Phase 9 remain outside this authorization.

### Post-build recurrence and final isolated verification

`make -j1 frontend-check browser-check` completed frontend lint, TypeScript and production build,
but its immediate browser run had **7 passed, 1 failed**, 51.4 s. The failing auth test reached
`page.evaluate` after navigation and timed out in the combined authentication request sequence;
it was not another layout assertion failure. Authentication tracing remains disabled to protect
credentials, so no claim is made about which individual auth request consumed that deadline.

This disproved treating the one-worker change alone as a complete remedy. The post-build
frontend logs show root responses reaching 14.5–15.6 s during the build window, then returning
to tens/hundreds of milliseconds. A subsequent host snapshot recorded 8 GiB physical RAM,
7,485 MiB used, 129 MiB unused and 3,343 MiB compressed, with load averages 7.24/10.18/10.29.
Docker had eight CPUs and 4,106,604,544 bytes of VM memory; all six services were healthy.
These observations support local capacity/scheduling pressure, but do not establish an exact
OS process or swap-rate diagnosis for the historical stall.

The reproducible execution correction therefore includes **post-build readiness and isolation**,
not just worker count. After build/other verification work ended, the actual preflight was:

- Frontend root: **200**, 0.248610 s.
- Frontend-proxied `/api/v1/health/ready`: **200**, `{status:ready}`, 0.088956 s.
- Direct API readiness: **200**, `{status:ready}`, 0.016021 s.
- Six main services: running/healthy; no disposable integration stack remained.

Then the unchanged `make browser-check` with the committed local worker setting completed
**8 passed, 0 failed in 13.3 s**. Authentication took 2.8 s. This was the declared single
isolated retest after investigation, not an automatic retry loop. No timeout was increased,
assertion weakened, test skipped, credential regenerated, or frontend functionality changed.
The failed run remains evidence; this does not promise that an overloaded development laptop
will always meet test deadlines. CI retains its original default concurrency and must pass
independently before final phase sign-off.

Additional evidence: `.local/phase8-browser-harness-frontend.log`,
`phase8-browser-harness-verification.log` (frontend pass/browser recurrence),
`phase8-browser-isolated-final.log` (all eight pass).

## Final local totals

**609 distinct application tests passed = 354 database + 247 backend + 8 browser**, preserving
the Phase 7 baseline of 547 and adding 32 database + 30 validation tests. The earlier failed
attempts are documented above and do not count as passes. Repeated/diagnostic runs are not added
to totals. **44 separate integration checks passed = 9 ingestion + 8 model + 9 scoring +
7 explanation + 11 case workflow**. Frozen 2,000-row inference and SHAP compatibility passed.

No remaining failing local check is being waived. Final scope/secret review, remote publication
and hosted CI remain the release gate for this feature branch. No merge or deployment is included.

Final read-only main schema checks (`alembic current`, `alembic check`, SQLAlchemy table
inspection) passed: **0001_initial_schema (head)**, no new upgrade operations and **18 domain
tables**. No migration or seed was run against main. Remote main was verified at 0ad65b4;
the Phase 8 remote branch did not yet exist at the pre-publication check.

## Implementation checkpoint publication

[377d5c4d3ec553a671ea1164508145efc88790bb](https://github.com/axyz97836/SentinaAI/commit/377d5c4d3ec553a671ea1164508145efc88790bb)
(`feat(investigations): add atomic alert and case workflows`) contains the complete locally
verified implementation, tests, integration workflow and local browser harness correction.
The staged file list/diff and whitespace/secret checks passed. No ignored evidence, credential,
private dataset or model artifact was staged. An explicit push to
`HEAD:refs/heads/feat/phase-08-alerts-cases` succeeded and `git ls-remote` returned the exact SHA.
The branch tracks origin and the working tree was clean after that checkpoint. No Git
authentication or synchronization error occurred; main remains the Phase 7 merge 0ad65b4.

The post-commit secret scan covered **162 working files and 270 reachable historical blobs**
plus API/worker logs, with no matches under the documented scan limits.
[Hosted ARM64 workflow 40824299746](https://github.com/axyz97836/SentinaAI/actions/runs/40824299746)
completed successfully against that exact implementation commit, as verified below.

## Resume verification and completed hosted CI (2026-10-29)

Resumed the existing branch and filesystem without resetting or reconstructing work. Local
HEAD and the remote feature branch were both **377d5c4d3ec553a671ea1164508145efc88790bb**.
The sole uncommitted change was the publication section above; it is preserved. Remote default
HEAD and `refs/heads/main` remain **0ad65b44c8747632724b1f57e3aa5f0c79fa27ad**, the Phase 7 merge.
Origin is still exactly `https://github.com/axyz97836/SentinaAI`.

Direct GitHub REST reads of `/actions/runs/40824299746` and `/jobs?per_page=100` confirm
**completed / success, attempt 1**, updated **2026-10-29T05:49:26Z**. This workflow contains
one job, [foundation](https://github.com/axyz97836/SentinaAI/actions/runs/40824299746/job/123283668611),
with all applicable checks implemented as steps. Every verification and cleanup step succeeded;
no job was failed or cancelled. Only the conditional failure-diagnostics step was skipped,
as expected on success. Downloaded logs confirm the counts independently of the saved watcher.

| Hosted check at 377d5c4 | Actual completed result |
|---|---|
| Compose, stack, runtime | Configuration/credential metadata, builds/startup and API/worker ARM64 fingerprints PASS |
| `make database-check` | **354 passed**, one existing warning, **75.58 s**; guarded disposable database |
| CI-local `make migrate seed` | PASS on the disposable hosted stack; does not touch the owner's local data |
| `make backend-check` | Ruff PASS, **80 files** formatted; mypy **52 modules** PASS; **247 passed**, 354 deselected, four existing warnings, **7.63 s** |
| `make frontend-check` | Lint, strict types and production build PASS |
| `make infra-check` | **5 groups passed**: restricted PostgreSQL, authenticated Redis, private/bucket-scoped S3, worker |
| `make outage-check` | **8 groups passed**, including PostgreSQL/Redis/storage outage and recovery, liveness and port isolation |
| Ingestion / model / scoring / explanation / case integration | **9 / 8 / 9 / 7 / 11 passed**; each disposable stack removed |
| `npm test` (Playwright) | **8 passed, 0 failed, 4.5 s**, two CI workers, zero retries |
| `npm audit --audit-level=high` | **0 vulnerabilities** |
| `make down` and workflow completion | PASS; final job/run conclusion **success** |

**609 distinct application tests passed = 354 database + 247 backend + 8 browser.**
**44 separate integration checks passed = 9 + 8 + 9 + 7 + 11.** These agree with the final
local totals; local and hosted executions are not added together as extra test coverage.
The full Python dependency audit and frozen 2,000-row compatibility test remain valid local
evidence, not checks falsely attributed to this hosted workflow.

### Browser failure resolution

All eight original browser tests passed in hosted CI, including authentication/HttpOnly/CSRF,
320/375/768/1024/1440px navigation and keyboard checks, live API links and automated WCAG AA
checks. Auth completed in **724 ms**; the previously failing 320/375/768px tests completed in
**728/545/716 ms**. `page.goto("/")` navigation timeouts did not recur. The existing final
isolated local run also passed all eight in **13.3 s**. The diff confirms that only local worker
selection changed: CI concurrency, original timeout, zero retries, assertions and all tests
remain intact. Local machine overload remains a capacity limitation, not a waived failing test.
Browser coverage is the existing foundation/auth suite; the future case UI is not implemented.

### Security, concurrency, audit integrity and final review

The completed review is retained, with a focused resume check of route/auth dependencies,
input schemas, tenant joins, transaction ownership, row locks, exact retries, immutable evidence
reads and their database tests. Six PostgreSQL race scenarios and nine event/audit insertion
failure cases are included in the passing database total. Existing schema tests deny application
UPDATE/DELETE of case events and audit logs and deny DDL. The hosted case workflow independently
passes real HTTP races, all three roles, foreign-org denial, safe validation, SQL event/audit
reconciliation, unchanged historical score/explanation snapshots and sanitized runtime logs.
No unresolved finding requires another code change or rerunning unchanged expensive local suites.

**Ponytail Review verdict: Ship for owner review.** Expected load remains the bounded demo
with one worker. Production throughput, external penetration testing, future case UI and public
launch controls are not claimed. Pagination is stable for fixed data, not a frozen concurrent
export. Existing deprecation warnings remain; no assertion or security control was waived.

Resume commands also checked `git status`, history/remotes/diff, `git ls-remote`, service status,
saved logs, approved-document SHA-256 hashes and the existing secret scanner. All **six main
services are healthy**; no disposable test stack remained. All **11 protected hashes match**.
The secret scan again covered **162 working files, 270 reachable historical blobs and API/worker
logs**, with no findings. Limits remain known local secret values and common token/private-key
patterns; this is not exhaustive secret detection or a penetration test.

The first read-only `alembic current` attempt in the application container correctly failed
because `migration_db_password` is absent. Repeating through the existing migration service
with `docker compose --env-file .env -f infra/compose.yaml -f infra/compose.database.yaml
--profile database run --rm --no-deps migration alembic current` returned
**0001_initial_schema (head)**. No migration, seed, credential regeneration or main-data reset
was executed. The prior no-drift/18-table comparison remains valid; no schema files changed.
Sandbox access initially blocked system Git and GitHub DNS; approved external execution
resolved those tool restrictions. No Git authentication or synchronization failure occurred.

Evidence is preserved in ignored `.local/phase8-implementation-ci-final.json` and the
mode-0600 `.local/phase4-ci-40824299746.zip` archive (legacy downloader filename), alongside
the previously listed local logs. Only this report changes during the resume task. The eleven
approved documents, Signal Atlas Design Pack, implementation, tests, dependencies, seed and
private data are unchanged. The final handoff supplies the report commit SHA, verified remote
ref and its independently completed hosted workflow result. Owner review/merge and any next
phase remain separate decisions.
