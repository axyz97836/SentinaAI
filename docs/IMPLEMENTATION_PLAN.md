# SentinelAI | Implementation Plan for VS Code AI Agent (5–7 Week Stretch, 8-Week Baseline)

**Version:** 1.1 approved baseline (revised 2026-10-16)  
**Status:** Approved on 2026-10-16. These prompts are authorized **one named phase at a time**, only when the owner asks to begin that phase.  
**Developer:** One third-semester CS student  
**Estimate:** 5–7 week stretch goal with sustained effort; 8-week conservative baseline. Owner expects roughly 7–9 focused hours/day for 5–6 days/week when practical, not an unlimited workday. No duration is guaranteed.

## 1. How to use this plan

The owner has approved the project. **This document update does not start implementation.** Begin **Phase 1 only** when the owner next asks for it. At the end of each phase, stop, review output, fix defects, commit, and wait for `next` or a clear phase instruction before advancing.

The prompts are intended for the owner's **VS Code AI agent (called GPT-6 Astra by the owner)**. Use agent/chat view to plan, editor/diff for review, integrated terminal for commands and actual browser automation/manual testing where available. Do **not** refer to nonexistent Antigravity Manager controls or claim unavailable tools ran successfully.

**Standing rules for every agent prompt:**

- Read `/docs/PRD.md`, `/docs/TRD.md`, `/docs/APP_FLOW.md`, `/docs/UIUX_BRIEF.md`, `/docs/BACKEND_SCHEMA.md`, and `/docs/IMPLEMENTATION_PLAN.md` before writing anything.
- Work **only on the named phase**, show planned file changes, and make no unrelated features or architecture swaps.
- Never use real financial/personal data. Use synthetic fixtures or explicitly approved non-sensitive, de-identified public/licensed data only; reject actual person-linked financial transaction records.
- No purple gradients, pill buttons, fake reviews, fake metrics/counters, vague hero slogans, emoji icons, em dashes in website copy, AI-looking stock photos, cursor animation or excessive motion.
- No fake placeholder text, broken/inert buttons or links, unused navigation, or horizontal **page** scrolling. Require mobile menu, legal routes, favicon and meta information before launch.
- Run the stated commands/tests; report **actual** output and failures rather than claiming success. Never auto-deploy.
- Owner supplied **references**, not unrestricted installation permission: UI UX Pro Max skill; Motion, Bklit UI, Kokonut UI, Anime.js, ThreeUI, Manus. Verify the skill really exists locally. Adopt only the individual approved, necessary components after checking license/security/dependencies/accessibility/performance. Other resources remain placeholders.
- If blocked, stop and ask. Do not silently replace requirements or fabricate test results.

### Development environment plan (for Phase 1 only, on instruction)

1. Create or open repository `sentinel-ai` while preserving `/docs`; initialize Git if needed.
2. Open repository in **VS Code** and use the configured GPT-6 Astra agent/chat to submit exactly one phase prompt. Verify the actual agent extension and availability.
3. Inspect diffs in VS Code editor and Source Control; use integrated terminal to run migrations/tests/lint; use Playwright or real browser inspection when available.
4. Start local services with Docker Compose, using **non-production secrets** stored outside Git. No actual financial data.
5. Commit only after verification and review; avoid stacking incomplete phases.

### Standing agent operating contract (paste as context before each phase when practical)

```text
You are implementing SentinelAI in VS Code using the current AI coding agent. Read all six files in /docs first. The project owner approved the architecture and scope. Execute ONLY the numbered phase requested in the current message. Before editing, state your plan, exact files affected, dependencies, acceptance tests and risks. Keep the architecture, API contracts, role names, routes, ML truthfulness rules and 18-table schema unchanged unless the owner explicitly approves an amendment. Verify whether the UI UX Pro Max skill is installed and readable; if present, use it only as subordinate UX guidance. Motion, Bklit UI, Kokonut UI, Anime.js, ThreeUI and Manus are owner-supplied references, not instructions to install all of them. Follow the no-purple-gradient/no-pill/no-fake-metrics/no-AI-template/no-horizontal-overflow design policy. Use synthetic data only. Run actual relevant tests, browser checks and lint/type/build commands. Provide truthful terminal output summaries and a pass/fail checklist. Do not proceed to the next phase, push a deployment, introduce secrets, claim a test passed without running it or publish the site automatically.
```

### Agent skill check and dependency intake

The owner has **already asked the VS Code agent to install** [UI UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill). Do not reinstall blindly. Inspect whether the relevant `SKILL.md` is present and readable. If using GitHub Copilot, the expected project skill location may be `.github/skills/ui-ux-pro-max/SKILL.md`; other VS Code agents may use another directory. If absent, **report** the missing installation and ask before installing. For any component actually selected, record source URL, license, version, added dependencies, potential privacy/security risks, a11y tests, bundle impact, and a CSS/native fallback. No new dependency solely for visual novelty.

### Accelerated delivery vs. eight-week baseline

