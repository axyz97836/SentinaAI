# Project-local agent skills

This directory contains instruction-only skills installed for repository contributors.
SentinelAI's root `AGENTS.md`, eleven approved planning/security documents, phase
boundaries, architecture, security, accessibility and test requirements remain
authoritative. Ponytail may simplify an implementation only after those requirements
are satisfied; it must not remove required validation, error handling or coverage.

Installed from `DietrichGebert/ponytail` version 5.3.2 at commit
`09c434ab73ca43761c5d8b0c5d341926c2fba710` using the official skills-only method:

```sh
DO_NOT_TRACK=1 npx --yes skills@1.7.4 add DietrichGebert/ponytail \
  --agent codex --skill ponytail --skill ponytail-review --copy --yes
```

The generated `skills-lock.json` records the source and content hashes. No Ponytail
plugin, lifecycle hook, global setting or runtime dependency is installed. Review an
upstream update and repeat verification before updating these copies.
