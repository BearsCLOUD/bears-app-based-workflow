---
name: subagents
description: Dispatch one bounded L3 app assignment to app-worker, app-reviewer, or app-analyst. Use only when the wave owner chooses delegation.
---

# Subagents

## Profiles

- Use `app-worker` for one current task and no workflow MCP access.
- Use `app-reviewer` for one immutable change digest and its limited read-only MCP set.
- Use `app-analyst` for one semantic snapshot slice and its limited read-only MCP set.

## Dispatch

1. Keep route selection, CAS fields, and every maintainer call with the `DIRECT` primary or persistent `repo-orchestrator`.
2. Bind one assignment to `project_ref`, `wave_id`, owner-session ref, revision, logical digest, target refs, and one expected result.
3. Start the installed profile with no inherited chat context when the collaboration transport supports that boundary.
4. Require the child to return only bounded result facts and exact evidence refs.
5. Re-read `project_status` before recording the result because child work never reserves the database revision.

## Boundaries

- Never let L1 `workflow-orchestrator` dispatch L3 work.
- Never let an L3 choose a phase, call `app-workflow-maintainer`, mutate workflow state, push, merge, or deploy.
- Reject a result when project, wave, snapshot, assignment, profile, or target identity drifts.
