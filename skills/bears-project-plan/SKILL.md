---
name: bears-project-plan
description: "Create or update Bears implementation plans through GitHub Projects and Issues from a constitution and specification. Use when planning work into Project items, issue hierarchy, fields, dependencies, L2 lanes, L3 @Bears role assignments, validation, and handoff to projectdevsubagents execution."
---

# Bears Project Plan

Use this skill to turn a ready specification into a GitHub Project-backed implementation plan.

A GitHub Project plan is the execution board plus linked Issues, sub-issues, fields, dependencies, labels, milestones, and owner routes that `$projectdevsubagents` can consume.

Use `$github-project-planning` when the task is Project administration: field model, views, roadmap structure, metadata hygiene, or operator-authorized Project/Issue mutations. Use this skill when the specification is ready and must be mapped into executable Project items.

## Boundary

Allowed:

- Read the specification packet, constitution packet, nearest `AGENTS.md`, existing GitHub Project/Issue metadata, repo docs, route/audit output, and validation policy.
- Draft Project field mappings, Issue hierarchy, dependencies, L2 lanes, L3 role slices, and metadata update packets.
- Create or update GitHub Project/Issue metadata only when the operator explicitly authorizes that mutation in the task packet.

Forbidden:

- Implementation file edits.
- Runtime, deploy, Kubernetes, provider, repo-setting, secret, `.env`, production-data, raw-log, or raw-chat mutation.
- Direct parent-agent Project mutation without explicit operator authorization.
- Treating Project planning as a substitute for repo-local spec/docs.

## Required inputs

- Constitution packet or explicit constitution gap.
- Specification packet with `planning_input=ready` or explicit operator approval to plan a draft.
- Owner repo and target paths.
- GitHub Project URL or explicit request to propose one.

## Workflow

1. Read `/srv/bears/AGENTS.md`, nearest target `AGENTS.md`, constitution, and spec.
2. Run route/audit for every planned repo/path owner.
3. Inspect existing GitHub Project fields, items, issue types, labels, milestones, and linked PR/release metadata needed for the target.
4. Split requirements into issue slices by repo boundary, owner role, write scope, validation path, and dependency.
5. Define Project fields with exact allowed values for status, repo, target path, role, validation, blocker, dependency, and closeout evidence.
6. Build L2 lane assignments for `bears-github-project-issues-orchestrator` and L3 assignment templates for route-selected @Bears roles.
7. If metadata mutation is authorized, create or update only the planned Project/Issue metadata and record ids/URLs. If not authorized, emit a dry-run packet.
8. Emit a `bears-project.github-plan-packet`.
9. Run `$bears-project-analyze` before handing execution to `$projectdevsubagents`.

## Project plan packet

```json
{
  "schema": "bears-project.github-plan-packet",
  "version": "1",
  "status": "draft|ready|applied|blocked",
  "project": "<url or proposed name>",
  "owner_repo": "<owner/repo>",
  "spec": "<path>",
  "constitution": "<path or gap>",
  "metadata_mutation_authorized": false,
  "items": [
    {
      "title": "<issue or item title>",
      "repo": "<owner/repo>",
      "target": "<path>",
      "role": "<route-selected @Bears role>",
      "dependencies": ["<item ids or titles>"],
      "validation": ["<commands or metadata checks>"],
      "acceptance": ["<requirement ids>"]
    }
  ],
  "l2_lanes": ["<orchestrator lanes>"],
  "execution_skill": "projectdevsubagents",
  "analysis_required": true,
  "recommendation": "<next action>"
}
```

Use `blocked` only for missing Project access, missing owner, missing route coverage, explicit operator stop, or impossible dependency order.
