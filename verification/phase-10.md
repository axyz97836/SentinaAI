# Phase 10 — Transactions and explanation interface

Status: **all mandatory local gates passed; owner-accepted residual availability
risk retained; verified feature-branch publication and hosted CI pending**. The original database lock timeout was not
reproduced and its cause is not proven (2026-11-12). Earlier results below are retained
as historical checkpoints. See the final polish section for current results.
This is not a Phase 10 completion claim.

## Authority and starting point

The owner authorized only `/transactions`, `/transactions/upload` and
`/transactions/[id]`, followed by a functional desktop/mobile visual-review
checkpoint before extensive polishing. No Phase 11, deployment or merge is authorized.

Branch: `feat/phase-10-transactions-ui`. Base:
`af6cea67c87513f481dbdc0e4f54d707e2f6de93`, the verified Phase 9 PR #9 merge.
Phase 9 checkpoint `92772db61a4adf8aaf63dadc78e49345d79afe46` is an ancestor.
Origin remains `https://github.com/axyz97836/SentinaAI`.
The existing implementation was preserved across the interruption. No new commit
or push has yet been made for Phase 10.

All eleven protected-document hashes passed
`shasum -a 256 -c verification/approved-documents.sha256` on 2026-11-10.
The Signal Atlas design pack, credentials, main database, model mathematics and
backend application source remain unchanged.

## Implementation and API boundaries

- Organization-scoped server-rendered transaction listing, reference/customer
  search, risk/date filters and opaque forward cursors. Filter changes omit the
  prior cursor. Desktop tables become mobile summary cards.
- Synthetic transaction form uses canonical fields, UTC event times, decimal
  amount strings, native constraints and associated validation messages. Real
  201/replay-200 responses navigate to persisted detail; conflicting IDs and
  missing active models remain errors.
- CSV upload is limited to synthetic data under the current backend provenance
  policy. The UI exposes TRAINING only to ADMIN; backend RBAC remains authoritative.
  Durable job URLs survive reload. Polling is non-overlapping, cancelled on
  unmount/hide, resumed on visibility, and stopped at terminal status.
- Detail shows the original score/model, actual component values/weights/points,
  recorded rule states and parameters, and genuine supervised-only SHAP log-odds.
  COMPLETE/PARTIAL labels and the approved screening caveat remain explicit.
  Alert/case identifiers have no links to unavailable interfaces.
- Existing server-side session verification, focus revalidation, HttpOnly cookies,
  memory-only CSRF proofs and mobile drawer behavior are retained. The proxy adds
  only transaction, explanation, ingestion and job paths, not an admin wildcard.
- No UI library, font, ML dependency or other package was added.

Endpoints: `GET/POST /api/v1/transactions`, `GET /api/v1/transactions/{id}`,
`GET /api/v1/transactions/{id}/explanation`, `POST /api/v1/ingestions`, and
`GET /api/v1/jobs/{id}`, alongside the existing authentication endpoints.

## Integration recovery evidence

The guarded driver is `node infra/scripts/check-ingestion.mjs --transactions-ui`
(`make transactions-ui-check`). It uses the existing disposable
`sentinelai-ingestion-tests` project, separate database/volumes, production Next.js
on loopback port 18010 and the frozen Linux ARM64 scoring runtime. The main stack
is not reseeded or reset. Existing credentials are read from ignored restrictive
storage and checked unchanged. No authentication traces, videos, password-bearing
DOM snapshots or automatic failure screenshots are enabled.

Earlier preparation defects were corrected without backend changes:

1. Chromium rejected the driver's seconds-bearing `datetime-local` fill string
   with `Malformed value`. A minimal browser reproduction confirmed that the
   minute-precision representation used by these fixtures is accepted. Application
   UTC conversion remains unchanged.
2. Browser HTML patterns require escaped hyphens under current Unicode-set syntax.
   A minimal reproduction showed the unescaped pattern did not reject an invalid
   reference. The form/search patterns now escape the hyphen; backend validation
   was never removed.
3. Error locators now target the application main region rather than also matching
   Next.js's empty route announcer. Assertions and timeout limits are unchanged.
4. Anonymous transaction routes return server HTTP 307 before rendering protected
   records. An early route loading boundary was removed to retain that behavior.

The last pre-recovery run passed **11 integration groups**: anonymous redirects,
real analyst access and no-model feedback, input validation, job-level FAILED,
real model training/activation, PARTIAL scoring, identical/conflicting replay,
COMPLETE evidence, list/filter/cursor behavior, durable CSV scoring, and partial-row
conflict handling. It then stopped at the invalid SCORING-row assertion.

Root cause of that latest failure: the new test expected a job-level `FAILED` for
a row whose amount was `NaN`. The existing scoring worker finishes row processing
as `SUCCEEDED` with `failed_rows`, even when all rows fail. TRAINING validation has
different whole-job rejection semantics. The test now requires the scoring
contract exactly: `SUCCEEDED`, zero processed rows, one failed row, `INVALID_AMOUNT`,
no matching persisted transaction, and a visible “Completed with row errors”
message. The UI additionally states that no rows were accepted. The earlier
genuine missing-model job-level FAILED check remains intact.

Safe prior output is retained only in ignored local evidence. The final rerun
observed exactly `SUCCEEDED`, zero processed rows and one failed row, and passed
the error-code, absent-transaction and visible-feedback assertions.

Subsequent recovery found a browser-driver issue at the first axe scan:
`browser.newPage()` creates an owned convenience context, whereas axe needs an
explicit context for its analysis pages. A credential-free static-page reproduction
returned `Please use browser.newContext()`. Using `browser.newContext()` followed
by `context.newPage()` resolved it. No accessibility rule or timeout was relaxed.

Ponytail review identified a real upload lifecycle issue: the existing secure
workspace hides/unmounts children during session revalidation. A job accepted after
initial page load could lose its in-memory ID when those children remounted.
The upload component now restores the validated UUID from the durable URL. A
pagehide/pageshow test checks the queued job survives that session-check cycle,
in addition to reload and worker-pause tests.

The request error mapping now uses the backend's exact `CSRF_REJECTED` code.
The driver deliberately changes the proof on one real form request, requires the
backend denial and specific safe feedback, and confirms no transaction was created.
It does not mock a successful API response.

## Verification status

- `make frontend-check`: final frontend ESLint, strict TypeScript and production
  build passed after the mobile upload-label correction.
