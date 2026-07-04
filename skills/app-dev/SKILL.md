---
name: app-dev
description: "Execute app-plan tasks from GitHub Project/Issues. Parent controls L2 lane orchestrators, L2 controls helpers and L3 workers, and L3 critic confirms each task before done."
---

# App Dev

`app` means one Bears product application directory under `/srv/bears/dev/app` or the `BearsCLOUD/apps` repository. `project` means only a GitHub Project board with linked Issues and metadata fields. Use `repo`, `path`, `target`, `workspace surface`, or `app directory` for filesystem ownership.

## App Target Gate

Every app-* skill starts with this gate:

- Name one exact app directory or app docs path.
- Classify each target as exactly one layer: `app`, `platform`, or `infra`.
- `app` layer belongs to `BearsCLOUD/apps` and one app directory under `/srv/bears/dev/app`.
- `platform` layer belongs to `/srv/bears/dev/platform`.
- `infra` layer belongs to `/srv/bears/kubernetes`.
- Legacy child repos and `/srv/bears/projects` are evidence only.
- Broad workspace scans are forbidden when target packets name paths.
- If a request crosses layers, keep the layers separate and pass them to `$app-plan` as separate lanes.

Use this skill to execute dependency-ready `app-plan` tasks after `$app-analyze` returns `pass` or the operator explicitly approves advisory execution.

`task` means one bounded app-plan work unit. `wave` means one parent-dispatched batch of dependency-ready tasks that may run in parallel only when repos and target sets do not overlap.

## Required topology

- Parent/L1 controls only L2 lane orchestrators and wave boundaries.
- L2 orchestrators control Project/Issue state, decomposition, helper subagents, and L3 assignments for their lane.
- L2 may spawn helper subagents only through `$subagents`; helpers support metadata, decomposition, evidence gathering, or packet shaping.
- L3 workers implement one task with `model=gpt-5.4-mini` and `reasoning=high` unless the task packet names a stricter model.
- L3 critic uses `model=gpt-5.5`, `reasoning=high`, no parent/start context, and receives only the task plus review objective.
- L3 critic confirms 100% task completion before `done`; it never controls L2 and never edits files.
- `python-codeflow` applies inside L3 worker packets when Python files are changed.

## Boundary

Allowed:

- Read `app-plan.project-task-packet`, `app-analysis.packet`, GitHub Project/Issue metadata, route evidence, target docs, and task-owned files.
- Start L2 lane orchestrators for `app`, `platform`, `infra`, and any sub-lanes already defined by `$app-plan`.
- Dispatch L3 workers only from decision-complete task packets.
- Update Project/Issue state only from L2 with concrete worker and critic evidence.

Forbidden:

- Parent/L1 implementation edits.
- L3 controlling L2.
- Inventing layer or lane boundaries not present in `app-plan.project-task-packet`.
- Combining unrelated layers, repos, target sets, providers, or roles into one task.
- Runtime, Kubernetes desired-state, repo-setting, secret, `.env`, production-data, raw-log, or raw-chat mutation unless the exact task and role own that layer.

## Execution loop

This skill uses the same conceptual loop as implementation-by-task workflows: read task, dispatch owner, collect evidence, run independent critic, close task. It does not call or depend on upstream `speckit-implement`.

1. Run the App Target Gate for the packet.
2. Read `app-analysis.packet`; stop unless handoff is ready or operator approved advisory execution.
3. Group dependency-ready tasks into a wave by non-overlapping repo/path targets.
4. Start or reuse one L2 orchestrator per lane in the packet.
5. Send each L2 only its lane tasks, dependencies, allowed Project/Issue mutations, helper rules, and closeout format.
6. L2 may use `$subagents` helpers for decomposition or metadata support, then dispatches L3 workers for ready tasks.
7. Each L3 worker returns changed files, commit/push evidence or exact blocker, Project/Issue evidence, and task completion claim.
8. L2 dispatches one L3 critic per completed task. The critic receives only the task and review objective.
9. L2 marks task `done` only after critic confirms 100% completion.
10. Parent integrates L2 closeout packets, advances the next wave, and reports remaining blockers or drift.

## L2 packet minimum

```json
{
  "schema": "app-dev.l2-lane-packet",
  "version": "1",
  "lane": "<lane id>",
  "layer": "app|platform|infra",
  "repo": "<repo path>",
  "tasks": ["<issue urls>"],
  "allowed_project_mutations": ["status", "comments", "dependency links", "field updates named by app-plan"],
  "helper_policy": "Use $subagents for L2 helpers only; helpers do not implement.",
  "completion": "all assigned tasks done by L3 worker plus L3 critic confirmation"
}
```

## Wave closeout

```json
{
  "schema": "app-dev.wave-closeout",
  "version": "1",
  "wave": "<wave id>",
  "status": "done|partial|blocked",
  "tasks_done": ["<issue urls>"],
  "tasks_blocked": [{"issue": "<url>", "blocker": "<exact blocker>", "owner": "<role>"}],
  "critic_confirmations": [{"issue": "<url>", "critic": "<agent id>", "result": "confirmed|rejected"}],
  "next_wave_ready": ["<issue urls>"]
}
```
