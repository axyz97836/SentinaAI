# Phase 3 verification — Session authentication, CSRF and RBAC

Date: 2026-10-20. Branch: `feat/phase-03-auth`.
Base: `39f8eb79039bec147a19fca44e46183319ef59d7` (merged Phase 2).
Scope: Phase 3 only. No deployment, merge, login UI or Phase 4 work.

## Result and preservation

Local verification: **PASS**. Hosted CI is pending the first checkpoint push and
must reach a final successful result before Phase 3 is declared complete.
The eleven approved documents match [their recorded SHA-256 hashes](approved-documents.sha256).
No SQLAlchemy domain model, migration, database grant or dependency lock changed.
The main database remains at `0001_initial_schema`, with eighteen domain tables
and the existing three fictional users. Its volume and credentials were preserved.
Browser verification creates and revokes a real session for the existing fictional
ANALYST and appends login/logout audits; it does not rerun the seed.

## Authentication and session lifecycle

Implemented `POST /api/v1/auth/login`, `GET /api/v1/auth/me`,
`POST /api/v1/auth/logout` and the supporting `GET /api/v1/auth/csrf`.
Login accepts only email/password, normalizes email, rejects extra fields and
verifies the existing Argon2id hashes (64 MiB, three iterations, parallelism four).
An unknown account still executes an Argon2id verification using an ephemeral
dummy hash. Wrong password, unknown and inactive accounts share the same generic
401 response. This is not a claim of formally constant-time end-to-end HTTP behavior.

Each successful login generates a fresh 256-bit opaque token. PostgreSQL stores
only its SHA-256 hash. The raw token is sent only as an HttpOnly cookie, never JSON.
A previous presented session is revoked on successful reauthentication.
Session and successful audit writes share a transaction which must finish before
cookies or success are sent. Tests inject audit and transaction-completion failures
and verify rollback, 503 and no session cookie.

Every authenticated request checks expiry, revocation, user activity and current
membership/role in PostgreSQL. Defaults: eight-hour absolute expiry and 30-minute
idle expiry. Activity updates last-seen but cannot extend absolute expiry.
Role changes take effect on the next request. Missing/invalid/revoked/expired
sessions, inactive users and removed memberships return 401.

The approved session table has no organization selector. Accounts with zero or
multiple memberships are refused; the implementation never guesses a tenant or
accepts an organization ID from the request as authority. The existing demo users
each have one membership. Supporting organization selection requires a future
explicitly approved design.

Logout follows the schema's API contract: **204 with an empty body**, server-side
revocation and expiration of both session and pre-login cookies. Replayed revoked
tokens return 401.

`make auth-cleanup` is a bounded maintenance command using the restricted
application role: at most ten batches of 500 expired or day-old revoked sessions,
with row locks and SKIP LOCKED. It preserves valid sessions and audit records.
Run daily; this phase does not install a host cron job. No cleanup was run against
the main database during verification; deletion behavior was tested in isolation.

## Cookies, CSRF and reverse proxy

All cookies: HttpOnly, SameSite=Lax, Path=/, explicit expiry, no Domain attribute.
Local Compose explicitly permits non-Secure cookies only for loopback HTTP origins.
Production configuration requires an auth key, HTTPS origins and Secure cookies,
using `__Host-sentinel_session` and `__Host-sentinel_preauth`.
HTTPS cookie flags were tested through an HTTPS TestClient transport; no public
TLS deployment or production hosting was configured or certified.

Token exchange:

1. GET `/api/v1/auth/csrf` returns `{csrf_token}` and a signed HttpOnly pre-login
   cookie with a ten-minute lifetime. A valid existing session instead receives a
   session-bound CSRF proof.
2. POST login with JSON `{email,password}`, `X-CSRF-Token` and an exact approved
   `Origin`. Browser fetch supplies Origin automatically.
3. Login returns identity/role/organization and a new session-bound CSRF proof,
   while the bearer token stays exclusively in the HttpOnly cookie.
4. Send the new proof in `X-CSRF-Token` with every authenticated unsafe request.
   After reload, GET the CSRF endpoint again. Keep proofs in memory.
5. Logout requires the same origin and session-bound proof. A proof from a prior
   session is rejected.

HMAC-SHA256 proofs use purpose separation and constant-time comparison, bound to
the opaque session or signed pre-login nonce. A separate randomly generated key
is stored only in ignored `.local/auth.env` (0600). Existing infrastructure/demo
credentials were not regenerated. Setup was rerun and byte preservation verified.

