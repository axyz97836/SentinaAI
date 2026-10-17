# SentinelAI | Product Requirements Document (PRD)

**Version:** 1.1 approved baseline (revised 2026-10-16)  
**Status:** Owner approved; documentation revised before the first implementation phase. Each coding phase still requires explicit instruction.  
**Product:** SentinelAI, Fraud & Risk Intelligence Platform  
**Owner:** Student developer, IIIT Lucknow  
**Target build window:** 5–7 week stretch target; 8-week conservative baseline and contingency, one developer  
**Primary purpose:** Portfolio, learning, viva, and an honest working demonstration

## 1. Executive summary

SentinelAI is a **demonstration-grade fraud and transaction-risk operations platform**. It accepts simulated or openly licensed transaction datasets, assigns a risk score using rules, an anomaly detector, and a supervised classifier, and helps an analyst investigate alerts through a structured case workflow. Risk scores contain interpretable reasons and traceable model versions. A risk manager can review patterns and export reports. An administrator can manage roles, rules, thresholds, and active model versions.

**It is not** a live bank integration, a production fraud prevention guarantee, or a service authorized to make financial decisions.

### Explicit decisions and changes from earlier discussion

| Earlier context | Decision for this PRD | Reason |
|---|---|---|
| Advanced project originally outlined over 12 weeks | Set a **6–8 week target** with an eight-week working plan | New owner constraint |
| Fraud, drift, forecasting, segmentation, NLP, RAG, API key manager all in early scope | Prioritize fraud scoring, alert/case operations, explanations, uploads, reporting, and admin; move drift to v2 and other modules later | One-developer feasibility |
| “Real time” was broad | Define **near-real-time** as synchronous single-transaction scoring and alert creation, followed by dashboard refresh at most every 10 seconds | Testable, honest, achievable scope |
| “User behavior” was broad | Analyze **transaction-linked behavior** such as repeat transactions within a time window and device changes; no general clickstream tracking | Avoid building a second data platform |
| Previously discussed general-purpose multi-project workspaces | One demo organization, but organization-scoped database schema and access control | Simpler MVP without unsafe cross-tenant assumptions |
| Live deployment was previously optional in the schedule | Public launch is blocked until domain, security, branding, legal pages, and launch checklist pass | Owner's mandatory release policy |

### Decisions added after initial planning (2026-10-16)

- **Primary IDE/agent is now VS Code with the user's chosen GPT-6 Astra agent**, not Google Antigravity. References to Antigravity in older discussions are historical; instructions in the updated implementation plan are for VS Code.
- Owner has asked the agent to install **UI UX Pro Max**. Installation is **not assumed successful** until its skill file is present and readable. Its output is optional guidance, never overriding SentinelAI requirements.
- Owner-supplied frontend references are Motion, Bklit UI, Kokonut UI, Anime.js, ThreeUI and Manus. Reference approval does not mean installing or copying them automatically.
- **Speed is subordinate to quality**. Accelerated 5–7 weeks is a stretch target; 8 weeks is the reference roadmap. We will not skip mobile, security, accessibility, legal pages, actual measurement or end-to-end testing to meet a date.
- All website details must be functional and truthful: no fake counters, fake model metrics, copy filler, review cards or invented social proof; include correct favicon, titles/meta, 404, footer/contact links (only when legitimate), success/error/empty states and zero horizontal page overflow.

## 2. Problem statement and vision

**Problem:** An ML notebook may detect suspicious transactions, but it rarely shows how analysts ingest data, explain individual scores, act on alerts, audit decisions, and evaluate model behavior in a coherent workflow.

**Vision:** An understandable risk-operations workspace where every suspicious transaction can move from ingestion to a traceable decision, without claims of real-world financial reliability.

**One-line pitch:** Score simulated transactions, investigate risk alerts, explain model decisions, and close the case with an audit trail.

## 3. Target users and personas

| Persona | Job to be done | Primary screens | Constraints |
|---|---|---|---|
| **Fraud Analyst** | Review incoming suspicious transactions, understand reasons, and investigate | Dashboard, Transactions, Alerts, Cases, Case Detail | Can triage and resolve cases but cannot change global risk configuration |
| **Risk Manager** | See risk trends, monitor queue outcomes, and export evidence | Dashboard, Alerts, Cases, Reports | Read access across demo organization; can investigate and export |
| **Admin** | Configure the system, manage access, train/activate a model | Admin Settings, Admin Users, all operational screens | Must preserve at least one active admin; settings changes audited |

