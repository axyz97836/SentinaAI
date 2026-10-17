# SentinelAI Phase 1 verification report

**Result: PASS for the Phase 1 local-foundation gate. Phase 2 has not started.**

- Verified on **2026-10-17**, completed approximately **14:01 UTC / 19:31 IST**.
- Environment: local macOS Apple Silicon host, Docker Desktop Linux containers.
- Tester: Codex, using terminal commands, VS Code tasks, Chromium/Playwright and visual inspection.
- Implementation commit: `bbd594268fa43ec9669c4f9d3d0c995e6ff959ed`.
- Branch: `feat/phase-01-foundation`. Local repository only; no remote, push or deployment.
- Authority: [implementation plan v1.1](../docs/IMPLEMENTATION_PLAN.md), the other five baseline documents and all five [security documents](../docs/security/).

This report covers the complete Phase 1 implementation, including the resumed work
after the usage-limit interruption. It does not certify later security or launch gates.
The previously approved documents retain their existing versions and historical status.

## What was resumed

The implementation, lockfiles, local environment and container volumes already existed.
The API was alive but not ready, and the worker had not started. PostgreSQL's initial
bootstrap script had failed with `bad interpreter: Permission denied` when executed
from its host bind mount, leaving the application login absent in the existing volume.

The database image now contains the initialization script as a non-executable file
that the official PostgreSQL entrypoint sources. The existing database was repaired
by running the idempotent bootstrap script, without deleting its volume or changing
credentials. A separate fresh database volume was also tested successfully and removed.
No implementation was restarted from scratch. Existing local credentials were retained.

## Services actually started

| Service | Final observed result | Host access |
|---|---|---|
| Next.js frontend | Running, healthy; page returns 200 | `http://127.0.0.1:3000` |
| FastAPI API | Runtime image built, running, healthy | `http://127.0.0.1:8000` |
| Celery worker | Runtime image built, running, healthy; directed ping returns `pong` | No published port |
| PostgreSQL | Running, healthy; authenticated application query succeeds | No published port |
| Redis | Running, healthy; authenticated broker works | No published port |
| SeaweedFS private S3 storage | Running, healthy; authenticated bucket operations succeed | No published port |

Docker's displayed container ports on infrastructure services are internal ports,
not published host bindings. Only frontend/API are published, both on loopback.
The infrastructure network is marked `internal: true`. The worker has its own health
check; API readiness checks PostgreSQL, Redis and the configured S3 bucket.

Final checks confirmed the running API's health module matched the verified source
SHA-256: `9703b6b3e20a7bda70d532e14f81497751969b8717c2deb3b826d7b91a9d8b8b`.

## Actual verification results

Commands below ran from the repository root unless a working directory is stated.
The final code edits after these checks only removed surplus blank lines at EOF.

| Check | Actual command or method | Observed result |
|---|---|---|
| Complete local stack build/start | `make up` via VS Code task | Exit 0; all six services healthy |
| Final API and worker build/start | `docker compose --env-file .env -f infra/compose.yaml up -d --build --wait --wait-timeout 240 api worker` | Exit 0; both runtime images built and services healthy |
| Backend verification | `make backend-check` | Exit 0 |
| Backend lint | `ruff check --no-cache .` in test image | `All checks passed!` |
| Backend formatting | `ruff format --no-cache --check .` in test image | `10 files already formatted` |
| Backend strict types | `mypy --cache-dir=/tmp/mypy-cache app` | `Success: no issues found in 6 source files` |
| Backend unit tests | `pytest -p no:cacheprovider` in test image | **13 passed, 4 warnings in 0.69s** |
| Frontend verification | Existing `SentinelAI: frontend checks` task, `make frontend-check` | Recovered successful task output: ESLint, Next type generation, strict TypeScript and production build passed |
| Frontend build detail | `npm run build` within the frontend checks | Next.js 16.4.2 compiled successfully; root route statically generated |
| Real infrastructure integration | `make infra-check` | Exit 0; all five reported integration groups passed, including after final API/worker rebuild |
| Dependency outage/recovery | `make outage-check` | Exit 0; three dependency outages and recoveries passed |
| Browser tests | `/usr/local/bin/node node_modules/playwright/cli.js test`, in `frontend` | **7 passed in 10.5s**, Chromium, zero retries |
| Automated accessibility | Axe within the browser suite | No detected violations for the configured WCAG A/AA tags |
| Visual review | Full-page screenshots at 375px and 1440px | Inspected; readable layout, visible working links, no clipping |
| npm dependency audit | `npm audit --audit-level=high`, in `frontend` | Exit 0; `found 0 vulnerabilities` |
| Python runtime audit | `docker run --rm sentinelai-backend-checks pip-audit -r requirements.txt --disable-pip --no-deps` | Exit 0; `No known vulnerabilities found` |
| Python development audit | Same command with `requirements-dev.txt` | Exit 0; `No known vulnerabilities found` |
| Editor diagnostics | VS Code problems tool | `No errors found` |
| Source whitespace | `git diff --cached --check -- . ':!docs'` before commit | Exit 0; original documents excluded to preserve their Markdown hard line breaks |
| Documentation preservation | SHA-256 compared with pre-implementation snapshot | **11/11 byte-for-byte unchanged** |
| Local credential scan | In-memory comparison against all five current local credential values | No matches in 56 source/document/evidence files, all six services' retained logs, rendered HTML or 15 browser JavaScript assets |
| Secret files | Git ignore and filesystem mode checks | Both local credential files ignored; mode `0600` |

