# SentinelAI CI stabilization

**Hosted CI: PASS. Phase 3 has not started.**

Verified on 19 October 2026. Fix commit:
[`2583966263a93630c5b7a0c0f3256aeb2115bad9`](https://github.com/axyz97836/SentinaAI/commit/2583966263a93630c5b7a0c0f3256aeb2115bad9),
branch [`feat/phase-02-database`](https://github.com/axyz97836/SentinaAI/tree/feat/phase-02-database).
The [successful hosted run](https://github.com/axyz97836/SentinaAI/actions/runs/39222797834)
finished with conclusion **success**. Every required job step succeeded; the failure-only
diagnostics step was correctly skipped. This report is a subsequent documentation-only checkpoint.

## Confirmed failures and fixes

### 1. SeaweedFS credential ownership caused the hosted startup failure

The [original failed run](https://github.com/axyz97836/SentinaAI/actions/runs/39135494319)
stopped at `make up` when object storage became unhealthy roughly two seconds after
starting. Its cleanup removed the container before application diagnostics were collected.

Inspection of the pinned SeaweedFS 4.48 image showed that its entrypoint starts as root,
fixes the data directory ownership and then drops to the `seaweed` account, UID/GID 1000.
The generated S3 credential file was a read-only bind mount with mode `0600`, owned by
the host user. The successful hosted run recorded the source metadata as **1001:1001 600**.
UID 1000 cannot read that file on a normal Linux filesystem.

An isolated Linux/amd64 reproduction placed an existing credential-file copy on a
Linux Docker volume with ownership 1001:1001 and mode 0600. Unmodified startup failed
with **exit 255, OOMKilled=false** and a fatal `permission denied` while loading the S3
config. The same pinned image started with a Mac bind mount on both ARM64 and amd64,
so a successful Mac startup alone had not established Linux permission compatibility.

The fix stages the read-only source into `/run/seaweedfs/s3.json` **before** the existing
entrypoint drops privileges. The copy is owned by `seaweed`, mode `0600`, inside a
mode-`0700` tmpfs mounted with `noexec,nosuid,nodev`. The upstream entrypoint is then
executed normally and the server remains UID/GID 1000. The source file stays read-only
and its host permissions and bytes are unchanged. Missing/empty sources fail startup.

A clean Linux/amd64 run using the previously failing ownership fixture became healthy.
The runtime copy matched the source byte-for-byte, the service user could read it, and
UID 65534 could not. Storage authentication and anonymous-access denial also passed.
No health check was removed, no timeout was extended, and no private port was published.

### 2. PostgreSQL's initialization server passed the old probe too early

The resumed isolated database run exposed a separate race: Compose declared PostgreSQL
healthy, then provisioning failed with `the database system is shutting down` on the
Unix socket. The official entrypoint starts an initialization-only server with
`listen_addresses=''`, runs setup scripts, stops it and starts the final server.

The previous `pg_isready` probe used the default Unix socket, which can accept connections
during that temporary phase. Both main and test Compose probes now specify
**`-h 127.0.0.1`**, waiting for the final TCP-listening server. The address is inside the
container; database host ports remain unpublished. Application readiness still verifies
an authenticated query separately. Isolated migration upgrade/downgrade/upgrade and all
153 database tests passed afterward.

The main PostgreSQL container was recreated only to apply its revised healthcheck, using
the same existing named data volume. No reset, destructive migration or main reseed occurred.

### 3. The local outage harness hit an idle HTTP socket failure

After PostgreSQL was fixed, an outage-check liveness request failed with `UND_ERR_SOCKET`.
The API remained healthy, with zero restarts and no OOM. The script used synchronous
Docker commands while retaining pooled HTTP connections, preventing socket lifecycle
callbacks from running while a service stopped.

Docker subprocess calls now use awaited asynchronous `execFile`. Their order, timeouts,
error handling, final restoration and all HTTP 200/503 assertions remain intact. This
lets the event loop retire idle/closed connections. Two controlled probes across a
seven-second asynchronous subprocess delay passed, followed by the complete real
outage/recovery test locally and on GitHub. No retry was added to hide a failed liveness
assertion. This was an additional local verification failure, not the original storage cause.

## Changed files

- [infra/compose.yaml](../infra/compose.yaml): private tmpfs credential staging and TCP PostgreSQL probe.
- [infra/compose.database-tests.yaml](../infra/compose.database-tests.yaml): final-server TCP readiness gate.
- [infra/scripts/check-stack.mjs](../infra/scripts/check-stack.mjs): asynchronous Docker orchestration.
- [infra/scripts/diagnose-compose.mjs](../infra/scripts/diagnose-compose.mjs): new bounded, redacted service-state/health/log diagnostics.
- [.github/workflows/ci.yml](../.github/workflows/ci.yml): quiet Compose validation, non-secret permission metadata and failure diagnostics before cleanup.
- [verification/phase-2.md](phase-2.md): updated CI status and link to this report.
- [verification/ci-stabilization.md](ci-stabilization.md): this evidence record.

No application functionality, dependencies, database schema, migrations, roles, frontend
components or approved architecture were changed. All eleven approved planning/security
documents retain their original hashes and version labels.

## Executed verification

| Check | Actual result |
|---|---|
| `docker compose --env-file .env -f infra/compose.yaml config --quiet` | PASS |
| `docker compose -f infra/compose.database-tests.yaml config --quiet` | PASS |
| Isolated Linux/amd64 permission reproduction | Original startup rejected source, exit 255; fixed clean startup healthy |
| Source/runtime permissions and identity | Source 1001:1001/0600; runtime 1000:1000/0600; directory 0700; PID 1 UID 1000; unrelated UID denied |
| `make backend-check` | Ruff lint/format PASS; mypy PASS for 9 files; **17 passed**, 153 deselected, 4 existing warnings, 12.41s locally |
| `make frontend-check` | ESLint, Next type generation, TypeScript and production build PASS; completed terminal fallback used when editor task output was unavailable |
| `make database-check` after TCP fix | **153 passed in 4.17s**; migration round trip, schema, constraints, permissions and seed checks included |
| `make infra-check` | All five integration groups PASS: database, Redis auth, private S3 operations, bucket restriction and Celery ping |
| `make outage-check` after async fix | PostgreSQL/Redis/storage each caused readiness 503 with liveness 200; all recovered; private port checks PASS |
| `make browser-check` | **7 passed in 15.1s**, Chromium |
| Diagnostics synthetic checks | 3 PASS: secret redaction in health/logs, failed-command stderr withholding, malformed-input refusal without disclosure |
| Actual diagnostics helper execution | PASS; output contained no current local credential values |
| JavaScript syntax, editor diagnostics, staged whitespace | PASS |
| Main preservation checks | Credential-file hashes unchanged; original PostgreSQL volume retained; revision `0001_initial_schema`, 18 domain tables and 3 demo users present |
| Final local service state | All six main services healthy; disposable reproduction/test containers and volumes removed |

The earlier isolated run failed before database tests began because of the temporary
server race; the affected checks were rerun after the fix. The initial outage attempt
failed on a client socket; the final affected checks passed. Completed unchanged backend
and frontend verification was retained across the interrupted task, not falsely counted
as a new run.

### Hosted evidence

Run [39222797834](https://github.com/axyz97836/SentinaAI/actions/runs/39222797834) verified:

- Source credential-file metadata: `1001:1001 600`.
- `make up`: PASS, including SeaweedFS and final PostgreSQL readiness.
- Database suite: **153 passed in 2.21s**.
- Migration and fictional demo seed: PASS on the disposable GitHub runner environment.
- Backend units: **17 passed in 0.75s**, four existing deprecation warnings.
- Ruff, mypy, frontend lint/type/build: PASS.
- Infrastructure and all three outage/recovery checks: PASS.
- Browser suite: **7 passed in 3.2s**.
- npm audit: **0 vulnerabilities**.
- Cleanup and job conclusion: **success**.

Thus **177 automated test cases passed both locally and in the hosted fix run**, alongside
the additional diagnostic and permission checks. GitHub success was confirmed through
the run/job APIs and the actual job log, not inferred from a successful push.

## Commands to repeat

From the project root with Docker running and the existing local credentials:

```sh
docker compose --env-file .env -f infra/compose.yaml config --quiet
make up
make backend-check
make frontend-check
make database-check
make infra-check
make outage-check
make browser-check
```

To diagnose a failure before stopping containers:

```sh
node infra/scripts/diagnose-compose.mjs
```

The helper prints selected container state and bounded logs after redacting known local
secrets and Argon2 hash strings. It does not dump container environment or resolved
Compose configuration. It is not a general-purpose secret scanner.

## Remaining limits and phase boundary

No CI blocker remains on the Phase 2 feature branch. The four pre-existing backend
deprecation warnings remain. GitHub also reports action-runtime deprecation notices;
the pinned actions completed successfully. They were not changed as part of this fix.

`main` remains the original Phase 1 baseline and was not merged or rewritten. Its
historical failed runs are unchanged; the owner must explicitly approve a future merge.
There was no deployment, credential rotation, production change or Phase 3 work.

## References

The runtime privilege drop is visible in the pinned
[SeaweedFS 4.48 entrypoint](https://github.com/seaweedfs/seaweedfs/blob/4.48/docker/entrypoint.sh).
The temporary socket-only PostgreSQL server and its shutdown are defined by the
[official PostgreSQL image entrypoint](https://github.com/docker-library/postgres/blob/master/docker-entrypoint.sh)
and were also inspected in the actual pinned container. The HTTP client symptom is
consistent with the upstream [Undici closed-connection issue](https://github.com/nodejs/undici/issues/3492).

Community context: [Core Trail Labs](https://dev.to/coretraillabs/a-running-container-doesnt-mean-a-healthy-service-5a16)
distinguishes process state, health output and causal evidence;
[jtorchia](https://dev.to/jtorchia/docker-healthcheck-what-the-command-actually-runs-and-what-it-doesnt-tell-you-j3k)
explains the limits of a probe. Comments likewise emphasize testing real dependency
paths. These two articles informed the diagnostic approach; the conclusions above
come from this project's actual failure reproductions and test results.
