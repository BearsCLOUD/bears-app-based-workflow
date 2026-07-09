# Project Dirty Baseline Gate

## Purpose

This gate captures read-only provenance about dirty nested repositories under a bounded root.

`/srv/bears/projects` is a transitional project container. It is **not** the baseline for Bears plugin-core stabilization. Plugin-governance-only closeout must not be blocked by unrelated dirty project repositories inside that container.

## What it does

- discovers nested git repositories by `.git` markers only;
- collects branch, HEAD, upstream when present, short status metadata, tracked change names/status codes, and untracked file paths;
- reports nearest governance-file presence for `AGENTS.md`, `SPEC.md`, and `requirements.md`;
- returns a conservative packet with `write_handoff_allowed=false` in every status.

## What it never does

- no raw diff output;
- no file-content output;
- no git cleanup, reset, stash, checkout, commit, merge, rebase, or rollback behavior;
- no product, runtime, deploy, integration, or source-mutation authorization.

Operator confirmation can change dirty-baseline status from `DIRTY_BASELINE_REQUIRES_OPERATOR_CONFIRMATION` to `BASELINE_ACCEPTED_READ_ONLY`, but it still does **not** open product writes.

## Scope modes

### `project-write-lane`

Default mode. Apply it only after selecting one concrete repo root for a product/runtime/deploy/integration write lane.

If the selected concrete repo root is dirty and the operator has not confirmed that baseline, the command returns `DIRTY_BASELINE_REQUIRES_OPERATOR_CONFIRMATION` and blocks only that concrete repo write lane.

### `container-inventory`

Read-only inventory mode. Apply it for broad containers such as `/srv/bears/projects` when the current task is plugin-core governance rather than a concrete project migration.

This mode returns `CONTAINER_INVENTORY_ONLY` and exits successfully even when nested repositories are dirty. It does not authorize writes and does not replace a future per-project baseline gate.

## Required commands

```bash
cd /srv/bears/plugins/bears
python3 scripts/project_dirty_baseline.py validate
python3 scripts/project_dirty_baseline.py capture --root /srv/bears/projects --scope-mode container-inventory --json
python3 scripts/project_dirty_baseline.py capture --root <concrete-repo-root> --json
```

## Role-gate rule

This gate never replaces:

```bash
python3 scripts/subagents_roles.py route <target>
```

Any later implementation handoff must still pass the exact route for the concrete write target and then follow the nearest local project gates.

Future project migration under `/srv/bears/projects` happens sequentially: pick one concrete project, pass the canonical role route, capture/confirm only that project's dirty baseline when needed, then run the nearest local project validation.
