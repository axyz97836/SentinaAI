# SentinelAI Phase 2 verification

**Local Phase 2 verification: PASS. GitHub CI: PASS after [CI stabilization](ci-stabilization.md). Phase 3 has not started.**

- Final verification date: **18 October 2026 IST** (17 October UTC).
- Environment: existing local macOS/Apple Silicon workspace and Docker Desktop Linux containers.
- Tester: Codex, using actual terminal commands, PostgreSQL inspection, pytest and Playwright.
- Implementation commit: `5c573a6886ac26bb0d7de1375181c5811b58c400`.
- Current publication branch: `feat/phase-02-database`. The original verified branch
  `feat/phase-02-schema` and all existing commits are preserved.
- Migration: **`0001_initial_schema`**, initial revision, no parent.
- Authority: [BACKEND_SCHEMA.md](../docs/BACKEND_SCHEMA.md), [implementation plan v1.1](../docs/IMPLEMENTATION_PLAN.md), all other approved baseline/security documents, and the owner's Phase 2 instructions.

All eleven approved documents remain byte-for-byte unchanged. Document versions,
frontend files, main Compose configuration and Phase 1 credential values were preserved.
Main data volumes were retained without reset or recreation. The database was upgraded and seeded
after isolated verification; it is no longer the empty Phase 1 database.

## Resume inspection and preservation

On resumption, Git contained the incomplete Phase 2 changes on the correct branch.
The main database still had zero public tables, no Alembic revision and no migration
role. Its existing `sentinel_owner` and restricted `sentinel_app` roles remained.
All six Phase 1 services were healthy. The failed isolated test run had cleaned up
its containers and network. Existing source, locks and local credentials were reused.

The final database remains in the **same main PostgreSQL volume/container**. The API
and worker were rebuilt/restarted with the new backend dependencies. Outage regression
tests stopped and restarted infrastructure services individually without deleting data.

## Database delivered

Exactly these eighteen domain tables exist:

```text
organizations       users                 memberships
sessions            risk_settings         rule_definitions
datasets            jobs                  job_errors
model_versions      transactions          transaction_labels
scoring_results     rule_hits             alerts
cases               case_events           audit_logs
```

Alembic adds its normal `alembic_version` bookkeeping table. This is not a nineteenth
domain entity. There are no other application tables.

Main PostgreSQL catalog inspection returned:

| Object | Domain count |
|---|---:|
| Tables | 18 |
| Primary keys | 18 |
| Foreign keys | 32 |
| CHECK constraints | 36 |
| UNIQUE constraints | 9 |
| Indexes, including primary/unique indexes | 53 |

The 53 indexes include 26 explicit indexes and the 27 indexes backing primary/unique
constraints. The explicit indexes include unique `lower(email)` and the partial unique
organization index for `model_versions WHERE is_active = true`.

The schema implements server-generated UUID identifiers, timezone-aware timestamps,
`NUMERIC(14,2)` amounts, `NUMERIC(7,6)` score components, JSONB fields and the documented
defaults. Constraints reject invalid threshold ordering, statuses, amounts/ranges,
duplicate organization-scoped external IDs, duplicate score/alert/case associations,
multiple active models per organization and invalid FK references. Closed cases require
a valid resolution, a non-whitespace note and a close timestamp; open/in-review cases
cannot carry a resolution or close timestamp.

Foreign keys use PostgreSQL's default non-cascading `NO ACTION` behavior, except the
documented `rule_hits.rule_definition_id ON DELETE SET NULL`. Tests confirmed that rule
edits/deletion preserve the historical rule code/details snapshot and referenced model
metadata cannot simply be deleted.

## Migration and permission design

The [initial revision](../backend/migrations/versions/0001_initial_schema.py) stores
explicit frozen SQL. It does not import mutable application table definitions to create
the schema. Alembic runs it transactionally using `sentinel_migrator`.