Missing, null, unapproved origins, cross-site Fetch Metadata, missing/wrong proofs,
tampered/expired pre-login cookies and proofs from another session are rejected.
SameSite alone is not relied on. CSRF bootstrap GET allows an absent Origin under
same-origin browser policy, rejects an explicitly unapproved Origin and enables no CORS.
All responses use no-store. Auth request bodies are limited to 4 KiB, including
chunked bodies; password input is bounded to 256 characters.

Next.js proxies only the four auth paths plus the existing health paths.
The browser test exercises the actual Next-to-FastAPI path.
Uvicorn uses `--no-proxy-headers`: forwarded IP/host/role headers do not establish
identity or change allowed origins. Behind Next, its socket-peer budget is shared
by its clients; trusted proxy attribution and production limit tuning remain
deployment decisions.

The CSRF design follows the session-binding guidance in the
[OWASP CSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).

## Authorization and organization isolation

Reusable `Identity` and `require_roles` dependencies read trusted server records.
All three roles may perform ordinary authenticated operations; ANALYST and
RISK_MANAGER have the documented overlap. ADMIN-only guards deny both with 403.
Extra JSON privilege fields are rejected; forged role/user/organization headers
cannot grant access.

`organization_record` includes the authenticated organization in the SQL predicate
for transactions, jobs (including report export jobs), datasets, models, alerts
and cases. Foreign and missing IDs return indistinguishable 404 responses.
Tests cover all six model types and all three roles; test-only routes exercise
actual dependency enforcement. No demonstration business/admin endpoints were added.

The last-active-ADMIN guard locks the organization row and refuses removal of its
last active administrator. Future management endpoints must perform authorization,
tenant checks and the mutation in that same locked transaction, including all
affected organizations on deactivation. Those endpoints do not exist yet.

## Login abuse protection and audit

Redis DB 1 uses one atomic Lua admission operation for peer and account budgets.
Defaults: 20 attempts per observed socket peer and 5 per normalized account per
300-second fixed window. Successes also consume budget, preventing successful
requests from resetting failure limits and bounding Argon2 work.
Keys contain keyed digests, not emails/IPs, and expire automatically.
Concurrent test: exactly 5 of 32 simultaneous admissions succeed with a limit of 5.
429 includes bounded Retry-After. Real connection refusal and injected Redis failure
both fail closed with 503; PostgreSQL sessions and logout remain usable.

Login/logout success adds an append-only audit row with trusted organization/actor,
session ID, request ID and empty bounded metadata. No raw token, token hash,
password hash, password or CSRF proof is included.
Unauthenticated failures are recorded in allowlisted security logs with action,
status and generated request ID. The schema requires a non-null organization for
audit rows, so unknown accounts are not assigned a fabricated organization.
Application UPDATE/DELETE on audit logs and schema DDL remain denied.

API Docker logs rotate at 10 MiB, three files. This bounds local log size; it does
not verify the proposed fourteen-day production log retention or ninety-day audit
archive/purge. Those operational retention controls remain future release gates.

## Executed checks

| Command/check | Actual result |
|---|---|
| `make database-check` | **209 passed**, 1 dependency deprecation warning, 8.17 s; 153 existing schema tests + 56 auth/security integration tests |
| Isolated Alembic round-trip | Upgrade → downgrade → upgrade, schema parity, keys/indexes/constraints and grants passed within database suite |
| `make backend-check` | **45 passed**, 209 deselected, 4 dependency warnings, 1.77 s; Ruff lint/format passed; strict mypy passed for 18 source files |
| `make frontend-check` | ESLint, Next type generation, TypeScript and production build passed |
| `make infra-check` | 5 PASS groups: restricted PostgreSQL identity, Redis authentication, S3 authenticated/anonymous checks, bucket restriction, Celery ping |
| `make outage-check` | 8 PASS groups: baseline, PostgreSQL/Redis/storage outage and recovery, private port bindings |
| `make browser-check` | **8 passed**, 28.6 s; seven existing foundation checks plus real browser auth/CSRF/cookie/logout regression |
| `make up` | All six services healthy; no volume reset |
| Compose `config --quiet` | Passed |
| Main database read-only inspection | `0001_initial_schema`; 18 domain tables; 3 users |
| Approved document hash check | 11/11 OK |
| Credential hygiene | Existing .env, migration, demo and new auth key files ignored, each mode 0600; auth key preserved on repeated setup |
| Editor diagnostics | No errors found; editor test runner found no tests, so actual pytest/Playwright commands were used |
| Hosted GitHub Actions | Pending first verified checkpoint push |