The same person can switch between **seeded demo accounts** in a local demo. Real user invitation and organization self-registration are not required for MVP.

## 4. In-scope product concept

- **Data:** Synthetic transactions with fictional customer/device references; optional public datasets only after verifying license and mapping to the canonical schema. Every upload records `source_kind`, and public data needs a license reference. Public datasets must be demonstrably synthetic or otherwise non-sensitive and de-identified; actual person-linked financial transaction records are prohibited even if publicly downloadable.
- **Ingestion modes:** One simulated transaction via authenticated REST/UI; CSV upload classified as `TRAINING` or `SCORING`.
- **ML:** Logistic Regression classifier, Isolation Forest anomaly detector, and auditable velocity/amount/device rules. A transparent weighted **composite risk score (0–100)**, **not a calibrated probability**.
- **Decisions:** Low 0–39, medium 40–69, high 70–84, critical 85–100 by default; admins can change thresholds subject to ordering constraints. Default alert threshold is 70.
- **Operations:** Inbox of risk alerts, create a case, add notes/status, and close with a mandatory resolution.
- **Evidence:** Persist scoring model version, rule hits, explanation, actor/timestamps, and audit log.

### Scoring principle

Default illustrative score formula: `round(100 * (0.60 * supervised_probability + 0.25 * anomaly_percentile + 0.15 * rule_signal))`. Every component is normalized to [0,1]. These coefficients are initial, **subject to validation on held-out synthetic/public data** and frozen in the model version. The score does **not** represent a true fraud probability. Rule explanations are never presented as proof of fraud.

## 5. Prioritized requirements (MoSCoW and release)

| ID | Requirement | MoSCoW | Release | Acceptance evidence |
|---|---|---|---|---|
| F01 | Email/password sign-in, sign-out, session expiry | Must | MVP | Authorized login, denial, logout tests |
| F02 | Enforce `ANALYST`, `RISK_MANAGER`, `ADMIN` roles and organization isolation | Must | MVP | 403/404 access tests and role matrix |
| F03 | Upload `TRAINING` or `SCORING` CSV, validate max 10 MiB / 10,000 rows, track job | Must | MVP | Good/bad files and async status tested |
| F04 | Create one transaction with unique external ID and idempotent replay | Must | MVP | 201 / same-data 200 / conflict 409 |
| F05 | Train/evaluate and activate one versioned model bundle | Must | MVP | Saved metrics and active-version trace |
| F06 | Combine rule, anomaly, and supervised signals into a risk score | Must | MVP | Deterministic integration fixtures |
| F07 | Show top score reasons, rules fired, model version, and explanation caveat | Must | MVP | Explanation viewed per transaction |
| F08 | Generate an alert at or above the current alert threshold | Must | MVP | Exactly one alert per qualifying scored transaction |
| F09 | Triage alerts: open case or dismiss with recorded reason | Must | MVP | Status updates and audited transitions |
| F10 | Case workflow `OPEN` → `IN_REVIEW` → `CLOSED`; resolution and note required to close | Must | MVP | Closing without resolution rejected |
| F11 | Dashboard of real observed demo-data counts and recent alerts | Must | MVP | Aggregates match DB, no fabricated metrics |
| F12 | Search/filter/paginate transaction, alert, and case lists | Must | MVP | Pagination and filter tests |
| F13 | Export date-filtered CSV report as a background job | Should | MVP | Download correct authorized export |
| F14 | Admin changes thresholds, rule enablement/parameters, user roles | Must | MVP | Audit log + guarded thresholds/last-admin test |
| F15 | Responsive layout, working mobile navigation, accessible feedback and empty states | Must | MVP | 320–1440px and keyboard checks |
| F16 | Privacy/Terms, favicon, proper metadata, custom 404, functional footer, domain/HTTPS launch checklist | Must | Launch | Recorded QA pass and working custom domain |
| F17 | Baseline drift monitoring with reference vs. scoring distributions and alerts | Should | v2 | PSI/KS result plus threshold methodology |
| F18 | Forecasting with rolling/walk-forward validation | Could | v2 | Backtest metrics and uncertainty statement |
| F19 | NLP classification of noisy synthetic fraud-report text | Could | v2 | Error analysis on labeled test set |
| F20 | RAG knowledge assistant with linked documents and citation checks | Could | v2 | Answers trace to retrieved source excerpts |
| F21 | Customer segmentation with interpretable group profiles | Could | v2 | Cluster evaluation and business descriptions |
| F22 | Public API keys, per-key quotas, usage dashboard | Could | v2 | Revocation, scope, rate-limit tests |
| F23 | Live WebSocket streaming, multi-bank connectors, automated account blocking | Won't | MVP/v2 | Explicit exclusion |