The opt-in [database tooling overlay](../infra/compose.database.yaml) receives the
separate migration credential file. Provisioning grants this role CONNECT and public
schema USAGE/CREATE for the local database. It is **not** a superuser and cannot create
databases, roles or replication connections. It owns the migrated objects. It is not
granted to the application role.

`sentinel_app` still cannot CREATE schema objects, ALTER/DROP tables, TRUNCATE tables,
change migration bookkeeping or SET ROLE to the migrator. The migration grants named
data operations needed by the documented model. Ordinary application updates/deletes
are denied for transactions, labels, scores, rule hits, audit logs and case events.
Model metadata is protected; only `is_active` and `activated_at` have update grants.
Session cleanup and rule deletion have the specifically needed DELETE privileges.

Destructive downgrade requires all three test-environment values and checks the actual
connected database name. The main local environment is refused. The automated fixture
ran **upgrade → downgrade to zero domain tables → upgrade again** against only
`sentinelai_schema_test` in the separate `sentinelai-db-tests` Compose project.
Its PostgreSQL storage is tmpfs and has no references to main volumes or published ports.

## Synthetic seed outcome

`make seed` successfully provisioned one **SentinelAI Fictional Demo** organization:

| Fictional account | Membership |
|---|---|
| `admin@sentinel-demo.invalid` | ADMIN |
| `risk-manager@sentinel-demo.invalid` | RISK_MANAGER |
| `analyst@sentinel-demo.invalid` | ANALYST |

There are three users, three memberships and one risk-settings row. Thresholds are
**medium 40, high 70, critical 85, alert 70**, with version 1. The three database password
values were verified as Argon2id hashes with 64 MiB memory, three iterations and
parallelism four. Passwords and hashes are intentionally absent from this report.

Random local passwords reside only in ignored `.local/demo/credentials.json` (mode
`0600`, directory `0700`). The migration password is separate in ignored
`.local/migration.env` (mode `0600`). Existing main credentials were not regenerated.

The seed ran **twice on the main database**. Private digest comparisons proved that
all seeded rows, IDs, timestamps, password hashes, the demo credential file and the
migration credential file remained unchanged on the second run. An advisory transaction
lock serializes seed operations. Missing credentials for existing accounts cause refusal;
the command does not silently reset passwords, reactivate accounts or overwrite roles.

No rule definitions were seeded: the documents name the rule codes but do not fully
specify initial parameter values. All fourteen other domain tables are empty, including
sessions, transactions, datasets, jobs, models, scores, alerts, cases and audit history.
No training, predictions, model metrics or authentication endpoints were fabricated.

## Actual checks and commands

Commands ran from the repository root, unless noted. The final source change after the
database suite was removal of trailing whitespace inside the frozen SQL; its formatter
check was rerun and main-database Alembic comparison still passed.

| Check | Command/method | Actual result |
|---|---|---|
| Isolated migration/schema/constraint/permission/seed suite | `make database-check` | **153 passed in 14.72s**, exit 0, no warnings |
| Backend lint, formatting, types and units | `make backend-check` | Exit 0 |
| Ruff | `ruff check --no-cache .` | `All checks passed!` |
| Formatting | `ruff format --no-cache --check .` | `19 files already formatted` |
| Strict types | `mypy --cache-dir=/tmp/mypy-cache app` | `Success: no issues found in 9 source files` |
| Unit tests | `pytest -p no:cacheprovider -m "not database"` | **17 passed, 153 deselected, 4 warnings in 2.69s**; database tests ran separately above |
| Main migration and first seed | `make migrate seed` | Exit 0; revision applied and fictional seed verified |
| Main repeated seed | `make seed` | Exit 0; byte/digest comparison confirmed no duplicate or changed seed data/credentials |
| Main schema drift | `docker compose --env-file .env -f infra/compose.yaml -f infra/compose.database.yaml --profile database run --rm --no-deps migration alembic check` | Exit 0; `No new upgrade operations detected.` |
| Production seed refusal | `docker run --rm -e APP_ENV=production sentinelai-api python -m app.seed` | **Expected exit 1** with sanitized refusal, before database access |
| API/worker build and start | `docker compose --env-file .env -f infra/compose.yaml up -d --no-deps --build --wait api worker` | Exit 0; both healthy |
| Infrastructure regression | `make infra-check` | Exit 0; all five integration groups passed |
| Outage/recovery regression | `make outage-check` | Exit 0; all three dependencies correctly caused readiness 503/liveness 200 and recovered |
| Browser regression | `make browser-check` | **7 passed in 26.2s**, Chromium, no retries |
| Runtime dependency audit | `docker run --rm sentinelai-backend-checks pip-audit -r requirements.txt --disable-pip --no-deps` | Exit 0; no known vulnerabilities |
| Development dependency audit | Same command with `requirements-dev.txt` | Exit 0; no known vulnerabilities |
| JavaScript tool syntax | `node --check` for both new scripts | Exit 0 |
| Editor diagnostics | Problems tool | No errors found |
| Git whitespace review | `git diff --cached --check` | Exit 0 |
| Approved-document hashes | `shasum -a 256 -c verification/approved-documents.sha256` | **11/11 OK** |

