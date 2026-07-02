---
name: project-mandate
description: "Use for one known /srv/bears target after project_registry_gate.py gate allows it; prints a small target-bound packet and forbids workspace scanning. This skill is not a source of truth."
---

# Bears Project Mandate

This skill is a checklist. It must reduce reads, not expand them.

## Gate

Run exactly for the user target:

```bash
cd /srv/bears/plugins/bears
python3 scripts/project_registry_gate.py gate <target-path>
python3 scripts/project_registry_gate.py mandate-packet <target-path>
```

Continue only when `status: matched` and `project_mandate_allowed: true`.

Stop with `PROJECT_REGISTRATION_BLOCKER` or the printed blocker when the target is not registered in `/srv/bears/dev/registry/projects.v1.json` or the role gate blocks it.

## Read budget

Read only:

- paths printed under `read_paths`;
- the exact user target when it is not already listed and the task needs its content.

Do not run:

- `find /srv/bears`;
- broad `grep` or `rg` over `/srv/bears`;
- repo-wide inventories;
- scans of `.git`, `.knowledge`, `runtime`, `.worktrees`, `.tmp`, `deprecated`, `legacy`, caches, or generated files.

Do not rerun `scripts/platform_roles.py route` when the packet already prints `primary_role` and `concrete_part`.

## What to check

Use the packet fields only:

- `project_id` — registered project owner;
- `artifact_profile` — expected artifact type;
- `primary_role` and `concrete_part` — role authority;
- `nearest_router` — local routing rules;
- `validation_commands` — allowed validation hint.

Do not build a full artifact inventory. If evidence is missing, record the exact missing file or follow-up; do not scan for substitutes.

## Safe edits

- Keep `AGENTS.md` short and router-only.
- Put stable rules in the owning contract, registry, README, or skill file.
- Put unresolved work in the narrowest existing `plans.md` only when the route allows it.
- Never create files for an unregistered target.
- Never read, print, store, or commit secrets, tokens, private keys, `.env` values, production data, raw logs, raw chats, or raw VPN configs.
- After validation, commit and push the completed tracked slice immediately; completed means validated, committed, and pushed.

## Output

Return:

- target;
- project id;
- profile;
- role result;
- read paths used;
- changed files or follow-up;
- validation result.
