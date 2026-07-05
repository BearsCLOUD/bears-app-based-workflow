---
name: app-dev
description: "Execute app-task-ledger tasks produced by app-plan. Parent controls L2 lane orchestrators, L2 controls helpers and L3 workers, L3 critic confirms each task before done, and GitHub Issues are manual notification records only."
---

# App Dev

`app` means one Bears product application directory under `/srv/bears/dev/app` or the `BearsCLOUD/apps` repository. `project` means only a GitHub Project board with linked items and metadata fields. Use `repo`, `path`, `target`, `workspace surface`, or `app directory` for filesystem ownership.

## App Target Gate

Every app-* skill starts with this gate:

- Name one exact app directory, app docs path, plugin path, platform path, or infra path.
- Classify each target as exactly one `target_layer`: `app`, `platform`, `infra`, or `plugin`.
- `app` belongs to `BearsCLOUD/apps` and one app directory under `/srv/bears/dev/app`.
- `platform` belongs to `/srv/bears/dev/platform`.
- `infra` belongs to `/srv/bears/kubernetes`.
- `plugin` belongs to `plugins/<plugin>`; for `@Bears`, use `/srv/bears/plugins/bears` plus computed `subagents-roles` owner and expected autoCI status.
- Legacy child repos and `/srv/bears/projects` are evidence only.
- Use target-named reads when target packets name paths.
- If a request crosses layers, keep the layers separate and pass them to `$app-plan` as separate lanes.

Use this skill to execute dependency-ready `app-task-ledger` tasks after `$app-analyze` returns `pass` or the operator explicitly approves advisory execution.

`task` means one bounded app-plan work unit in `docs/app-task-ledger.v1.json`. `wave` means one parent-dispatched batch of dependency-ready tasks that may run in parallel only when repos and target sets do not overlap.

## Required topology

- Parent/L1 controls only L2 lane orchestrators and wave boundaries.
- L2 orchestrators control Project item state, decomposition, helper subagents, and L3 assignments for their lane.
- L2 may spawn helper subagents only through `$subagents`; helpers support metadata, decomposition, evidence gathering, or packet shaping.
- L3 workers implement one ledger task with `model=gpt-5.4-mini` and `reasoning=high` unless the task packet names a stricter model.
- L3 critic uses `model=gpt-5.5`, `reasoning=high`, no parent/start context, and receives only the task plus review objective.
- L3 critic confirms 100% task completion before `done`; it never controls L2 and never edits files.
- `python-codeflow` applies inside L3 worker packets when Python files are changed.

## Plugin target mode

Use `target_layer=plugin` when app-style flow helps a plugin governance or workflow change.

- `app-constitution` creates or updates a plugin governance baseline, not a retired standalone artifact.
- `app-research` gathers current plugin source, generated inventory, computed role ownership, runtime, GitHub, or install/update evidence.
- `app-specify` writes plugin-local requirements or specification docs for plugin behavior.
- `app-plan` creates plugin-local task packets; for `@Bears`, use `BearsCLOUD/bears_plugin` metadata only when the operator authorizes metadata mutation.
- `app-analyze` checks drift across plugin baseline, specs, task packets, computed role ownership, role-principle ledger, and metadata.
- `app-dev` executes bounded plugin task packets through selected `@Bears` roles, skills, or subagents and updates the ledger when role principles change.
- Plugin-target `task` and `wave` keep the app-dev meanings, with plugin repo/path ownership instead of product app ownership.

## Boundary

Allowed:

- Read `app-plan.project-task-packet`, `app-analysis.packet`, app functional graph, app task ledger, Project item metadata, route evidence, target docs, and task-owned files.
- Start L2 lane orchestrators for `app`, `platform`, `infra`, and any sub-lanes already defined by `$app-plan`.
- Dispatch L3 workers only from `ready` ledger tasks with valid `functionality_refs`, `graph_node_refs`, `autoci_zones`, and `expected_statuses`.
- L3 workers update only their assigned ledger task through `$app-functional-graph` `claim-task` and `mark-task-status`; L2 updates Project item state from concrete worker, critic, commit, and status evidence.
- Record GitHub Issue URLs only in `notification_refs` after explicit manual notification authorization.

Forbidden:

- Parent/L1 implementation edits.
- L3 controlling L2.
- Reading GitHub Issues as execution task source.
- Inventing layer or lane boundaries not present in `app-plan.project-task-packet` and app task ledger.
- Combining unrelated layers, repos, target sets, providers, roles, functionality refs, or graph node refs into one task.
- Runtime, Kubernetes desired-state, repo-setting, secret, `.env`, production-data, raw-log, or raw-chat mutation unless the exact task and role own that layer.
- Direct CI/CD, Dagger, local_cd, or Kubernetes trigger commands from app-dev; app-dev consumes automatic status evidence only.

