# SentinelAI | Threat Model.md

**Version:** 1.0, 2026-10-16  
**Status:** **Hypothetical threats**, not confirmed bugs. No application exists yet for verification.  
**Basis:** MIKENWO quick start page 6; the six SentinelAI planning files and the companion `Security.md`, `Auth.md`, `Data Security.md`.

## 1. System and trust boundaries

```text
Public Internet / Browser (untrusted)
     |  HTTPS, cookies, CSRF, input validation, rate limits
     v
FastAPI (trusted to authenticate, authorize, validate and score)
     |                 |                         |
     | SQL/tenant      | background IDs          | authenticated storage API
     v                 v                         v
PostgreSQL         Redis -> Celery           Private object storage
(meta, sessions,   (worker processes          (CSVs, model bundles,
 transactions,      imports/ML/exports)        exports)
 cases, audit)
     ^                 |                         ^
     +-----------------+-------------------------+

Trusted operator: seeded ADMIN and deployment owner.
Untrusted: browser, user-uploaded CSV, case notes, query IDs, external UI scripts,
  malicious/duplicate queue delivery, unknown model-file bytes, outside services.
```

**Important assets:** session tokens and password hashes; model activation rights; organization-scoped transaction data and exports; case disposition history; integrity of risk score, ground-truth labels, rules and audit trail; private training artifacts; availability of CPU-intensive scoring/training jobs.

**Primary security objectives:** confidentiality of organization records; integrity of fraud explanations/case decisions; availability under bounded demo usage; accountability for actions; truthful interpretation of synthetic scores.

## 2. Three highest-priority realistic abuse scenarios

| Rank | Risk / attack preconditions | Possible harm | Proposed protection | Concrete test | Owner | Status |
|---|---|---|---|---|---|---|
| 1 | **Broken object-level authorization (IDOR):** authenticated user obtains a UUID from another organization and changes `/transactions/{id}`, `/cases/{id}`, `/jobs/{id}` or report download URL | Disclosure of reports/transactions and investigation evidence | Derive organization from session; filter every repository query; authorize storage object through related job ID; return 404 for wrong org | Create two isolated test organizations and request B's resources using A session; verify 404 and no bytes | Student developer | PROPOSED / NOT TESTED |
| 2 | **Privilege escalation or forged state change:** an analyst tries ADMIN routes, role over-posting or cross-site request against an existing session | Malicious model activation, altered thresholds, rewritten case outcome | Server-side role checks on each request, explicit admin-only endpoints, origin + CSRF checks, last-ADMIN guard, atomic case/audit writes | Analyst attempts training/role edit, forged CSRF case resolution, last-admin demotion; verify denies and DB unchanged | Student developer | PROPOSED / NOT TESTED |
| 3 | **Hostile CSV/job input:** user uploads malformed, oversized, spreadsheet-formula, or sensitive rows; floods training/exports | Resource exhaustion, accidental data exposure, unsafe exported spreadsheet, misleading metrics | Streaming size/row cap, schema/PII allowlist, provenance/license review, formula escaping, rate limiting, bounded worker queue and job quotas | Upload >10 MiB, >10k rows, unsupported fields, formula cells and repeat jobs; verify rejects/escape and no leaked rows | Student developer | PROPOSED / NOT TESTED |

## 3. Additional threat register

Likelihood/impact are **preliminary qualitative assessments**, not vulnerability-scanner findings or probability estimates.

