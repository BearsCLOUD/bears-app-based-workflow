---
name: project-mandate
description: "Use after the Bears project registry gate allows a /srv/bears path, when auditing or creating project, repository, module, AGENTS.md, SPEC.md, requirements.md, README, docs layout, registry, or validation artifacts. This skill is a checklist only; it is not a source of truth."
---

# Bears Project Mandate

This skill is a checklist. It is not the registry and not the role gate.

## Mandatory gate

Before using this checklist for any `/srv/bears` path:

```bash
cd /srv/bears/plugins/bears
python3 scripts/project_registry_gate.py gate <target-path>
```

Stop with `PROJECT_REGISTRATION_BLOCKER` when the path is not registered in `/srv/bears/dev/registry/projects.v1.json`.

Only continue when the gate prints `project_mandate_allowed: true`.

## Truth order

1. Nearest `AGENTS.md`.
2. `/srv/bears/dev/PROJECTS.md` human registry.
3. `/srv/bears/dev/registry/projects.v1.json` machine registry.
4. `scripts/platform_roles.py route <target-path>` role gate.
5. This checklist.

## Profiles

Choose exactly one profile for the registered target.

### `workspace_group`

Use for `/srv/bears/dev` and other registered governance groups.

Required:

- `AGENTS.md` router or linked parent router.
- `README.md`, `WORKSPACE.md`, or equivalent overview.
- Registry entry in `/srv/bears/dev/PROJECTS.md`.
- Machine entry in `/srv/bears/dev/registry/projects.v1.json`.
- Contract or `plans.md` for unresolved boundary work.

Do not require product `SPEC.md` or `requirements.md` for a pure workspace group.

### `repo_project`

Use for registered product or service repositories.

Required:

- local `AGENTS.md`;
- local `SPEC.md`;
- local `requirements.md`;
- local validation command;
- `plans.md` only for unresolved work.

Do not create these files for an unregistered path.

### `plugin_repo`

Use for `/srv/bears/plugins/bears` and registered plugin skill paths.

Required:

- `AGENTS.md`;
- `SPEC.md`;
- `requirements.md`;
- `.codex-plugin/plugin.json`;
- skill `SKILL.md` when the target is a skill;
- validator or unit test for changed workflow behavior.

### `infra_repo`

Use for `/srv/bears/kubernetes` and registered deploy infrastructure paths.

Required:

- local `AGENTS.md` when the repo exists;
- `SPEC.md` and `requirements.md` when implementation starts;
- deploy validation command;
- rollback runbook;
- approval packet for runtime mutation.

No production mutation is allowed from this checklist.

### `module_service`

Use for registered lanes inside dev-core, such as Android emulator, Sentry, E2E, ops, or provenance.

Required:

- nearest router;
- README or contract for purpose, owner, allowed writes, forbidden writes, and validation;
- exact role route;
- `plans.md` for missing evidence.

## Documentation placement

- Keep `AGENTS.md` short and link to contracts.
- Put stable interface facts in `docs/reference/` or the nearest registry.
- Put operator procedures in `docs/runbooks/`.
- Put durable decisions in `docs/adr/`.
- Put unresolved work in the narrowest `plans.md`.
- Put user-provided stable workflow facts in the Bears plugin when they change agent behavior.
- Put user-provided workspace boundary facts in `/srv/bears/dev/PROJECTS.md`, `/srv/bears/dev/registry/projects.v1.json`, or `/srv/bears/contracts/`.
- Put product behavior facts only in the registered product repo after the product role allows it.

## Restricted data rule

Do not read, print, store, or commit raw secrets, tokens, private keys, `.env` values, production data, raw logs, raw chats, or raw VPN configs.

If a task needs a secret, document only the approved secret manager reference or runtime injection method.

## Workflow

1. Run the project registry gate.
2. Run the role route for the target.
3. Select the profile from the gate packet.
4. Check required artifacts for that profile.
5. Create small missing docs only when the role route allows the exact path.
6. Record larger gaps in the narrowest `plans.md`.
7. Run the validator named by the changed docs or plugin surface.
8. For non-product closeout, follow `assets/catalog/subagent-orchestration-policy.v1.json` and run the required four audits at the lifecycle stage boundary; treat old post-task wording as alias-only.

## Output

Return:

- target path;
- registry entry id;
- profile;
- role route result;
- present required artifacts;
- missing required artifacts;
- files changed or planned follow-up;
- validation command and result.
