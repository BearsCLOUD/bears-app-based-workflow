---
name: bears-plugin-update
description: "Use for @Bears plugin updates: route policy ownership, keep central plugin config separate from target AGENTS.md and target .codex surfaces, and rely on automatic CI/local-commit checks for validation."
---

# Bears Plugin Update

Use this skill when changing the `@Bears` plugin source under `/srv/bears/plugins/bears`.

This skill is regulatory. It defines where update facts belong and which owner surface must be changed. It does not store target-specific product facts and does not replace route/audit ownership discovery.

## Ownership routing

### Central plugin config

Use central plugin config only when the change affects shared plugin policy or generated plugin surfaces:

- plugin manifest or capability metadata;
- skill catalog and generated skill inventory;
- role catalog and role TOML profiles;
- Git, CI, CD, hook, closeout, and workflow policy catalogs;
- generated plugin inventory;
- plugin-owned scripts, hooks, schemas, tests, and capability packages.

### Target AGENTS.md

Edit a target `AGENTS.md` only when the rule belongs to one exact repo or path:

- local ownership and directory rules;
- forbidden paths;
- source-of-truth pointers;
- target-specific workflow entrypoints;
- target-specific repo, path, or app directory responsibility.

### Target .codex/

Use a target `.codex/` surface only for materialized Codex runtime behavior inside that target:

- repo-local agent files;
- repo-local skill wrappers;
- generated local prompts or config;
- target-local Codex behavior that must not become global plugin policy.

## Plugin storage limits

The plugin must not store target-specific product facts, board facts, repo-local implementation details, or per-target docs content. Put those facts in the target `AGENTS.md`, target docs, or target `.codex/` according to the routing rules above.

The plugin stores only shared routing rules, governance contracts, role definitions, policy catalogs, hook policy, generated plugin inventory, and validators that enforce those surfaces.

## Route and audit use

Run route/audit only as ownership discovery before edits. Route/audit output is not PASS evidence and must not replace automatic CI or local-commit validation.

## Validation ownership

Automatic CI and local-commit validation own plugin checks. Skill text must not list manual script-command runbooks as the operator workflow.

Manual command execution is allowed only when the operator names a command or when the nearest repo instructions explicitly allow that exact agent-local ownership check.

## Update checklist

1. Identify whether the changed fact belongs to central plugin config, target `AGENTS.md`, or target `.codex/`.
2. Run route/audit for ownership discovery on the exact target path.
3. Keep target-specific facts out of plugin policy.
4. Update generated plugin inventory when the skill catalog changes.
5. Let automatic CI/local-commit validation own blocking check results.
6. Report changed files, ownership route result, validation source, and any carried unrelated dirty paths.