| Mode | Target | Governing condition |
|---|---|---|
| **Stretch** | 5–7 weeks | Sustained 7–9 focused hours/day for 5–6 days/week, AI agent available, dependencies work and tests pass |
| **Baseline/contingency** | 8 weeks | Use detailed Week 1–8 phases below as the authoritative sequence, with Weeks 7–8 protecting testing and launch |
| **If delayed** | Beyond 8 weeks as required | Do not skip security, legal/domain conditions, accessibility or complete user journeys; defer optional work |

Shorter calendar time is possible by finishing some phase pairs sooner, **not** by running multiple uncontrolled agents, skipping reviews or claiming work complete before tests. Schedule breaks; agent usage limits are a practical risk, not a target to exhaust.

## 2. Milestone overview

| Week | Phase(s) | Deliverable / gate |
|---|---|---|
| **1** | 1. Foundation, 2. Database/schema | App/dev environment and migrated, seeded DB |
| **2** | 3. Authentication, 4. CSV/job pipeline | Role-gated app and safe asynchronous uploads |
| **3** | 5. ML training, 6. Scoring API | Tested model bundle and synchronous transaction score |
| **4** | 7. Explainability/rules, 8. Alerts/cases | Explainable alert-to-resolution backend workflow |
| **5** | 9. UI shell/auth, 10. Transactions UI | Responsive screens and end-to-end transaction submission |
| **6** | 11. Dashboard/alerts/cases UI, 12. Reports/admin UI | Full MVP browser journeys |
| **7** | 13. Integration/E2E, 14. Security/performance/a11y | Measured reliability and quality evidence |
| **8** | 15. Deploy/legal/domain, 16. Final QA/README/demo | Launch only if mandatory gates pass |

Every phase is one focused work sitting or two short sessions if an unexpected dependency appears. **Quality outranks deadline**: postpone optional export/report polish before weakening transaction, security or case integrity.

---

## Week 1 | Phase 1: Repository and local foundation

**Goal:** Reproducible development environment; no product feature beyond health check.

**Tasks:** Preserve docs; set up the agreed directory layout (`frontend`, `backend`, `infra`), local Compose for Postgres, Redis, object storage, FastAPI and worker; Next.js app; env example with no secrets; health endpoints; lint/type/test commands; initial README setup section.

**Exact VS Code agent prompt:**

```text
Read all six files in /docs and follow IMPLEMENTATION_PLAN.md standing rules. Execute Phase 1 only. First list the exact files you will add and the acceptance checks. Create the minimal local workspace for Next.js/TypeScript, FastAPI/Pydantic, PostgreSQL, Redis, Celery and private S3-compatible development object storage. Preserve /docs. Add safe environment examples without real credentials, Docker Compose, a minimal API /api/v1/health/live and /api/v1/health/ready, and a minimal frontend route that boots. Do not implement business features or style a marketing page. Run startup, lint, type and health checks using the available terminal. Report changed files, real commands/results and blockers, then stop. Do not start Phase 2 or deploy.
```

**Expected:** project folders, dependency manifests/locks, Compose definition, health endpoints, test runner config, README start commands.  
**Verify:** start local stack, frontend loads, health/live 200, readiness 200 only when dependencies are healthy, lint/type checks execute.  
**Common errors/fixes:** busy ports -> remap local host ports; DB/Redis not ready -> explicit readiness/retry; missing environment variable -> compare against example, never hardcode secrets.  
**Done when:** another machine can follow README to boot local services; no failing initial checks.

## Week 1 | Phase 2: Schema, migrations and demo seed

**Goal:** Durable, constrained core data model before business code.

**Tasks:** Implement exactly the 18 tables in `BACKEND_SCHEMA.md`, enum checks, indexes, FKs, partial active-model uniqueness, migration/revert, 1 synthetic demo organization and user accounts across all three roles. Use invented/demo credentials explicitly marked for local use only.

**Exact VS Code agent prompt:**

```text
Read the six /docs contracts. Execute Phase 2 only. Implement the PostgreSQL schema from BACKEND_SCHEMA.md using SQLAlchemy and Alembic, including all 18 tables, indexes, uniqueness constraints, checks and FK relationships. Seed one synthetic demo organization and users with ANALYST, RISK_MANAGER, ADMIN roles using safe local-only credentials; do not put passwords or secrets in tracked files. Add migration round-trip and integrity tests. Show the planned change set first. Run migrate, inspect constraints, test and rollback/reapply in an isolated local database. Report observed results and stop before Phase 3.
```

**Expected:** ORM models, migrations, synthetic seed command, relationship/integrity tests.  
**Verify:** migrate fresh DB, inspect tables/indexes, test rejected duplicate external transaction IDs and invalid case/threshold constraints, migration down/up on a disposable DB.  
**Common errors/fixes:** migration order -> align FK dependencies; index creation failure -> remove dirty dev state and rerun in isolated DB; circular ORM relation -> use explicit foreign keys/relationship definitions.  
**Done when:** schema matches docs and constraints fail safely for invalid fixtures.

---

## Week 2 | Phase 3: Session auth, CSRF and RBAC

**Goal:** Secure role-aware access to the demo organization.

**Tasks:** Argon2id passwords, hashed server-side sessions, HttpOnly cookie config, login/me/logout endpoints, CSRF strategy, membership RBAC, organization query guard, rate limit sign-in, audit security-relevant actions.

