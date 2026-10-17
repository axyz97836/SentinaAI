# SentinelAI | Auth.md

**Version:** 1.0, 2026-10-16  
**Status:** Design policy only, **not implemented or tested**.  
**Basis:** MIKENWO quick start page 4 and SentinelAI `APP_FLOW.md` / `BACKEND_SCHEMA.md`. The three canonical roles are `ANALYST`, `RISK_MANAGER`, `ADMIN`; do not add a different role model without an approved architecture change.

## 1. Login and session design

- **MVP login:** seeded fictional demonstration users sign in with email/password at `/login` via `POST /api/v1/auth/login`. Public self-registration, social login and production account onboarding are **out of scope**.
- **Storage:** Argon2id password hash in `users.password_hash`; random opaque cookie session token; SHA-256 (or otherwise vetted one-way representation) in `sessions.token_hash`. No plaintext passwords or raw tokens persisted or logged.
- **Cookie:** `HttpOnly`, `Secure` on public HTTPS, `SameSite=Lax`, restricted path/domain as necessary, explicit expiry. On successful login establish a fresh session. Cookies are not exposed through JavaScript.
- **CSRF:** Check token and origin for all unsafe cookie-authenticated actions. Login uses login-CSRF/origin protection appropriate to session design. Do not trust SameSite as the sole CSRF control.
- **Session validation:** On **every** protected request check token hash, expiry, revocation, `users.is_active`, and current organization membership/role. Session becomes invalid after logout/revocation; newly restricted roles take effect on next request.
- **Session logout:** `POST /api/v1/auth/logout` revokes server record and expires cookie. Do not rely on clearing browser cookie alone.
- **Password recovery:** Not a self-service MVP feature. For demo/dev, an authorized owner can reset synthetic accounts through a controlled local provisioning procedure once implemented. Do not invent a public reset link or imply an email service exists.
- **Demo credential policy:** Never commit active, reusable demo passwords or secret tokens in a public repo; test fixtures use isolated values. Rate-limit login attempts and use generic incorrect-credential responses.
- **Session timeouts and rate limits:** Choose/configure during authentication phase, document observed behavior, and add tests before deployment. No timeout or throttle is asserted to be active today.

## 2. Permission table

All ordinary reads and writes below are **scoped to the organization of the authenticated membership**. UI hiding is not an authorization check. `ALLOW` means designed permission, not implemented permission.

| Resource/action | ANALYST | RISK_MANAGER | ADMIN | Server guard |
|---|---|---|---|---|
| View dashboard, transactions, scores/explanations | ALLOW | ALLOW | ALLOW | valid session + same organization |
| Ingest one transaction or SCORING CSV | ALLOW | ALLOW | ALLOW | session + tenant + input/quota checks |
| Upload TRAINING CSV | DENY | DENY | ALLOW | `ADMIN` + source policy |
| View alerts and cases | ALLOW | ALLOW | ALLOW | same-organization record lookup |
| Dismiss alert; open case | ALLOW | ALLOW | ALLOW | same org + state guard + CSRF |
| Add case note, progress and resolve case | ALLOW | ALLOW | ALLOW | same org + concurrency/version check + CSRF |
| View reports or create/download exports | ALLOW | ALLOW | ALLOW | same-org job and export check |
| View active model and metrics | ALLOW | ALLOW | ALLOW | same org |
| Train or activate a model | DENY | DENY | ALLOW | `ADMIN` + CSRF + verified artifact |
| View/change risk settings and rules | DENY | DENY | ALLOW | `ADMIN` + CSRF + version lock |
| List/change users' roles | DENY | DENY | ALLOW | `ADMIN` + last active ADMIN guard |
| View admin audit summaries | DENY | DENY | ALLOW | `ADMIN` + same org |
| Cross-organization records | DENY | DENY | DENY | tenant-scoped service/repository query |

The MVP does **not** establish a finer separation between `ANALYST` and `RISK_MANAGER`; both can resolve cases. Their separate labels are retained for future workflow changes, not portrayed as extra security boundaries.

## 3. Record-level checks and HTTP behavior

- Resolve organization from the signed-in membership; never trust incoming `organization_id` or a guessed UUID as authority.
- Before returning `GET /transactions/{id}`, `/transactions/{id}/explanation`, `/cases/{id}`, `GET /jobs/{id}` or export download, verify the record's organization. Return **404** for other organizations, not private metadata or partial content.
- For `PATCH /admin/users/{id}/role`, enforce ADMIN and the target user's membership in the same organization. Refuse removing/demoting the last active ADMIN in a locked transaction; log allowed changes without plaintext tokens.
- Read-only views do not need CSRF; mutations do. Session expiration => 401 and login route; a forbidden role => 403; missing or cross-org object => 404; case version conflict => 409.
- Do not allow role changes by over-posting: a profile/form payload containing `role=ADMIN` is ignored/rejected unless sent through the authorized admin endpoint.
- On administrative role changes or user deactivation, revoke active sessions where practical and always recheck active membership every request. Test behavior after removal rather than trusting a UI cache.

## 4. Account and session lifecycle

```text
Provision fictional user -> ADMIN assigns demo membership
    -> login (verify hash, origin, rate limit)
    -> server generates session, stores token HASH, sets cookie
    -> each request verifies session + current role + org + resource
    -> logout / expiry / deactivation / removal => access rejected
    -> expired session rows periodically purged
```

**Data model references:** `users`, `memberships`, `sessions`, `organizations`, `audit_logs`. No new authentication entity is required by this plan.

## 5. Required two-account / three-role tests

| Test ID | Setup and attempt | Expected |
|---|---|---|
| AUTH-01 | Signed-out user requests a transaction | 401; no record |
| AUTH-02 | `ANALYST` requests `GET /admin/settings`, trains a model, or changes roles | 403; no state mutation |
| AUTH-03 | `RISK_MANAGER` resolves a permitted organization case with CSRF | success and audit event |
| AUTH-04 | Create organization A and B **in isolated test fixtures**. A member requests B's transaction, case, dataset job or export UUID | 404; no leaked content, file or metadata |
| AUTH-05 | Logout, then reuse same cookie on `/auth/me` | 401 |
| AUTH-06 | Deactivate user/remove membership and retry existing session | 401/403; no access |
| AUTH-07 | Send valid login, then missing/invalid CSRF on case resolution and admin rule edit | forbidden; no write |
| AUTH-08 | Change own profile-like payload with `role=ADMIN`; test last-admin demotion | no privilege escalation; last ADMIN preserved |
| AUTH-09 | Try guessed `job_id` on export download and guessed object location | deny unless session/org allow |
| AUTH-10 | Attempt repeated failed logins | limit enforced once configured; no account existence disclosure |

**All statuses: NOT RUN.** Implement tests using fictitious users and fixtures. Store request/response and DB inspection evidence in `Security Checklist.md`, not fabricated screenshots or assertions.

## 6. Open questions

1. Exact session idle/absolute expiry and cookie domain for final custom domain: **to be approved and tested**.
2. Account recovery and invitation flows beyond dev-only reset: **v2/out of scope** unless owner explicitly changes PRD.
3. Login throttling values and deployment proxy client-IP trust settings: **to be measured**.
4. Managed authentication alternative: **not selected**; changing auth stack requires updated TRD/schema/review.

**Implementation owner:** Student project owner, supported by VS Code AI agent. A coding agent must not mark authorization secure without test evidence.
