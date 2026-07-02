---
name: app-docs2project-bears
description: "Convert Bears app documentation into concrete, drift-safe GitHub Issues and Apps Project #20 items. Use when app docs under /srv/bears/dev/app must become executable mini-model tasks with exact paths, roles, acceptance criteria, dependencies, and projectdevsubagents handoff."
---

# App Docs to Project Bears

Use this skill to convert a Bears product app documentation set into GitHub Issues and Apps Project #20 items.

`app` means a Bears product application source directory under `/srv/bears/dev/app` or `BearsCLOUD/apps`. `project` means a GitHub Project planning board with linked Issues and metadata fields. Use `target`, `repo`, `path`, or `app directory` for filesystem/source ownership.

The output is not a draft plan. The output is applied GitHub metadata: concrete Issues in `BearsCLOUD/apps`, linked Project #20 items, filled fields, dependencies, and ready handoff input for `$projectdevsubagents`.

## Boundary

Allowed:

- Read `/srv/bears/AGENTS.md`, nearest app `AGENTS.md`, app docs, existing GitHub Project #20 metadata, existing Issues, route/audit output, and validation policy.
- Create or update bounded GitHub Issues, sub-issues, Project item links, Project item fields, labels, milestones, and evidence comments for app-docs planning in `BearsCLOUD/apps` and Apps Project #20.
- Create only decomposition, dependency, acceptance, validation, blocker, and handoff metadata needed for execution by `$projectdevsubagents`.

Forbidden:

- Implementation file edits.
- Runtime, deploy, Kubernetes, provider, repo-setting, branch-protection, environment, webhook, secret, variable, `.env`, production-data, raw-log, or raw-chat mutation.
- Product behavior decisions not stated by app docs or route/audit evidence.
- Broad Issues that require the worker to choose architecture, scope, files, validation, role, or dependency order.

## Defaults

- Project URL: `https://github.com/users/BearsCLOUD/projects/20`.
- Project number: `20`.
- Owner repo: `BearsCLOUD/apps`.
- Local app root: `/srv/bears/dev/app`.
- Execution skill: `$projectdevsubagents`.
- Target worker class: mini-model-compatible L3 task.

Invoking this skill for an app docs target runs the bounded GitHub metadata writes listed in `Allowed` directly. The skill returns `blocked` when required GitHub access or route proof is missing.

## Required inputs

- Exact app directory or app docs path under `/srv/bears/dev/app/*`.
- App docs that state product behavior, requirements, or development plan.
- GitHub access to `BearsCLOUD/apps` and Apps Project #20.

## App docs intake

Read only the needed app docs from the target app:

- nearest `AGENTS.md`;
- `README.md`;
- `SPEC.md`;
- `requirements.md`;
- `plans.md`;
- `tasks.md`;
- `docs/**` files that define product behavior, implementation plan, acceptance, validation, or operator workflow.

Do not use root `/srv/bears/specs`, root `.specify`, root `plans.md`, root `roadmap.md`, or `/srv/bears/docs/plans.md` as app planning sources.

## Drift-safe decomposition rules

One GitHub Issue is one mini-model task.

Every execution Issue must include:

- exact app directory;
- exact repo and local path;
- exact allowed file/path list;
- exact forbidden paths;
- route-selected @Bears role;
- source doc references with section names;
- acceptance criteria checklist;
- validation source from CI/check metadata or commit-validation expectation, not ad hoc manual tests;
- dependency Issue URLs;
- completion proof: changed files, commit SHA, push proof, Project status update, and closeout comment.

Split an Issue whenever any of these differ:

- repo;
- local path;
- allowed write scope;
- route-selected role;
- validation target;
- dependency order;
- platform boundary;
- deploy boundary;
- secret or restricted-data boundary.

Block broad work instead of creating an execution Issue when the docs do not make the task decision-complete. Forbidden broad titles include `implement backend`, `make UI`, `finish MVP`, `integrate platform`, and any equivalent title without exact files, behavior, acceptance, validation, and role.

## Issue body template

Each created or updated execution Issue must contain this structure:

```markdown
## Source docs
- <path>#<section>

## Scope
- App directory: <path under /srv/bears/dev/app>
- Repo: BearsCLOUD/apps
- Local path: <exact path>
- Allowed paths: <exact list>
- Forbidden paths: <exact list>

## Acceptance criteria
- [ ] <decision-complete criterion>

## Dependencies
- <issue URL or none>

## Validation source
- <CI/check metadata or commit-validation expectation>

## L3 goal
/goal
lane=l3
role=<route-selected @Bears role>
model_class=mini
repo=/srv/bears/dev/app
owner_repo=BearsCLOUD/apps
app_directory=<exact app directory>
target=<exact files/paths>
allowed_actions=<bounded list>
forbidden_actions=<bounded list>
acceptance_criteria=<checklist copied from this issue>
validation=<metadata checks or commit-validation expectation>
completion_criteria=changed files, commit SHA, push proof, Project status update, closeout comment
```

If any field cannot be filled exactly, create a blocker Issue instead of an execution Issue.

## Workflow

1. Read `/srv/bears/AGENTS.md`, nearest app `AGENTS.md`, and app docs needed for the requested app.
2. Confirm the target is under `/srv/bears/dev/app/*` and maps to `BearsCLOUD/apps`.
3. Inspect Apps Project #20 fields, existing items, linked Issues, labels, milestones, and dependency metadata needed for the app.
4. Run route/audit for every planned target path.
5. Extract requirements, product slices, docs slices, platform-boundary checks, validation slices, and blockers from app docs.
6. Split all work by the drift-safe decomposition rules.
7. Create or update GitHub Issues and sub-issues in `BearsCLOUD/apps`.
8. Add every Issue to Project #20 and fill required fields: `source_repo`, `app_directory`, `migration_stage`, `infra_local_cd_safety`, `platform_boundary`, and `archive_readiness`.
9. Link dependencies with Issue URLs and Project metadata.
10. Emit `app-docs2project-bears.project-task-packet` with applied mutation proof.
11. Run `$bears-project-analyze` before handing execution to `$projectdevsubagents`.

## Block rules

Use `blocked` only for:

- target outside `/srv/bears/dev/app/*`;
- missing GitHub access to `BearsCLOUD/apps` or Apps Project #20;
- owner repo not resolved to `BearsCLOUD/apps`;
- route/audit `ROLE_COVERAGE_BLOCKER`;
- requirement that cannot be decomposed into no-choice mini-model tasks;
- impossible dependency order.

## Project task packet

```json
{
  "schema": "app-docs2project-bears.project-task-packet",
  "version": "1",
  "status": "applied|blocked",
  "project": {
    "url": "https://github.com/users/BearsCLOUD/projects/20",
    "number": 20
  },
  "owner_repo": "BearsCLOUD/apps",
  "local_root": "/srv/bears/dev/app",
  "app_directory": "<exact app directory>",
  "docs_checked": ["<paths>"],
  "issues": [
    {
      "title": "<issue title>",
      "url": "<issue url>",
      "project_item_id": "<id>",
      "target": "<exact path>",
      "role": "<route-selected @Bears role>",
      "dependencies": ["<issue urls>"],
      "acceptance": ["<checklist items>"],
      "validation": ["<metadata checks or commit-validation expectation>"],
      "mini_model_ready": true
    }
  ],
  "blockers": ["<exact blocker issues or reasons>"],
  "execution_skill": "projectdevsubagents",
  "analysis_required": true,
  "recommendation": "Run $bears-project-analyze, then hand ready items to $projectdevsubagents."
}
```