The editor test runner discovered no tests, so it was not counted as a pass. Actual
pytest and Playwright execution above supplied the test results. The frontend check
task's completed output was recovered instead of duplicating the unchanged build.

### Backend cases

The 13 cases cover liveness with dependencies available/unavailable, readiness 200/503,
each dependency failure, sanitized unexpected errors, safe unknown-route responses,
absence of permissive CORS, allowlisted logging fields, hidden configuration secrets,
missing-secret rejection and rejection of a production environment in this local scaffold.

### Infrastructure and outage evidence

The executable integration check observed:

1. PostgreSQL accepts the application login; it is not a superuser, cannot create
   databases or roles, and cannot create objects in the public schema.
2. Redis rejects unauthenticated commands.
3. S3 permits authenticated synthetic object write/read/delete, while anonymous
   object listing and download return 403.
4. The S3 application identity cannot create an arbitrary other bucket (403).
5. Celery replies to a directed ping through the authenticated Redis broker.

The outage script stopped PostgreSQL, Redis and object storage **one at a time**.
In each case liveness stayed 200, readiness became 503 with the documented error
envelope, and readiness returned to 200 after restart. Its `finally` blocks restored
the services. Main project data volumes were preserved.

Fresh initialization used project `sentinelai-bootstrap-check` with its own volume:

```sh
docker compose --env-file .env -f infra/compose.yaml -p sentinelai-bootstrap-check up -d --build --wait postgres
```

An authenticated TCP query using the existing application credentials returned
`sentinel_app|f|f|f` for role/superuser/create-database/create-role, and **0** public
tables. The disposable project's container, network and volume were then removed;
the main project's resources were unaffected.

### Browser cases and evidence

Five viewport cases at **320, 375, 768, 1024 and 1440 pixels** checked the title,
heading, page language, no horizontal page overflow, keyboard focus, visible focus
outline, minimum 44px link target height and absence of browser JavaScript errors.
The other two tests checked both health links against the real API and automated
accessibility. No authentication or business workflow was invented for the tests.

- [375px screenshot](foundation-375.png)
- [1440px screenshot](foundation-1440.png)

UI UX Pro Max was already installed and was read, not reinstalled. Two targeted
searches returned no verified match. The approved UI brief and the skill's general
accessibility/layout defaults were used as the fallback, with real browser checks.

## Failures encountered and resolution

| Failure or warning | Resolution/status |
|---|---|
| PostgreSQL host-mounted bootstrap script could not execute; app login missing; readiness 503 | Package/source script inside the image, repair existing volume idempotently; existing and fresh-volume checks passed |
| Python development hash lock omitted pip/setuptools required by pip-tools | Regenerated dev lock with `--allow-unsafe` and runtime constraints; hash-checked test image build passed |
| Initial redis-py version conflicted with Celery/Kombu's requirement | Use compatible locked redis-py 6.4.0; real broker and worker checks passed |
| Initial Next.js lint-config dependency graph reported five high audit findings | Use direct ESLint/TypeScript/React Hooks rules; current npm audit reports zero vulnerabilities |
| Ruff reported long lines and integration-test assertions | Formatted code and scoped the assertion allowance to the integration test file |
| Ruff formatter tried to write its cache in non-root `/app` | Disable formatter cache in the Make target; final formatting check passed |
| Strict mypy rejected `Redis[bytes]` for the locked library | Corrected annotation to `Redis`; strict types passed |
| First disposable DB attempt used `--no-build` with a new project image name | Built the isolated project's image; fresh initialization passed; disposable resources cleaned up |
| Native host Node is 22.11.0, below lint dependencies' supported 22.13+ requirement | Used pinned container Node 22.23.3 for frontend lint/types/build; browser tests ran successfully with the installed host runtime |
| Sandboxed terminal did not expose all host tools/network operations | Authorized host executions completed; this is not an application failure |