- Protected documents: 11/11 hashes match.
- Whitespace check: `git diff --check` passed on recovery inspection.
- Final exact-file transaction UI integration:
  `/usr/bin/time -p node infra/scripts/check-ingestion.mjs --transactions-ui`:
  **18 groups passed, 0 failures, real 153.79 s**, including the CSRF-message
  assertion and mobile upload-label correction. The disposable resources were
  removed successfully. No retries, skipped assertions or increased timeouts.
- Production Phase 9 browser regression: **23 passed, 0 failed, 11.9 s**, using
  `cd frontend && npm test`. Only upload help text changed afterward; authentication,
  shell, navigation, fonts and global CSS are unchanged since this run.
- Focused backend regression: **65 passed, 1 existing Starlette deprecation warning,
  1.69 s**; command:
  `docker compose --env-file .env -f infra/compose.yaml --profile checks run --rm --no-deps backend-checks pytest -p no:cacheprovider tests/test_scoring.py tests/test_auth_primitives.py`.
- `make infra-check`: **5 groups passed** (restricted PostgreSQL, authenticated Redis,
  private S3 access, bucket-scoped S3 identity and authenticated Celery).
- `cd frontend && npm audit --audit-level=high`: **0 vulnerabilities**.
- Post-capture non-disclosing scanner: **222 working files, 334 historical blobs and
  API/worker logs**, no findings. Scope is known local
  secret values and common token/private-key patterns, not exhaustive detection.
- Current credential-value checks against the three new UI/browser/backend logs:
  **no matches**. The integration separately checks API/worker logs and screenshot
  bytes and verifies the existing credential file is byte-for-byte unchanged.
- Final screenshot inspection: all **8** inspected; no clipping, overlapping
  content or page-level overflow observed. The long mobile purpose option found
  in the first capture was shortened; its complete meaning is now wrapping help
  text associated with the select.
- Full hosted Phase 10 regression/CI: not run; publication awaits the required
  owner visual checkpoint and verified final work.

## Limitations and remaining work

Public datasets are rejected by current backend policy. Training uploads only
validate a dataset; model activation has no new frontend control. Related alert
and case statuses are not supplied by this API, so the UI displays identifiers
only. Synthetic screening is not fraud proof or a calibrated probability.
Manual assistive-technology and production-load coverage are not claimed.

Phase 9's verified baseline remains 354 database + 247 backend + 23 browser tests
and 44 integration checks; these are historical baseline results, not new Phase 10
passes. Backend numerical behavior and protected planning/security files are unchanged.

## Changed-file inventory

New frontend files:
- `frontend/app/_components/transaction-evidence.tsx`
- `frontend/app/_components/transaction-filters.tsx`
- `frontend/app/_components/transaction-form.tsx`
- `frontend/app/_components/transaction-upload.tsx`
- `frontend/app/_lib/protected-api.ts`
- `frontend/app/_lib/transaction-request.ts`
- `frontend/app/_lib/transactions.ts`
- `frontend/app/transactions/page.tsx`
- `frontend/app/transactions/upload/page.tsx`
- `frontend/app/transactions/[id]/page.tsx`

Existing frontend files changed: `frontend/app/_components/workspace.tsx`
(working transaction navigation only), `frontend/app/dashboard/page.tsx`
(truthful availability text), `frontend/app/globals.css`, `frontend/next.config.ts`,
and `frontend/tests/workspace.spec.ts` (assert both real navigation destinations).

Verification infrastructure: new `infra/scripts/check-transactions-ui.mjs`, scoped
extensions to `infra/scripts/check-ingestion.mjs`, `Makefile` and
`.github/workflows/ci.yml`. The existing 23 browser checks remain enabled; the new
integration target is added after browser installation in CI. No timeout was raised.

Evidence: this report and the eight PNGs under `verification/phase-10/`.
Ignored diagnostic logs, credential files and disposable Compose configuration are
not deliverables and must not be staged.

## Final functional evidence and visual review

The 18 groups cover server HTTP 307 guards; real analyst form login; empty state;
canonical field validation; no-active-model feedback; genuine job-level FAILED;
real isolated model training/activation; matching persisted scoring and PARTIAL
evidence; identical replay and conflicting IDs; COMPLETE rules/SHAP; search, date,
risk-band and cursor filters; queued-job reload/session-remount/worker recovery;
successful scoring CSV; mixed and all-invalid row outcomes; invalid headers and
oversized file; ADMIN training and non-admin denial; real CSRF/Origin rejection;
responsive/accessibility screenshots; cross-organization transaction/explanation/job
denials; logout/revoked-cookie denial; and credential-safe outputs.

Accessibility evidence includes **24 layout checks** (four screens × 320, 375,
768, 1024, 1440 and 1920px) and **8 axe scans with zero violations** (four screens
at desktop/375px, WCAG 2A/2AA/2.1AA/2.2AA tags). Native labels, inline errors and
focus, mobile drawer Tab/Shift+Tab containment, Escape/focus restoration, reduced
motion and fallback-font/200% text reflow were exercised. These checks are not a
formal WCAG certification or an exhaustive assistive-technology audit.

All captures are full-page screenshots of the actual production frontend with
isolated synthetic records and real persisted scores. They are not mockups. The
fixture records were removed with the disposable stack; they were never added to
the main development database. The main local frontend was refreshed to the tested
image, and its health check passed; the main backend/data were preserved.

| Screen | Desktop (1440px) | Mobile (375px) |
|---|---|---|
| Transactions | [Desktop](phase-10/transactions-1440.png) | [Mobile](phase-10/transactions-375.png) |
| Submission form | [Desktop](phase-10/submission-1440.png) | [Mobile](phase-10/submission-375.png) |
| CSV upload and real row-error job | [Desktop](phase-10/upload-1440.png) | [Mobile](phase-10/upload-375.png) |
| Persisted explanation | [Desktop](phase-10/detail-1440.png) | [Mobile](phase-10/detail-375.png) |

Comparison with the approved Phase 9 screenshots and Signal Atlas pack: the same
self-hosted typefaces, navy text, paper/canvas surfaces, emerald actions, sidebar,
account panel and footer remain. Operational pages use restrained borders, square
controls, a navy table header, textual risk labels and numbered evidence sections.
The large editorial mountain artwork is not repeated in dense operational content.
Tables become stacked cards on mobile; long IDs wrap rather than overflow.

Visual limitations for owner feedback: the inline form plus record list makes a
long mobile page, and the detail page deliberately exposes a substantial amount of
evidence. Compactness and spacing can be refined after owner review. No speculative
dashboard metrics or unavailable controls were added.

## Ponytail Review and handoff

What this change does: it connects three protected transaction screens to the
existing scoring and ingestion contracts. It presents persisted evidence and
durable outcomes without changing backend calculations or authentication behavior.