**Exact VS Code agent prompt:**

```text
Read all six /docs and implement Phase 3 only. Add session-cookie email/password auth backed by users, memberships and sessions. Use Argon2id, hashed random session tokens, HttpOnly cookies (Secure in production), SameSite=Lax, CSRF protection for mutations, expiration/revocation, and organization-scoped RBAC for ANALYST/RISK_MANAGER/ADMIN. Implement POST /api/v1/auth/login, GET /auth/me, POST /auth/logout with documented error envelope. Add tests for wrong passwords, expired session, CSRF rejection, cross-organization access, and admin-only guards. Do not build UI or business operations yet. Execute tests and report actual results; stop.
```

**Expected:** auth/router/middleware modules, tests, session lifecycle documentation.  
**Verify:** login sets cookie, `/auth/me` reports correct role, logout invalidates, forbidden route returns 403, invalid CSRF rejects mutation.  
**Common errors/fixes:** cookie not set over local HTTP -> dev-only Secure setting, strict production setting; preflight/CORS -> exact localhost origin; CSRF missing -> implement token fetch/submit flow before allowing writes.  
**Done when:** no privileged operation can be performed unauthenticated or under wrong role.

## Week 2 | Phase 4: CSV ingest, private storage, durable jobs

**Goal:** Validate file uploads safely and track async processing without depending on model training.

**Tasks:** CSV size/schema limits, purpose/source provenance and license requirements, purpose permissions, private file storage, `datasets` and `jobs`, `job_errors`, queue task `ingestion.process_csv`; for `SCORING` allow validation/staging but mark as waiting for active model instead of generating fake scores; implementation may stage imports until Phase 6. `TRAINING` validates and stores only.

**Exact VS Code agent prompt:**

```text
Read all six /docs, execute Phase 4 only. Implement POST /api/v1/ingestions and GET /api/v1/jobs/{id}; accept one CSV max 10 MiB and 10,000 rows with strict canonical schema, TRAINING/SCORING purpose, SYNTHETIC/PUBLIC_DATASET source_kind, and a verified license reference for public data. Only ADMIN can upload TRAINING. Store private objects, persist durable dataset/job states, bounded sanitized job_errors, and add a Celery ingestion.process_csv worker task with retry/backoff. TRAINING datasets validate to VALIDATED. SCORING datasets must not invent scores if there is no active model; return a truthful FAILED/ACTIVE_MODEL_REQUIRED or otherwise documented blocked state within existing status vocabulary. Do not yet build ML or UI. Test malformed files, row errors, oversized streams, source/license validation, purpose RBAC and job state. Report results and stop.
```

**Expected:** upload/API, storage abstraction, worker task, validation tests, progress state transitions.  
**Verify:** 202 job, queue status progresses, invalid upload refused/sanitized, row cap enforced, training file never produces operational transactions.  
**Common errors/fixes:** worker cannot reach storage -> configure shared service endpoint; duplicate deliveries -> durable job lock/idempotency; CSV encoding errors -> reject with named code; missing active model -> don't mark fake completion.  
**Done when:** file validation/jobs work with real status and no mislabeled success.

---

## Week 3 | Phase 5: Model training and activation

**Goal:** Trusted repeatable classifier plus anomaly model, with valid held-out evidence.

**Tasks:** synthetic fixture generator, strict features, preprocessing, temporal split if supported, Logistic Regression, Isolation Forest, hold-out metrics, model artifact/digest, admin train route and active model APIs, trusted artifact loading and versioning.

**Exact VS Code agent prompt:**

```text
Read the six /docs and do Phase 5 only. Build a reproducible synthetic transaction TRAINING dataset generator without real personal or financial data. Implement backend ML training with training-only preprocessing, Logistic Regression, Isolation Forest, documented held-out split, class-balance checks, PR-AUC/precision/recall/F1/confusion matrix, and trusted bundle checksum/feature schema. Add Celery models.train_baseline, GET /api/v1/admin/models, POST /api/v1/admin/models/train, POST /api/v1/admin/models/{id}/activate, GET /api/v1/models/active. Activation must enforce one active bundle per organization and ADMIN role. Report observed model metrics honestly. Unit and integration test train, save, load and activate; stop before Phase 6.
```

**Expected:** deterministic training module, private bundle, DB `model_versions`, admin APIs, fixture data, metrics tests.  
**Verify:** training job completes, metrics come from hold-out, checksum validated, activation changes only one active record, unsupported/bad dataset rejected.  
**Common errors/fixes:** only one label/class -> synthetic dataset balance and explicit refusal; leakage -> fit transformers on train only; artifact mismatch -> schema/checksum compatibility check.  
**Done when:** trusted active model can be loaded and produces bounded supervised/anomaly values on fixture input.

## Week 3 | Phase 6: Direct transaction scoring and CSV scoring

**Goal:** Produce one durable explanation-ready risk result and optional alert per input.

**Tasks:** canonical single-transaction API, deduplication, prior-only behavioral features, score formula, bands, alert in same transaction, scoring-data CSV worker completion, internal audit/latency trace.

**Exact VS Code agent prompt:**

