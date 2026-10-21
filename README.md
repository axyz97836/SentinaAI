# SentinelAI

Local foundation for a synthetic-data fraud and risk intelligence demonstration.
Phase 1 contains a minimal Next.js page, FastAPI health endpoints, PostgreSQL,
Redis, a Celery worker, and private S3-compatible development storage. Phase 2 adds
the approved eighteen-table schema, Alembic migrations and fictional demo accounts.
Phase 3 adds session authentication, CSRF protection and reusable authorization guards.
Phase 4 adds bounded CSV uploads, private storage and durable validation jobs.
Fraud scoring and investigation workflows are not implemented.

The approved [implementation plan](docs/IMPLEMENTATION_PLAN.md) remains authoritative.
All eleven planning/security documents are preserved. This project is not deployed.

## Prerequisites

- Docker Engine/Desktop with Compose v2.20 or newer, running Linux containers.
- Node.js 22.13+ within the 22.x line for native frontend tooling. The pinned Docker
  image supplies the supported runtime for service startup, lint, types and build.
  Node 22.11 can run the environment generator, but does not meet every lint dependency's engine requirement.
- GNU Make (optional; the equivalent Compose command is below).
- Python 3.12 only if using the optional native backend environment.

Run all root commands from this project directory. Downloading container images and
locked packages requires Internet access. No paid services or cloud accounts are needed.

## Start locally

```sh
node infra/scripts/setup-env.mjs
make up
```

The generator creates random local credentials in ignored `.env` and
`.local/seaweedfs.json` files, restricts their permissions and never prints secrets.
It preserves existing credentials on subsequent runs. `.env.example` intentionally
has blank secrets and cannot start the stack as-is. Do not commit or share `.env`.

Without Make:

```sh
docker compose --env-file .env -f infra/compose.yaml up -d --build --wait --wait-timeout 240
```