Review traced server cookie forwarding and redirects, mutation CSRF proofs,
organization-scoped APIs, 200/201/409/422 handling, canonical timestamp/amount inputs,
opaque cursor preservation, upload purpose enforcement, polling cancellation and
remount behavior, COMPLETE/PARTIAL rule/SHAP semantics, mobile layout, component
reuse and credential-safe diagnostics. Load assumption: the existing demonstration
application, bounded list pages, one non-overlapping poll per visible active job,
and existing backend 10 MiB/10,000-row limits.

Confirmed findings were fixed and exercised: native pattern escaping, the
session-remount job ID loss, exact CSRF error mapping, and mobile select clipping.
The latest CSV failure was a new test-contract mismatch; the backend stayed intact.
The axe failure was a test-driver context error; scans now run and pass.
No unresolved material issue was found within this checkpoint's reviewed scope.

**Verdict: ready for owner visual review; Phase 10 is not yet ready for final PR
review/publication.** Full hosted regression, the broader final security/regression
gate and owner visual acceptance remain. Production load testing and an external
security audit were not performed. The unchanged Phase 9 real elapsed-expiry evidence
is retained rather than incorrectly counted as a fresh Phase 10 elapsed-time run.
The local browser driver uses existing Node 22.11.0; the authoritative build uses
the pinned Node 22 container, and hosted CI will use the configured Node 22 runtime.