## Remaining issues and limits

There is **no outstanding Phase 1 runtime/build/test blocker**. Remaining observations:

- The final pytest run reports **four deprecation warnings**: one from Starlette's
  current `httpx` TestClient compatibility path (suggesting `httpx2` for a future
  update), and three for Redis's `retry_on_timeout` argument. They are not test
  failures; review them with the next dependency-maintenance change.
- Native frontend lint/build requires Node 22.13+ within 22.x. Docker already supplies
  a supported runtime, so an OS-wide upgrade was not performed.
- The optional native Python virtual environment was configured for lock maintenance;
  all backend application/test dependencies were installed and verified in Docker.
  Install the development lock before trying native pytest/mypy.
- Hosted CI, a second physical machine, other browser engines, a formal WCAG audit,
  container OS vulnerability scanning and a general-purpose secret scanner were not
  run. The recorded secret scan specifically checked current local credential values.
- npm/pip audits reflect known advisories at execution time, not proof of absence of
  all vulnerabilities. pip-audit emitted its generic `--no-deps` caution; both inputs
  are complete hash-pinned locks and the scans succeeded.
- The stack is local HTTP development, with no production TLS, provider encryption,
  backup/restore evidence or launch approval. Those remain future approved gates.
- The original security checklist remains unchanged, including its historical
  pre-implementation labels. This report records only the Phase 1 evidence above.

## Files created or changed

These are the new Phase 1 files. Resume work repaired existing implementation files;
it did not recreate the project. The eleven pre-existing documents were added to the
new local Git repository without content changes.

| Area | Files |
|---|---|
| Root setup | [README.md](../README.md), [Makefile](../Makefile), [.env.example](../.env.example), [.gitignore](../.gitignore), [.dockerignore](../.dockerignore), [.editorconfig](../.editorconfig) |
| Editor/CI | [.vscode/tasks.json](../.vscode/tasks.json), [.vscode/settings.json](../.vscode/settings.json), [.github/workflows/ci.yml](../.github/workflows/ci.yml) |
| Backend setup | [Dockerfile](../backend/Dockerfile), [pyproject.toml](../backend/pyproject.toml), [requirements.in](../backend/requirements.in), [requirements.txt](../backend/requirements.txt), [requirements-dev.in](../backend/requirements-dev.in), [requirements-dev.txt](../backend/requirements-dev.txt) |
| Backend application | [__init__.py](../backend/app/__init__.py), [config.py](../backend/app/config.py), [health.py](../backend/app/health.py), [main.py](../backend/app/main.py), [observability.py](../backend/app/observability.py), [worker.py](../backend/app/worker.py) |
| Backend tests | [conftest.py](../backend/tests/conftest.py), [test_config.py](../backend/tests/test_config.py), [test_health.py](../backend/tests/test_health.py) |
| Frontend setup | [Dockerfile](../frontend/Dockerfile), [package.json](../frontend/package.json), [package-lock.json](../frontend/package-lock.json), [tsconfig.json](../frontend/tsconfig.json), [next-env.d.ts](../frontend/next-env.d.ts), [next.config.ts](../frontend/next.config.ts), [eslint.config.mjs](../frontend/eslint.config.mjs), [postcss.config.mjs](../frontend/postcss.config.mjs) |
| Frontend page/tests | [layout.tsx](../frontend/app/layout.tsx), [page.tsx](../frontend/app/page.tsx), [globals.css](../frontend/app/globals.css), [playwright.config.ts](../frontend/playwright.config.ts), [foundation.spec.ts](../frontend/tests/foundation.spec.ts) |
| Infrastructure | [compose.yaml](../infra/compose.yaml), [postgres/Dockerfile](../infra/postgres/Dockerfile), [init-app-role.sh](../infra/postgres/init-app-role.sh), [setup-env.mjs](../infra/scripts/setup-env.mjs), [check-infra.py](../infra/scripts/check-infra.py), [check-stack.mjs](../infra/scripts/check-stack.mjs) |
| Verification | [This report](phase-1.md), [document hashes](approved-documents.sha256), [mobile screenshot](foundation-375.png), [desktop screenshot](foundation-1440.png) |

Ignored local artifacts include credentials, dependency installations, build output,
browser test output and the original documentation hash snapshot. They are not committed.
No existing documentation or document version number was edited.

## Observed versions

