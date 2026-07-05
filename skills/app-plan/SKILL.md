---
name: app-plan
description: "Convert Bears app documentation into concrete GitHub Issues and Apps Project #20 items. Use when app docs must become app-dev tasks with exact app/platform/infra lanes, paths, roles, dependencies, and handoff."
---

# App Plan

`app` means one Bears product application directory under `/srv/bears/dev/app` or the `BearsCLOUD/apps` repository. `project` means only a GitHub Project board with linked Issues and metadata fields. Use `repo`, `path`, `target`, `workspace surface`, or `app directory` for filesystem ownership.

## App Target Gate

Every app-* skill starts with this gate:

- Name one exact app directory, app docs path, plugin path, platform path, or infra path.
- Classify each target as exactly one `target_layer`: `app`, `platform`, `infra`, or `plugin`.
- `app` belongs to `BearsCLOUD/apps` and one app directory under `/srv/bears/dev/app`.
- `platform` belongs to `/srv/bears/dev/platform`.
- `infra` belongs to `/srv/bears/kubernetes`.
- `plugin` belongs to `plugins/<plugin>`; for `@Bears`, use `/srv/bears/plugins/bears` plus `subagents-roles` route/audit.
- Legacy child repos and `/srv/bears/projects` are evidence only.
- Use target-named reads when target packets name paths.
- If a request crosses layers, keep the layers separate and pass them to `$app-plan` as separate lanes.

Use this skill to convert app docs into GitHub Issues and Apps Project #20 items for `$app-dev`.

The output is applied GitHub metadata: concrete Issues in `BearsCLOUD/apps`, Project #20 items, filled fields, dependencies, lane map, and ready handoff input for `$app-dev`.



## Plugin target mode

Use `target_layer=plugin` when app-style flow helps a plugin governance or workflow change.

- `app-constitution` creates or updates a plugin governance baseline, not a retired standalone artifact.
- `app-research` gathers current plugin source, generated inventory, route/audit, runtime, GitHub, or install/update evidence.
- `app-specify` writes plugin-local requirements or specification docs for plugin behavior.
- `app-plan` creates plugin repo Issues and plugin-local task packets; for `@Bears`, use `BearsCLOUD/bears_plugin` issue metadata.
- `app-analyze` checks drift across plugin baseline, specs, task packets, route/audit evidence, role-principle ledger, and issue metadata.
- `app-dev` executes bounded plugin task packets through selected `@Bears` roles, skills, or subagents and updates the ledger when role principles change.
- Plugin-target `task` and `wave` keep the app-dev meanings, with plugin repo/path ownership instead of product app ownership.

## Boundary

Allowed:

- Read `/srv/bears/AGENTS.md`, nearest app `AGENTS.md`, app constitution, app-research packet, app spec/docs, existing GitHub Project #20 metadata, existing Issues, and route evidence.
- Create or update bounded GitHub Issues, sub-issues, Project item links, Project item fields, labels, milestones, dependencies, and evidence comments in `BearsCLOUD/apps` and Apps Project #20.
- Create only decomposition, dependency, acceptance, proof, schema-packet, blocker, lane, and handoff metadata needed by `$app-dev`.

Forbidden:

- Implementation file edits, including schema skeleton files or generated product contract files.
- Runtime, Kubernetes desired-state, provider account, repo-setting, branch-protection, environment, webhook, secret, variable, `.env`, production-data, raw-log, or raw-chat mutation.
- Product behavior decisions not stated by docs, `$app-research`, schema packets, or route evidence.
- Broad Issues that require a worker to choose architecture, scope, files, role, proof, or dependency order.

## Defaults

- Project URL: `https://github.com/users/BearsCLOUD/projects/20`.
- Project number: `20`.
- Owner repo: `BearsCLOUD/apps`.
- Local app root: `/srv/bears/dev/app`.
- Execution skill: `$app-dev`.
- Execution unit: `task`.
- Parallel batch: `wave`.

## Required inputs

- Exact app directory or app docs path under `/srv/bears/dev/app/*`.
- `app-constitution.packet` or explicit approved gap.
- `app-specification.packet`.
- `app-research.packet` when the risk gate matched.
- GitHub access to `BearsCLOUD/apps` and Apps Project #20.

## Lane map rules

Every task belongs to one layer and one lane:

- `app` lane for product app source under `/srv/bears/dev/app/<app-name>`.
- `platform` lane for shared platform work under `/srv/bears/dev/platform`.
- `infra` lane for Kubernetes desired-state or local_cd integration work under `/srv/bears/kubernetes`.

