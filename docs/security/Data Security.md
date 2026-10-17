# SentinelAI | Data Security.md

**Version:** 1.0, 2026-10-16  
**Status:** Planned safeguards and retention proposals; **no live configuration has been inspected**.  
**Basis:** MIKENWO quick start page 5; SentinelAI `TRD.md` and `BACKEND_SCHEMA.md` section 7. Only synthetic or vetted, non-sensitive public demo datasets are accepted.

## 1. Data handling principles

1. Collect only fields required to run the explicitly documented demo. Do not accept real payment card details, bank-account numbers, names, addresses, phone numbers, identifiable transaction histories, or live behavioral trackers.
2. Use `SYNTHETIC` or `PUBLIC_DATASET` provenance for datasets. Public data requires owner-reviewed licensing and a check that it does not contain actual person-linked financial records. **Public** does not automatically mean safe to ingest or republish.
3. Store large files in private object storage, relational metadata in PostgreSQL, task IDs only in Redis. Encrypt traffic with HTTPS/TLS in deployment and use managed encryption features at rest when supported. Whether a particular provider has encryption enabled remains **unverified** until inspected.
4. Treat fictional identifiers as internal data regardless of whether they correspond to real people. Restrict access by authentication, organization membership and role.
5. Database and file deletion are distinct operations. Don't claim data is deleted until current copies under app control are addressed, and explicitly state backup/log retention lag.
6. Never expose secret values, password hashes, cookies, token hashes, CSV rows or complete customer references to client error messages, analytics, AI-agent prompts or logs.

## 2. Inventory: purpose, location, access and lifecycle

All retention periods are **proposed demo policy**, copied/aligned with `BACKEND_SCHEMA.md`; they are not statutory deadlines or verified provider settings.

| Data type / source | Purpose | Primary location | Who may access | Proposed retention and cleanup |
|---|---|---|---|---|
| Demo organization and user records (`organizations`, `users`, `memberships`) | Demo login and roles | PostgreSQL | User sees own identity; ADMIN sees org demo users | For demo lifetime; deactivate accounts and delete via reviewed teardown policy; no promise of instant backup erasure |
| Password hashes and session-token hashes (`users`, `sessions`) | Login and revocation | PostgreSQL, server-managed cookie only for opaque raw token | Backend auth process; not UI/analytics | Sessions to expiry/logout; purge expired records daily; credentials removed on account teardown subject to backup lag |
| Synthetic scoring transactions and behavioral references | Evaluate fraud scenarios | PostgreSQL `transactions` | All authenticated roles, scoped by organization | 90 days from ingest, then audited purge |
| Model scores, reasons and rule hits | Explain decision at scoring time | `scoring_results`, `rule_hits` | Same-org ANALYST/RISK_MANAGER/ADMIN | 90 days with linked transactions, subject to retention integrity |
| Ground-truth demo labels | Offline test/evaluation only | `transaction_labels`, training objects | Authorized scoring/evaluation services; role-aware reporting | 90 days with scoring transactions; never join into inference feature path |
| Alerts, cases, investigation notes and timeline | Fraud review workflow | `alerts`, `cases`, `case_events` | Same-org authenticated roles; admin audit summaries | 90 days; documented purge preserving referential integrity |
| Uploaded CSVs, synthetic training/scoring source | Reproducible modeling/ingestion | Private object store; `datasets` metadata in Postgres | Backend/worker after org/purpose checks; ADMIN for training | Uploaded object target 30 days; storage deletion and metadata consistency checked |
| Trained ML model bundles | Repeatable vetted inference | Private object store and `model_versions` | Trusted training/score services, ADMIN can activate | Active + prior two artifacts; older inactive objects eligible after 90 days **only if not needed for history** |
| Job state and bounded validation errors | Progress and troubleshooting | Postgres `jobs`, `job_errors`; transient broker IDs in Redis | Same-org actor/roles, admin where applicable | Jobs 30 days, detailed errors 7 days; Redis expiry set after provider verification |
| Generated CSV report exports | Allow authorized data review | Private object storage, `jobs.object_key` | Same-org authenticated user on every download | Delete output object after 24 hours; expired link denied and metadata updated |
| Audit events and case events | Accountability and investigation history | PostgreSQL `audit_logs`, `case_events` | Admin-scoped audit summaries; evidence shown as relevant in case UI | 90 days in demo then reviewed archive/purge; no normal edits |
| Sanitized server/worker/access logs | Diagnosis and security monitoring | Managed log output configured by host | Project owner/operator | 14 days or more restrictive host setting; verify actual host retention |
| Database/object storage backups | Recover from mistakes | Host backup system **[provider to be added]** | Owner/operator with restricted credentials | Schedule, expiry and deletion lag **unknown until selected and tested**; never claim immediate total erasure |
| Browser session cookies | Authenticate browser without exposing token to JS | Browser cookie jar | Browser sends automatically to authorized host | Until expiry/logout; session invalidation server-side |
| Frontend static assets and charts | Display UI and real aggregated demo results | Next.js deployed assets, browser memory | Public for static assets; protected for risk data API | Static assets follow release caching; no private datasets embedded in bundles |
| External service metadata | Hosting, repository CI, possible resource CDN | **[provider to be added]** | Per provider contract | Review privacy/settings and data transfer before introducing each service |