```text
Read six /docs and execute Phase 6 only. Implement POST /api/v1/transactions, GET /api/v1/transactions and GET /api/v1/transactions/{id}. Use canonical schema, prior-transaction-only features, active model bundle, fixed weighted 0–100 composite score, configured risk bands, and exactly one alert when score reaches alert threshold. Persist transaction, scoring_results, optional rule_hits/alert and audit event atomically. Enforce unique external_id: same normalized payload replay 200 with same result; different payload 409. Complete SCORING CSV worker with identical scoring service, per-row atomicity and honest job counters; use SUCCEEDED with failed_rows > 0 and visible partial-row warning if some rows fail. No new UI. Run integration and concurrency tests; stop.
```

**Expected:** scoring domain service, transaction routers, CSV scoring integration, DB state and tests.  
**Verify:** direct POST -> 201 score and optional alert; replay -> 200 no duplicate; conflicting replay -> 409; CSV creates consistent scores and reports row outcomes.  
**Common errors/fixes:** no active model -> return `ACTIVE_MODEL_REQUIRED`; wrong feature order -> assert schema; concurrency duplicates -> unique key + retry-safe DB boundary; historical features from future -> timestamp tests.  
**Done when:** deterministic fixtures reconcile between API response and relational rows.

---

## Week 4 | Phase 7: Rules, reasons and explainability

**Goal:** Show a defensible reason for every generated risk score.

**Tasks:** versioned rules and their parameter snapshots, SHAP top supervised feature contributors for compatible linear model, breakdown, explanation status, admin rule API, threshold editor endpoint, risk caveats.

**Exact VS Code agent prompt:**

```text
Read the six /docs and implement Phase 7 only. Finish rule engine (AMOUNT_OUTLIER, HIGH_VELOCITY, DEVICE_CHANGE), persist snapshot details in rule_hits, and add top supervised-model SHAP LinearExplainer features when compatible. Add GET /api/v1/transactions/{id}/explanation, GET/PATCH /api/v1/admin/settings, and PATCH /api/v1/admin/rules/{id}. Explicitly distinguish supervised probability, anomaly percentile, rule signal and composite score; never call composite score a probability. Return COMPLETE or PARTIAL explanation status with honest fallback. Validate threshold ordering, config versions, role and audit history. Test expected rule hits and missing-history behavior; stop.
```

**Expected:** explainability service, rule settings APIs, stable explanations and audit events.  
**Verify:** component breakdown matches score and weights; SHAP attribution describes only supervised component; previously scored records stay unchanged after admin rule edits.  
**Common errors/fixes:** SHAP feature-name mismatch -> align transformed feature mapping; slow explanation -> bounded feature count and cached explainer; drift in rules -> persist evaluated parameters.  
**Done when:** every scored transaction shows genuine, cautious, reproducible reasons or explicit partial status.

## Week 4 | Phase 8: Alert and case APIs

**Goal:** Durable investigation workflow with audit trail.

**Tasks:** alert list/dismissal, case create/read/list, `OPEN` to `IN_REVIEW` to `CLOSED`, notes, mandatory resolution, 409 conflict handling, persistent case events and audit logs.

**Exact VS Code agent prompt:**

```text
Read all six /docs and execute Phase 8 only. Implement GET /api/v1/alerts, POST /alerts/{id}/dismiss, POST /alerts/{id}/cases, GET /cases, GET /cases/{id}, PATCH /cases/{id}, POST /cases/{id}/events, POST /cases/{id}/resolve. Enforce exact statuses: alerts NEW/IN_CASE/DISMISSED, cases OPEN/IN_REVIEW/CLOSED; closing requires CONFIRMED_FRAUD/FALSE_POSITIVE/INCONCLUSIVE and nonblank note. Use row locks or version checks, one case per alert, append-only case_events, and redacted audit_logs. Add role/org boundary and concurrency tests. No UI yet, stop after verification.
```

**Expected:** case and alert routers/services/tests, append-only events and atomic transitions.  
**Verify:** alert -> case -> note -> in review -> closed; invalid reclose/dismiss rejects; concurrent requests create one case.  
**Common errors/fixes:** stale version -> return 409 with refresh guidance; FK mismatch -> join through scoring_results; blank resolution note -> reject via validation.  
**Done when:** all state transitions and audit records are consistent.

---

## Week 5 | Phase 9: UI shell, login, legal drafts for owner review

**Goal:** Accessible professional interface foundation, no fake data or stock designs.

**Tasks:** responsive light-first design tokens, desktop sidebar and mobile menu, login page, auth session flow, route guards, system feedback, custom 404, Privacy and Terms **draft routes for review** (must not publish falsely reviewed legal text), an original favicon/logo draft clearly tracked for final owner review before launch.

**Exact VS Code agent prompt:**

