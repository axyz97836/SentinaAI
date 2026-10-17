# SentinelAI | Security Checklist.md

**Version:** 1.0, 2026-10-16  
**Status:** PRE-IMPLEMENTATION. All tests are **NOT RUN**; no security control is declared implemented, verified or passed.  
**Source:** MIKENWO quick start page 7 and the four companion security documents.  
**Target:** Local isolated synthetic-data test environment first, then a deployment/staging environment when selected.  
**Test owner:** Student developer; VS Code AI agent may help execute and report tests, but the owner verifies evidence.  
**Build identifier:** Not yet created. Record **Git commit SHA, environment, run date, tester and dependency versions** before each real execution.

## 1. How to record results

This is an **executable release gate**, not a list of assumed security features. For each row, record:

- **Setup:** Required test users, roles, fixture records, environment and preconditions.
- **Action:** Exact test to run, including both allowed and forbidden paths where relevant.
- **Expected:** What the app must do, including denial status and no partial writes when rejected.
- **Actual result:** Observed HTTP status/output, database or object-store effect and any difference.
- **Evidence:** Test file + test run/CI URL, screenshot if helpful, sanitized response/log excerpt, date and commit. **Never attach real credentials or bank data.**
- **Status:** `NOT RUN` until executed; afterwards `PASS`, `FAIL`, `BLOCKED` or `N/A` with written reason. `BLOCKED` is not a pass. `N/A` must explain scope and be approved by owner.
- **Launch blocker:** A `YES` row must `PASS` or have an explicitly reviewed justified `N/A` where it genuinely does not apply. Critical failures or unchecked core authorization prevent launch.

**Global defaults for every checklist row:** Actual result = `Not observed (pre-implementation)`; evidence = `Pending`; status = `NOT RUN`; owner = `Student developer`. Individual rows repeat these values to prevent ambiguity.

## 2. Verification matrix

### Authentication and organization authorization

| ID | Control | Owner | Setup | Action | Expected result | Actual result | Evidence | Status | Launch blocker |
|---|---|---|---|---|---|---|---|---|---|
| S-01 | Seeded demo auth | Student developer | Two fictional users and seeded accounts | Valid login, invalid password, missing user | Valid login establishes session; invalid credentials fail generically; no secret exposed | Not observed (pre-implementation) | Pending | NOT RUN | YES |
| S-02 | Cookie protections | Student developer | App served over configured production-like HTTPS | Inspect Set-Cookie and browser storage | HttpOnly, Secure in production, SameSite=Lax, correct expiry; no raw session token in JS | Not observed (pre-implementation) | Pending | NOT RUN | YES |
| S-03 | Revocation and expiry | Student developer | Logged-in synthetic user, active sessions DB row | Log out, reuse cookie; test expiry | Old token rejected on protected API; server hash revoked/purged | Not observed (pre-implementation) | Pending | NOT RUN | YES |
| S-04 | CSRF and origin defense | Student developer | Authenticated test user and valid case or admin action | Send unsafe mutation with valid, missing and invalid CSRF / Origin | Valid authorized action works; forged or missing CSRF rejected without mutation | Not observed (pre-implementation) | Pending | NOT RUN | YES |
| S-05 | Role matrix | Student developer | One ANALYST, RISK_MANAGER, ADMIN | Request admin settings/training as analyst, permitted case actions as all | Forbidden admin actions => 403; allowed case actions succeed with correct audit trail | Not observed (pre-implementation) | Pending | NOT RUN | YES |
| S-06 | Cross-organization isolation | Student developer | Isolated organizations A/B in test fixtures; each has transaction, case, job, export | Use A session to request B transaction, case, job, export IDs | All cross-org requests return 404/denied; no body/object metadata leak | Not observed (pre-implementation) | Pending | NOT RUN | YES |
| S-07 | Access removal and last ADMIN | Student developer | Two admins plus an analyst; sessions alive | Revoke membership, demote active user, then attempt to demote last ADMIN | Changes reflected on next request; last ADMIN demotion refused | Not observed (pre-implementation) | Pending | NOT RUN | YES |
| S-08 | Password and token storage | Student developer | Seeded users and session records | Inspect persisted fields and exception logs | Only Argon2id hashes and opaque session token hashes; no plaintext secrets | Not observed (pre-implementation) | Pending | NOT RUN | YES |
| S-09 | Login brute-force control | Student developer | Test environment with controlled IP/proxy settings | Repeat incorrect login over configured limit | Generic messages and actual rate limiting after documented threshold | Not observed (pre-implementation) | Pending | NOT RUN | YES |

