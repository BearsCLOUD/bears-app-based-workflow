---
name: app-constitution
description: "Create or update app constitutions for one Bears app target before app-research, app-specify, app-plan, or app-dev when ownership rules, layer boundaries, artifact locations, or proof duties are missing or changed."
---

# App Constitution

`app` means one Bears product application directory under `/srv/bears/dev/app` or the `BearsCLOUD/apps` repository. `project` means only a GitHub Project board with linked metadata fields. GitHub Issues are notification records for blockers, incidents, bugs, or operator questions; they are not execution tasks. Say `repo`, `path`, `target`, `workspace surface`, or `app directory` for filesystem ownership.

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

Required: activate this skill to create or update the app constitution: the concrete rule document that later app specs, docs, app functional graph, app task ledger, GitHub Project status items, notification refs, and app-dev agents must obey.



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

- Read nearest `AGENTS.md`, current app docs, existing constitution, app functional graph, app task ledger, GitHub Project status metadata, notification refs, and computed role ownership evidence for the exact target.
- Create or update only the narrow constitution artifact and short links from owned docs.
- Record unresolved drift as owner-scoped follow-up work.

Forbidden:

- Product implementation.
- Runtime, Kubernetes desired-state, provider, repo-setting, secret, `.env`, production-data, raw-log, or raw-chat mutation.
- Root `/srv/bears/specs`, `.specify`, root `plans.md`, root `roadmap.md`, or `/srv/bears/docs/plans.md` recreation.


## Platform microtask service constitution scope

When the target is a future Codex microtask queue, the constitution may define only ownership and boundaries. Runtime implementation is out of scope for this skill.

The constitution must state:

- `@Bears` owns policy packets and workflow rules only.
- The platform service owns runtime execution.
- Kubernetes owns runtime placement and secret references.
- Taskiq means the Python task worker layer. Redis means the queue or state backend. Secret values are never stored in plugin artifacts.
- The future flow is JSON packet -> platform service -> Taskiq/Redis -> `codex exec` stream.

## Artifact placement

Required: select the narrowest owner path:

- App: `/srv/bears/dev/app/<app-name>/docs/constitution.md`, or `/srv/bears/dev/app/docs/<app-name>-constitution.md` when the app directory has no docs directory.
- Platform: `/srv/bears/dev/platform/docs/reference/<target>-constitution.md` only for shared platform layer rules.
- Infra: `/srv/bears/kubernetes/docs/reference/<target>-constitution.md` only for infra layer rules.
- Plugin: plugin-local docs or catalog only when the plugin is the target.

## Workflow

1. Run the App Target Gate and stop on ambiguous target, repo, or layer ownership.
2. If operator principles are missing, ask at most five concrete questions covering owner, scope, forbidden behavior, proof, and GitHub Project impact.
3. Inspect only target docs and metadata needed for the constitution.
4. Write the constitution with: scope and owner; layer map; principle table; artifact map; forbidden paths/actions; drift handling; amendment rule.
5. Add only short links from owned docs; do not duplicate the constitution into routers.
6. Emit `app-constitution.packet`.

## Packet

```json
{
  "schema": "app-constitution.packet",
  "version": "1",
  "status": "draft|review|approved|blocked",
  "target": "<exact path or repo>",
  "app_directory": "<app directory or none>",
  "layers": ["app|platform|infra"],
  "constitution": "<artifact path>",
  "owner": "<repo or team>",
  "dependent_artifacts": ["<spec/docs/graph/ledger/Project item/notification urls>"],
  "open_drift": ["<issue urls or exact follow-up>"],
  "recommendation": "<next action>"
}
```

Required: set `blocked` only for access, missing owner, missing route coverage, or explicit operator stop.