```text
Read all six /docs and execute Phase 9 only. Build the Next.js app shell with light-first neutral design, sharp 6px buttons (not pills), strong typography, semantic nav/footer, login/logout/me session handling, guarded routes, accessible mobile drawer menu and custom 404. Add /privacy and /terms as clearly marked OWNER-REVIEW DRAFT content that accurately describes synthetic-only demo and does not pretend legal approval. Use an original locally created favicon for development and confirm its final version before launch; no AI branding or unauthorized badge removal. Review UI UX Pro Max skill only if installed. Consider selected Kokonut UI controls or Motion transitions **only if necessary** and after source/license/a11y review; prefer native components. Do not invent icon/font sources, reviews or metrics. Test keyboard/menu, 320/375/768/1440px overflow, reduced motion and sign-in flows in a real browser. Report actual results and stop.
```

**Expected:** route shell, login, menu, reusable buttons/forms/status components, legal draft pages and basic metadata.  
**Verify:** correct auth redirect, no protected flash, menu keyboard works, zero horizontal **page** overflow, footer routes valid.  
**Common errors/fixes:** hydration mismatch -> remove browser-only server assumptions; cookies missing -> same-origin proxy/CORS config; phone nav clipped -> flex `min-width:0`, overflow handling, appropriate table cards.  
**Done when:** clean accessible navigation and working auth across viewports.

## Week 5 | Phase 10: Transactions and upload screens

**Goal:** Analyst can submit, upload and explain a simulated transaction through UI.

**Tasks:** `/transactions`, `/transactions/upload`, `/transactions/[id]`, forms, filters, cursor pagination, job polling/progress, breakdown, rule hits, explanations, error/retry/empty states.

**Exact VS Code agent prompt:**

```text
Read all six /docs; execute Phase 10 only. Build /transactions, /transactions/upload, and /transactions/[id] using existing APIs, with responsive list/cards, honest filters, new simulated transaction form, TRAINING/SCORING permission selector, CSV progress via /jobs/{id}, and score explanation showing components, rule hits, SHAP supervised features and caveat. Use real API responses only, not mocked success/metric counters. Handle duplicate ID, invalid CSV, no active model, PARTIAL explanations, failure and empty states. Test complete browser journey and mobile widths; stop.
```

**Expected:** transaction components/pages, API client typing, validations, responsive states and tests.  
**Verify:** submit one transaction, see real returned score, upload valid/invalid CSV, page reflects backend statuses; all actions clickable and truthful.  
**Common errors/fixes:** CSRF 403 -> include CSRF token; 409 replay -> show existing result; row progress stuck -> poll persisted job and stop polling terminal states.  
**Done when:** one analyst can use the core scoring system with no developer tools.

---

## Week 6 | Phase 11: Dashboard, alerts and cases UI

**Goal:** Complete alert-to-resolution browser journey.

**Tasks:** `/dashboard`, `/alerts`, `/cases`, `/cases/[id]`, real chart data, filters/pagination, alert-to-case, dismissal reasons, case notes, resolution dialog and activity timeline.

**Exact VS Code agent prompt:**

```text
Read six /docs and execute Phase 11 only. Build /dashboard, /alerts, /cases and /cases/[id]. Use only measured records from GET /api/v1/dashboard/summary and alerts/cases APIs. Dashboard polls every 10 seconds while active and shows last-updated/stale state. Implement open-case, dismiss with reason, IN_REVIEW, append note, and close with outcome plus note. Show timeline, transaction link, visible success/error feedback and concurrency refresh. Make tables usable as mobile cards at 320/375px. No fabricated statistics. Browser-test the full path, report findings and stop.
```

**Expected:** live-feeling dashboard, alerts and cases interfaces, realistic chart and workflow states.  
**Verify:** transaction crosses threshold -> alert appears -> case opened -> case closed -> real aggregate count changes; no inaccessible modal or mobile overflow.  
**Common errors/fixes:** stale data -> invalidate cache/refetch; double action -> disable pending control and handle 409; charts clip -> responsive container and visible table fallback.  
**Done when:** complete evidence-based investigation through the browser.

## Week 6 | Phase 12: Reports and admin screens

**Goal:** Manager reports and admin-only governance controls.

**Tasks:** reports summary/export backend and UI; `/reports`, `/admin/settings`, `/admin/users`; admin model train/activate, rules/thresholds, user role changes, last-admin guard, audit summary.

**Exact VS Code agent prompt:**

```text
Read all six /docs and do Phase 12 only. Implement GET /api/v1/reports/summary, POST /reports/exports, GET /reports/exports/{job_id}/download with reports.create_csv worker and private expiry; build /reports UI for date-filtered actual counts and queued authenticated download. Build /admin/settings (model versions, training action, activation, risk bands, rules) and /admin/users (role changes, last-admin protection) using existing admin APIs, implementing GET /api/v1/admin/users and PATCH /admin/users/{id}/role if still pending. Guard backend and frontend, audit changes. Test report values and role denials; stop.
```

**Expected:** report export worker, reporting UI, admin configuration/role screens, role-aware tests.  
**Verify:** report CSV matches filtered records and requires session; admin thresholds change only future scores; analyst access denied to admin; cannot demote last admin.  
**Common errors/fixes:** timezone date off-by-one -> UTC boundary conversion; export blocked after browser refresh -> persisted job lookup; last admin race -> row-lock membership transaction.  
**Done when:** operations and governance workflows are complete, with truthful data.

---

## Week 7 | Phase 13: Full integration and regression suite