### Input, ingestion and machine learning

| ID | Control | Owner | Setup | Action | Expected result | Actual result | Evidence | Status | Launch blocker |
|---|---|---|---|---|---|---|---|---|---|
| S-10 | Transaction server validation | Student developer | Synthetic direct scoring fixture | Submit invalid amount/time/currency, forbidden fraud_label, unexpected role or risk_score | 422/400 with field errors; no unsafe record or client-provided score accepted | Not observed (pre-implementation) | Pending | NOT RUN | YES |
| S-11 | SQL injection and pagination safety | Student developer | Seeded transactions; DB accessible to test harness | Send special-character search and limit >100 | Input treated as value; bounded paginated results; tables unchanged | Not observed (pre-implementation) | Pending | NOT RUN | YES |
| S-12 | CSV size and row limits | Student developer | Synthetic CSV below and above thresholds | Upload >10 MiB, >10k rows, wrong MIME or malformed CSV | Rejected with safe codes, correct status and no partial unauthorized processing | Not observed (pre-implementation) | Pending | NOT RUN | YES |
| S-13 | CSV prohibited data and provenance | Student developer | Synthetic valid/invalid CSVs; public dataset license reference omitted or reviewed | Include real-like identity/card fields, extra columns, public dataset without license | Unsafe source rejected, provenance recorded for valid source | Not observed (pre-implementation) | Pending | NOT RUN | YES |
| S-14 | ML label separation and time leakage | Student developer | Labeled SCORING CSV, TRAINING CSV, temporal fixtures | Score direct request with fraud_label and inspect pipeline feature list | No fraud_label or future-only values feed inference, test scores explain provenance | Not observed (pre-implementation) | Pending | NOT RUN | YES |
| S-15 | Trusted artifact activation | Student developer | Two model versions and a deliberately corrupted test artifact | Try to activate wrong checksum/schema, then valid artifact | Corrupt artifact denied; prior active version remains; valid activates atomically | Not observed (pre-implementation) | Pending | NOT RUN | YES |
| S-16 | Score and explanation integrity | Student developer | Known deterministic seeded features and risk thresholds | Score fixture and check risk decomposition and SHAP label | Server computed score; explanation uses model-version snapshot; composite not called fraud probability | Not observed (pre-implementation) | Pending | NOT RUN | YES |
| S-17 | Duplicate scoring and alert idempotence | Student developer | Two concurrent synthetic clients and same external_id | Replay identical and conflicting payloads; redeliver job | Identical replay stable; conflict =>409; one score and <=1 alert per transaction | Not observed (pre-implementation) | Pending | NOT RUN | YES |
| S-18 | Report CSV formula defense | Student developer | Synthetic case/transaction field beginning with =,+,-,@ and controls | Export and inspect parsed CSV / spreadsheet interpretation | Dangerous cell values neutralized; no spreadsheet formula execution | Not observed (pre-implementation) | Pending | NOT RUN | YES |
| S-19 | Request limits and queue bounds | Student developer | Configured login/upload/train/report limits and multiple fake users | Burst costly submissions and oversized pagination | 429 or safe rejection; worker bounded; one tenant cannot exhaust system | Not observed (pre-implementation) | Pending | NOT RUN | YES |

### Investigation, objects, audit and privacy