## Execution loop

This skill uses the same conceptual loop as implementation-by-task workflows: read ledger task, dispatch owner, collect evidence, run independent critic, close task. It does not call or depend on upstream `speckit-implement`.

1. Run the App Target Gate for the packet.
2. Read `app-analysis.packet`; stop unless handoff is ready or operator approved advisory execution.
3. Read `docs/app-functional-graph.v1.json` and `docs/app-task-ledger.v1.json`.
4. Validate graph and ledger through `$app-functional-graph` before wave grouping; each ready task needs computed autoCI zones.
5. Group dependency-ready ledger tasks into a wave by non-overlapping repo/path targets and graph node refs.
6. Start or reuse one L2 orchestrator per lane in the packet.
7. Send each L2 only its lane tasks, dependencies, graph refs, allowed Project item mutations, helper rules, and closeout format.
8. L2 may use `$subagents` helpers for decomposition or metadata support, then dispatches L3 workers for ready ledger tasks.
9. Each L3 worker claims its task, implements only that task, marks its ledger task status, and returns changed files, commit/push evidence or exact blocker, ledger evidence, Project item evidence when used, and task completion claim.
10. L2 dispatches one L3 critic per completed task. The critic receives only the task and review objective.
11. L2 accepts task `done` only after L3 has marked ledger status and critic confirms 100% completion with commit/evidence refs.
12. Parent integrates L2 closeout packets, advances the next wave, and reports remaining blockers or drift.

Hard rule: no valid ledger task means no L3 dispatch.

## L3 autoCI/CD status matrix

`autoCI/CD` means automatic status evidence created after an L3 commit is pushed. It is not a Codex command queue and it is not an L2 blocker.

Rules:

- The matrix applies only to L3 workers. L2 may continue lane orchestration while automatic statuses are pending.
- One `task` closes through one L3-owned commit. Split the task when a second commit would be needed.
- L3 closeout must name the task id, commit SHA, push proof, expected status names, and ledger update result.
- Fast CI statuses are automatic after commit or push. Agents must not create, dispatch, or run local check layers to prove completion.
- Full product proof is a fixed Dagger objective-runtime-proof scenario, followed by Kubernetes `kubernetes_deployment` plus `local_cd` evidence when live proof is required.
- Tests, validators, schemas, lint, static checks, and local host processes may be internal safety guardrails only. They are never PASS evidence.
- Missing or failing statuses become follow-up evidence for L2 triage unless the task packet declares them a hard blocker.

Required L3 status packet:

```json
{
  "schema": "app-dev.l3-status-matrix",
  "version": "1",
  "task_id": "<app-T001>",
  "functionality_refs": ["<app>.<functionality>"],
  "graph_node_refs": ["<app>.<functionality>.<node>"],
  "commit_sha": "<sha>",
  "push_proof": "<url or exact ref>",
  "autoci_zones": ["<zone id>"],
  "expected_statuses": ["<status name>"],
  "status_evidence_refs": ["<proof ref>"],
  "full_proof": "dagger-objective-runtime-proof:<scenario>|none",
  "live_proof": "kubernetes_deployment+local_cd|none",
  "task_ledger_update": "done|blocked|needs-review",
  "l2_blocking": false
}
```

## L2 packet minimum

```json
{
  "schema": "app-dev.l2-lane-packet",
  "version": "1",
  "lane": "<lane id>",
  "layer": "app|platform|infra",
  "repo": "<repo path>",
  "functional_graph": "<app directory>/docs/app-functional-graph.v1.json",
  "task_ledger": "<app directory>/docs/app-task-ledger.v1.json",
  "tasks": [
    {"task_id": "<app-T001>", "functionality_refs": ["<id>"], "graph_node_refs": ["<id>"], "allowed_paths": ["<paths>"], "autoci_zones": ["<zone id>"]}
  ],
  "allowed_project_mutations": ["status", "field updates named by app-plan"],
  "helper_policy": "Use $subagents for L2 helpers only; helpers do not implement.",
  "completion": "all assigned tasks have L3 commit evidence, automatic status matrix evidence, ledger updates, and L3 critic confirmation"
}
```

## Wave closeout

```json
{
  "schema": "app-dev.wave-closeout",
  "version": "1",
  "wave": "<wave id>",
  "status": "done|partial|blocked",
  "tasks_done": ["<task ids>"],
  "tasks_blocked": [{"task_id": "<id>", "blocker": "<exact blocker>", "owner": "<role>"}],
  "critic_confirmations": [{"task_id": "<id>", "critic": "<agent id>", "result": "confirmed|rejected"}],
  "status_matrices": [{"task_id": "<id>", "commit_sha": "<sha>", "task_ledger_update": "done|blocked", "l2_blocking": false}],
  "next_wave_ready": ["<task ids>"]
}
```