**Priority rule:** If implementation is late, preserve F01–F12, F14–F16 and move F13 to v2 before weakening security, testing, or case integrity.

## 6. User stories and acceptance criteria

| Persona | Story | Definition of successful behavior |
|---|---|---|
| Analyst | As an analyst, I can submit a simulated transaction and see its risk outcome | Screen displays score, band, factors, model ID, and any created alert; failed submissions have actionable feedback |
| Analyst | As an analyst, I can ingest a CSV and continue other work | Upload returns a job ID; status becomes `QUEUED` / `PROCESSING` / `SUCCEEDED` / `FAILED` with row counts |
| Analyst | As an analyst, I can distinguish suspicious signals from confirmed fraud | Every score uses language “risk signal”; no unsupported conviction or definitive guilt |
| Analyst | As an analyst, I can turn an alert into an investigation | Alert becomes `IN_CASE`, one linked case exists, action attributed to me |
| Analyst | As an analyst, I can resolve an investigation | Case requires an outcome: `CONFIRMED_FRAUD`, `FALSE_POSITIVE`, or `INCONCLUSIVE`, with a note |
| Risk Manager | As a manager, I can filter queues and download a summary | Date bounds applied, counts match stored data, export only available to authorized role |
| Admin | As an admin, I can update alert rules/thresholds | Inputs validated, changes affect new scores only, prior evidence remains unchanged |
| Admin | As an admin, I can train and activate a model | Training job records held-out evaluation; only validated candidate can become active |
| Admin | As an admin, I can change a user's role | Change audited, permissions enforced on next request, cannot demote last admin |

## 7. Non-functional requirements

| Area | MVP target / rule | How to assess |
|---|---|---|
| Single-transaction latency | Warm API p95 under **2 s** for 1 request/s on a documented local test machine | Load test, publish actual hardware/observations |
| Alert timeliness | Alert persisted in same logical scoring operation; dashboard visibly updates within **10 s** via polling | Timestamp and UI timing tests |
| Batch ingestion | <=10 MiB and <=10,000 CSV rows; show truthful progress and failure counts | Boundary tests; no fixed claim for end-to-end batch time |
| Availability | Local demo is restartable; no invented 99.9% SLA | Docker Compose startup and health check |
| Security | Hashed passwords, server-side sessions, CSRF protection, validation, RBAC, secrets excluded from Git | Security test suite and configuration review |
| Data handling | Synthetic or licensed public datasets only; reject direct identifiers and avoid storing full IPs | Dataset policy, fixtures, review |
| Explainability | Persist breakdown, rule hits, top contributing features, active model version | Unit tests and spot inspection |
| Integrity | Unique external transaction ID per organization; one result/alert per transaction; state transitions atomic | Concurrency/integration tests |
| Accessibility | Aim for WCAG 2.2 AA for core routes | Keyboard checks, semantic labels, automated audit |
| Responsiveness | No horizontal overflow at 320, 375, 768, 1024, 1440px | Viewport tests on all screens |
| Maintainability | Types, migrations, unit/integration/E2E tests, code reviewable commits | CI pipeline |
| Observability | Structured logs, request/job correlation IDs, sanitized error messages | Failure injection |

Targets are **acceptance criteria**, not preexisting measured achievements.

## 8. Success metrics and evidence

Metrics must be calculated from real execution of demo datasets; **never invent** user counts, model accuracy, response times, reviews, or business outcomes.

| Product outcome | Evidence to collect | Acceptance criterion |
|---|---|---|
| End-to-end flow works | Demo trace: ingest → score → alert → case → resolution → export | All six steps complete and are auditable |
| Scores are meaningful | PR-AUC, precision, recall, F1, confusion matrix; per-class counts | Stored from held-out set; not just accuracy |
| Explainability is inspectable | Top contributing features plus fired rules and version | Displayed for each scored transaction |
| Operations reflect real data | Dashboard counts cross-checked with SQL | Exact match for test fixtures |
| Robust error behavior | Invalid CSV, duplicate, missing model, unauthorized role, failed export | Informative UI + expected HTTP status |
| Recruiter-ready delivery | Public demo, clean README, diagram, tests, demo walkthrough | Verified before external launch |