| Component | Version |
|---|---|
| Host Node / npm | 22.11.0 / 10.9.0 |
| Container Node / Python | 22.23.3 / 3.12.15 |
| Host Python used for lock tooling | 3.12.6 |
| Docker / Compose | 29.8.2 / 5.6.0 |
| PostgreSQL / Redis server / SeaweedFS | 17.11 / 8.10.2 / 4.48 |
| Next.js / React / Tailwind / TypeScript | 16.4.2 / 19.3.1 / 4.3.3 / 5.9.3 |
| FastAPI / Uvicorn / SQLAlchemy | 0.143.3 / 0.54.0 / 2.1.4 |
| Pydantic settings / psycopg / Celery | 2.16.0 / 3.3.6 / 5.6.3 |
| redis-py / boto3 | 6.4.0 / 1.43.114 |
| pytest / Ruff / mypy / pip-audit | 9.1.1 / 0.17.1 / 2.4.0 / 2.10.1 |
| Playwright / axe-core Playwright integration | 1.64.1 / 4.14.0 |

Full transitive versions and hashes are in the dependency locks. Base container
images are pinned by digest in the Dockerfiles/Compose configuration.

## Commands to run locally

From the repository root, for this already-configured checkout:

```sh
make up
make status
```

Open [the frontend](http://127.0.0.1:3000), [API liveness](http://127.0.0.1:8000/api/v1/health/live)
or [API readiness](http://127.0.0.1:8000/api/v1/health/ready).

For a new checkout only, create its own local credentials before starting:

```sh
node infra/scripts/setup-env.mjs
make up
```

The generator preserves credentials if a valid local environment already exists.
Do not copy credentials into source files or regenerate them to fix a startup error.

```sh
make backend-check
make frontend-check
make infra-check
make outage-check
cd frontend
npm test
```

On a fresh machine, first install frontend test dependencies and Chromium using the
[README instructions](../README.md). They are already installed on this machine.
`make outage-check` deliberately interrupts the local dependencies briefly.

Stop services while preserving their data:

```sh
make down
```

Verify the preserved documents from the root:

```sh
shasum -a 256 -c verification/approved-documents.sha256
```

## Manual attention

1. Keep Docker Desktop running while using the stack. No manual repair or credential
   regeneration is needed for the current working services.
2. If you want native frontend lint/build, update your chosen Node environment to
   supported Node 22.x (22.13 or newer); otherwise use the existing Docker commands.
3. Review the warnings and limitations above. A Git remote and hosted CI can be
   configured separately; nothing was pushed.
4. Explicitly approve Phase 2 when ready. No product tables, migrations, demo accounts,
   authentication, transactions, ML, dashboards or business worker tasks were added.

## Reference decisions

The existing architecture was retained. Private local S3 storage is provided by
SeaweedFS under Apache-2.0; no production storage provider was selected. Its
[mini-server documentation](https://github.com/seaweedfs/seaweedfs/wiki/Quick-Start-with-weed-mini)
and [S3 credential documentation](https://github.com/seaweedfs/seaweedfs/wiki/S3-Credentials)
were checked before configuration. Startup uses the healthy-dependency conditions
described by [Docker Compose](https://docs.docker.com/compose/how-tos/startup-order/).

Community research was limited to two relevant articles with no substantive comments
returned; it is supporting context, not evidence of broad consensus or a substitute
for the actual tests above.

### 🌐 Community Wisdom: [Stop your app from starting before Postgres is ready: Compose healthchecks done right](https://dev.to/anthany_wingo_195f7057a9e/stop-your-app-from-starting-before-postgres-is-ready-compose-healthchecks-done-right-1nmp)

> **Source**: [Anthany Wingo](https://dev.to/anthany_wingo_195f7057a9e)
>
> **Tags**: `docker`, `dockercompose`, `postgres`, `devops`
>
> The article distinguishes container start from dependency readiness. This implementation
> uses healthy-dependency conditions and tests authenticated API readiness separately.
>
> [Read Full Discussion](https://dev.to/anthany_wingo_195f7057a9e/stop-your-app-from-starting-before-postgres-is-ready-compose-healthchecks-done-right-1nmp)

### 🌐 Community Wisdom: [Restart Unhealthy Docker Containers Automatically](https://dev.to/binarypatrick/restart-unhealthy-docker-containers-automatically-4c00)

> **Source**: [binarypatrick](https://dev.to/binarypatrick)
>
> **Tags**: `docker`, `systemd`
>
> The article notes that an unhealthy status alone does not trigger Docker's usual
> restart policy. This scaffold documents that limitation and tests recovery; it does
> not add a Docker-socket-powered automatic repair service.
>
> [Read Full Discussion](https://dev.to/binarypatrick/restart-unhealthy-docker-containers-automatically-4c00)
