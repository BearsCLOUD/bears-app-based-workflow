---
name: github-project-planning
description: "Use for non-app GitHub Project planning and administration: creating or selecting Projects, defining field models, roadmap views, issue and sub-issue metadata, item hygiene, and planning PASS packets. Do not use for app workflow planning, Apps Project #20 decomposition, app-dev handoff, product implementation, runtime/deploy work, repository settings, secrets, or raw logs."
---

# GitHub Project Planning

Use this skill to plan and govern non-app GitHub Projects and linked Issues as an independent GitHub Project workflow surface. App workflow planning belongs to `$app-plan`.

## Scope

In scope:

- select an existing GitHub Project or prepare an operator-authorized Project creation packet;
- define Project fields, views, roadmap slices, issue types, labels, milestones, and item hygiene rules;
- create a planning PASS packet with Project URL/number, fields, views, owner repos, local paths, owner roles, proof targets, and mutation authorization state;
- plan Issues, sub-issues, draft items, comments, labels, and milestones;

Out of scope:

- app workflow planning, Apps Project #20 app decomposition, app lane mapping, or `$app-dev` handoff;
- product, platform, infra, runtime, deploy, MCP, connector, or provider implementation;
- L2/L3 development dispatch from existing Project state;
- direct mutation of repository settings, branch protection, environments, webhooks, Actions settings, secrets, variables, or production state;
- reading raw logs, raw CI logs, raw chats, shell history, credential files, production data, `.env` values, or secret values.


## Required references

Load only the references needed for the current planning task:

- `references/planning-flow.md` for intake, Project setup, fields, views, item fill, and PASS;
- `references/field-model.md` for required field definitions and allowed values;
- `references/item-and-issue-rules.md` for Issue, sub-issue, draft item, comment, label, and milestone decisions;
- `references/views-and-roadmap.md` for standard views and roadmap slicing;

## Operating rules

1. Start from the nearest `AGENTS.md`, the owning repository boundary, and explicit operator intent.
2. Use the owning repo or operator packet to identify the correct owner role before planning work items.
3. Treat GitHub Project or Issue mutations as external metadata changes. Require an explicit operator authorization packet before creating or editing Projects, fields, views, Issues, sub-issues, labels, milestones, comments, or item fields.
4. Use GitHub metadata only. Do not read raw logs or secret-bearing surfaces.
5. Keep one work item mapped to one owner repo, one local path, one owner role, one proof target, and one blocker state.
6. Split items when repo boundary, local path, owner role, proof target, deployment boundary, or secret-custody boundary differs.
7. Mark planning PASS only after required fields, views, issue links, owner roles, proof targets, and blocker states are complete.
8. Do not dispatch implementation workers from this skill; return Project and Issue metadata that a non-app workflow can consume.
9. If the target is `/srv/bears/dev/app`, `BearsCLOUD/apps`, Apps Project #20, app lane planning, or `$app-dev`, stop and route to `$app-plan`.

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
  "fields": ["Status", "Priority", "Owner repo", "Local path", "Owner role", "Issue type", "Workstream", "Blocker status", "Proof target"],
  "views": ["Backlog", "Ready", "Blocked", "In progress", "Review", "Done", "Roadmap", "Repo boundary"],
  "items_ready": 0,
  "items_blocked": 0,
  "consumer_inputs": ["project_url", "project_number", "owner_repos", "issue_ids", "field_ids"],
  "blockers": []
}
```

Use `status: "review"` when planning is not ready or metadata mutation lacks authorization.