| ID | Risk and prerequisite | Potential harm | Mitigation and where enforced | Validation test | Priority | Owner | Evidence/status |
|---|---|---|---|---|---|---|---|
| TM-04 | Stolen session cookie / unrevokeable session | Unauthorized dashboard and case access | Opaque token hash in DB, HttpOnly/Secure cookie, expiry/logout/revocation + current membership checks | Reuse cookie after logout/role revocation; expect 401/403 | High | Student developer | NOT RUN |
| TM-05 | Password guessing or account enumeration on `/auth/login` | Compromise seeded accounts | Argon2id, generic errors, rate limiting, no demo password in repo | Many invalid login attempts; inspect 429/logs and generic response | High | Student developer | NOT RUN |
| TM-06 | Stored/reflected XSS through case notes, transaction fields, UI package | Session-adjacent actions and UI compromise | Escape untrusted text, CSP, review dependencies and copied components | Synthetic HTML/script-like input renders as inert text | High | Student developer | NOT RUN |
| TM-07 | Untrusted serialized model artifact replaces active bundle | Arbitrary code/data corruption or wrong scoring | Worker-created artifact only, checksum/schema verification, private storage, restrict deserializer | Inject corrupted artifact, activation must fail without model swap | High | Student developer | NOT RUN |
| TM-08 | Score spoofing/model leakage through client request or `fraud_label` feature | Fake risk result, data leakage, misleading demo | Server calculates score; block label in direct API; feature extraction from prior data only; immutable results | Send `risk_score`, `fraud_label`, future events; verify validation/no trusting client | High | Student developer | NOT RUN |
| TM-09 | Concurrent replay creates multiple cases/alerts | Incorrect dashboards, duplicated cases and reports | Unique transaction IDs, unique score/alert/case FKs, ACID transactions, idempotent worker retry | Send duplicate requests concurrently; verify single persisted chain | High | Student developer | NOT RUN |
| TM-10 | Sensitive content leaked in exceptions, logs, Git or browser bundles | Credential/data disclosure | Redaction, sanitized errors, secret scanning and reviewed env files | Trigger errors and inspect output, image artifacts, commits and JS bundle | High | Student developer | NOT RUN |
| TM-11 | Bad role/threshold/model change bypasses audit | Nonrepudiation and forensic gaps | Atomic audit writes with actor, request ID, time, redacted diff; append-only role policy | Change settings/model and ensure audit row; DB cannot silently edit audit via app | Medium | Student developer | NOT RUN |
| TM-12 | Export object stored publicly or downloadable using guessed ID | Private report leak | Private bucket, auth & tenant checks each download, 24h expiry | Anonymous and wrong-org download attempts fail; inspect bucket policy | High | Student developer | NOT RUN |
| TM-13 | Malicious public dependency/UI snippet or third-party remote script | Supply-chain compromise, extra telemetry | Review license/permissions/dependencies, lockfile and CI scans; no unapproved telemetry | Inspect installed component scripts and dependency audit | Medium | Student developer | NOT RUN |
| TM-14 | Redis exposed or worker consumes untrusted tasks | Queue spoofing, data or resource abuse | Private Redis network/auth where available, task allowlist, IDs-only payloads, limited concurrency | Network access controls, malformed task rejection | Medium | Student developer | NOT RUN |
| TM-15 | Deletion only removes metadata but leaves CSV/report or backup | Long-lived accessible copies and false privacy claims | Verified purge for objects + metadata, expiry job, documented backup lag | Execute synthetic deletion and inspect objects/backup policy | Medium | Student developer | NOT RUN |
| TM-16 | Model poisoning / leakage by using mislabeled or real-world personal datasets | Unreliable fraud classifications or privacy harm | Dataset provenance, label-feature separation, train-only preprocessing, held-out evaluation, synthetic default | Test known leakage column and external dataset license/privacy review | Medium | Student developer | NOT RUN |
| TM-17 | Unbounded filters / training/report requests | CPU/DB exhaustion or high hosting bills | Cursor pagination, job rate limits, bounded 10k rows, training concurrency caps | Request huge limit and repeat jobs, inspect correct cap | Medium | Student developer | NOT RUN |

## 4. Trust-sensitive product decisions

- **Synthetic only:** No real bank integration, live financial monitoring, payment blocking or real user behavioral tracking in MVP. The threat model does not authorize those integrations.
- **AI explanations:** SHAP features may explain the supervised component, not necessarily the entire composite score. A misleading statement is a **product integrity risk**; test labels and caveats in UI and API.
- **Known attack surface, not known flaw:** Every risk above is a plausible scenario. It is **not evidence** that SentinelAI currently contains that vulnerability. No implementation is known to exist at this stage.
- **No blanket security guarantee:** A passing checklist after implementation reduces certain tested risks; it does not prove the product cannot be attacked.

## 5. Testing order and response to discoveries

1. At auth and schema phase, start with **TM-01 equivalent IDOR** and **TM-02 authorization/CSRF** using two synthetic organizations and all three roles. The shipped MVP may show just one organization, but tests must exercise boundary isolation.
2. At ingestion phase, run CSV/quota tests; at model phase, run artifact and label-leakage tests; at frontend phase, run XSS/supply-chain checks; at integration phase, run concurrency, export and audit tests.
3. If testing reveals an actual flaw, open a tracked issue with version, reproduction using fake data, severity and owner; update Security/Auth/Data Security docs as needed.
4. Fix in a small reviewed change. Re-run positive and negative cases, attach actual evidence to `Security Checklist.md`, then update threat status from hypothetical to remediated/verified when justified.
5. Block public release for critical confidentiality, privilege escalation, integrity or exposed-secret failures.

## 6. Open questions

- [Hosting/Redis exposure and firewall design: pending provider].
- [Object storage security policy, encryption and backup deletion lag: pending provider].
- [Decided login throttles and session lifetime: pending implementation approval].
- [External UI code/security review: only after owner chooses a specific dependency].
- [Independent review for critical security paths: recommended before public demo].

**All listed risks are proposed, all tests are NOT RUN, and no discovered code vulnerability is asserted.**