## 9. Assumptions, risks, and mitigations

| Assumption or risk | Plan |
|---|---|
| One student available for extended daily work | Target roughly 7–9 hours/day on 5–6 days/week when sustainable; reserve breaks and expect variability from agent limits, debugging, exams or fatigue. This does not guarantee a 5–7 week finish. |
| Public datasets may not carry timestamps/customer/device fields | Canonical synthetic generator is the guaranteed MVP source; public datasets need adapters and licensing review |
| Labeled fraud data is imbalanced | Stratified metrics where suitable; prefer temporal split when time order is meaningful; never resample test set |
| Explanations can be misunderstood | Clearly label score as a heuristic composite, not proof or probability |
| Training and scoring can leak data | Separate `TRAINING` and `SCORING` purposes; no ground truth fed into inference |
| Cloud workers or object storage may cost money | Local Compose + private local object storage first, publish actual hosting constraints later |
| Third-party resource choices unavailable | Leave explicit placeholders; use system fonts and basic components until selected |
| Launch legal pages cannot be generic | Draft from actual data practices, mark for owner review; no assertion of legal approval |

## 10. Out of scope for the MVP

Bank/payment network connections; real identities or bank credentials; real-time card authorization; payment blocking or external enforcement; chargebacks; identity verification; automated model retraining; push/email notifications; full multi-tenant customer onboarding; an in-product API-key marketplace; full streaming infrastructure; customer social profiling; mobile native apps; full RAG/forecasting/NLP/segmentation/drift suites.

## 11. Mandatory design and release policy

- No purple gradients, pill-shaped controls, fake reviews, fake performance metrics, fabricated counters, generic marketing hero language, emoji icons, AI-looking stock photography, unnecessary cursor effects, or excessive scroll animations.
- No em dashes in **website UI copy**. Documentation may use ordinary technical punctuation.
- No horizontal page scrolling, broken links, broken buttons, empty placeholder text, unused navigation, or mobile overflow. Add feedback for success, loading, empty, and errors.
- Use an accessible mobile menu; clickable logo, footer links, phone `tel:` and email `mailto:` if contact information appears.
- Require a favicon, unique page titles, page descriptions, custom 404, valid copyright year at release, and optimized images.
- Do **not** launch before custom domain + HTTPS, Privacy Policy, Terms and Conditions, and legally permissible removal of unwanted AI-builder branding. Do not violate third-party attribution requirements.
- No claim of “zero bugs”; release only after documented testing with known issues reviewed.

## 12. External resource slots

- [Frontend animations: Motion (https://motion.dev) preferred for short purposeful transitions; Anime.js (https://animejs.com) optional for justified custom effects]
- [UI component references: Bklit UI (https://bklit.com/docs/components) for data charts; Kokonut UI (https://kokonutui.com) selectively; ThreeUI (https://threeui.com/browse) research only; Manus (https://manus.im) inspiration only]
- [UI/UX agent skill: https://github.com/nextlevelbuilder/ui-ux-pro-max-skill (verify installation)]
- [Icons: to be added; use simple non-emoji placeholders during planning]
- [Fonts: to be added; default system sans-serif]
- [Datasets and licenses: to be added; synthetic generated data is the fallback]
- [LLM / third-party APIs: to be added; not required for MVP]
- [Hosting provider: to be added]
- [Custom domain: to be added]
- [Additional reference sites: to be added; current supplied sites listed above]

### Release audit evidence (mandatory)

Record screenshots or automated test reports for `/login`, `/dashboard`, `/transactions`, `/transactions/upload`, `/transactions/[id]`, `/alerts`, `/cases`, `/cases/[id]`, `/reports`, `/admin/settings`, `/admin/users`, `/privacy`, `/terms`, and custom 404 at mobile and desktop sizes. Check all usable controls, internal and relevant external links, responsive navigation, contact links only if published, metadata, current-year copyright, compressed assets, auth/error flows, keyboard controls and reduced-motion behavior. Launch is blocked on any critical failure; no unsupported promise of zero bugs.

## 13. Acceptance gate

**Owner approved the project on 2026-10-16.** Work is permitted **one named phase at a time** in VS Code with the owner's AI agent. Updating these documents does not itself start a coding phase. Public launch remains separately gated by QA, domain/HTTPS, legal pages and branding compliance.