**Total automated test cases: 170 backend + 7 browser = 177 passed.** The editor test
adapter found no tests; it was not counted as success. The actual container pytest and
Playwright runs above supplied the results. Frontend lint/type/build were not repeated
for this backend-only phase; their unchanged Phase 1 results remain in that report.

### Required database-test coverage

| Requested area | Evidence in the executed suite |
|---|---|
| All eighteen tables | Exact catalog/table inventory plus Alembic bookkeeping |
| Primary and foreign keys | Independent documented FK inventory and PK inspection for every table |
| Indexes and uniqueness | Catalog definitions, sort direction, functional/partial indexes and unique-key inspection |
| Duplicate external ID in one org | Rejected with PostgreSQL `23505` |
| Same external ID in different orgs | Allowed with separate synthetic supporting organization |
| Email case variants | Rejected with `23505` |
| Invalid risk thresholds | Rejected with `23514`; valid defaults and alert boundaries tested |
| Invalid enum-like values | Rejected for documented roles, purposes, sources and statuses |
| Invalid closed-case state/note | Missing fields, empty/whitespace notes and invalid open-state resolution rejected |
| Amount/score bounds | Zero, negative and NaN amounts; invalid scores/components/latency rejected; valid bounds allowed |
| Active model uniqueness | Second active model in same org rejected; inactive history/other org allowed |
| Invalid FK references | Each of the 32 documented references tested with an unknown UUID |
| Seed roles/memberships | Exactly the three canonical memberships; defaults and hashes verified |
| Seed idempotency | Repeated isolated/main seed; no changed hashes, IDs, timestamps or credential bytes |
| Migration round trip | Upgrade, empty downgrade, upgrade; local-environment downgrade refusal also tested safely |
| Models match migrated schema | Alembic comparison plus columns, nullability, types/defaults, FK/unique/index/check inventories |

Tests use valid synthetic supporting records inside transactions that roll back. The
seed integration test cleans up only its guarded disposable database. No destructive
test used the main database.

## Security evidence and boundaries

| Verification | Actual result |
|---|---|
| App DDL and migration-role escalation | CREATE/ALTER/DROP/TRUNCATE/SET ROLE attempts denied with `42501` |
| Immutable and append-only evidence | Normal app UPDATE/DELETE attempts denied; permitted INSERT/SELECT tested |
| Migration identity capability | Main and isolated role flags verified: no superuser/createdb/createrole |
| Password storage | Three actual seeded hashes have the intended Argon2id encoding; verification against protected credentials passed |
| Seed environment | Four unit cases refuse production/staging/test/empty; real production CLI refusal also executed |
| Credentials | Main original files unchanged; new files mode `0600`, demo directory `0700`; all ignored by Git |
| Credential separation | API, worker and frontend container environments contain neither migration nor database-owner credentials |
| Targeted disclosure scan | Current actual credential values absent from candidate source files, retained main service logs, HTML and 15 served JS assets |
| Network | DB/Redis/storage/worker have no published host ports; frontend/API bind only to `127.0.0.1` |
| Regression | API health, authenticated dependency access, private storage, Celery ping and browser checks passed |
| Data policy | Fictional `.invalid` demo accounts only; all operational/model tables empty after main seed |

