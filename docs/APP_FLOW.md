# SentinelAI | App Flow and User Journeys

**Version:** 1.1 approved baseline (revised 2026-10-16)  
**Status:** Owner approved; no implementation in this documentation update  
**Scope:** Eight-week MVP; synthetic or public licensed data only

## 1. Navigation model

Authenticated app shell uses a left navigation rail on desktop and a keyboard-accessible toggle menu on mobile. Entries: **Dashboard**, **Transactions**, **Alerts**, **Cases**, **Reports**. **Admin Settings** and **Admin Users** appear only to `ADMIN`, but backend RBAC applies even if a route is requested directly.

```text
/                         -> /dashboard if signed in, else /login
/login                    -> /dashboard after successful login
/dashboard
   |-- /transactions
   |      |-- /transactions/upload
   |      `-- /transactions/[id]         (score + explanation)
   |-- /alerts
   |      |-- /transactions/[id]
   |      `-- /cases/[id]               (after opening a case)
   |-- /cases
   |      `-- /cases/[id]
   |-- /reports
   `-- /admin/settings                   (ADMIN only)
           |-- model training/activation panel
           `-- /admin/users               (ADMIN only)

Global links: /privacy, /terms
Fallback: custom not-found page for unknown routes
```

Every screen includes a clickable logo (links to `/dashboard` if authorized, otherwise `/login`), an account/logout control, and footer links to Privacy and Terms. No inactive or dummy links. Contact `mailto:`/`tel:` links only if real owner-approved contact details are supplied.

## 2. Role permissions at a glance

| Action | ANALYST | RISK_MANAGER | ADMIN |
|---|:---:|:---:|:---:|
| Read dashboard/transactions/alerts/cases | Yes | Yes | Yes |
| Submit transaction and scoring CSV | Yes | Yes | Yes |
| Upload training CSV | No | No | Yes |
| Dismiss alert or open case | Yes | Yes | Yes |
| Change case state, close with resolution | Yes | Yes | Yes |
| View reports / request CSV export | Yes | Yes | Yes |
| Train or activate model | No | No | Yes |
| Modify rules, thresholds, roles | No | No | Yes |
| Read audit summaries in admin area | No | No | Yes |

All actions are scoped to the signed-in user's organization. Initial demo has one organization.

## 3. User journey A: Log in and log out

1. User opens `/login`. Page shows brand, email field, password field, and concise sample-data context; no fake testimonials.
2. User enters valid credentials and submits.
3. Frontend calls `POST /api/v1/auth/login`; API validates password, establishes a secure server-side session, and sets cookie.
4. UI navigates to `/dashboard`; `GET /api/v1/auth/me` provides role and organization context.
5. A session expiry redirects to `/login` with “Your session expired. Sign in again.” No protected data remains on screen.
6. User selects Log out. `POST /api/v1/auth/logout` revokes the session and redirects to `/login`.

**Errors:** Incorrect details: “Email or password is incorrect.” Disabled user: generic access message. Network failure: “Sign-in is unavailable. Try again.” Avoid account enumeration.

## 4. User journey B: Dashboard and triage

1. User lands on `/dashboard` after login.
2. UI calls `GET /api/v1/dashboard/summary`; displays counts **derived from demo records**, latest alerts, risk band distribution, and case status summary.
3. Filter by time window (24 hours, 7 days, custom). Count labels include the active selected range.
4. Dashboard refreshes every 10 seconds while the page is active and visibly shows “Last updated” time. Stale data is labeled if polling fails.
5. Clicking an alert opens the relevant transaction detail or case; clicking a count opens its filtered list.

**Empty state:** “No transactions in this date range. Upload a synthetic dataset or submit a sample transaction.” Never show decorative fabricated graphs.

## 5. User journey C: Upload transaction dataset

1. User chooses **Transactions > Upload**, route `/transactions/upload`.
2. User selects dataset purpose: `SCORING` (all roles) or `TRAINING` (`ADMIN` only), then declares `SYNTHETIC` or `PUBLIC_DATASET` provenance. Public datasets require a verified license reference and review confirming that they contain no real personal or financial transaction records.
3. User selects one CSV (max 10 MiB, max 10,000 rows). Show required columns and a link to locally provided canonical demo format, not to an invented external dataset.
4. UI displays filename, file size and a warning to upload only synthetic/licensed public data.
5. `POST /api/v1/ingestions` accepts multipart upload and `purpose`; returns HTTP 202 with `{job_id, status: "QUEUED", dataset_id}`.
6. UI shows status via `GET /api/v1/jobs/{id}`: `QUEUED`, `PROCESSING`, `SUCCEEDED`, or `FAILED`, with valid/invalid/processed row counts.
7. Successful `SCORING` import creates transactions, scores and alerts where appropriate. A successful `TRAINING` import stores a validated dataset for admin model training but does not show imported rows as operational transactions.
8. Button “View transactions” leads to `/transactions`; admin training upload offers “Go to model settings” linking to `/admin/settings`.

**Errors:** Oversize file; wrong extension; missing columns; invalid timestamps/amounts; row limit; duplicate conflicting `external_id`; worker failure. Show a bounded sanitized list of failing row numbers and reason codes (no raw data dump). A row-partial CSV job uses `SUCCEEDED` with `failed_rows > 0` and a prominent “Completed with row errors” message. A job-level failure is `FAILED`. Neither silently discards errors.

## 6. User journey D: Ingest a single simulated transaction

1. User visits `/transactions` and selects **New simulated transaction** (inline form or accessible dialog on that route).
2. Enter `external_id`, synthetic `customer_ref`, time, amount, currency, merchant category, country, channel, optional device reference.
3. Frontend validates basic format, then `POST /api/v1/transactions`.
4. Backend persists and scores it with the active model. Response contains transaction ID, 0–100 score, risk band, scoring result ID, model version and optional alert ID.
5. UI navigates to `/transactions/[id]` and displays score breakdown and reasons.
6. If score >= active alert threshold, alert appears in `/alerts`, ordinarily by the next 10-second poll.

**Errors:** No active model: `409 ACTIVE_MODEL_REQUIRED` with “An admin must activate a model before scoring.” Identical external ID/payload: return existing transaction/result with a non-alarming “Already received” message. ID reused with different content: `409 DUPLICATE_TRANSACTION_CONFLICT` and a clear correction instruction.

## 7. User journey E: Alert generation and triage

1. New scored transaction meets threshold; server atomically stores an `alerts` row with status `NEW`.
2. Analyst opens `/alerts`, filters by `NEW`, risk band, or time.
3. Each row shows synthetic reference, risk band, score, time, concise rule reason and status; no guessed real customer identity.
4. Analyst selects an alert and goes to `/transactions/[id]` to inspect evidence.
5. Analyst chooses **Open case** (`POST /api/v1/alerts/{id}/cases`) or **Dismiss alert** (`POST /api/v1/alerts/{id}/dismiss` with required reason).
6. Opening a case creates exactly one case and changes alert status to `IN_CASE` atomically. Dismissal changes it to `DISMISSED` and leaves an audit record.

**Errors:** Alert already dismissed/in case: show current status, no duplicate case. A concurrency conflict produces 409 and UI refreshes the alert state.

## 8. User journey F: Explain a risk score

1. On `/transactions/[id]`, show amount, timestamp, anonymized references and immutable scoring details.
2. Call `GET /api/v1/transactions/{id}/explanation`; show composite score, component values, fired rules, and the supervised model's top SHAP features if available.
3. Show model version and explanation status (`COMPLETE` or `PARTIAL`).
4. State: “This score is a screening signal, not proof of fraud or a calibrated fraud probability.”
5. Link to the alert/case if they exist. Explain missing context as “Not evaluated,” never as zero risk.

**Error or partial state:** If SHAP could not be produced, render stored score and rule/component reasons with a non-blocking “Some model feature details are unavailable.” Never invent a reason.

## 9. User journey G: Case investigation

1. Analyst opens `/cases`, chooses a case, and lands on `/cases/[id]`.
2. Detail shows linked alert, immutable transaction summary, reasons, case timeline, assignee and status.
3. Analyst marks `OPEN` → `IN_REVIEW` via `PATCH /api/v1/cases/{id}` with optional note.
4. Analyst records observations as a case event via `POST /api/v1/cases/{id}/events` (text max 2,000 chars, no real PII).
5. Case remains available across sessions; timeline records actor and time. No silent editing/deleting of historical events.
6. An alert in status `IN_CASE` links back to the case detail.

**Errors:** Absent case = 404; invalid status transition = 409; lost connection shows unsaved note clearly rather than claiming success.

## 10. User journey H: Resolve a case

1. Analyst clicks **Resolve case** on `/cases/[id]`.
2. Select one required outcome: `CONFIRMED_FRAUD`, `FALSE_POSITIVE`, `INCONCLUSIVE`.
3. Enter required resolution note (max 2,000 chars). This is an analyst conclusion about demo data, not a direct model-training label.
4. `POST /api/v1/cases/{id}/resolve` atomically sets `status=CLOSED`, records outcome, note, close time, and case/audit events.
5. UI shows “Case closed” only after confirmed success; resolves are idempotent for the same outcome/note or return 409 for conflicting edits.
6. Closed cases are read-only in MVP; reopening is v2.

**Errors:** Missing outcome/note = field error; concurrency conflict = refresh and show latest state.

## 11. User journey I: Report export

1. User visits `/reports`, chooses date range (valid UTC boundaries mapped from displayed timezone) and chooses CSV export.
2. Page shows computed totals for transactions by risk band, alerts by status and cases by outcome. `GET /api/v1/reports/summary` supplies values.
3. `POST /api/v1/reports/exports` enqueues export, returning `job_id`.
4. UI polls `GET /api/v1/jobs/{id}`. Once `SUCCEEDED`, button becomes an authenticated link to `GET /api/v1/reports/exports/{job_id}/download`.
5. Download is a real generated CSV with date range, synthetic identifiers and data provenance header/manifest. No prefilled fake numbers.

**Errors:** Empty range: show zero totals and “No records match this period”; export may be disabled with clear explanation. Expired export: ask to regenerate. Unauthorized/other-org download: 404.

## 12. User journey J: Admin settings and users

1. ADMIN selects `/admin/settings`; see active model, thresholds and rules.
2. Threshold edit validates `0 < medium < high < critical <= 100`. Saving uses `PATCH /api/v1/admin/settings`; server stores actor and audit event.
3. Rule activation/parameters are edited through `PATCH /api/v1/admin/rules/{id}`; new settings apply only to newly scored transactions. Historic scores are not rewritten.
4. Admin uploads `TRAINING` CSV and then starts a model training job with `POST /api/v1/admin/models/train`; view status in Jobs control on settings page.
5. After checking stored held-out metrics, ADMIN activates a model with `POST /api/v1/admin/models/{id}/activate`.
6. `/admin/users` lists demo users and lets ADMIN change roles with `PATCH /api/v1/admin/users/{id}/role`. The last active admin cannot be demoted or deactivated.
7. Access by ANALYST/RISK_MANAGER must result in 403/denied screen even if navigation is manually entered.

**Errors:** Invalid threshold ordering, unsuccessful training job, incompatible bundle, last-admin guard, expired session, conflicting version change. Show field-specific recovery.

## 13. One transaction from ingest to alert (system sequence)

```text
Analyst (browser)      FastAPI                PostgreSQL          Model cache
       |                  |                      |                    |
       | POST transaction |                      |                    |
       +----------------->| authenticate, RBAC   |                    |
                          | validate + dedupe    +-- lookup ID ------>|
                          | derive historical signals <--- query -----|
                          | load ACTIVE model ----------------------->|
                          |<--------- supervised/anomaly scores ------|
                          | evaluate enabled versioned rules          |
                          | create risk band & explanation            |
                          | BEGIN DB transaction                       |
                          |  insert transaction + score                |
                          |  if score >= threshold: insert alert NEW   |
                          |  insert audit action                       |
                          | COMMIT ----------------------------------->|
       |<---- 201 / result + optional alert ID ----------------------|
       | Dashboard /alerts poll within 10 s                           |
       | Open case -> alert IN_CASE + case OPEN (one DB transaction)  |
       | Resolve -> case CLOSED + case_events + audit_logs           |