**Goal:** Prove workflow integrity and fix failures before visual polishing.

**Tasks:** unit, service-level PostgreSQL/Redis integration, deterministic ML fixture tests, browser E2E, duplicate submission/race tests, migration smoke, fixture reset, screenshot inspection, explicit test report.

**Exact VS Code agent prompt:**

```text
Read six /docs and execute Phase 13 only. Add and run comprehensive unit, PostgreSQL+Redis integration, and Playwright browser E2E tests for login, TRAINING CSV -> model train/activate, single and CSV scoring, explanation, alert, case transition/resolve, report export, admin RBAC, empty and error states. Add deterministic synthetic fixtures and a safe local reset. Exercise duplicate/race and partial job failures; check DB reconciliation. Fix scoped defects only. Produce a test matrix with actual commands, exit codes, failures and coverage limitations. Do not deploy; stop.
```

**Expected:** reproducible tests, a CI-ready test matrix and fixed defects.  
**Verify:** clean DB run passes test suite; ensure relevant negative and concurrency cases are covered, no assertion that unrun tests passed.  
**Common errors/fixes:** flaky async tests -> explicit polling timeout/fixtures; DB residue -> isolated test schema; nondeterministic model -> fixed random state and pinned data.  
**Done when:** critical paths and failure paths pass and results are recorded.

## Week 7 | Phase 14: Security, responsiveness, accessibility and measured performance

**Goal:** Turn MVP into credible engineering demonstration.

**Tasks:** audit headers/cookies/CSRF, origin restrictions, file validation, logs/redaction, consent/privacy statements, route authorization, focus/contrast, mobile overflow, no broken buttons/links, image optimization, latency measurement, test actual targets.

**Exact VS Code agent prompt:**

```text
Read all six /docs; execute Phase 14 only. Audit application security (cookies, Argon2id, CSRF, RBAC/org isolation, rate limiting, input/file limits, private exports, secret/log redaction). Check every route at 320, 375, 768, 1024 and 1440px for horizontal page scrolling, working menus, focus, chart fallback, correct success/error and empty states. Test links, nav, footer, logo, forms and custom 404. Run accessible keyboard/a11y checks and load-test warm direct scoring at 1 req/s, reporting observed p95 and machine. Fix actual defects; do not invent passing evidence or start deployment. Stop with a QA report.
```

**Expected:** security and QA findings, fixes, measured load result, accessibility and viewport matrix.  
**Verify:** protected downloads/cross-org IDs fail safely, no sensitive logs; screenshot/automated measurements show no page overflow; no broken links/forms.  
**Common errors/fixes:** insecure local-only cookie configuration -> production-specific Secure settings; small-screen table width -> switch to card view; flaky load tests -> warm model and record sample duration/hardware.  
**Done when:** all must-have defects fixed or launch blocked explicitly.

---

## Week 8 | Phase 15: Deployment, policies, custom domain and public readiness

**Goal:** Prepare an honest hosted demo, without bypassing launch requirements.

**Tasks:** owner chooses [hosting], [database], [Redis], [object storage], [custom domain]; HTTPS, secure env and storage, worker health, backup/restart; finalize Privacy and Terms from actual data practices (owner review), favicon, titles/meta, robots/indexing decision, copyright year, builder branding compliance.

**Exact VS Code agent prompt:**

```text
Read six /docs. Execute Phase 15 only after the owner supplies and explicitly approves hosting, object storage and custom domain details. Prepare managed deployment for frontend, FastAPI, Celery worker, PostgreSQL and Redis, with private objects, secure environment variables, HTTPS, readiness checks and safe migrations. Connect and verify the owner-provided custom domain. Finalize /privacy and /terms based on actual data/retention/services and flag for owner/legal review rather than claiming legal approval. Add verified favicon, correct page titles/meta descriptions, custom 404, current year and correct footer. Remove unwanted AI-builder branding only if permitted by provider terms. Do not publish publicly unless every launch gate passes. Report blockers and stop.
```

**Expected:** deployment config, owner-reviewed policies, domain/HTTPS evidence, release checklist draft, operational README.  
**Verify:** health on real HTTPS domain, DB+worker connectivity, private objects, policies and metadata, DNS/certificate, deployment rollback steps.  
**Common errors/fixes:** DNS propagation -> wait/recheck and do not assert success; CSRF/CORS mismatch -> exact production origin; worker process sleeping -> choose host with always-on worker; legal content outdated -> review actual service list.  
**Done when:** owner reviews all legal and infrastructure details and domain/security checks pass; otherwise **not launched**.

## Week 8 | Phase 16: Final release QA, README, portfolio and demo

**Goal:** Public, reproducible, resume-ready demonstration with evidence.

**Tasks:** run final site audit, real sample data labeling, metrics and latency evidence, dataset/license manifest, architecture diagrams, README, screenshot capture, demo script, tag/release plan; no fake product claims. Public launch only if gate is clear.

**Exact VS Code agent prompt:**

