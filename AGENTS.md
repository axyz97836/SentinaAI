# SentinelAI agent workflow

## Authority and phase boundaries

Implement only the phase explicitly authorized by the project owner. Completion of a
phase does not authorize starting the next one. Stop after the final verification,
commit, push and report, then wait for owner review and explicit phase approval.

Read and follow all eleven approved planning/security documents before implementation:

1. [PRD](docs/PRD.md)
2. [TRD](docs/TRD.md)
3. [Application flow](docs/APP_FLOW.md)
4. [UI/UX brief](docs/UIUX_BRIEF.md)
5. [Backend schema](docs/BACKEND_SCHEMA.md)
6. [Implementation plan](docs/IMPLEMENTATION_PLAN.md)
7. [Security](docs/security/Security.md)
8. [Authentication](docs/security/Auth.md)
9. [Data security](<docs/security/Data Security.md>)
10. [Threat model](<docs/security/Threat Model.md>)
11. [Security checklist](<docs/security/Security Checklist.md>)

The implementation plan defines phase scope regardless of its historical v1.1 label.
The backend schema defines the eighteen domain tables, columns, types, constraints,
relationships and API contracts. Preserve all eleven documents and their versions
unless the owner explicitly authorizes a specific documentation change. Record actual
implementation evidence separately under `verification/`.

Retain the approved Next.js, TypeScript, Tailwind CSS, FastAPI/Pydantic, SQLAlchemy,
Alembic, PostgreSQL, Redis, Celery and private S3-compatible storage architecture.
Do not add product features, tables, roles, UI libraries or architecture substitutions
outside the authorized phase. UI UX Pro Max is installed; do not reinstall it.

## Repository and standing push authorization

The owner explicitly authorizes publishing verified SentinelAI code to:

`https://github.com/axyz97836/SentinaAI`

Use this exact URL for `origin`. If a remote is absent, configure it. If it already
exists, inspect it before changing anything; never silently replace a different remote.
The authorization covers verified checkpoints and final phase results on the appropriate
feature branch throughout development. Routine authorized pushes do not require another
confirmation. It does not authorize deployment, changing GitHub security controls,
force-pushing, deleting remote branches or automatically merging into `main`.

- `main` starts from verified Phase 1 commit `ccd5f97e793dc90a9b5f33a7365190cd74fc2a7e`.
  Never reset or move an existing published main branch backward to this baseline.
- Use **`feat/phase-02-database`** for Phase 2. The earlier `feat/phase-02-schema`
  branch and existing commits are preserved; do not reconstruct Phase 2 history.
- Future phases use a clear phase-specific feature branch. Inspect the approved base
  and remote state before creating one; do not assume pending feature work is merged.
- Never force-push, rewrite published history, or automatically merge a feature branch
  into `main`. A merge or deployment needs separate explicit owner authorization.
- If synchronization is not a straightforward safe push, fetch and inspect ancestry.
  Preserve local/remote commits; report a substantive conflict instead of overwriting it.

## Verified checkpoints

Consider a checkpoint after approximately **200–300 meaningful changed lines**.
Prefer a logical, independently testable unit over an exact line count. This is a prompt
to review completed work, not a target that justifies shipping incomplete changes.

For each checkpoint:

1. Inspect Git status, current branch, configured remotes and pending changes.
2. Review the scoped diff and run relevant tests, lint, types and builds for that change.
3. Fix failures before committing. Never call an unexecuted check a pass.
4. Check the staged file list and staged diff, including whitespace and secret hygiene.
5. Commit completed, verified work with a descriptive conventional message, for example
   `feat(db): add transaction models and constraints`,
   `test(db): verify organization isolation`, or `fix(db): correct migration permissions`.
6. Push the verified commit to the appropriate remote feature branch using an explicit
   refspec when useful. Do not push unrelated local branches or all tags by default.
7. Verify the remote branch points to the intended commit using `git ls-remote` or an
   equivalent authenticated GitHub check. A successful local commit is not a push.

Commit and push the final verified phase result and verification report. Do not push
known-broken, unfinished or unverified code to meet a checkpoint size. Preserve existing
verified commits rather than retroactively splitting or rewriting them for this policy.

## Secrets, credentials and local data

- Never commit `.env`, database passwords, API keys, generated demo login credentials,
  private storage contents, sensitive logs or uploaded data. Keep local credentials in
  Git-ignored files with restrictive permissions.
- Before the first push, inspect all history being published, not just the working tree.
  Before later pushes, inspect the new commits and staged contents for credentials and
  accidentally tracked private files. Report the scope and limitations of secret scans.
- Use synthetic data only. Do not introduce real identities or financial records, or
  present synthetic predictions/metrics as genuine observed results.
- Use existing secure Git authentication or an interactive browser/device/credential-manager
  flow when needed. Never request a token in agent chat or embed one in a remote URL,
  shell command, tracked file or log. Do not disable GitHub security controls.
- Preserve working files, database volumes, existing credentials and verified seed data.
  Do not regenerate credentials, reset the main database or repeat seed setup unnecessarily.
- Keep migration credentials separate from the restricted application identity. Do not
  grant schema DDL to the application account or publish database/broker/storage ports.

## Resume and verification procedure

When resuming after interruption, first inspect Git status/history, changed files,
the relevant verification report, saved test/build results, migration status and running
services/test resources. Determine what is actually incomplete; do not restart a phase
or duplicate completed work. Reuse valid test evidence for unchanged code, and rerun
checks when changes, failures or unresolved concerns justify it.

For Phase 2, schema and destructive migration round-trip tests run only in the guarded
disposable database through `make database-check`. Never run destructive rollback tests
against the main development database. Applicable checks also include `make backend-check`,
main schema inspection/Alembic comparison, seed idempotency and production refusal,
`make infra-check`, `make browser-check` and dependency outage/recovery verification.

Maintain `verification/phase-N.md` with exact changed files, migration revisions where
applicable, executed commands, actual counts/results, errors/fixes, security evidence,
remaining limitations and local Git references. Do not mark future security controls
as passed. Report GitHub branch/commit URLs, commits created in the current task,
remote refs verified and any authentication/synchronization errors in the final response.

## Current development boundary

Phases 1, 2 and 3 have been completed, verified
and merged into main.

Each phase requires explicit owner authorization. Historical completion notes
are not authorization to restart work or advance to another phase.
Phase 4 (secure CSV ingestion, private storage and durable jobs) is explicitly
authorized on `feat/phase-04-ingestion`, based on current merged `origin/main`.
Stop after verified commits, push and report; merging and Phase 5 need separate approval.

Before starting a new phase:
1. Confirm the previous phase is merged into main.
2. Synchronize local main with origin/main.
3. Create a dedicated phase-specific feature branch.
4. Read the current approved implementation plan.
5. Execute only the authorized phase.
6. Verify, commit, push and report.
7. Wait for owner review before merging or advancing.

Do not treat historical phase instructions as
authorization to restart completed work.