```

For direct submit, keep authoritative transaction+score+alert writes in one ACID boundary. If any step fails before commit, nothing is partially scored. For CSV, the worker processes each valid row using the same transaction-scoring service and records bounded row errors in `job_errors`.

## 14. Global loading, empty, error and accessibility states

| Context | Loading | Empty | Error and recovery |
|---|---|---|---|
| Dashboard | Neutral skeleton with meaningful labels | “No transactions in this period” | Retry + last updated time |
| Transactions | Accessible table loading status | Upload CTA, no fabricated counts | Field feedback; duplicate/no-model handling |
| Alerts | Loading row placeholders | “No alerts match these filters” | Retry; concurrency refresh |
| Cases | Loading list/detail | “No cases yet” | Invalid transition message |
| Reports | Disabled export while job queued; spinner with text | Explain no rows in selected range | Retry generation |
| Admin | Save button disabled during submission | “No training datasets available” | Validation and audit-safe failure |
| Upload/jobs | File size and progress text | “Choose a CSV to begin” | Row error details and retry steps |

All forms expose success and error announcements through accessible live regions, focus the first invalid field, have keyboard support and usable 44px touch targets. Risk states use visible text labels, not only color. Modals/dialogs trap focus and restore it after closing.

## 15. Responsive behavior and route inventory

- 320–767px: single-column content, menu button, responsive cards, tables convert to summarized stacked rows or **contained** horizontally scrollable data regions (never horizontal page overflow), full-width fields.
- 768–1023px: compact sidebar or collapsible navigation and 2-column stat cards.
- >=1024px: fixed sidebar, main content columns, stable data tables, no excessive animation.
- Public routes: `/login`, `/privacy`, `/terms`, custom 404.
- Authenticated: `/dashboard`, `/transactions`, `/transactions/upload`, `/transactions/[id]`, `/alerts`, `/cases`, `/cases/[id]`, `/reports`.
- Admin only: `/admin/settings`, `/admin/users`.

### Full route and interaction audit (release contract)

The mobile drawer is available on **every authenticated route** and exposes only role-authorized destinations. Logo navigates to `/dashboard` when logged in and `/login` when logged out. Login, legal pages and 404 link to valid destinations. Footer legal links must work; phone (`tel:`) and email (`mailto:`) links are included only when real owner-approved contact details exist. Never invent a phone number or email address.

For each route in the navigation map, check: no horizontal **page** scroll at 320/375/768/1024/1440px; accessible mobile navigation and focus management; no dead buttons; form success, validation failure and server-error states; real data or an explanatory empty state; correct `<title>` and description; asset compression; readable charts and text without animation. Missing or incorrect data should be labelled unavailable rather than displayed as fabricated zero. Custom 404 must handle invalid URLs. Public launch is blocked by unresolved critical failures and by missing domain/HTTPS, favicon, approved legal text or applicable branding compliance.

**Visual resources:** use Motion for purposeful menu/dialog transitions; Bklit UI for verified accessible line/bar charts when appropriate; Kokonut UI for carefully chosen controls. Anime.js is optional, ThreeUI generally excluded from MVP and Manus is reference-only. None may change workflow or add new screens without approval; see `UIUX_BRIEF.md`.

## 16. External resource placeholders

[Screen design references: UI UX Pro Max; Manus and ThreeUI as research only; further references to be added]  
[UI components: Bklit UI charts; Kokonut UI selectively; license/quality review required]  
[Icons: to be added]  
[Fonts: to be added]  
[Functional animations: Motion preferred for purposeful transitions; Anime.js optional]  
[Datasets / public sample formats: to be added]  
[External API integrations: to be added, v2 only]
