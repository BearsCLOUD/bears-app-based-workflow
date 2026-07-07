---
name: app-plan
description: "Convert Bears app documentation into app-task-ledger execution tasks and Apps Project #20 status items. Use when app docs must become app-dev tasks with exact functionality refs, app/platform/infra lanes, paths, roles, dependencies, and handoff; GitHub Issues are manual notifications only."
---

# App Plan

`app` means one Bears product application directory under `/srv/bears/dev/app` or the `BearsCLOUD/apps` repository. `project` means only a GitHub Project board with linked items and metadata fields. Use `repo`, `path`, `target`, `workspace surface`, or `app directory` for filesystem ownership.

## App Target Gate

Every app-* skill starts with this gate:

- Name one exact app directory, app docs path, plugin path, platform path, or infra path.
- Classify each target as exactly one `target_layer`: `app`, `platform`, `infra`, or `plugin`.
- `app` belongs to `BearsCLOUD/apps` and one app directory under `/srv/bears/dev/app`.
- `platform` belongs to `/srv/bears/dev/platform`.
- `infra` belongs to `/srv/bears/kubernetes`.
- `plugin` belongs to `plugins/<plugin>`; for `@Bears`, route to `/srv/bears/plugins/bears` plus computed `subagents-roles` owner and expected autoCI status.
- Legacy child repos and `/srv/bears/projects` are evidence only.
- Read target-named paths when target packets name paths.
- If a request crosses layers, keep the layers separate and pass them to `$app-plan` as separate lanes.

Required: activate this skill to convert app docs into app-local ledger tasks for `$app-dev` and Project #20 planning/status refs.

For `target_layer=app`, run `$app-functional-graph` before creating execution tasks.

## Plugin target mode

Required: set `target_layer=plugin` when app-style flow helps a plugin governance or workflow change.

- `app-constitution` creates or updates a plugin governance baseline, not a retired standalone artifact.
- `app-research` gathers current plugin source, generated inventory, computed role ownership, runtime, GitHub, or install/update evidence.
- `app-specify` writes plugin-local requirements or specification docs for plugin behavior.
- `app-plan` creates plugin-local task packets; for `@Bears`, write `BearsCLOUD/bears_plugin` metadata only when the operator authorizes metadata mutation.
- `app-analyze` checks drift across plugin baseline, specs, task packets, computed role ownership, role-principle ledger, and metadata.
- `app-dev` executes bounded plugin task packets through selected `@Bears` roles, skills, or subagents and updates the ledger when role principles change.
- Plugin-target `task` and `wave` keep the app-dev meanings, with plugin repo/path ownership instead of product app ownership.

## Boundary

Allowed:

- Read `/srv/bears/AGENTS.md`, nearest app `AGENTS.md`, app constitution, app-research packet, app spec/docs, app functional graph, app task ledger, Apps Project #20 metadata, and computed role ownership evidence.
- Create or update app-local `docs/app-functional-graph.v1.json` and `docs/app-task-ledger.v1.json` through `$app-functional-graph`.
- Create or update Project item refs as planning/status metadata linked to `task_id` and `functionality_ref`.
- Create decomposition, dependency, acceptance, proof, schema-packet, lane, and handoff metadata needed by `$app-dev`.
- Record GitHub Issue URLs only in `notification_refs` after explicit manual notification authorization.

Forbidden:

- Implementation file edits, including schema skeleton files or generated product contract files.
- Automatic GitHub Issue creation for execution tasks.
- Runtime, Kubernetes desired-state, provider account, repo-setting, branch-protection, environment, webhook, secret, variable, `.env`, production-data, raw-log, or raw-chat mutation.
- Product behavior decisions not stated by docs, `$app-research`, schema packets, functional graph, or computed role ownership evidence.
- Broad tasks that require a worker to choose architecture, scope, files, role, proof, or dependency order.

## Defaults

- Project URL: `https://github.com/users/BearsCLOUD/projects/20`.
- Project number: `20`.
- Owner repo: `BearsCLOUD/apps`.
- Local app root: `/srv/bears/dev/app`.
- Execution skill: `$app-dev`.
- Execution unit: `task`.
- Parallel batch: `wave`.
- Functional graph: `docs/app-functional-graph.v1.json`.
- Task ledger: `docs/app-task-ledger.v1.json`.

## Required inputs

- Exact app directory or app docs path under `/srv/bears/dev/app/*`.
- `app-constitution.packet` or explicit approved gap.
- `app-specification.packet`.
- `app-research.packet` when the risk gate matched.
- App functional graph or permission to create it through `$app-functional-graph`.
- App task ledger or permission to create it through `$app-functional-graph`.
- GitHub Project access when Project status refs are requested.

## Lane map rules

Every task belongs to one layer and one lane:

- `app` lane for product app source under `/srv/bears/dev/app/<app-name>`.
- `platform` lane for shared platform work under `/srv/bears/dev/platform`.
- `infra` lane for Kubernetes desired-state or local_cd integration work under `/srv/bears/kubernetes`.

`app-plan` may create more lanes inside a layer only when each lane has disjoint repo/path targets and explicit dependencies. `$app-dev` must consume this lane map and must not invent layer or lane boundaries.

## Task rules

One `app-task-ledger` task is one `$app-dev` execution task. Each ready task must satisfy the required fields in `app-plan.project-task-packet` below plus exact allowed paths, forbidden paths, source refs, acceptance criteria, and closeout proof.