Open [the local frontend](http://127.0.0.1:3000). Its two health links proxy to the API.

| Check | Address | Behavior |
|---|---|---|
| Liveness | `http://127.0.0.1:8000/api/v1/health/live` | 200 while API handles requests, even when dependencies are down |
| Readiness | `http://127.0.0.1:8000/api/v1/health/ready` | 200 only after an authenticated PostgreSQL query, Redis ping and S3 bucket check; otherwise 503 |

Readiness covers the API's dependencies. The worker has its own directed Celery
ping healthcheck. Neither health response reveals connection strings or credentials.
Only API/frontend ports are published, bound to `127.0.0.1`. Database, broker,
storage and worker remain on a private internal Compose network. Do not expose this
local development stack publicly; deployment controls belong to later phases.

```sh
make status
make down
```

`make down` preserves the named data volumes. Restart with `make up`. Rebuild with
`make up` after source changes; source is copied into images rather than bind-mounted.
Do not use `down -v` unless you intend to delete this project's local data.
Changing credentials does not automatically rotate initialized database users.

If a port is busy, edit `FRONTEND_PORT`/`API_PORT` in `.env` and run `make up` again.
For browser tests on a remapped frontend, set `PLAYWRIGHT_BASE_URL` to that address.
The application uses same-origin health requests and enables no credentialed CORS.
Set `AUTH_ALLOWED_ORIGINS` to the exact local origins when changing ports. Authentication
also uses the same-origin proxy; no credentialed CORS is enabled.

## Verification

With the stack running:

```sh
make backend-check
make frontend-check
make infra-check
make outage-check
```

- Backend checks: Ruff lint/format, strict mypy, pytest positive/negative health and
  configuration tests. They run in the pinned Python test image.
- Frontend checks: ESLint, Next type generation, strict TypeScript and production build.
- Infrastructure checks: restricted PostgreSQL role, Redis authentication,
  authenticated S3 write/read/delete, denied anonymous listing/download and
  unauthorized bucket creation, and directed Celery ping.
- Outage checks **temporarily stop this project's PostgreSQL, Redis and storage one
  at a time**, verify liveness 200/readiness 503 and restore each service in `finally`.
  Use only on this local development project. No data volumes are removed.

Browser smoke tests require local npm dependencies and Chromium:

```sh
cd frontend
npm ci --ignore-scripts
npx playwright install chromium
npm test
```

Linux may need `npx playwright install --with-deps chromium`. Tests check five widths
(320, 375, 768, 1024, 1440), overflow, headings, keyboard focus, touch target size,
JavaScript errors and both links against the real API. These tests are not a formal
accessibility certification.

The CI workflow runs the same foundation checks. A workflow file is not evidence
of a successful hosted CI run. Dated local results and limitations are recorded in
[the Phase 1 report](verification/phase-1.md).

## Phase 2 database and fictional demo seed

The schema follows [BACKEND_SCHEMA.md](docs/BACKEND_SCHEMA.md). The initial revision
is `0001_initial_schema`. There are eighteen domain tables plus Alembic's own
`alembic_version` bookkeeping table. No business records or trained models are seeded.

After starting the Phase 1 services, run from the repository root:

```sh
make database-check
make migrate
make seed
```

`make database-check` builds a separate `sentinelai-db-tests` Compose project. Its
PostgreSQL data directory is RAM-backed, has no host ports, and references none of
the main project's volumes. It tests upgrade/downgrade/upgrade, schema/model parity,
constraints, privileges and seed behavior, then removes only those test resources.
Do not run two copies of this named test project at the same time.

`make migrate` provisions `sentinel_migrator` with its own protected local credentials
in ignored `.local/migration.env`, then applies Alembic using an opt-in Compose overlay.
It preserves existing credentials and the main database volume. The migration role
is not a superuser, cannot create databases or roles, and receives schema creation
rights only for this database. API/worker containers do not receive its password.
The existing application identity retains no schema DDL privileges. Main-database
downgrade is deliberately refused; rollback testing is restricted to the disposable DB.

`make seed` first ensures the migration is current, then runs the seed as the existing
application database identity. It creates one **SentinelAI Fictional Demo** organization,
three fictional accounts and memberships, and default thresholds 40/70/85, alert 70:

| Fictional account | Role |
|---|---|
| `admin@sentinel-demo.invalid` | ADMIN |
| `risk-manager@sentinel-demo.invalid` | RISK_MANAGER |
| `analyst@sentinel-demo.invalid` | ANALYST |

Random passwords are saved only to ignored `.local/demo/credentials.json` with mode
`0600`; its containing directory is `0700`. Inspect this file locally in your editor
when needed; do not paste it into chat, logs or source control. PostgreSQL stores only
Argon2id hashes (64 MiB, three iterations, parallelism four). Repeating the command
preserves account IDs, hashes, memberships and credential-file bytes. If accounts exist
but the file is lost, restore it; the command refuses silent credential replacement.
The seed refuses any environment other than explicit `APP_ENV=local`.

Default rule codes are documented, but complete approved initial parameter values
are not. Therefore no rule definitions are seeded. No sessions, transactions, scores,
alerts, cases, datasets, jobs or model versions are invented by the seed.

To inspect as the restricted application user, without exposing the database port:

```sh
docker compose --env-file .env -f infra/compose.yaml exec postgres sh -ec 'PGPASSWORD="$APP_DB_PASSWORD" psql -h 127.0.0.1 -U "$APP_DB_USER" -d "$POSTGRES_DB"'
```

Inside psql:

```sql
\dt
\d+ cases
\d+ model_versions
SELECT version_num FROM alembic_version;
SELECT u.email, m.role FROM users u JOIN memberships m ON m.user_id = u.id ORDER BY u.email;
SELECT medium_threshold, high_threshold, critical_threshold, alert_threshold FROM risk_settings;
SELECT tablename, indexname, indexdef FROM pg_indexes WHERE schemaname = 'public' ORDER BY tablename, indexname;
```

Use `\q` to exit. Do not query or share password hashes. [Phase 2 verification](verification/phase-2.md)
records observed results and the boundary between database constraints and future
service-layer rules such as tenant checks, last-admin protection and state transitions.

## Phase 3 authentication

`make up` first creates or preserves `.local/auth.env`, a separate 0600 signing key
used only by the API. Without Make, run `node infra/scripts/setup-auth-env.mjs`
before Compose. Existing database, storage, Redis and demo credentials are preserved.

The future frontend can call these same-origin endpoints:

1. `GET /api/v1/auth/csrf` obtains JSON `csrf_token` and an HttpOnly pre-login cookie.
2. `POST /api/v1/auth/login` sends only `email` and `password` as JSON, with
   `X-CSRF-Token`. Browsers supply `Origin`; non-browser clients must supply the
   configured exact origin too. The response sets an opaque HttpOnly session cookie
   and returns identity plus a new session-bound `csrf_token`.
3. `GET /api/v1/auth/me` rechecks the active account, expiry/revocation and current
   organization membership/role. `GET /api/v1/auth/csrf` refreshes the CSRF proof after reload.
4. `POST /api/v1/auth/logout` requires the session-bound header and approved Origin,
   revokes the database session, expires both cookies and returns 204 with no body.

Keep CSRF proofs in memory; never store session tokens in JavaScript or localStorage.
Use `credentials: "same-origin"` (fetch default). Responses are `Cache-Control: no-store`.
Sessions have an eight-hour absolute lifetime and 30-minute idle timeout by default.
The current schema has no tenant selector: accounts with zero or multiple memberships
are refused rather than choosing an organization or accepting a client-supplied ID.

Local Compose explicitly uses non-Secure host-only cookies on loopback HTTP.
Production configuration requires HTTPS origins, Secure `__Host-` cookies and a
separately provisioned signing key; it does not turn this local stack into a deployment.
Cookies always use HttpOnly, SameSite=Lax and Path=/, with no Domain attribute.
Uvicorn ignores forwarded identity/IP headers. Behind the Next proxy, the peer-IP
budget is shared by clients of that proxy; no untrusted forwarded IP is accepted.

Redis DB 1 enforces atomic fixed-window budgets: 20 attempts per socket peer and
5 per normalized account in 300 seconds. All attempts count, including successes,
to bound password-hash work. Keys contain keyed digests and expire automatically.
Configuration: `AUTH_LOGIN_IP_LIMIT`, `AUTH_LOGIN_ACCOUNT_LIMIT`,
`AUTH_LOGIN_WINDOW_SECONDS`, `AUTH_SESSION_SECONDS`, `AUTH_IDLE_SECONDS`.
Redis failure denies new logins with 503; existing PostgreSQL sessions and logout
continue to work. Limits return 429 and `Retry-After` without account existence details.

Successful login/logout and their session changes commit atomically with append-only
audit records. Unauthenticated failures go to bounded, allowlisted security logs:
the existing audit schema requires a known organization, so unknown users are never
assigned a guessed tenant. API Docker logs rotate at 10 MiB, three files. No email,
password, token, CSRF proof or credential hash is included in those log records.

Run `make auth-cleanup` daily while the stack is running. It deletes at most 5,000
expired or day-old revoked sessions per invocation in batches of 500, preserving
active sessions and audit history. Schedule this command through the eventual approved
operations environment; this phase does not install a host cron job or audit purge.

Future APIs must use `Identity`, `require_roles("ADMIN")` where required and
`organization_record` for tenant-scoped lookups. Both ANALYST and RISK_MANAGER retain
the documented ordinary-operation permissions. Role/deactivation services must use
the locked last-active-ADMIN invariant guard in the same transaction as their change.
These helpers do not imply future business endpoints have been implemented or tested.

`make database-check` also starts private disposable Redis and runs auth integration
tests. Browser auth regression uses the existing fictional account, creates/revokes
one real session and writes corresponding audit events; tracing is disabled for that
test to keep credentials out of artifacts. See [Phase 3 evidence](verification/phase-3.md).

## Phase 4 CSV validation and jobs

`POST /api/v1/ingestions` accepts multipart fields `file`, `purpose`, `source_kind`
and optional `license_reference`, with the existing session cookie, Origin and
`X-CSRF-Token`. Only ADMIN may submit TRAINING; all three roles may submit SCORING.
Use a `.csv` filename and CSV media type (`text/csv`, `application/csv` or
`application/vnd.ms-excel`). The endpoint returns 202 with `job_id`, `dataset_id`
and `status: "QUEUED"` after private storage and the durable upload record commit.

Limits: 10 MiB of file bytes, 10,000 data rows, one file, three bounded metadata
fields, bounded multipart headers/overhead and a 60-second body-read timeout.
The parser accepts strict UTF-8 with an optional BOM. Required columns are
`external_id,customer_ref,occurred_at,amount,currency,merchant_category,country_code,channel`;
optional columns are `device_ref,fraud_label`. Unknown columns, malformed values,
formula prefixes and obvious prohibited identifiers are rejected. These syntactic
checks cannot prove that a string is fictional: synthetic data remains an operator
requirement. Public datasets fail closed until independent owner approval exists.

Poll `GET /api/v1/jobs/{job_id}` for PostgreSQL-backed state, counts, up to 100 safe
row errors and any pending rejected-object cleanup. Cross-organization IDs return
404. `processed_rows` means valid rows examined in the reported VALIDATION phase;
it does not mean scored transactions. Valid TRAINING files become VALIDATED and
SUCCEEDED. Row-invalid files are rejected as a whole with their counts preserved.
SCORING validates/stages only and ends FAILED/ACTIVE_MODEL_REQUIRED without a model
(SCORING_NOT_AVAILABLE if one exists). No transaction, score, label or alert is created.

The API republishes durable unfinished jobs every 15 seconds, with per-job cooldowns.
Celery uses late acknowledgement, advisory locks across progress commits and at most
three started attempts. Storage retries back off; duplicate terminal deliveries are
no-ops. Interrupted uploads and rejected objects have durable cleanup that retries
after storage recovery. Admission defaults are five pending imports and ten upload
intents per organization in five minutes; these are demo limits, not measured capacity.

`make ingestion-check` builds a separate `sentinelai-ingestion-tests` Compose project
with its own database, Redis, storage volumes and loopback API port 18004. It uses
existing credentials read-only to seed only that isolated database, exercises real
uploads, Celery delivery, process restart and dependency recovery, then deletes only
its isolated test resources. Its resolved configuration contains secrets and stays
in ignored `.local/ingestion-tests.compose.json` with mode 0600. Do not run two copies
at once. The main database, volumes and credentials are preserved.

See [Phase 4 verification](verification/phase-4.md) for exact results and limitations.

## Optional native backend development

The supported baseline is Python 3.12; no system packages are installed by setup.

```sh
python3.12 -m venv backend/.venv
backend/.venv/bin/python -m pip install --require-hashes -r backend/requirements-dev.txt
cd backend
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy app
.venv/bin/pytest
```

Native unit tests use isolated fixtures and need no service credentials. The
recommended way to run the API is Compose because DB/Redis/S3 have no host ports.
The API and worker share runtime code and dependencies. SQLAlchemy models, Alembic
migrations and the local seed command live in the backend. The database bootstrap
only creates an unprivileged app login with CONNECT and schema USAGE, not CREATE or
superuser rights. Migration credentials will stay separate from this app login.

## Dependencies and maintenance

- npm uses an exact manifest plus `frontend/package-lock.json`; installs use `npm ci`.
- pip + pip-tools use `backend/requirements.in` and `requirements-dev.in` as inputs;
  both generated lockfiles include exact versions and artifact hashes.
- Image tags are accompanied by immutable multi-platform registry digests.
- SeaweedFS 4.48 (Apache-2.0) supplies local private S3 storage. The application key
  is restricted to the configured bucket. Admin UI, WebDAV, Iceberg/Lance endpoints
  and cluster telemetry are disabled. No cloud storage provider has been selected.
- The frontend uses locally authored HTML/Tailwind and system fonts. No animation,
  chart, tracking, third-party UI or remote font package is installed.
- Direct ESLint/TypeScript/React rules avoid a vulnerable dependency in the current
  Next.js bundled lint configuration. Framework type generation/build still run.

Regenerate Python locks in the configured Python 3.12 environment:

```sh
backend/.venv/bin/python -m piptools compile --generate-hashes --strip-extras --output-file=backend/requirements.txt backend/requirements.in
backend/.venv/bin/python -m piptools compile --generate-hashes --allow-unsafe --strip-extras --output-file=backend/requirements-dev.txt backend/requirements-dev.in
```

Audit after dependency changes:

```sh
cd frontend
npm audit --audit-level=high
```

From the root with the native backend environment installed:

```sh
backend/.venv/bin/python -m pip_audit -r backend/requirements.txt --disable-pip
```

Lock updates require review and rerunning checks. Do not apply blind force upgrades.
Health status does not cause Docker to restart an unhealthy-but-running process;
inspect service health and diagnose the dependency. Restart policies cover process
exit, not automatic repair of every possible failure.

## Scope and remaining gates

Phase 4 implements backend CSV validation and durable jobs. The login/upload frontend,
ML and scoring, case workflows, dashboards, reports and deployment remain pending.
Phase 5 requires separate explicit owner approval.
Legal pages, full navigation, favicon and custom 404 are Phase 9/launch work; the
foundation does not display links to routes that do not exist. No real financial or
personal data may be added. The existing security checklist retains its historical
planning status; the Phase 1 report records only checks actually performed here.