```text
Read all six /docs and execute Phase 16 only. Run the full release gate: working custom-domain HTTPS, favicon, owner-reviewed Privacy/Terms, branding compliance, no horizontal scrolling/mobile overflow, accessible mobile menu, no broken links/buttons, working logo/footer/contact links where present, correct titles/meta/copyright/404, compressed images, success/error/empty states, no placeholders or unused nav, security and tests. Record real model metrics/latency and clearly mark synthetic/demo data. Write thorough README with installation, system architecture, data policy, model evaluation, API docs, tests, limitations, screenshots, demo steps and resume-safe achievement bullets based only on measurements. Provide pass/fail evidence and unresolved blockers. Do not claim zero bugs or launch unless owner explicitly approves release.
```

**Expected:** final QA record, README, demo assets, traceable commit/release, publish recommendation.  
**Verify:** manual demo from login to export on production domain; full tests pass; no unresolved launch blocker.  
**Common errors/fixes:** dead link -> fix route then re-scan; fake/preset values -> replace with real aggregated observations; missing policy/domain -> leave staging private.  
**Done when:** release checklist passed with evidence and owner explicitly permits launch.

---

## 3. Git workflow and review gates

- Repository branch `main` must remain runnable. Each phase uses a short-lived branch, e.g. `feat/phase-06-scoring` or `fix/case-concurrency`.
- Before the agent edits: `git status` clean or explain pending changes; state file list. Never mix documents/prototype work unexpectedly.
- Commits are small and descriptive (`feat(scoring): add atomic transaction scoring`, `test(auth): cover expired sessions`).
- Each phase ends with local tests and self-review; merge to `main` only with reviewed diff and passing required checks.
- CI on pull requests: backend lint/unit and integration, frontend lint/type/build, minimal Playwright smoke; full performance tests may be manual on documented hardware.
- Never commit `.env`, real secrets, uploaded data, unlicensed datasets, generated private artifacts, or credential screenshots.
- If an agent change breaks a prior phase, revert or fix before continuing. Capture decisions in an optional `docs/decision-log.md` only during an instructed implementation phase, not as a seventh planning deliverable.

## 4. Risk register with fallbacks

| Risk | Trigger | Fallback |
|---|---|---|
| Stretch target slips or agent reaches limits | Core workflow incomplete by target milestone, agent quota exhausted or fatigue causes errors | Use 8-week baseline, switch to review/tests/docs while agent unavailable, defer optional export polish; never skip critical quality gates |
| Public dataset incompatible | Missing time/device/customer columns | Use canonical synthetic generator; document that velocity uses fictional history |
| Imbalanced or weak ML performance | Unstable PR-AUC or one-class split | Rebalance **training folds only**, try regularization/feature fixes, report actual limitation rather than fabricating accuracy |
| SHAP fragile or slow | Explanation errors/latency | Persist PARTIAL status and real rule/component reasons, fix attribution in a scoped follow-up; do not show fake SHAP |
| Worker/storage cost | Managed services exceed budget | Keep a private local demo and delay public launch until domain+hosting requirements can be met |
| CSRF/session issue | Failed protected browser submissions | Fix auth boundary first; never disable security for demo convenience |
| Data privacy/licensing ambiguity | Dataset provenance unknown | Do not ingest dataset; synthetic fixtures only |
| Model cache disagrees with DB | Activation followed by stale scoring version | Load/check active version per request or synchronized cache invalidation; test model version ID |
| Duplicate scoring under retries | Parallel worker requests same external ID | Rely on DB uniqueness + idempotent transactional service |
| Mobile overflow | 320px layout breaks | Replace tables with summary cards, fix long text and flex shrink, retest all routes |
| Hosting lacks persistent worker | CSV/model jobs remain queued | Pick always-on worker host or keep project non-public until infra works |
| Legal/domain/branding blocker | Custom domain or policies missing | No launch. Continue private staging and owner review |
| Agent introduces unrelated features | Large unexplained diffs | Reject diff, revert to checkpoint, restate phase-specific prompt |
| UI dependency bloats bundle or license is unsuitable | Third-party component performs poorly or imposes incompatible terms | Use accessible native CSS or an already reviewed chart library; remove unnecessary packages |
| Skill conflicts with product design | UI UX Pro Max suggests decorative effects, fake KPI examples or prohibited button styles | Explicit PRD/UIUX brief override; strip demo content and require real APIs |

### Frontend implementation decisions for Phases 9–14

| Reference | Phase | Rule |
|---|---|---|
| UI UX Pro Max skill | 9–14 | Check it is installed, read instructions, accept only guidance compatible with `/docs` |
| Motion (motion.dev) | 9 / 11 | Optional subtle menu, sidebar and dialog transitions; honor reduced motion |
| Kokonut UI (kokonutui.com) | 9 / 10 / 11 | Select and adapt accessible controls only, no prebuilt AI hero or novelty effects |
| Bklit UI (bklit.com/docs/components) | 11 / 12 | Prefer bar and line charts with real data, labels, text equivalents; verify terms and dependency size |
| Anime.js (animejs.com) | Optional | Defer unless a needed interaction cannot be handled simply with CSS/Motion |
| ThreeUI (threeui.com/browse) | Not planned for MVP | Research only; no default WebGL or decorative 3D |
| Manus (manus.im) | Research only | Not a runtime dependency, not a replacement for VS Code agent |

