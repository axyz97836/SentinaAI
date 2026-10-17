# SentinelAI | Security.md

**Version:** 1.0, 2026-10-16  
**Status:** Approved product/architecture decisions translated into **proposed controls**. Implementation and verification have **not started**.  
**Source:** Adapted from *MIKENWO Five Security Documents Quick Start*, page 3, and SentinelAI `PRD.md`, `TRD.md`, `BACKEND_SCHEMA.md`, and `IMPLEMENTATION_PLAN.md`.  
**Applies to:** Next.js browser UI, FastAPI `/api/v1`, PostgreSQL, Celery/Redis, private object storage, local development, CI and deployed demo.

## 1. Scope and security objective

SentinelAI is a **synthetic-data fraud and risk intelligence demo**, not a banking, payment, or real-card authorization platform. Prevent misuse of demo accounts, unauthorized access across organizations, altered scores/cases/settings, untrusted file processing, credential exposure, and resource exhaustion. All fraud explanations and metrics must be traceable to authentic system output. Do not accept real financial transactions, card data, identity records, names, phone numbers, addresses or actual customer behavioral histories in transaction ingestion.

**Control status vocabulary:** `PLANNED` = documented only; `IMPLEMENTED` = code/config exists but not yet tested; `VERIFIED` = reproducible test with dated evidence. Every item below starts `PLANNED`. Never treat an agent's statement as evidence of a successful test.

## 2. Rules, enforcement points and evidence

| ID | Security rule | Enforce at | How to test using fake data | Status |
|---|---|---|---|---|
| SEC-01 | Validate and normalize every accepted API field; reject extra/prohibited transaction fields and invalid types/amounts/dates | FastAPI Pydantic schemas and domain service, not only forms | Send negative amount, invalid country, extra `role`, `fraud_label` in direct score; expect appropriate 422/400 and no record | PLANNED |
| SEC-02 | Never use user-controlled strings to construct raw SQL; enforce DB constraints and bound query sizes | SQLAlchemy parameterized queries, Alembic DB constraints, paginated endpoints | Pass SQL-like search input; verify treated as data; lists cap `limit <=100` | PLANNED |
| SEC-03 | Session secrets, database credentials, storage keys and signing keys never reach client bundles, URLs, logs or Git | Backend env/secret store, Next.js public/private env separation, CI secret scanning | Inspect browser build and Git diff/history; rotate test secret and confirm no disclosure | PLANNED |
| SEC-04 | Session cookie is opaque and `HttpOnly`, `Secure` in production, `SameSite=Lax`; only a hash is stored in `sessions` | FastAPI auth middleware, Set-Cookie, PostgreSQL | Inspect Set-Cookie; inspect DB hash; logout then replay old cookie => 401 | PLANNED |
| SEC-05 | Every state-changing cookie-authenticated endpoint checks CSRF and origin; authenticated CORS never uses wildcard origin | Auth/CSRF middleware, deploy config | Missing/invalid CSRF on case closure, admin rules and upload => 403; valid request succeeds | PLANNED |
| SEC-06 | Every protected endpoint verifies membership/role and resource organization from server-side session context | Service authorization guard + organization-filtered repositories | Analyst attempts `/admin/settings`; wrong-org user guesses transaction/report ID; expect 403/404 without private content | PLANNED |
| SEC-07 | File upload limited to CSV of maximum 10 MiB and 10,000 rows; allowlisted columns, bounded parser resources; reject real identifiers | Multipart streaming limit, ingestion worker, schema validation | Oversized CSV => 413; malformed/extra columns, PII-like fields, too many rows rejected; no unsafe object becomes operational | PLANNED |
| SEC-08 | Uploaded CSVs, generated exports and model artifacts stay in private object storage; no public listing or user-supplied object key | Storage adapter, server-authorized retrieval, object-store policy | Try accessing object URL unauthenticated or with another org's ID; verify denial | PLANNED |
| SEC-09 | No arbitrary code/model loading from uploaded data; only trusted worker-produced versioned artifacts with expected checksum/schema can be loaded | Model activation and inference loader | Tamper artifact checksum or replace with unexpected format; activation/inference rejects, keeps previous active model | PLANNED |
| SEC-10 | Lock down expensive operations with per-session/IP limits and bounded job queue; admins only can train | Login, ingestion, report, train APIs; worker concurrency | Rapid login attempts, repeated exports, analyst training attempt; expect throttling/403 and no unbounded jobs | PLANNED |
| SEC-11 | Do not place raw cookies, passwords, imported rows, full customer references, secret keys or unsanitized errors into logs | Structured logging filters, exception handlers, worker logs | Trigger invalid CSV/auth error; inspect logs and client response for private content/stack traces | PLANNED |
| SEC-12 | Render untrusted text as text, not HTML; apply an appropriate CSP and safe data-chart labels | Next.js rendering, response headers | Submit HTML/script-like note/reference; confirm no execution, safe output | PLANNED |
| SEC-13 | Encode/export CSV safely against spreadsheet formula interpretation | Report serializer | Create synthetic field beginning with `=`, `+`, `-`, `@` or control prefix; verify neutralized in downloaded CSV | PLANNED |
| SEC-14 | Retry, replay and concurrency must not duplicate transactions, scores, alerts or cases | Unique DB constraints, transactions, row locking, task idempotency | Concurrent same `external_id`, duplicate Celery delivery and case creation; assert one authoritative result | PLANNED |
| SEC-15 | Case resolution, dismissals, role/rule/settings updates and model activation generate sanitized audit records atomically | Domain services + `audit_logs` and `case_events` | Perform one of each; verify actor/time/request ID and no secret leakage | PLANNED |
| SEC-16 | Prevent unverified legal/security claims in UI, docs or README; no fake counts, fake accuracy or asserted compliance certification | Product review + CI documentation gate | Search UI/docs for hard-coded metrics, claim 'secure/compliant' without evidence; remove or qualify | PLANNED |
| SEC-17 | Deploy only behind TLS with protected health/readiness endpoints, safe error pages, managed secrets and least-privilege DB/storage identities | Host/TLS, FastAPI settings, infrastructure | Inspect headers, health paths, production configuration and restricted IAM/DB roles | PLANNED |
| SEC-18 | Keep dependencies pinned, run dependency/security scans, review external UI snippet licenses and scripts before adding | Git workflow, CI, package review | Run dependency audit/SAST, inspect installed skill and copied components; record any exceptions | PLANNED |

