---
name: app-constitution
description: "Create or update app constitutions for one Bears app target. Use before app-research, app-specify, app-plan, or app-dev when ownership rules, layer boundaries, artifact locations, or proof duties are missing or changed."
---

# App Constitution

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

Use this skill to create or update the app constitution: the concrete rule document that later app specs, docs, GitHub Project items, Issues, and app-dev agents must obey.

## Boundary

Allowed:

- Read nearest `AGENTS.md`, current app docs, existing constitution, GitHub Project or Issue metadata, and route evidence for the exact target.
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

Use the narrowest owner path:

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
  "dependent_artifacts": ["<spec/docs/GitHub Project/Issue urls>"],
  "open_drift": ["<issue urls or exact follow-up>"],
  "recommendation": "<next action>"
}
```

Use `blocked` only for access, missing owner, missing route coverage, or explicit operator stop.