| ID | Control | Owner | Setup | Action | Expected result | Actual result | Evidence | Status | Launch blocker |
|---|---|---|---|---|---|---|---|---|---|
| S-20 | Case and alert atomicity | Student developer | NEW alert, two simulated reviewers | Dismiss/create case concurrently; resolve with stale version | One valid state transition and audit; conflicts rejected; no partially updated rows | Not observed (pre-implementation) | Pending | NOT RUN | YES |
| S-21 | Audit append-only and redaction | Student developer | Admin model/rule/role edits, case closures, export events | Perform actions and inspect audit_logs/case_events and modification privileges | Actor, time, request ID and safe diff captured atomically; no plaintext secrets | Not observed (pre-implementation) | Pending | NOT RUN | YES |
| S-22 | Private dataset/model/export storage | Student developer | Private object store with two org test objects | Access objects anonymously, via guessed path, wrong-org job ID | No public listing/download; server authorization enforced | Not observed (pre-implementation) | Pending | NOT RUN | YES |
| S-23 | Export expiry and deletion | Student developer | Completed report job with export and test clock | Advance past 24h; request download and inspect object store | Expired download denied and object deleted/retried with recorded cleanup | Not observed (pre-implementation) | Pending | NOT RUN | YES |
| S-24 | Raw-data and secret leakage | Student developer | Failed jobs/login and bad requests containing fake markers | Inspect backend/worker logs, browser bundles, exception responses | No cookies, credentials, raw CSV rows, full customer refs or stack traces | Not observed (pre-implementation) | Pending | NOT RUN | YES |
| S-25 | Retention and cleanup | Student developer | Synthetic transactions, upload, audit, job errors and export fixtures | Run safe dry-run then retention cleanup in isolated environment | Configured 90d/30d/7d/24h rules applied as approved, with dependent records handled; counts logged | Not observed (pre-implementation) | Pending | NOT RUN | YES |
| S-26 | Backup restoration | Student developer | Provider-selected isolated staging, synthetic records | Run backup then isolated restore; check tenant scope and stored objects | Restored integrity and access controls demonstrated; backup expiry documented | Not observed (pre-implementation) | Pending | NOT RUN | YES |
| S-27 | XSS and copied UI code | Student developer | Case note synthetic HTML payload and selected third-party component | Render input; review component sources and CSP | Inert text; no unauthorized remote scripts or disclosure | Not observed (pre-implementation) | Pending | NOT RUN | YES |
| S-28 | App error responses | Student developer | Missing model, invalid case transition, unauthorized access | Inspect 401/403/404/409/413/422/429/500 safe envelopes | Clear recovery text and request ID; no internal traces/private content | Not observed (pre-implementation) | Pending | NOT RUN | YES |

### Operations, deployment and release

| ID | Control | Owner | Setup | Action | Expected result | Actual result | Evidence | Status | Launch blocker |
|---|---|---|---|---|---|---|---|---|---|
| S-29 | Dependency and code secret scanning | Student developer | Commit SHA and locked dependencies | Run dependency audit, static checks, secret scan and review external UI snippets | Blocking findings remediated; evidence and exceptions recorded | Not observed (pre-implementation) | Pending | NOT RUN | YES |
| S-30 | Network / TLS / Redis isolation | Student developer | Deployment environment selected, services running | Verify HTTPS headers, protected readiness and Redis/DB reachability | TLS configured; Redis/DB not publicly reachable; least privilege documented | Not observed (pre-implementation) | Pending | NOT RUN | YES |
| S-31 | CSRF/CORS production origin setup | Student developer | Final custom domain and frontend/backend origins set | Test allowed origin and hostile external origin with credentials | Only intended origin permitted; unsafe authenticated requests blocked | Not observed (pre-implementation) | Pending | NOT RUN | YES |
| S-32 | Synthetic-only public demo promise | Student developer | Final seed data, database and publicly visible UI | Inspect data and demo content; check Privacy/Terms text | No real financial/personal info, no fake metrics and correct limited-demo wording | Not observed (pre-implementation) | Pending | NOT RUN | YES |
| S-33 | Mandatory launch experience | Student developer | All supported pages in release build | Test routes, mobile viewport, footer, favicon, policy pages, 404, titles/meta, buttons | No broken links/overflow; mobile menu, accessibility basics and feedback work | Not observed (pre-implementation) | Pending | NOT RUN | YES |
| S-34 | Domain, branding and legal approval | Student developer | Final host/domain provider, privacy and terms drafts | Verify DNS/TLS, favicon, correct legal pages and badge policy | Domain resolves with HTTPS; legal docs owner-approved; no impermissible branding edits | Not observed (pre-implementation) | Pending | NOT RUN | YES |
| S-35 | Security regression after fixes | Student developer | Security suite with recorded failures and patched commit | Rerun failed tests and affected positive flows | All launch blockers PASS with new evidence; no untested change declared fixed | Not observed (pre-implementation) | Pending | NOT RUN | YES |

