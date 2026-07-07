---
name: app-specify
description: "Create or update app specifications and functional documentation from operator intent, app constitution, app-research evidence, repo evidence, and acceptance criteria. Use for app behavior docs and implementation-ready requirements."
---

# App Specify

`app` means one Bears product application directory under `/srv/bears/dev/app` or the `BearsCLOUD/apps` repository. `project` means only a GitHub Project board with linked metadata fields. GitHub Issues are notification records for blockers, incidents, bugs, or operator questions; they are not execution tasks. Use `repo`, `path`, `target`, `workspace surface`, or `app directory` for filesystem ownership.

## App Target Gate

Every app-* skill starts with this gate:

- Name one exact app directory, app docs path, plugin path, platform path, or infra path.
- Classify each target as exactly one `target_layer`: `app`, `platform`, `infra`, or `plugin`.
- `app` belongs to `BearsCLOUD/apps` and one app directory under `/srv/bears/dev/app`.
- `platform` belongs to `/srv/bears/dev/platform`.
- `infra` belongs to `/srv/bears/kubernetes`.
- `plugin` belongs to `plugins/<plugin>`; for `@Bears`, route to `/srv/bears/plugins/bears` plus computed `subagents-roles` owner and expected autoCI/local-commit validation status.
- Legacy child repos and `/srv/bears/projects` are evidence only.
- Read target-named paths when target packets name paths.
- If a request crosses layers, keep the layers separate and pass them to `$app-plan` as separate lanes.

Required: activate this skill to turn operator intent into concrete app documentation and implementation-ready requirements.

A specification states what the work must do, for whom, where it lives, how success is proven, and what is out of scope.



## Plugin target mode

Required: set `target_layer=plugin` when app-style flow helps a plugin governance or workflow change.

- `app-constitution` creates or updates a plugin governance baseline, not a retired standalone artifact.
- `app-research` gathers current plugin source, generated inventory, computed role ownership, runtime, GitHub, or install/update evidence.
- `app-specify` writes plugin-local requirements or specification docs for plugin behavior.
- `app-plan` creates plugin-local task packets; for `@Bears`, write `BearsCLOUD/bears_plugin` Project metadata only when authorized.
- `app-analyze` checks drift across plugin baseline, specs, task packets, computed role ownership evidence, role-principle ledger, Project metadata, and notification refs.
- `app-dev` executes bounded plugin task packets through selected `@Bears` roles, skills, or subagents and updates the ledger when role principles change.
- Plugin-target `task` and `wave` keep the app-dev meanings, with plugin repo/path ownership instead of product app ownership.

## Boundary

Allowed:

- Read nearest `AGENTS.md`, constitution, app-research packet, README, SPEC, requirements, current docs, app functional graph, app task ledger, computed role ownership evidence, relevant GitHub Project status metadata, and notification refs.
- Create or update `spec.md`, feature docs, operator docs, user docs, or README sections in the owning repo path.
- Produce acceptance criteria and proof expectations for `$app-plan`.

Forbidden:

- Implementation code edits.
- Runtime, Kubernetes desired-state, provider, repo-setting, secret, `.env`, production-data, raw-log, or raw-chat mutation.
- Root `/srv/bears/specs`, `.specify`, root `plans.md`, root `roadmap.md`, or `/srv/bears/docs/plans.md` recreation.

## Artifact placement

Required: select the narrowest owner path:

- Existing feature docs directory when one already exists in the owning repo.
- `docs/features/<slug>/spec.md` for repo-local feature work.
- `SPEC.md` only when it already owns the repo-level product contract.
- README only for entrypoint summaries and links.

## Workflow

1. Run the App Target Gate.
2. Read the target constitution. If missing, run `$app-constitution` or record an explicit constitution gap.
3. Run or consume `$app-research` when the risk gate matches. If skipped, record the exact skip reason.
4. Extract operator intent into scope, actors, flows, inputs, outputs, data boundaries, errors, recovery behavior, and proof expectations.
5. Inspect only files needed to prevent contradictions with current implementation and docs.
6. Write or update the specification with: problem and outcome; scope and non-goals; actors and workflows; functional requirements; docs requirements; data, secret, runtime, infra, and GitHub metadata boundaries; acceptance criteria; dependencies and open questions.
7. Emit `app-specification.packet` and hand it to `$app-plan`.

## Packet

```json
{
  "schema": "app-specification.packet",
  "version": "1",
  "status": "draft|review|ready|blocked",
  "target": "<exact path or repo>",
  "app_directory": "<app directory or none>",
  "layers": ["app|platform|infra"],
  "constitution": "<path or gap>",
  "research": "<app-research.packet path|skipped: reason>",
  "spec": "<path>",
  "docs_changed": ["<paths>"],
  "requirements": ["<stable ids>"],
  "acceptance_criteria": ["<ids or summaries>"],
  "planning_input": "ready|needs-operator-review|blocked",
  "recommendation": "<next action>"
}
```

Required: set `blocked` only for missing owner, missing route coverage, missing required constitution decision, access failure, or explicit operator stop.