Security coverage includes successful/wrong/unknown/inactive login; missing and
invalid sessions; idle/absolute expiry; logout/replay; current roles/memberships;
ADMIN allow/deny; overposting and forged headers; tenant isolation; last-admin
invariant; login/mutation CSRF; rate limiting/concurrency/expiry; Redis outage;
development/production cookie flags; secret redaction; audit/session atomicity;
safe cleanup; and actual restricted application-role operation.

Warnings retained from the pinned dependency set: Starlette's httpx TestClient
deprecation and Redis health probe retry_on_timeout deprecation. No dependency
versions were changed merely to suppress them.

## Errors found and resolved

- Initial isolated run: **199 passed, 1 failed**. In
  `test_session_rotation_and_csrf_binding`, replay used an httpx domainless cookie.
  After server-side revocation was correctly rejected with 401, GET CSRF expired
  the host cookie, but httpx retained the separately scoped domainless test cookie.
  Replaying with the original `testserver.local` domain and `/` path restored
  browser-equivalent semantics. The cookie-removal and revoked-token assertions
  remain intact. Subsequent runs passed 205, then 208, then 209 tests as coverage grew.
- Browser collection failed with `ReferenceError: require is not defined` because
  `import.meta.url` conflicted with Playwright's CommonJS test loader. Using
  `resolve(__dirname, ...)` fixed the file lookup without changing module settings
  or adding dependencies.
- Final contract review found logout returning 200 instead of the approved 204.
  Endpoint, integration assertions and browser assertion now require 204 and no body.
- Redis sync/async shared annotations required explicit synchronous result typing
  and string Lua arguments; strict mypy validates the implementation.
- Ruff identified import ordering/long lines in new code and tests; formatting fixes
  were applied. These failed checks were not counted as passes.
- Native Ruff was absent from the optional host venv. Checks used the existing
  pinned Docker test image. Host Node 22.11 remains below the documented native
  tooling recommendation; supported pinned Docker Node builds passed, and the
  local browser suite also ran successfully.

Authentication browser tests explicitly disable trace, screenshots and video so
credentials do not enter test artifacts. Isolated auth tests disable pytest's
value-rich assertion rewriting to avoid echoing temporary test cookies on failures.
Raw local test logs remain ignored and are not committed.

## Exact file changes

Created:

- `backend/app/auth/__init__.py`
- `backend/app/auth/body_limit.py`
- `backend/app/auth/cleanup.py`
- `backend/app/auth/crypto.py`
- `backend/app/auth/dependencies.py`
- `backend/app/auth/errors.py`
- `backend/app/auth/limiter.py`
- `backend/app/auth/routes.py`
- `backend/app/auth/service.py`
- `backend/tests/test_auth_primitives.py`
- `backend/tests/database/test_auth.py`
- `frontend/tests/auth.spec.ts`
- `infra/scripts/setup-auth-env.mjs`
- `verification/phase-3.md`

Modified:

- `.env.example`
- `AGENTS.md`
- `Makefile`
- `README.md`
- `backend/Dockerfile`
- `backend/app/config.py`
- `backend/app/main.py`
- `backend/tests/conftest.py`
- `frontend/next.config.ts`
- `infra/compose.database-tests.yaml`
- `infra/compose.yaml`
- `infra/scripts/check-database.mjs`
- `infra/scripts/diagnose-compose.mjs`

The private auth key and verification logs under `.local/` are local-only files,
not source deliverables.

## Git and hosted CI

Implementation commit, remote confirmation and hosted workflow URL will be recorded
after the verified checkpoint is pushed. No force push, main merge or deployment
is authorized or performed.

## Remaining boundaries and operator steps

- Full login frontend, public registration, invitations, password recovery and all
  business workflows are outside Phase 3.
- No claim is made that future APIs are protected before they use the guards and
  gain their own tests.
- Arrange daily `make auth-cleanup` in the eventual approved operations environment.
  Do not run destructive migration checks against the main database.
- Single-membership MVP behavior, shared proxy peer limits and deployment TLS,
  secret management, backups and time-based log/audit retention need future review.
- Existing seeded credentials remain private and unchanged. No real identities or
  financial data were introduced.
- Stop after Phase 3 verification and publication; Phase 4 requires explicit approval.