These are Phase 2 results, **not** blanket passes for the approved release checklist.
The following remain later service-layer responsibilities: deriving organization from
a session; checking same-organization references; last-active-admin protection; ordered
state transitions and no reopening; optimistic version updates; canonical replay payload
comparison; verified public-data licensing; JSON/format validation; TRAINING dataset
eligibility; artifact/metric verification; atomic business audit writes; retention cleanup.
Database constraints establish valid rows and uniqueness, not complete authorization
or the later business workflows. No authentication endpoint or tenant-access API was added.

## Errors found and fixed

1. **Initial isolated run: 152 setup errors.** The JSON weight default used colons
   adjacent to numbers in a SQLAlchemy text expression. Compilation treated them as
   parameter markers, leaving invalid `NULL` text in the frozen JSON SQL. Corrected
   both the model default and initial migration; added an observed-default assertion.
2. **Next isolated run: 41 passed, 1 failed, 110 errors.** A test helper's `name`
   parameter collided with `organizations.name`. Renamed the helper parameter; the
   database constraints were unchanged. The final expanded suite passed all 153 cases.
3. **Static-check findings.** Fixed missing `func` import, imports, formatting and long
   executable-code lines. Frozen SQL and the independent document inventory have
   narrowly scoped line-length exceptions; security checks remain enabled.
4. **Verification tooling only.** A one-off secret scan referenced an undefined buffer
   variable; corrected it and reran successfully. No secret values were emitted.
   Sandboxed Git/hash utilities required authorized host execution; those checks then passed.

## Files created and modified

**Created (17, including this report):**

- [backend/alembic.ini](../backend/alembic.ini)
- [backend/app/database.py](../backend/app/database.py)
- [backend/app/models.py](../backend/app/models.py)
- [backend/app/seed.py](../backend/app/seed.py)
- [backend/migrations/env.py](../backend/migrations/env.py)
- [backend/migrations/script.py.mako](../backend/migrations/script.py.mako)
- [backend/migrations/versions/0001_initial_schema.py](../backend/migrations/versions/0001_initial_schema.py)
- [backend/tests/database/conftest.py](../backend/tests/database/conftest.py)
- [backend/tests/database/schema_contract.py](../backend/tests/database/schema_contract.py)
- [backend/tests/database/test_schema.py](../backend/tests/database/test_schema.py)
- [backend/tests/test_seed.py](../backend/tests/test_seed.py)
- [infra/compose.database.yaml](../infra/compose.database.yaml)
- [infra/compose.database-tests.yaml](../infra/compose.database-tests.yaml)
- [infra/postgres/provision-migrator.sql](../infra/postgres/provision-migrator.sql)
- [infra/scripts/setup-database.mjs](../infra/scripts/setup-database.mjs)
- [infra/scripts/check-database.mjs](../infra/scripts/check-database.mjs)
- [verification/phase-2.md](phase-2.md)

**Modified (8):** [README.md](../README.md), [Makefile](../Makefile),
[backend/Dockerfile](../backend/Dockerfile), [backend/pyproject.toml](../backend/pyproject.toml),
[backend/requirements.in](../backend/requirements.in), [backend/requirements.txt](../backend/requirements.txt),
[backend/requirements-dev.txt](../backend/requirements-dev.txt), and
[.github/workflows/ci.yml](../.github/workflows/ci.yml).

The existing [.gitignore](../.gitignore) already protects the local credentials and
was not changed. Original documentation, frontend and main infrastructure configuration
are unchanged. Ignored local credentials, test outputs and private comparison digests
are not included in commits.

## Remaining limitations and environment