`app-plan` may create more lanes inside a layer only when each lane has disjoint repo/path targets and explicit dependencies. `$app-dev` must consume this lane map and must not invent layer or lane boundaries.

## Task rules

One GitHub Issue is one app-dev task.

Every execution Issue must include:

- exact app directory;
- layer and lane;
- exact repo and local path;
- exact allowed file/path list;
- exact forbidden paths;
- route-selected @Bears role;
- source doc references with section names;
- acceptance criteria checklist;
- L3 autoCI/CD status matrix names from automatic CI/check metadata or commit closeout expectation;
- dependency Issue URLs;
- completion proof: changed files, one commit SHA, push proof, status matrix evidence, Project status update, and closeout comment.

Split an Issue whenever repo, path, write scope, role, proof source, dependency order, platform boundary, infra boundary, or restricted-data boundary differs.

Block broad work instead of creating an execution Issue when docs do not make the task decision-complete. Forbidden broad titles include `implement backend`, `make UI`, `finish MVP`, `integrate platform`, and any equivalent title without exact files, behavior, acceptance, proof, and role.


## Product schema packets

`schema packet` means planning metadata for a future product schema or contract. It is not a file and not PASS evidence.

Rules:

- `app-plan` may design schema packets to make parallel L3 work decision-complete.
- `app-plan` must not create schema skeleton files, generated contracts, migrations, validators, or tests.
- Each schema packet must become one or more L3 materialization tasks owned by `$app-dev`.
- Schema packets may define names, owner layer, app directory, consumers, allowed paths, forbidden paths, dependencies, and status matrix expectations.
- If a schema shape is not decision-complete, create a blocker Issue instead of an execution Issue.

Schema packet shape:

```json
{
  "schema": "app-plan.product-schema-packet",
  "version": "1",
  "name": "<schema or contract name>",
  "owner_layer": "app|platform|infra",
  "app_directory": "<exact app directory or none>",
  "consumers": ["<consumer path or issue>"],
  "allowed_paths": ["<future file paths>"],
  "forbidden_paths": ["<paths>"],
  "materialization_tasks": ["<issue urls>"],
  "status_matrix": ["<automatic status names>"]
}
```

## L3 goal block

Each execution Issue must include:

```markdown
## L3 goal
/goal
unit=task
lane=<app|platform|infra|sub-lane>
layer=<app|platform|infra>
role=<route-selected @Bears role>
model=gpt-5.4-mini
reasoning=high
repo=<exact repo path>
owner_repo=<GitHub repo>
app_directory=<exact app directory or none>
target=<exact files/paths>
allowed_actions=<bounded list>
forbidden_actions=<bounded list>
acceptance_criteria=<checklist copied from this issue>
proof=<automatic status matrix or commit closeout expectation>
completion_criteria=changed files, one commit SHA, push proof, status matrix evidence, Project status update, closeout comment
```

If any field cannot be filled exactly, create a blocker Issue instead of an execution Issue.

## Workflow

1. Run the App Target Gate.
2. Read target constitution, app-research packet when required, spec, docs, and existing Project/Issue state.
3. Build the lane map first: app, platform, infra, plus optional sub-lanes with disjoint paths.
4. Convert requirements into decision-complete tasks.
5. Create dependencies so app-dev waves can run only dependency-ready, non-overlapping tasks.
6. Ensure every task has one role, one layer, one lane, one repo boundary, one L3 status matrix, and one proof requirement.
7. Emit `app-plan.project-task-packet`.
8. Run `$app-analyze` before handing execution to `$app-dev`.

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
  "lane_map": [
    {"layer": "app|platform|infra", "lane": "<lane id>", "repo": "<repo path>", "target_paths": ["<paths>"], "parallel_group": "<group id>", "dependencies": ["<issue urls>"]}
  ],
  "issues": [
    {"url": "<issue url>", "task_id": "<id>", "layer": "app|platform|infra", "lane": "<lane id>", "role": "<@Bears role>", "dependencies": ["<issue urls>"], "status_matrix": ["<automatic status names>"], "status": "ready|blocked"}
  ],
  "product_schema_packets": [
    {"name": "<schema or contract name>", "owner_layer": "app|platform|infra", "materialization_tasks": ["<issue urls>"], "status_matrix": ["<automatic status names>"]}
  ],
  "blocked_requirements": ["<requirement ids and reason>"],
  "execution_skill": "app-dev",
  "recommendation": "Run $app-analyze, then hand ready items to $app-dev."
}
```
