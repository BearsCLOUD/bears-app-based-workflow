---
name: app-research
description: "Research external solutions, prior art, product logic, integration options, UI/UX patterns, provider behavior, and market constraints for a Bears app target. Use before app-specify and again before app-plan when risk-gated unknowns remain."
---

# App Research

`app` means one Bears product application directory under `/srv/bears/dev/app` or the `BearsCLOUD/apps` repository. `project` means only a GitHub Project board with linked metadata fields. GitHub Issues are notification records for blockers, incidents, bugs, or operator questions; they are not execution tasks. Use `repo`, `path`, `target`, `workspace surface`, or `app directory` for filesystem ownership.

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

Use this skill to gather current external and repo-local evidence for product logic before the app workflow locks requirements or lane tasks.

## When required

Run `$app-research` when the app work includes any of these:

- new product or major feature;
- external provider, integration, API, data source, or market dependency;
- UI/UX, operator flow, status, error, recovery, or notification behavior;
- unclear architecture, data model, product logic, queue/runtime ownership, or prior-art choice.

Skip only for exact bugfix or docs-only work with no new product logic and record the skip reason in the next app packet.



## Plugin target mode

Use `target_layer=plugin` when app-style flow helps a plugin governance or workflow change.

- `app-constitution` creates or updates a plugin governance baseline, not a retired standalone artifact.
- `app-research` gathers current plugin source, generated inventory, route/audit, runtime, GitHub, or install/update evidence.
- `app-specify` writes plugin-local requirements or specification docs for plugin behavior.
- `app-plan` creates plugin-local task packets; for `@Bears`, use `BearsCLOUD/bears_plugin` Project metadata when authorized.
- `app-analyze` checks drift across plugin baseline, specs, task packets, route/audit evidence, role-principle ledger, Project metadata, and notification refs.
- `app-dev` executes bounded plugin task packets through selected `@Bears` roles, skills, or subagents and updates the ledger when role principles change.
- Plugin-target `task` and `wave` keep the app-dev meanings, with plugin repo/path ownership instead of product app ownership.

## Boundary

Allowed:

- Read exact target docs and route evidence.
- Use current web, official docs, GitHub, package, and product sources when external evidence is needed.
- Summarize source links, decision options, constraints, and concrete recommendations.

Forbidden:

- Implementation edits.
- GitHub Project mutation or GitHub Issue notification mutation.
- Runtime, deploy, provider-account, secret, `.env`, production-data, raw-log, or raw-chat mutation.
- Copying large source text or proprietary content.


## Platform microtask service research scope

For future Codex microtask queues, research must compare only architecture options and handoff contracts. It must not implement a handler, queue worker, Kubernetes manifest, secret reference, or `codex exec` runner.

Required comparison axes:

- platform service ownership versus app-local ownership;
- Taskiq and Redis operational fit;
- JSON packet shape needed by L2 wave decomposition;
- safety limits for parallel `codex exec` streams;
- how status evidence returns to app-dev without blocking L2.

## Workflow

1. Run the App Target Gate.
2. State the research question, target layer, and decision that downstream skills need.
3. Search current external sources when the answer depends on outside products, APIs, market behavior, or maintained examples.
4. Compare options by fit for the exact app, app/platform/infra boundary, risk, cost, maintenance, user impact, and non-goals.
5. Emit `app-research.packet` and hand it to `$app-specify` or `$app-plan`.

## Packet

```json
{
  "schema": "app-research.packet",
  "version": "1",
  "status": "ready|needs-decision|blocked",
  "target": "<exact path or repo>",
  "app_directory": "<app directory or none>",
  "layers": ["app|platform|infra"],
  "questions": ["<decision question>"],
  "sources": [{"title": "<source>", "url_or_path": "<link or path>", "use": "<why it matters>"}],
  "recommendations": ["<concrete product or implementation logic recommendation>"],
  "non_goals": ["<not doing>"],
  "handoff": "app-specify|app-plan|operator-decision"
}
```