At handoff, HEAD remains `af6cea67c87513f481dbdc0e4f54d707e2f6de93`, the Phase 9
merge. `git ls-remote` confirmed that same `origin/main` and no remote Phase 10
branch. Changes are preserved uncommitted and unstaged for the required visual
checkpoint. **No new commits, pushes or Phase 10 CI run exist yet.** Phase 9's
[successful hosted run](https://github.com/axyz97836/SentinaAI/actions/runs/42090607813)
is historical evidence only, not a CI pass for these new files. No merge, deployment,
credential rotation or Phase 11 work occurred.

## Owner-approved visual polish — 2026-11-12 continuation

The owner explicitly approved the existing Phase 10 visual direction and authorized
only responsive disclosures, density/hierarchy refinements, ingestion status clarity
and compact operational session spacing. Work remains on the existing uncommitted
`feat/phase-10-transactions-ui` implementation; no reset or reconstruction occurred.
The owner requires another visual-review stop after these refinements.

### UI refinements

- Submission opens from the existing action using `aria-expanded`/`aria-controls`.
  Opening focuses the first input; closing restores the trigger. The mounted hidden
  form retains its draft and validation/error state. The trigger cannot collapse an
  in-flight submission. The existing `?new=1` intent opens the inline form, including
  the deliberately expanded submission screenshots.
- Below 768px, Filters is a native disclosure. Applied filters or an invalid query
  keep it open initially; an active label does not invent a result count. Desktop
  controls remain visible. GET query state and the opaque cursor contract are unchanged.
- Risk components, rule evidence and supervised SHAP use independent native details.
  Components start open on mobile; longer rule/SHAP sections start closed. Desktop
  sections remain open. Identity, score/band, model, status/caveat and missing-evidence
  notices remain outside the collapsible bodies. Without JavaScript all evidence
  is initially open and native disclosures remain usable.
- Desktop rows have less padding, stronger tabular amounts/scores, real reference
  links with an arrow cue, and restrained hover/focus-within treatment. Mobile cards
  pair amount and score and retain a separate textual risk band.
- Job status styling follows only persisted statuses. Row-error success remains
  “Completed with row errors”; actual FAILED stays an alert. Four desktop/two mobile
  metric columns show returned counts. Row errors have a distinct always-visible
  section with actual row numbers/codes, bounded sanitized summaries, and no raw rows.
- A single scoped operational-session spacing token compacts the panel on transaction
  routes. The Phase 9 overview/login shell, authentication logic and controls remain
  unchanged by this polish. No framework, package, font or backend change was added.

Polish files: new `frontend/app/_components/responsive-disclosure.tsx`; refinements
to `transaction-form.tsx`, `transaction-filters.tsx`, `transaction-evidence.tsx`,
`transaction-upload.tsx` in that same components directory, `frontend/app/transactions/page.tsx`,
`frontend/app/globals.css`, `infra/scripts/check-transactions-ui.mjs`, this report,
and eight `*-polished.png` captures. Earlier implementation files are listed above.

### Focus recovery and review findings

The first new outline check ran before the scheduled focus move completed. It now
requires the input to be focused before asserting its computed outline. No timeout
was changed. The current run observed **solid / 3px / rgb(4, 106, 56)** and passed
draft preservation, validation-message preservation and real backend-error behavior.

Ponytail review found one responsive-focus edge case: resizing a desktop filter
while its input was focused could collapse the input on mobile and strand focus.
The native disclosure now moves focus to its summary only when the breakpoint change
would hide the focused descendant. A dedicated resize assertion verifies this.
The previous 21-group run completed before this final fix was built; the fresh complete
run below passed against the final build. Native disclosure state is retained across
breakpoint changes, and independent evidence panels do not close each other.

### Current verification

- Final-code `make frontend-check`: ESLint, strict TypeScript and production build PASS.
- Prior polished integration: **21 groups passed in 154.45 s**; historical, before
  the final resize-focus build and stronger outline/validation-preservation assertions.
- Exact-current integration: **21 groups passed, 0 failures, real 154.13 s** using
  `/usr/bin/time -p node infra/scripts/check-ingestion.mjs --transactions-ui`.
  The corrected keyboard test observed the solid 3px emerald outline; value and
  validation-message preservation, genuine backend failure feedback, and resize
  focus restoration all passed. The guarded disposable stack was cleaned up.
- Full production browser suite: **23 passed, 0 failed, 11.8 s**, `cd frontend && npm test`.
  This includes real login/logout, revocation/revalidation, mobile drawer keyboard
  behavior, legal navigation, no-JavaScript sign-in, font fallback and reduced motion.
- Accessibility: **10 axe scans, zero violations**: eight screenshot-state scans
  plus expanded mobile evidence and active-filter scans, with WCAG 2A/2AA/2.1AA/2.2AA
  tags. Independent disclosure, active-state/cursor, no-JavaScript evidence and
  focus assertions are separate checks within the 21 integration groups.
- Responsive: **24 layout checks** across four screens at 320, 375, 768, 1024, 1440
  and 1920px. No page-level horizontal overflow. All eight polished images inspected.
- `make infra-check`: **5 groups passed**. `cd frontend && npm audit --audit-level=high`:
  **0 vulnerabilities**. No dependency or lockfile changes.
- Post-capture non-disclosing scan: **231 working files, 334 HEAD-reachable historical
  blobs and API/worker logs**, no findings under its known-value/common-pattern scope.
  The integration checks runtime logs, every captured image for credential bytes,
  and byte-for-byte preservation of the restrictive existing credentials file.
  A final known-value check of the four polish integration/browser/infra/audit logs
  also found no current credential matches. All eleven protected-document hashes
  matched again at handoff; staging was empty and `git diff --check` passed.
- The earlier **65 focused backend passes** remain valid for unchanged backend code;
  they were not rerun or counted as new polish results. No scoring/SHAP/authentication
  implementation, schema, migration, model artifact or approved document was edited.
- Protected planning/security files, authentication protections, numerical scoring,
  model artifacts, SHAP generation and demo credentials remain unchanged.

Final publication and hosted CI remain future gates after the requested polished
visual-review checkpoint. No merge, deploy or Phase 11 action is authorized.

### Polished screenshots and visual comparison

| Screen | Desktop 1440px | Mobile 375px |
|---|---|---|
| Transactions | [transactions-1440-polished.png](phase-10/transactions-1440-polished.png) | [transactions-375-polished.png](phase-10/transactions-375-polished.png) |
| Open submission form | [submission-1440-polished.png](phase-10/submission-1440-polished.png) | [submission-375-polished.png](phase-10/submission-375-polished.png) |
| CSV and actual row-error job | [upload-1440-polished.png](phase-10/upload-1440-polished.png) | [upload-375-polished.png](phase-10/upload-375-polished.png) |
| Persisted explanation | [detail-1440-polished.png](phase-10/detail-1440-polished.png) | [detail-375-polished.png](phase-10/detail-375-polished.png) |

These are actual production-frontend captures with authorized isolated synthetic
records. The original eight screenshots remain intact. Submission was deliberately
expanded before capture. Additional browser assertions demonstrate filters opening,
active query preservation, independent rule/SHAP expansion, and important notices
remaining visible; no mocked successful API responses were introduced.

Compared with the accepted first captures, mobile listing reaches records sooner
because empty filters and the form are collapsed. Amount/score hierarchy is clearer,
desktop rows are tighter, job counts use the requested grid, and row errors are
separated visibly. Mobile explanation starts with components open and rules/SHAP
closed while retaining the score, identity, model, COMPLETE/PARTIAL status and caveat.
No color/font/branding redesign or unsupported information was introduced. All eight
images were inspected for wrapping, clipping, overlap and consistent spacing; no
material visual defect remains. Full-page captures remain long when the owner-requested
form is expanded above all 18 fixture records; the working collapse action removes
that form height without discarding its current inputs.

### Final scoped Ponytail Review

What this change does: it reduces mobile information density through native
disclosures, improves numerical and job-state hierarchy, and retains real transaction
integration. Security-sensitive submission, polling and server verification paths
remain unchanged by the polish.

Reviewed disclosure lifecycle and breakpoint behavior, draft/error preservation,
keyboard focus, server-rendered/no-JavaScript evidence, semantic table/card links,
status/error truthfulness, bounded errors, styling scope and component reuse.
The resize-focus issue was fixed and verified. The early outline failure was test
ordering, corrected by waiting for actual focus rather than relaxing its assertion.
No unresolved material finding remains in this reviewed polish scope.

**Verdict: ready for final owner visual approval.** This is not permission to merge
or deploy, nor a claim of complete Phase 10 hosted verification. Remaining limits:
Chromium-focused automation, no exhaustive assistive-technology certification,
no production-load/penetration test, and the already documented demo/public-dataset
restrictions. Draft preservation covers collapse/reopen in the mounted form; drafts
are not stored across reload, logout or security-driven workspace unmounting.

At this polished checkpoint all implementation is preserved on
`feat/phase-10-transactions-ui`, still uncommitted and unstaged. No Phase 10 commits,
pushes or hosted CI runs were created. Final phase-wide regression/security gates,
verified publication and successful hosted CI remain outstanding after owner review.

## Final owner approval and mandatory regression stop — 2026-11-12

The owner explicitly approved the eight polished screenshots and authorized final
verification, commit and push only to `feat/phase-10-transactions-ui`. The owner also
required stopping on a critical test failure without weakening assertions or hiding
failures. The approved design and screenshot files were not edited during this pass.

The current frontend was compared with the tested running production image: **41
application/configuration/font files matched byte hashes**. The existing passed
21-group UI integration, 23-test production browser suite, 10 accessibility scans,
24 responsive checks and frontend build/lint/types remain valid for unchanged code.
No expensive screenshot-generating UI run was repeated merely to resume publication.

The standard `make check` aggregate now includes the already verified
`transactions-ui-check` target. `make -n check` confirmed the wiring and
`git diff --check` passed. No application behavior was changed in this final pass.

### Observed final gates

| Command | Actual result |
|---|---|
| `make model-runtime-check` | PASS, exit 0; API and worker authoritative ARM64 runtime checks |
| `make backend-check` | PASS, exit 0; Ruff, formatting and mypy; **247 passed, 354 deselected, 4 existing warnings, 21.76 s** |
| `make database-check` | **FAIL**; **353 passed, 1 failed, 1 warning, 188.32 s**; pytest exit 1, Make exit 2 |
| `backend/.venv/bin/python -m pip_audit --disable-pip --no-deps -r backend/requirements-dev.txt` | PASS, exit 0; **No known vulnerabilities found** for the complete unchanged development/runtime lock |
| Outage, ingestion, model, scoring, explanation and case targets | NOT RUN in this final sequence: stopped after the mandatory database failure |
| Final commit/push and hosted Phase 10 CI | NOT PERFORMED because the required local gate failed |

### Exact blocker

Failed test:
`tests/database/test_attribution_scoring.py::test_concurrent_replay_retains_one_attribution_snapshot`.
It submits the same transaction through four concurrent workers and requires one
creation, identical replay results and a persisted genuine attribution snapshot.

One worker raised `sqlalchemy.exc.OperationalError`, wrapping PostgreSQL
`psycopg.errors.LockNotAvailable: canceling statement due to lock timeout`, at
`backend/app/scoring/service.py:110`. The failing query was the organization-scoped
`SELECT organizations.id ... FOR UPDATE`; SQL parameter values were hidden.
`backend/app/database.py:52` configures `lock_timeout=5000` milliseconds.

The scoring service intentionally serializes each demo organization's scoring work
under that row lock, including model/attribution work before the caller commits.
The waiting concurrent replay could not acquire it within the configured five seconds.
The available trace does **not** establish why the holder exceeded that window;
resource contention, cold work or another cause has not been proven. The failure is
not classified as harmless or waived. No rerun was used to erase it, no timeout was
increased, no assertion was weakened, and no scoring/authentication code was changed.

Private, restrictive evidence remains in ignored local storage:
`.local/phase10-final-database-check.log`, `.local/phase10-final-gates.log`,
`.local/phase10-final-backend-check.log`, and `.local/phase10-final-python-audit.log`.
The database driver redacts configured secrets/hashes and hides SQL parameters.
Do not stage these logs or the temporary orchestration helper.

### Preserved state and review verdict

The disposable `sentinelai-db-tests` stack was removed by its existing cleanup path.
All six main services were observed healthy afterward. Existing credentials, main
database volumes, model artifacts, approved visuals and all eleven protected
documents were preserved; all protected-document hashes matched again. Staging is empty.

Ponytail final-gate finding: concurrent replay/attribution integrity verification is
unresolved because one required worker failed on the organization lock. The frontend
review remains valid, but a full-phase Ship verdict cannot be issued while this gate
fails. Further investigation needs actual lock-holder timing/resource evidence, not
a longer timeout or a guessed backend change.

**Phase 10 is NOT complete or ready for owner PR review.** Work remains uncommitted
on `feat/phase-10-transactions-ui`, at base HEAD
`af6cea67c87513f481dbdc0e4f54d707e2f6de93`. No final Phase 10 commit, remote feature
HEAD or hosted CI URL exists. Nothing was pushed, merged or deployed; Phase 11 was
not started. Publication stopped as explicitly instructed on the critical test failure.

## Concurrency investigation results — 2026-11-12

The interrupted full-suite instrumentation command **completed successfully**. It
was neither cancelled nor a new database failure. Its saved pytest result was
355 passed, and the private test stack was removed. The original 353-pass/one-failure
record remains preserved and has not been replaced or waived.

### Fixed configuration and observational scope

All reproductions used the guarded `sentinelai-db-tests` project and
`sentinelai_schema_test` database on `database-test`, with RAM-backed disposable
PostgreSQL storage. The existing migrations/fixture setup and original lock order
were retained. Linux ARM64, pinned image/requirements, 8 Docker vCPUs and
4,106,539,008 bytes of Docker VM memory (about 3.825 GiB) were observed. The
application pool remained size 5 with maximum overflow 10. The instrumented
connection's actual `SHOW lock_timeout` returned **5s**.

The exact test invokes four domain-service submissions through separate sessions.
Its existing fixture uses real PostgreSQL and in-memory fixture storage for model
and training-reference bytes. External S3 and HTTP request handling are not part of
this test. Existing fixture setup built its usual disposable synthetic test models;
no development model was retrained or replaced, and no model artifact, frozen
numerical fixture or dependency was modified.

Private Python hooks observed monotonic request/transaction start, connection
checkout, lock attempt/acquisition, individual model/reference/SHAP/inference stages,
SQL operation classes, commit/rollback and request completion. SQL text/parameters,
payloads, credentials, object keys and private records were not emitted. Later
instrumentation also recorded thread CPU and garbage-collection durations.
Readonly PostgreSQL sampling ran every 100 ms and retained PID/state/wait/blocker
information and lock modes only.

Connection checkout is directly timed. Commit completion and the wrapper's request
completion bound the return from the session context (which commits and closes the
session); a separate pool-checkin event timestamp was **not** recorded. Short waits
can fall between the PostgreSQL samples. These limitations are not presented as
precise measurements that were never collected.

### Executed reproductions

| Command / scope | Actual pytest outcome | Targeted concurrent submissions |
|---|---|---|
| `node .local/phase10-concurrency-runner.mjs`: exact failing test plus ten-round private probe | **2 passed**, 1 warning, **16.66 s** | 4 original-test calls + 40 probe calls |
| `node .local/phase10-concurrency-ordered.mjs`: original attribution module in normal order plus probe | **13 passed**, 1 warning, **18.04 s** | 4 original-test calls + 40 probe calls |
| `node .local/phase10-concurrency-full.mjs`: original complete database suite plus probe | **355 passed**, 1 warning, **136.33 s**; runner wall **166.92 s** | 4 original-test calls + 40 probe calls |
| `node .local/phase10-normal-observe.mjs`: invokes unchanged **`make database-check`**, external monitoring only | **354 passed**, 1 warning, **79.29 s**, exit 0; observer wall **97.08 s** | Original unmodified suite; no Python hooks or extra test |

The private repeated test ran **30 rounds / 120 concurrent submissions** across
the first three experiments, in addition to the 12 calls in the exact target test.
Each four-call round required exactly one creation and three identical replays,
a genuine persisted attribution, exactly one additional scoring result, and unchanged
earlier explanation snapshots. The verified model was reused between the ten rounds
within each probe fixture. There were no duplicates or probe assertion failures.
The normal full suite also exercised the existing atomicity, idempotency, tenant
isolation and historical-evidence tests without changing any assertion or tolerance.

### Measured lock and computation timing

All numbers below are observed milliseconds, not timeout changes or performance promises.

| Context | Original target: max holder / wait | Ten-round probe: max holder / wait | Maximum observed checkout delay |
|---|---:|---:|---:|
| Isolated target | **212.308 / 215.096** | **417.517 / 443.172** | **77.282** |
| Original module order | **73.156 / 71.081** | **98.647 / 77.031** | **23.776** |
| Full-suite instrumentation | **70.321 / 62.356** | **486.097 / 518.481** | **49.679** |

In the full-suite target, model preparation took **57.653 ms wall / 55.709 ms thread
CPU**: bundle loading 12.387 ms, reference-row loading 30.121 ms, attribution setup
4.015 ms; inference was 2.763 ms and SHAP generation 0.653 ms. In the ten-round
full-suite probe, the largest model-preparation duration was **337.178 ms wall /
315.936 ms thread CPU**. The largest recorded garbage-collection duration there
was **7.936 ms**. No observed computation approached the original five-second wait.

PostgreSQL samples showed ordinary queued `tuple` and `transactionid` waits. An
observed holder was `idle in transaction / ClientRead` while Python computed under
the existing organization lock; other calls waited on that holder/queue. No sampler
errors or blocking cycle was observed in the instrumented scenarios. This is not
a claim that all possible deadlocks have been excluded.

The unchanged-command comparison produced **834 PostgreSQL samples** and **19
resource samples**. Eleven sampled organization-lock wait rows were observed;
the largest waiting transaction age was **173 ms**. That is a sampled transaction
age, **not** an exact maximum lock-wait measurement. The monitor's connection-closed
message occurred when the successful guarded command removed its disposable server;
pytest and Make both succeeded.

### Findings, differences and remaining uncertainty

1. **Database/transaction defect:** not demonstrated. Separate connections, real
   serialization, single-result replay and atomicity tests passed in the observed runs.
2. **Long critical section:** model/reference/attribution work does occur while the
   organization lock is held. Its longest measured hold here was 486.097 ms. The
   evidence does not show which operation exceeded the budget in the original failure.
3. **Fixture/order/pool defect:** not reproduced with the original preceding fixtures,
   original module order, full suite or unchanged repository command. Checkout
   delays measured well below five seconds; the original exception arose after a
   connection had reached PostgreSQL, rather than from a pool checkout timeout.
4. **External contention:** plausible but unproven. The original failure had no
   lock-holder-stage/resource timeline. The finalization session had also launched a
   Python dependency audit, but its overlap with the failing call was not recorded.
   Diagnostic runs did not overlap other verification commands; existing main
   services/health checks remained running. The normal comparison's host one-minute
   load ranged **9.26–12.97**, so it was not an idle-host benchmark. Different total
   suite durations do not prove a causal resource explanation.
5. **Current classification:** an **insufficiently understood intermittent failure**.
   The original five-second `LockNotAvailable` remains unexplained. Passing reruns
   establish only the behavior under the measured conditions; they do not prove a fix.

No application/test correction, lock removal, retry, timeout increase, migration,
new dependency, numerical change or fixture weakening was applied. Only ignored
diagnostic helpers and this evidence report were added during the investigation.

### Evidence hygiene and next action

Private logs are retained under `.local/phase10-concurrency-*`, including the first,
ordered and full probe logs, the normal-run log, readonly PostgreSQL observations
and resource JSON. Seven log/JSON files were checked against known current local
secret values: **zero matches**, all **0600**. This is a scoped secret check, not
an exhaustive detector. No diagnostic file is staged or intended for publication.
All eleven approved-document hashes match, backend/design Git diffs are empty,
and all six main services remain healthy. Approved Phase 10 files/screenshots and
existing credentials were preserved; the main database was not reset or modified
by the investigation fixtures.

Ponytail review conclusion: there is no demonstrated cause that justifies a backend
locking change. **Publication remains blocked.** Recommended next action is to
capture an actual failing event with bounded request-stage and pool-checkin timings,
PostgreSQL blockers, and VM scheduling/throttling/pause telemetry together. The
current private probes can be extended for that targeted capture. Do not increase
the lock timeout or move model work across the established transaction boundary
without evidence and any required owner approval.

Remaining Phase 10 finalization gates were not resumed because this blocker is
unresolved. No commit, push, hosted CI run, merge, deployment or Phase 11 work occurred.
Phase 10 is **not yet ready for owner PR review**, notwithstanding the approved UI
and the newly passing normal database suite.

## Bounded final diagnostics and owner release decision — 2026-11-12

The owner authorized a predetermined final set of **three unchanged full database
runs and one original-order attribution module run**, followed by an engineering
assessment and a stop for owner decision. All four attempts completed. No extra
repetition rounds, speculative backend fixes or publication actions were added.
The existing 120-submission evidence was reviewed and retained rather than rerun.

### Protocol and instrumentation

`node .local/phase10-bounded-plan.mjs` ran the four attempts sequentially. The first
three invoke the unchanged `make database-check`; no Python probe or extra test is
loaded in those runs. The fourth invokes the original attribution module through
the existing private guarded runner, now with probe version 3. It selects only
`tests/database/test_attribution_scoring.py` and retains its original order and
assertions. The ten-round private test is not selected.

All use the existing isolated database, pinned Linux ARM64 test image, unchanged
pool configuration and **5-second lock timeout**. Docker configuration remained
8 vCPUs / 4,106,539,008 bytes memory, Engine 29.9.2. Original test-fixture setup is
unchanged; no development model, artifact, credential or main database was altered.

External PostgreSQL sampling at 100 ms records UTC anchors, backend PIDs and
transaction IDs, blocker PIDs, wait states, transaction ages and lock modes. Only
an allowlisted query category is retained, never query contents or parameters.
Host-monotonic resource samples record Docker CPU/memory statistics, guest CPU
scheduling counters/uptime, CPU/memory/I/O pressure, and database/test-container
cgroup CPU-quota/throttle/OOM counters. Known build/audit/integration process overlap
is checked. Existing main services and health checks remain running.

The focused probe adds actual pool **check-in** events, safe SQLSTATE reporting and
commit/rollback release boundaries to the existing stage timings. A UTC/monotonic
anchor aligns its timeline with external observations. Transaction-lock release is
confirmed by successful commit/rollback completion; the reported boundary is the
client-observed completion, not a separately measured kernel release instant.
The previous probe source and all earlier evidence were preserved.

### Exact outcomes

| Attempt | Command | Test result | Pytest duration | Observed command wall duration |
|---|---|---|---:|---:|
| Full 1 | `make database-check` | **354 passed**, 0 failed, 1 existing warning | **54.91 s** | **65.59 s** |
| Full 2 | `make database-check` | **354 passed**, 0 failed, 1 existing warning | **64.99 s** | **75.03 s** |
| Full 3 | `make database-check` | **354 passed**, 0 failed, 1 existing warning | **53.79 s** | **63.29 s** |
| Original module | `node .local/phase10-bounded-module.mjs` | **12 passed**, 0 failed, 1 existing warning | **6.88 s** | **17.03 s** |

Every command exited 0. These are repetitions of existing tests, not 1,074 distinct
test cases. No test was skipped/quarantined, timeout raised or automatic retry added.
The module checks genuine attribution, COMPLETE/PARTIAL behavior, historical/replay
consistency, isolation and concurrent snapshot behavior; the complete suites retain
the existing atomicity, uniqueness and organization-isolation assertions.

### Focused four-request timeline

Times are milliseconds from the focused probe's monotonic origin. Four distinct
connections were used and all four were checked back into the pool before request
completion. The outcome was **one creation and three identical replays**.

| Request / backend PID | Transaction start | Checkout | Lock attempt | Lock acquired | Commit acknowledged / release confirmed | Check-in | Request complete |
|---|---:|---:|---:|---:|---:|---:|---:|
| R1 / 155 | 1.631 | 1.896 | 2.024 | 2.357 | 64.852 | 64.878 | 64.910 |
| R2 / 157 | 3.379 | 17.700 | 17.776 | 72.200 | 75.573 | 75.588 | 75.608 |
| R3 / 158 | 3.806 | 14.697 | 14.804 | 64.990 | 68.819 | 68.838 | 68.861 |
| R4 / 159 | 8.873 | 17.560 | 17.629 | 68.912 | 72.111 | 72.130 | 72.148 |

Longest observed hold: **62.495 ms**. Longest acquisition wait: **54.424 ms**.
R1's commit interval was **64.721–64.852 ms**. Its model preparation took
**48.765 ms wall / 46.083 ms thread CPU**, including bundle load 9.530 ms, reference
row load 25.326 ms and attribution setup 3.204 ms. Inference took 2.220 ms; SHAP
generation took 0.504 ms. No database error, sampler error or rollback occurred in
this successful four-request trace. Rollback hooks were installed but are not
misreported as observed rollback timings.

The prior 120-submission probe evidence remains: 30 four-call rounds, one new score
per round, identical replay results, genuine attribution and unchanged earlier
snapshots; historical measured maxima were 486.097 ms holding / 518.481 ms waiting.
Neither those passes nor the latest trace proves the original timeout was fixed.

### PostgreSQL and resource observations

| Attempt | PostgreSQL samples | Sampled organization-lock wait rows | Largest sampled waiting transaction age | Resource samples |
|---|---:|---:|---:|---:|
| Full 1 | 591 | 16 | 176 ms | 13 |
| Full 2 | 679 | 15 | 152 ms | 14 |
| Full 3 | 556 | 15 | 244 ms | 12 |
| Module | 85 | 0 | No wait captured at the sampling instants | 3 |

The module's directly measured sub-100-ms waits illustrate the sampler's resolution
limit. Transaction age is not an exact lock-wait duration. All sampled blocker PIDs
were represented in the activity observations, with transaction IDs retained in
private evidence. Normal `tuple`/`transactionid` queues were observed; no new lock
timeout or duplicated/inconsistent scoring result was detected.

Across **42 resource samples / 77 database-and-checker metric reads**:

- No monitored unrelated build/audit/integration command overlapped the attempts.
- Sampled CPU quota was `max 100000`; `nr_throttled` and `throttled_usec` were **0**.
- Sampled `oom` and `oom_kill` were **0**; guest CPU-steal counters were **0**.
- Peak guest PSI `some avg10` values were **3.51 CPU**, **0 memory**, **0.30 I/O**.
  Runnable-process observations reached 11; blocked-process observations reached 1.
- No resource sampling error was recorded. Expected sampler disconnects accompanied
  successful disposal of the temporary database; they were not test failures.

These observations describe the new attempts only. They cannot reconstruct the
original event, exclude every short host/hypervisor scheduling pause, or establish
resource contention as its cause. Resource sampling is coarser than request timing,
and the normal running services/host workload were not artificially stopped or throttled.

### Release assessment and recommendation

**Classification: nonreproduced intermittent failure with documented residual risk.**
There is neither a demonstrated-and-corrected root cause nor a currently reproduced
unresolved defect. The original trace proves a failed five-second lock acquisition;
it does not identify the exact holder stage or prove a single holder occupied the
entire interval. No reproducible correctness or security defect was demonstrated.
All measured concurrent outcomes retained exact-once result/attribution semantics.

Residual risk remains an intermittent scoring/replay request error if the organization
lock cannot be acquired in time. Its recurrence rate cannot be estimated reliably
from these non-independent runs. No data-corruption finding was observed, but that
is not a universal proof of absence. No backend change is justified by the current
evidence, and changing lock/transaction semantics would still need separate approval.

**Recommendation:** for this demonstration-scale project, propose **explicit owner
acceptance of the documented residual availability risk**, followed by the remaining
Phase 10 gates. This is proportionate to three consecutive unchanged full-suite passes,
the original-order module pass, preserved atomicity/idempotency/isolation checks,
and the prior 120-submission evidence. More identical reruns alone have diminishing
diagnostic value when no failing event is captured.

Acceptance should retain the original five-second timeout and concurrency test,
retain the original failure/evidence, require the remaining regression/security gates
and final hosted CI to pass, and reopen the blocker if the failure recurs. It is not
a production reliability claim, deployment approval or automatic waiver. If the owner
requires the cause to be proven before accepting any request-failure risk, the alternative
is further targeted capture of a recurrence before publication.

**No risk acceptance is presumed.** Stop here for the owner's release decision.
No commit, push, hosted CI run, merge, deployment or Phase 11 work was performed.
Phase 10 remains incomplete and is not yet ready for final owner PR review.

### Evidence preservation

New evidence is private under `.local/phase10-bounded-*`; previous logs remain intact.
Twenty-one helper/log/JSON files were restricted to **0600** and checked against known
current local secret values: **zero matches**. No raw transaction/credential data is
collected by the new probes, and private evidence is not staged. All eleven protected
document hashes match; backend/design diffs and staging remain empty. Existing
credentials retain restrictive permissions; main services are healthy and all test
resources were removed. Only private diagnostics and this report changed in this
bounded continuation; the approved frontend/screenshots remain preserved.

## Explicit conditional owner acceptance and finalization — 2026-11-12

The owner reviewed the bounded investigation and **explicitly accepted the documented
residual availability risk for this demonstration-scale project**, authorizing the
remaining Phase 10 verification and verified feature-branch publication. This decision
applies only to the previously observed, nonreproduced five-second PostgreSQL
organization-lock timeout. It is risk acceptance, **not proven remediation**.

The original failure and all subsequent evidence above remain preserved. Acceptance
was based on the three unchanged 354-test full-suite passes, original-order 12-test
module pass, prior 120 concurrent submissions without duplicate/inconsistent snapshots,
and absence of a demonstrated reproducible integrity, isolation or security defect.
The exact cause and recurrence rate remain unknown; no production reliability claim
is made. Existing lock timeout, concurrency assertions, transaction semantics, numerical
fixtures and SHAP behavior remain unchanged.

**Recurrence reopens the investigation and stops publication.** A new required-test,
security, numerical or transaction-integrity failure is not waived by this approval.
No retries, test skips or weakened assertions are authorized. Final hosted CI must
actually succeed before completion can be declared. This approval does not permit
merging, deployment or Phase 11 work.

Finalization resumes only gates not yet completed or whose evidence no longer applies.
The exact approved frontend and unchanged backend/database code retain the verified
results recorded above; remaining integration/outage and publication results follow
when observed. Private investigation/orchestration files will not be staged.

## Final verification resume — 2026-11-13

The usage-limit interruption did not stop the saved verification runner. Inspection
of its completion log, individual gate logs and orchestration source established
that **all six targets completed with exit 0**, including the final preservation
assertions. No target was restarted merely because the agent was interrupted.
No verification process or disposable test container remained. All six main
services were healthy. No cleanup, database reset, reseed or credential regeneration
was needed. Git remained on `feat/phase-10-transactions-ui` at the Phase 9 merge
`af6cea67c87513f481dbdc0e4f54d707e2f6de93`, with the existing implementation
uncommitted and unstaged. Fetch and remote inspection confirmed that same main
commit and no existing remote Phase 10 branch.

### Recovered completed gates

These commands ran on November 12 after conditional owner acceptance. Their actual
results were recovered on November 13; they are not claimed as newly rerun tests.

| Command | Actual result, each exit 0 |
|---|---|
| `make outage-check` | **8 assertions passed**: live/ready; PostgreSQL, Redis and storage failure/readiness recovery; private ports and loopback bindings |
| `make ingestion-check` | **9 integration checks passed**; isolated resources removed |
| `make model-check` | **8 integration checks passed**; isolated resources removed |
| `make scoring-check` | **9 integration checks passed**; isolated resources removed |
| `make explanation-check` | **7 integration checks passed**; isolated resources removed |
| `make case-check` | **11 integration checks passed**; isolated resources removed |

Ingestion verified real CSV validation and private objects, duplicate task delivery,
invalid-row rejection/deletion, missing-model refusal, row 10,001 rejection,
durability across API restart and worker pause, durable admission during a Redis
outage and publication after recovery, and storage outage recovery with durable
attempt counts and no duplicate progress. During the storage outage the observed
state was QUEUED, attempt 1, STORAGE_UNAVAILABLE and zero processed rows; recovery
and terminal assertions passed. Credential/log checks passed too.

Model integration verified real synthetic training, held-out evaluation, private
artifact integrity, explicit activation, all-role read access, administrative and
CSRF denials, durable broker/restart recovery, tamper refusal and storage recovery.
These are synthetic scenario metrics only, not real-world accuracy claims.
Scoring verified concurrent HTTP replay, CSV partial success, storage recovery,
SIGKILL recovery and exact reconciliation: **805 transactions, 805 scores, 805
alerts, 803 labels and 805 audits**, with every persisted score reproduced.
Explanation verified genuine SHAP log-odds reconciliation, COMPLETE evidence,
versioned settings, unchanged historical/replay snapshots and tenant isolation.
Cases verified all three roles, concurrent creation/version conflicts,
note-versus-resolution and dismissal-versus-opening races, SQL/audit reconciliation,
CSRF and foreign-organization denial.

### Retained evidence and fresh final checks

No application, backend, test assertion, timeout, numerical fixture, dependency,
design asset or screenshot was changed in this resume. Only this report is being
updated for publication; private preservation helpers remain ignored.

- Retained unchanged-code gates: **354 database tests** (three consecutive bounded
  passes already recorded; not 1,062 distinct tests), **247 backend tests** with
  Ruff/format/mypy, authoritative API/worker model-runtime checks, frontend
  lint/types/production build, **23 browser tests**, **21 transaction UI integration
  groups**, **10 axe scans with zero violations**, and **24 responsive layout checks**.
  The separate 12-test module and 65-test focused regressions overlap these suites
  and are not added to the unique test count.
- Saved full Python development/runtime lock audit remains valid for unchanged
  lockfiles: `backend/.venv/bin/python -m pip_audit --disable-pip --no-deps
  -r backend/requirements-dev.txt`, exit 0, **no known vulnerabilities found**.
- Fresh `make infra-check`: exit 0, **5 groups passed**, covering the restricted
  application database role, authenticated Redis, private/bucket-scoped S3 and
  authenticated Celery. Fresh `npm --prefix frontend audit --audit-level=high`:
  exit 0, **0 vulnerabilities**.
- Read-only main database version inspection returned **0001_initial_schema**.
  No migration was created or executed in this resume. Backend/schema and
  dependency diffs against the approved base are empty.
- `shasum -a 256 -c verification/approved-documents.sha256`: **11/11 matched**.
  `git diff --check`: passed. The Signal Atlas design-system diff is empty.
- Byte hashes of **43 frontend application/font/configuration files** match the
  running production frontend image. The previous 41-file comparison covered a
  narrower selection; this check additionally includes package manifests.
  **164 source/evidence/credential files**, including **all 16 Phase 10 screenshots**
  (8 original and 8 approved polished captures), are checked by a private preservation
  manifest. No screenshot-generating local suite was rerun.
- Fresh non-disclosing scan: **231 working files, 334 HEAD-reachable historical
  blobs and API/worker logs**, **zero findings**. This covers known current local
  secret values and common token/private-key patterns; it is not exhaustive secret
  detection or a penetration test. Staging/publication checks follow below.

### Final Ponytail Review

What this change does: it connects the three approved transaction routes to real,
organization-scoped APIs and presents persisted scoring/explanation/job outcomes.
It preserves the approved Signal Atlas interface and uses native responsive
disclosures to keep the mobile workflow usable.

The final review read the complete new components, routes, request helpers and
integration driver together with session/CSRF helpers, workspace lifecycle,
backend transaction/ingestion/job contracts, CI wiring and the scoped diff.
Reviewed paths include UTC/decimal validation, safe replay feedback, cursor reset,
role enforcement, cookie forwarding without caching, bounded error rendering,
non-overlapping cancellable polling, URL-based job restoration, disclosure focus,
historical evidence and supervised-only SHAP labeling. Existing frontend security
and integration evidence applies to these exact files. Load assumption remains
the bounded demonstration application, not production traffic.

**Verdict: Ship the verified feature branch, subject to successful hosted CI.**
No new must-fix or should-fix finding was identified. The prior lock-timeout event
remains a **nonreproduced intermittent availability failure with owner-accepted
residual risk**, not a fixed defect. Its cause and recurrence rate are unknown;
recurrence immediately stops publication and reopens investigation. No recurrence
was observed in the recovered gates. Timeouts and concurrency assertions are intact.

Not checked: production-load reliability, exhaustive assistive-technology support,
independent penetration testing, provider/TLS/backup controls or future-phase
features. Existing synthetic-only/public-dataset and draft-policy limitations remain.
No merge, deployment or Phase 11 work is authorized or performed.

### Publication record

Local release gates and review are complete. Final staged-file/secret review,
feature-branch push, remote SHA confirmation and hosted Actions outcome will be
recorded after actual execution. No hosted result is inferred from local passes.