## 3. Test execution log template (copy per check)

```text
Control ID:
Commit SHA / version:
Environment (local/staging) and test date:
Tester:
Setup / synthetic fixtures:
Action / exact command or browser steps:
Expected result:
Actual HTTP status and observed DB/object-store effect:
Status: PASS | FAIL | BLOCKED | N/A (reason required)
Evidence paths / CI link (redacted):
Bugs raised / next steps:
Retest commit and date:
```

No sample filled-in success report is provided because no implementation exists yet. Attach screenshots and logs **only after actual execution**, with all credential and demo-identifiers sanitized where appropriate.

## 4. Phase checkpoints and launch decision

| Phase window in `IMPLEMENTATION_PLAN.md` | Security controls to implement and verify |
|---|---|
| Phases 1–2 | S-08 (secrets/storage baseline), S-11 (safe DB), local access controls; do not mark provider-specific checks as passed |
| Phases 3–4 | S-01 through S-07, S-09 through S-13, S-22 |
| Phases 5–8 | S-14 through S-17, S-19 through S-21, S-16 explanation integrity |
| Phases 9–12 | S-18, S-23, S-27, S-28, S-33 accessible frontend feedback |
| Phases 13–14 | S-24 through S-31, negative integration tests and fail/retest loop |
| Phases 15–16 | S-26, S-30 through S-35 plus the **existing** PRD/UIUX launch checklist |

**Release decision:** Public launch is blocked until all applicable `YES` controls actually PASS; valid N/A requires recorded owner reason, test environment and impact. Do not silently skip a failed/blocked critical security check for the 5–7-week stretch schedule. User's other mandatory conditions also apply: owner-reviewed `/privacy` and `/terms`, custom HTTPS domain, favicon, accurate titles/meta, correct copyright year, functional mobile menu, working links/actions, accessible responsive UI, no fake metrics or branding removal that violates terms.

## 5. Open dependencies and honest exceptions

- Deployment host, database/storage provider, security scan tooling, provider encryption/backups and production domain are **to be selected/verified**.
- Legal text must describe actual behavior. Until hosting, telemetry and cookie settings are verified, do not claim Privacy Policy correctness.
- A release can never be guaranteed free of all defects; this checklist provides **testable evidence** for named controls.
- **Current release decision:** `NOT READY / NOT TESTED`. No application code, deployment or security test has been completed in this documentation-only step.

## 6. VS Code agent prompt for one security control, later

**Do not execute until the owner requests the corresponding implementation phase.**

> Read all six SentinelAI baseline documents plus `docs/security/Security.md`, `docs/security/Auth.md`, `docs/security/Data Security.md`, `docs/security/Threat Model.md`, and `docs/security/Security Checklist.md`. Implement **only** control `[CONTROL_ID]` within the owner's current approved phase. First report what exists, files to change, positive and negative cases and test commands. Use fake records only; do not expose secrets or deploy. Make a small reviewable change. Actually run permitted and forbidden tests. Report observed results, files changed and any limitations. Update the checklist row **only with real evidence**. Stop before the next phase.
