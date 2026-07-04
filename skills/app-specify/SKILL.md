---
name: app-specify
description: "Create or update app specifications and functional documentation from operator intent, app constitution, app-research evidence, repo evidence, and acceptance criteria. Use for app behavior docs and implementation-ready requirements."
---

# App Specify

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

Use this skill to turn operator intent into concrete app documentation and implementation-ready requirements.

A specification states what the work must do, for whom, where it lives, how success is proven, and what is out of scope.

## Boundary

Allowed:

- Read nearest `AGENTS.md`, constitution, app-research packet, README, SPEC, requirements, current docs, route evidence, and relevant GitHub Project or Issue metadata.
- Create or update `spec.md`, feature docs, operator docs, user docs, or README sections in the owning repo path.
- Produce acceptance criteria and proof expectations for `$app-plan`.

Forbidden:

- Implementation code edits.
- Runtime, Kubernetes desired-state, provider, repo-setting, secret, `.env`, production-data, raw-log, or raw-chat mutation.
- Root `/srv/bears/specs`, `.specify`, root `plans.md`, root `roadmap.md`, or `/srv/bears/docs/plans.md` recreation.

## Artifact placement

Use the narrowest owner path:

- Existing feature docs directory when one already exists in the owning repo.
- `docs/features/<slug>/spec.md` for repo-local feature work.
- `SPEC.md` only when it already owns the repo-level product contract.
- README only for entrypoint summaries and links.

## Workflow

1. Run the App Target Gate.
2. Read the target constitution. If missing, run `$app-constitution` or record an explicit constitution gap.
3. Run or consume `$app-research` when the risk gate matches. If skipped, record the exact skip reason.
4. Extract operator intent into scope, actors, flows, inputs, outputs, data boundaries, errors, recovery behavior, and proof expectations.
5. Inspect only files needed to avoid contradicting current implementation and docs.
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

Use `blocked` only for missing owner, missing route coverage, missing required constitution decision, access failure, or explicit operator stop.