## 3. Service-specific rules

- **Browser:** No API credentials, model artifacts or security decisions in client state. Hide forbidden menus for usability **and** enforce permission on the server. No third-party tracking/analytics SDK without explicit owner review and privacy-policy update. Only minimal, purposeful Motion animations; third-party UI components must pass dependency, license and a11y review.
- **FastAPI:** Authenticate by hashed session token, load `memberships.role`, derive organization context server-side, enforce CSRF for unsafe cookie-authenticated methods and return standardized errors `{error:{code,message,request_id,field_errors?}}` without tracebacks. Differentiate 401, 403, and cross-org 404.
- **Database:** Use an app DB account with least privilege; require tenant filter in all tenant-scoped queries, check constraints, unique indexes and auditable ACID writes. Do not expose connection strings to frontend.
- **Worker/Redis:** Queue messages contain IDs only (`job_id`, `dataset_id`, `training_dataset_id`), never CSV bytes, passwords or cookies. Broker not Internet-exposed. Duplicate tasks are safe and their durable status is stored in Postgres.
- **Storage:** Private buckets/containers; server-generated unpredictable keys; authorize each download on every request; short-lived access paths if signed URLs are later adopted. Avoid trusting file extension, MIME declaration or client filename alone.
- **ML:** Never train on the validation/test subset; do not include `fraud_label` or future events as scoring features; clearly label composite risk score as **not** a fraud probability. Attackers must not be able to submit their own pickled model objects.

## 4. Response and incident handling (demo scope)

1. Reject dangerous requests without partial writes, return safe user-facing messages, and emit sanitized server-side events with `request_id`.
2. On suspected compromise, stop public access or disable affected account, revoke sessions, rotate exposed secrets, and preserve minimal relevant logs under the data-retention policy.
3. For critical issues (cross-org leakage, admin privilege escalation, exposed secret or public raw CSV), **block launch** until remediated and retested.
4. Use synthetic fixtures for security tests. Never paste production-like credentials or real bank data into VS Code agent chats or bug reports.

## 5. Phase integration and acceptance

- **Phases 1–4:** environment/secrets hygiene; sessions; CSRF/RBAC; upload validation and storage isolation.
- **Phases 5–8:** training-artifact trust, scoring integrity, case concurrency and audit trails.
- **Phases 9–12:** XSS-safe UI, accessible error feedback, safe export and route authorization.
- **Phases 13–16:** adversarial integration tests, dependency review, backup/restore verification, TLS, security checklist and launch gate.

Every applicable security change must include at least a positive and negative test. Mark it `VERIFIED` only with actual output, version/commit and dated evidence in `Security Checklist.md`.

## 6. Open questions and decisions deferred

- [Hosting / TLS / secret management provider: to be added]. Confirm supported cookie/HTTPS settings before deployment.
- [Object storage provider and backup retention: to be added]. Prove private access and documented deletion behavior.
- [Exact login/report/upload throttling numbers: to be measured and approved], rather than inventing SLOs.
- [Security scanning tooling and dependency allowlist: to be confirmed].
- [Owner-approved contact email and incident contact: to be added, only if displayed].
- [Production legal/privacy review and data-handling confirmation: pending].

**Do not implement or mark these controls complete solely because this document exists.**
