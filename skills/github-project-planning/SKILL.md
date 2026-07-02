---
name: github-project-planning
description: "Use for Bears GitHub Project planning and administration before development execution: creating or selecting GitHub Projects, defining field models, roadmap views, issue and sub-issue structure, item field hygiene, planning PASS packets, and handoff to projectdevsubagents. Do not use for product implementation, L2/L3 dev dispatch, runtime/deploy work, repository settings, secrets, or raw logs."
---

# GitHub Project Planning

Use this skill to plan and govern GitHub Projects and linked Issues before any development orchestration starts.

## Scope

In scope:

- select an existing GitHub Project or prepare an operator-authorized Project creation packet;
- define Project fields, views, roadmap slices, issue types, labels, milestones, and item hygiene rules;
- create a planning PASS packet with Project URL/number, fields, views, owner repos, local paths, owner roles, validation targets, and mutation authorization state;
- plan Issues, sub-issues, draft items, comments, labels, and milestones;
- verify that `BearsCLOUD/apps` planning follows the canonical Apps Project #20 field policy when that Project is in scope.

Out of scope:

- product, platform, infra, runtime, deploy, MCP, connector, or provider implementation;
- L2/L3 development dispatch from existing Project state;
- direct mutation of repository settings, branch protection, environments, webhooks, Actions settings, secrets, variables, or production state;
- reading raw logs, raw CI logs, raw chats, shell history, credential files, production data, `.env` values, or secret values.

After planning PASS, hand off development execution to `projectdevsubagents` with the Project/Issue state and route/audit targets.

## Required references

Load only the references needed for the current planning task:

- `references/planning-flow.md` for intake, Project setup, fields, views, item fill, and PASS;
- `references/field-model.md` for required field definitions and allowed values;
- `references/item-and-issue-rules.md` for Issue, sub-issue, draft item, comment, label, and milestone decisions;
- `references/views-and-roadmap.md` for standard views and roadmap slicing;
- `references/apps-migration-project.md` for `BearsCLOUD/apps` Project #20 migration planning.

## Operating rules

1. Start from the nearest `AGENTS.md`, the owning repository boundary, and explicit operator intent.
2. Run route/audit before changing plugin planning artifacts or before assigning an owner role to planned work.
3. Treat GitHub Project or Issue mutations as external metadata changes. Require an explicit operator authorization packet before creating or editing Projects, fields, views, Issues, sub-issues, labels, milestones, comments, or item fields.
4. Use GitHub metadata only. Do not read raw logs or secret-bearing surfaces.
5. Keep one work item mapped to one owner repo, one local path, one owner role, one validation target, and one blocker state.
6. Split items when repo boundary, local path, owner role, validation target, deployment boundary, or secret-custody boundary differs.
7. Mark planning PASS only after required fields, views, issue links, owner roles, validation targets, and blocker states are complete.
8. Send development execution to `projectdevsubagents`; do not dispatch L2/L3 workers from this skill.

## Planning PASS packet

Return this shape when the planning slice is ready:

```json
{
  "schema": "bears.github-project-planning.pass",
  "version": "1",
  "status": "pass",
  "project": {
    "owner": "BearsCLOUD",
    "number": 20,
    "url": "https://github.com/users/BearsCLOUD/projects/20",
    "creation_authorized": false,
    "metadata_mutation_authorized": false
  },
  "fields": ["Status", "Priority", "Owner repo", "Local path", "Owner role", "Issue type", "Workstream", "Blocker status", "Validation target"],
  "views": ["Backlog", "Ready", "Blocked", "In progress", "Review", "Done", "Roadmap", "Repo boundary"],
  "items_ready": 0,
  "items_blocked": 0,
  "handoff_skill": "projectdevsubagents",
  "handoff_inputs": ["project_url", "project_number", "owner_repos", "issue_ids", "field_ids", "route_audit_targets"],
  "blockers": []
}
```

Use `status: "review"` when planning is not ready or metadata mutation lacks authorization.
