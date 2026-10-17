# SentinelAI

Local foundation for a synthetic-data fraud and risk intelligence demonstration.
Phase 1 contains a minimal Next.js page, FastAPI health endpoints, PostgreSQL,
Redis, a Celery worker, and private S3-compatible development storage. No accounts,
product tables, fraud scoring, ingestion or investigation workflows exist yet.

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
Authentication and its CSRF/CORS policy are explicitly deferred to Phase 3.

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
The API and worker share runtime code and dependencies. A future schema phase will
add SQLAlchemy models, Alembic migrations and demo seed data. The database bootstrap
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

Phase 2 has not begun. All eighteen application tables, migrations, demo accounts,
auth/RBAC/CSRF, uploads, ML, cases, dashboards, reports and deployment remain pending.
Legal pages, full navigation, favicon and custom 404 are Phase 9/launch work; the
foundation does not display links to routes that do not exist. No real financial or
personal data may be added. The existing security checklist retains its historical
planning status; the Phase 1 report records only checks actually performed here.