No unresolved Phase 2 blocker remains. The unit suite retains the four pre-existing
deprecation warnings from Phase 1: one Starlette/httpx compatibility warning and three
Redis `retry_on_timeout` warnings. They did not cause failures and were not changed in
this schema phase. Native frontend lint/build still needs supported Node 22.13+; the
pinned container provides Node 22.23.3. No new UI packages were installed.

New dependencies are **Alembic 1.20.0 (MIT)** and **argon2-cffi 25.1.0 (MIT)**, verified
from installed metadata. Existing SQLAlchemy 2.1.4, psycopg 3.3.6, Python 3.12.15 in
Docker and PostgreSQL 17.11 were retained. Runtime/development locks include exact
versions and hashes. pip-audit's generic `--no-deps` warning was emitted, but both full
locked dependency inventories were scanned successfully.

Hosted CI had not run at the original local Phase 2 sign-off. Publication subsequently
triggered the startup failures documented below. A completed test suite on another
operating system, a general-purpose secret scanner, container OS vulnerability scanning,
formal security certification, production TLS/backup/restore and future auth/tenant
workflows are not claimed as passed. The secret
scan compared actual current local credential values. Audit results reflect known
advisories at execution time. Isolated test containers and network were removed;
reusable build images remain. All six main local services were healthy at final inspection.

## Commands for local use and inspection

```sh
make up
make database-check
make migrate
make seed
make backend-check
make infra-check
make browser-check
```

The current checkout is already migrated/seeded. `make migrate` and `make seed` are
repeatable. `make outage-check` additionally verifies dependency failure/recovery and
briefly interrupts only this local stack. `make down` stops it while preserving volumes.

Open psql as the restricted app identity without publishing a database port:

```sh
docker compose --env-file .env -f infra/compose.yaml exec postgres sh -ec 'PGPASSWORD="$APP_DB_PASSWORD" psql -h 127.0.0.1 -U "$APP_DB_USER" -d "$POSTGRES_DB"'
```

```sql
\dt
\d+ cases
\d+ model_versions
SELECT version_num FROM alembic_version;
SELECT u.email, m.role FROM users u JOIN memberships m ON m.user_id=u.id ORDER BY u.email;
SELECT medium_threshold, high_threshold, critical_threshold, alert_threshold FROM risk_settings;
SELECT tablename, indexname, indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY tablename,indexname;
\q
```

No manual database repair or credential rotation is needed. Keep the protected local
credential files; do not paste their contents into chat or source control. Git contains
the implementation and verification commits above. They were subsequently pushed under
the owner's explicit GitHub authorization, as recorded below. No feature branch was
merged into main and nothing was deployed. Review this result and explicitly approve
Phase 3 before authentication work begins.

## GitHub synchronization update — 18 October 2026 IST

The owner authorized regular verified commits/pushes and the persistent workflow in
[AGENTS.md](../AGENTS.md). That file defines the approximately 200–300 meaningful-line
checkpoint review, relevant checks before commits, conventional messages, feature-branch
pushes, remote verification, secret hygiene, the eleven authoritative documents and the
explicit approval gate before another phase. It was completed in commit
`d6018e7bc88a4a0be2aff36796c998c21f5a2c03` and required no reconstruction after interruption.

The GitHub repository was empty and no local remote was configured. `origin` was added
as exactly `https://github.com/axyz97836/SentinaAI`. The initial pushes were verified
with `git ls-remote`, not inferred from local commits:

