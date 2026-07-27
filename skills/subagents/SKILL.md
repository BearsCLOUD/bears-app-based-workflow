---
name: subagents
description: Use the app-worker, app-reviewer, or app-analyst role entry points when the orchestrator workflow chooses delegation.
---

# Subagents

This skill is an entry point for the three app subagent roles. The typed source
for role definitions, authority, tool access, and role boundaries is
`roles/roles.json`.

## Roles

- `app-worker` is a mutation role for one bounded app task. It may change only
  assigned targets and may not call either workflow server or change workflow
  state.
- `app-reviewer` is a read-only role for reviewing one immutable task change
  digest. It may use its enabled read-only workflow tools and may not edit
  files or record workflow state.
- `app-analyst` is a read-only role for comparing one exact workflow snapshot
  slice. It may use its enabled read-only workflow tools and may not edit
  artifacts or record analysis or audit state.

The wave owner remains the sole writer and the only role authorized to call
`app-workflow-maintainer`. No listed subagent chooses a phase, delegates,
commits, pushes, merges, or deploys.

## Orchestrator ownership

The orchestrator workflow owns dispatch decisions, assignment context, result
handling, and process recording. This entry point does not prescribe those
mechanics.
