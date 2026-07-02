---
name: bears-project-constitution
description: "Create or update a Bears project constitution: concrete principles, ownership rules, artifact locations, validation duties, and dependent documentation sync. Use before project specification, GitHub Project planning, or plan execution when a repo/project lacks a current constitution or its rules changed."
---

# Bears Project Constitution

Use this skill to create or update a project constitution for a Bears repo, app, platform part, plugin, infra lane, or migration workstream.

A constitution is the project rule document that later specs, plans, GitHub Project items, and execution agents must obey.

## Boundary

Allowed:

- Inspect nearest `AGENTS.md`, README, SPEC, requirements, docs, existing contracts, GitHub issue/project metadata, and route/audit output.
- Create or update the narrow project constitution artifact.
- Add short router links from README or AGENTS only when the nearest router owns that pointer.
- Record unresolved drift as owner-scoped follow-up work.

Forbidden:

- Runtime, deploy, Kubernetes, provider, repository setting, secret, credential, `.env`, production-data, or raw-log mutation.
- Product implementation.
- Root `/srv/bears/specs`, `.specify`, root `plans.md`, root `roadmap.md`, or `/srv/bears/docs/plans.md` recreation.

## Artifact placement

Pick the narrowest existing owner path:

- Plugin: `/srv/bears/plugins/<plugin>/docs/reference/<project>-constitution.md` or plugin catalog when a machine contract already owns the rule.
- Infra: `/srv/bears/kubernetes/docs/reference/<project>-constitution.md` or the nearest manifest/runbook docs path.
- Platform: `/srv/bears/dev/platform/docs/reference/<project>-constitution.md`.
- Apps: `/srv/bears/dev/app/<app>/docs/constitution.md` or `/srv/bears/dev/app/docs/<app>-constitution.md` when the app has no docs directory.
- Workspace router: tracked root docs only when the rule is workspace-wide.

Do not create a new parent docs tree when a nearer repo-local docs path exists.

## Workflow

1. Read `/srv/bears/AGENTS.md`, the nearest project `AGENTS.md`, and route/audit for the exact target path.
2. If operator principles are missing, ask at most five concrete questions covering owner, scope, forbidden behavior, validation, and GitHub planning impact.
3. Inspect current README, SPEC, requirements, docs, catalogs, and GitHub issue/project metadata needed for the target only.
4. Draft or update the constitution with these sections:
   - Scope and owner;
   - Principle table with stable ids, exact rule text, rationale, validation proof, and dependent artifacts;
   - Artifact map for spec, documentation, GitHub Project plan, execution, validation, and closeout;
   - Forbidden paths and forbidden actions;
   - Drift handling with owner repo and issue requirement;
   - Amendment rule with required validation and approval.
5. Sync dependent docs by adding only short links or replacing conflicting rule text. Do not duplicate the full constitution into routers.
6. Emit a `bears-project.constitution-packet` before closeout.
7. Run validation commands that match changed files, then request gitflow closeout.

## Constitution packet

```json
{
  "schema": "bears-project.constitution-packet",
  "version": "1",
  "status": "draft|review|approved|blocked",
  "target": "<exact path or repo>",
  "constitution": "<artifact path>",
  "owner": "<repo or team>",
  "principles": ["<stable ids>"],
  "dependent_artifacts": ["<spec/docs/project/plan paths or urls>"],
  "validation": ["<commands or metadata checks>"],
  "open_drift": ["<issue urls or exact follow-up>"],
  "recommendation": "<next action>"
}
```

Use `blocked` only for missing access, missing owner, missing required route coverage, or explicit operator stop.