## 3. Protection rules for data at rest and in transit

- **PostgreSQL:** use least-privilege application role, migrations separate where practical, managed storage encryption if available, index tenant scoped tables, prohibit direct public DB ingress, and back up/restore with test evidence. Organization comes from session, not request body.
- **Object storage:** all datasets/artifacts/exports are private; keys server-generated and non-guessable; do not publicly list buckets; storage access limited to relevant API/worker identities. Authenticate every export request; verify object belongs to an authorized `job_id` and organization before streaming.
- **Redis/Celery:** Redis must not be publicly reachable. Payload IDs only, no raw imported content. Do not infer job completion from transient queue state; PostgreSQL is authoritative.
- **Model artifacts:** only trusted worker creates them. Check SHA-256 and feature schema before promotion; do not deserialize arbitrary user-submitted executables/pickle files. Record `model_versions` metadata for historical explanation.
- **CSV:** 10 MiB/10k row limit, schema/field allowlist and PII rejection; reject unexpected direct transaction `fraud_label`; never leak labels into scoring. Escape formula-like exported cell values to prevent spreadsheet evaluation.
- **Logs:** use `request_id`, role/organization IDs when required, HTTP status, latency and sanitized error code. No raw headers containing cookies/auth, free-text case notes, imported row data, customer references or password material.
- **Browser:** avoid localStorage for session credentials; no real transaction examples compiled into front-end code. Charts are computed from protected API responses and use no fabricated counters.
- **Third parties:** Motion/Bklit/Kokonut/other owner-listed UI references are not automatically approved network dependencies. Review telemetry, embedded remote scripts, licensing and data-handling before adoption; no unsolicited tracking.

## 4. Deletion, restore and backups

**Deletions require a real procedure, not just a UI status change:**

1. Record a purge run and affected organization/time range. Block concurrent modifications as appropriate.
2. Check foreign keys and references (especially `model_versions`, scoring results, `case_events` and `audit_logs`) and execute a safe transactional cleanup plan.
3. Delete associated private storage objects (CSV, generated reports, eligible artifacts); retry failures and record error counts without logging private file contents.
4. Verify objects are no longer retrievable by authorized or unauthorized paths, and DB queries no longer return purged data.
5. Document whether backup snapshots and provider logs may continue to hold copies until their normal expiry. Do **not** assert full erasure from backups without evidence.
6. For requested account/organization teardown, perform a separate owner-approved dependency and retention review. The demo has no public account-deletion promise in MVP.

**Recovery expectations:** Before public demo launch, prove one controlled restore using synthetic fixtures, including database consistency and access to required private artifacts. Set backup frequency, recovery point and recovery-time expectations after hosting is chosen. Tested results are stored in `Security Checklist.md`.

## 5. Sharing, legal pages and user expectations

- The public `/privacy` page must accurately describe seeded/demo accounts, any personal data truly collected (e.g. voluntary contact details if added), cookies/sessions, synthetic transactions, hosting/processors and actual retention/deletion practice. Draft for owner review; it is **not a substitute for legal advice**.
- `/terms` must not imply authorization to process real payment data. Clearly state demonstration-only purpose and limitations of score/explanation outputs.
- Do not publish raw user IDs, secrets, dataset bytes, real customer identifiers or private object links in screenshots, README, analytics or demo recording.
- Do not add real analytics/customer tracking without updating documentation and obtaining owner consent. The absence of this SDK is a default assumption, not something verified in code.

## 6. Evidence checks to perform after implementation

| ID | Test (synthetic fixtures only) | Success criterion |
|---|---|---|
| DATA-01 | Access another organization's CSV, export or model object | 403/404 or inaccessible; no bytes or object metadata leaked |
| DATA-02 | Upload 10 MiB+ file, over 10k rows, sensitive or disallowed fields | Rejected with appropriate safe error; no operational transaction stored |
| DATA-03 | Trigger invalid login and failed worker import then examine all logs | No passwords, raw tokens, full CSV rows or personal-like fields |
| DATA-04 | Expire an export and try to download it | Download rejected; object deleted/queued for cleanup, verified |
| DATA-05 | Run a synthetic purge and inspect DB, bucket and logs | Expected active copies removed; residual backups transparently documented |
| DATA-06 | Restore an isolated backup with seeded test data | Restored objects, permissions and audit relationships behave as documented |
| DATA-07 | Inspect configured TLS and encryption/backup settings at chosen providers | Evidence records actual provider configuration, not assumptions |

**Current results: ALL NOT RUN.**

## 7. Open questions

- [Hosting / database / Redis / S3-compatible storage providers: to be added].
- [Provider encryption, backup and log retention: to be inspected].
- [User-facing contact information: to be approved if present].
- [Retention execution frequency and incident response contact: to be finalized before deployment].
- [Public dataset/license: to be selected and independently reviewed].
- [Legal/privacy review: owner approval pending].

**No external provider setting is considered enabled or validated by this document.**