Split a task whenever repo, path, write scope, role, proof source, dependency order, functionality ref, graph node ref, platform boundary, infra boundary, or restricted-data boundary differs.

Block broad work instead of creating an execution task when docs and graph do not make the task decision-complete. Forbidden broad titles include `implement backend`, `make UI`, `finish MVP`, `integrate platform`, and any equivalent title without exact files, behavior, acceptance, proof, role, `functionality_refs`, and `graph_node_refs`.

GitHub Issue rule: `app-plan` may create a GitHub Issue only after explicit manual notification authorization. Store the URL in `notification_refs` with reason `blocker`, `incident`, `bug`, or `operator-question`.

## Product schema packets

`schema packet` means planning metadata for a future product schema or contract. It is not a file and not PASS evidence.

Rules:

- `app-plan` may design schema packets to make parallel L3 work decision-complete.
- `app-plan` must not create schema skeleton files, generated contracts, migrations, validators, or tests.
- Each schema packet must become one or more L3 materialization tasks in the app task ledger.
- Schema packets may define names, owner layer, app directory, consumers, allowed paths, forbidden paths, dependencies, functionality refs, graph node refs, and status matrix expectations.
- If a schema shape is not decision-complete, create a ledger task with `status=blocked` or record a manual notification Issue after authorization.

Schema packet shape:

```json
{
  "schema": "app-plan.product-schema-packet",
  "version": "1",
  "name": "<schema or contract name>",
  "owner_layer": "app|platform|infra",
  "app_directory": "<exact app directory or none>",
  "consumers": ["<consumer path or task_id>"],
  "allowed_paths": ["<future file paths>"],
  "forbidden_paths": ["<paths>"],
  "functionality_refs": ["<app>.<functionality>"],
  "graph_node_refs": ["<app>.<functionality>.<node>"],
  "materialization_tasks": ["<task ids>"],
  "status_matrix": ["<automatic status names>"]
}
```

## L3 goal block

Each execution task must provide the packet fields below to `$app-dev`. If any field cannot be filled exactly, create a blocked ledger task instead of a ready execution task.

```markdown
## L3 goal
/goal
unit=task
task_id=<app-T001>
lane=<app|platform|infra|sub-lane>
layer=<app|platform|infra>
role=<route-selected @Bears role>
model=gpt-5.4-mini
reasoning=high
repo=<exact repo path>
owner_repo=<GitHub repo>
app_directory=<exact app directory or none>
functional_graph=<app directory>/docs/app-functional-graph.v1.json
task_ledger=<app directory>/docs/app-task-ledger.v1.json
functionality_refs=<ids>
graph_node_refs=<ids>
graph_edge_refs=<ids or none>
target=<exact files/paths>
allowed_actions=<bounded list>
forbidden_actions=<bounded list>
acceptance_criteria=<checklist copied from ledger task>
proof=<automatic status matrix or commit closeout expectation>
completion_criteria=changed files, one commit SHA, push proof, status refs, ledger update, Project status update when used, closeout comment
```

## Workflow

1. Run the App Target Gate.
2. Read target constitution, app-research packet when required, spec, docs, existing functional graph, task ledger, and Project state when used.
3. Use `$app-functional-graph` to initialize or update graph and ledger.
4. Build the lane map first: app, platform, infra, plus optional sub-lanes with disjoint paths.
5. Convert requirements into decision-complete ledger tasks with functionality refs and graph node refs.
6. Create dependencies so `$app-dev` waves can run only dependency-ready, non-overlapping tasks.
7. Ensure every task satisfies the packet schema, has one owner role, and has valid graph refs.
8. Emit `app-plan.project-task-packet`.
9. Run `$app-analyze` before handing execution to `$app-dev`.

## Packet

```json
{
  "schema": "app-plan.project-task-packet",
  "version": "1",
  "status": "planned|partial|blocked",
  "project_url": "https://github.com/users/BearsCLOUD/projects/20",
  "owner_repo": "BearsCLOUD/apps",
  "target": "<exact app docs path>",
  "app_directory": "<exact app directory>",
  "functional_graph": "<app directory>/docs/app-functional-graph.v1.json",
  "task_ledger": "<app directory>/docs/app-task-ledger.v1.json",
  "lane_map": [
    {"layer": "app|platform|infra", "lane": "<lane id>", "repo": "<repo path>", "target_paths": ["<paths>"], "parallel_group": "<group id>", "dependencies": ["<task ids>"]}
  ],
  "tasks": [
    {"task_id": "<id>", "layer": "app|platform|infra", "lane": "<lane id>", "role": "<@Bears role>", "functionality_refs": ["<id>"], "graph_node_refs": ["<id>"], "graph_edge_refs": [], "dependencies": ["<task ids>"], "project_refs": [], "notification_refs": [], "status_matrix": ["<automatic status names>"], "status": "ready|blocked"}
  ],
  "product_schema_packets": [
    {"name": "<schema or contract name>", "owner_layer": "app|platform|infra", "functionality_refs": ["<id>"], "graph_node_refs": ["<id>"], "materialization_tasks": ["<task ids>"], "status_matrix": ["<automatic status names>"]}
  ],
  "blocked_requirements": ["<requirement ids and reason>"],
  "execution_skill": "app-dev",
  "recommendation": "Run $app-analyze, then hand ready ledger tasks to $app-dev."
}
```