| Remote branch | Verified initial published commit | Scope |
|---|---|---|
| [main](https://github.com/axyz97836/SentinaAI/tree/main) | [ccd5f97e793dc90a9b5f33a7365190cd74fc2a7e](https://github.com/axyz97836/SentinaAI/commit/ccd5f97e793dc90a9b5f33a7365190cd74fc2a7e) | Last verified Phase 1 baseline; contains no Phase 2 schema/migrations |
| [feat/phase-02-database](https://github.com/axyz97836/SentinaAI/tree/feat/phase-02-database) | [d6018e7bc88a4a0be2aff36796c998c21f5a2c03](https://github.com/axyz97836/SentinaAI/commit/d6018e7bc88a4a0be2aff36796c998c21f5a2c03) | Preserved Phase 2 implementation/report plus persistent Git workflow |

The original four commits were retained without rewriting. Before the first push, a
targeted scan checked all four commits and 83 unique file blobs for the actual current
local credentials, sensitive/generated paths, private-key markers and selected token/hash
signatures. It found no matches. Subsequent documentation changes were checked separately.
All credential files remain Git-ignored; all eleven approved document hashes still match.

There were no Git push authentication or synchronization errors. Existing secure Git
authentication worked. Anonymous access to Actions job logs returned 403; using that
existing credential in memory for read-only API access succeeded. No token was printed,
stored in the repository or requested in chat, and no GitHub security control was changed.

### GitHub Actions results

| Run | Commit | Observed result |
|---|---|---|
| [Initial main run](https://github.com/axyz97836/SentinaAI/actions/runs/39062845290) | `ccd5f97` | Failed at `Run make up`, exit 2 |
| [Initial Phase 2 branch run](https://github.com/axyz97836/SentinaAI/actions/runs/39062904343) | `d6018e7` | Failed at `Run make up`, exit 2 |

Both logs report `dependency failed to start: container sentinelai-object-storage-1 is
unhealthy`. Hosted verification steps were skipped after startup failed; they are **not
passes**. The captured job logs do not establish the underlying storage-service cause.
These historical failures were subsequently resolved by the verified
[CI stabilization fixes and successful hosted run](ci-stabilization.md). The
existing local results remain **153 database + 17 unit + 7 browser = 177 passing tests**;
they were not rerun solely for this documentation/synchronization change.

This report update is a subsequent documentation-only checkpoint. Its final pushed
commit is recorded in the synchronization response and can be inspected using
`git log -1 --format=%H -- verification/phase-2.md` and `git ls-remote origin`.
Application functionality and CI behavior were not changed during synchronization.
There were no force-pushes, history rewrites, automatic merges, credential rotations,
database resets or Phase 3 changes. Successful publication does not imply successful CI.

## Sources and community context

Primary references used for dependency behavior:
[Alembic autogeneration](https://alembic.sqlalchemy.org/en/latest/autogenerate.html) and
[argon2-cffi API](https://argon2-cffi.readthedocs.io/en/stable/api.html).
The schema itself is governed by the approved local documents. Community research
yielded two pertinent cautionary articles with no comments returned; this is a narrow
supporting sample, not a consensus or evidence that this project suffered those incidents.

### 🌐 Community Wisdom: [Migration says applied, but production says column does not exist](https://dev.to/gemmein/migration-says-applied-but-production-says-column-does-not-exist-7e8)

> **Source**: [gemmein](https://dev.to/gemmein)
>
> **Tags**: `postgres`, `prisma`, `supabase`, `webdev`
>
> The article recommends checking the actual schema rather than trusting migration
> bookkeeping alone. Here, catalog assertions, model comparison and real constraint
> failures verify what PostgreSQL actually created.
>
> [Read Full Discussion](https://dev.to/gemmein/migration-says-applied-but-production-says-column-does-not-exist-7e8)

### 🌐 Community Wisdom: [One Wrong Shadow Database URL Wiped 22 Tables. 4 Guards for Agent-Run Migrations](https://dev.to/gabrielanhaia/one-wrong-shadow-database-url-wiped-22-tables-4-guards-for-agent-run-migrations-4l2e)

> **Source**: [gabrielanhaia](https://dev.to/gabrielanhaia)
>
> **Tags**: `postgres`, `prisma`, `ai`, `database`
>
> The article highlights the importance of the database targeted by a destructive
> operation and the privileges of its owner. This implementation uses a separate
> disposable server, exact target checks and a restricted application identity.
>
> [Read Full Discussion](https://dev.to/gabrielanhaia/one-wrong-shadow-database-url-wiped-22-tables-4-guards-for-agent-run-migrations-4l2e)