Update UI phase plans and definition-of-done checks to include desktop/phone screenshots, working route title/meta, responsive menu and focus, valid chart data, action feedback and no horizontal page overflow.

## 5. Quality gates at every phase

| Gate | Requirement |
|---|---|
| Build | App/code compiles, migrations apply safely |
| Correctness | Positive, negative, and relevant replay/concurrency tests pass |
| Safety | No secrets/real financial data, RBAC verified, errors redacted |
| Design | No forbidden visual/copy patterns, no fake metrics |
| Functionality | Buttons, links and forms exercised, not merely rendered |
| Responsiveness | Primary UI tested for page overflow at 320/375/768/1024/1440px |
| Documentation | Changed behavior reflected in docs or ADR proposal |
| Evidence | Agent reports actual commands, outputs, tests, failures, and limitations |

### Hard blockers for public launch

- Custom domain connected and HTTPS verified.
- Favicon installed and custom 404 operational.
- Privacy Policy and Terms and Conditions accurate and approved by owner (legal review advised where appropriate).
- Unwanted AI-builder branding removed **if contractually permitted**, or alternative host chosen.
- All pages have correct titles/meta and accurate copyright year.
- No broken internal/external links, buttons, forms, footer links, logo links, or contact links if used.
- No horizontal page scroll or viewport overflow; every screen mobile-optimized; mobile menu works.
- No placeholder content, unused nav, fake metrics/testimonials/customer counters, AI-slop visuals/copy, excessive motion or cursor animation.
- Visible success, error, loading and empty states; keyboard and basic accessibility checks pass.
- Compressed images/assets, secure cookies, CSRF, cross-organization guards, private file storage and tests pass.
- Models and results clearly identified as synthetic/public-demo only. No claims of zero bugs or unmeasured performance.

## 6. Portfolio README outline

1. Product overview with one factual sentence and demo-only disclaimer.
2. Evidence-led screenshots and short video link [demo media: to be added].
3. Architecture diagram, service responsibilities and request/job flow.
4. Stack and why each component was selected.
5. Local setup with prerequisites and environment variables (no secret values).
6. Sample-data generation, dataset provenance/license, canonical CSV schema.
7. Model approach: supervised + anomaly + rules, score weights, hold-out evaluation, caveats and SHAP scope.
8. REST endpoint overview and sample safe request/response documentation.
9. DB schema, ACID/idempotency choices, queue retry states and audit policy.
10. Unit/integration/E2E commands and actual recorded outcomes.
11. Security controls, privacy/retention and limitations.
12. Deployment instructions and custom domain [to be added].
13. Known gaps and practical v2 roadmap.

## 7. Five-to-seven-minute viva / demo script

| Time | What to demonstrate | Engineering explanation |
|---|---|---|
| 0:00–0:40 | State problem and disclose **synthetic demo data** | Operational fraud screening, not real bank adjudication |
| 0:40–1:20 | Log in as analyst; dashboard with actual fixture records | Session auth, RBAC, database aggregates, polling |
| 1:20–2:10 | Submit suspicious synthetic transaction | Canonical validation, prior-only behavioral features, synchronous score |
| 2:10–3:05 | Open transaction details and explanation | Three scoring components, SHAP supervised factors, caveat, model version |
| 3:05–4:00 | Navigate new alert and open case | DB constraints, ACID transaction, unique alert/case |
| 4:00–4:45 | Add note, set IN_REVIEW, close with outcome | Optimistic concurrency, append-only events, audit trail |
| 4:45–5:30 | Export real date-filtered CSV report | Celery/Redis, durable job status, private artifact |
| 5:30–6:10 | ADMIN shows configured rules and model metrics | Held-out PR-AUC/precision/recall, rule versioning, permissions |
| 6:10–7:00 | Show tests, architecture, metrics measured on machine, remaining limitations | DBMS, OS, CN, DSA, Software Engineering concepts and honest trade-offs |

**Practice fallback:** If export takes longer, show persisted job status and revisit after other screens. If no alert crosses threshold in an unscripted fixture, use a documented deterministic synthetic fixture rather than changing risk evidence to fake a result.

## 8. Academics mapping

| Subject | Concrete material to explain |
|---|---|
| DBMS | 18 normalized tables, FK constraints, indexing, ACID case transitions, unique active model |
| OS | Worker processes, background jobs, retries, race conditions, concurrency |
| CN | HTTP verbs/status codes, cookies/CSRF, REST, TLS, polling vs. push, rate limits |
| DSA | Queues, hash/idempotency, ordered/cursor pagination, indexed time-window lookups |
| Software Engineering | PRD/TRD, iterative phases, tests, Git branch/PR process, CI/CD, risk register |
| AI/ML | Imbalanced classification, anomaly detection, explanations, leakage prevention and held-out evaluation |

## 9. Owner approval and phase boundary

The owner approved the SentinelAI plan on **2026-10-16**, and approved **updating the six documents first**. That documentation revision alone does not mean Phase 1 has been executed. The VS Code agent may implement **Phase 1 only when explicitly asked**, and may advance to each next phase only after review and a new `next`/phase instruction. Public launch requires separate owner approval after the release gate is passed.
