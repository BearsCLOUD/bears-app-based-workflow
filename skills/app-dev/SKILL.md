---
name: app-dev
description: Execute planned app tasks sequentially with exact change digests, review, and correction records. Use after app-plan.
---

# App Dev

## Ownership

- Keep the stage and every workflow write with the `DIRECT` primary or persistent `repo-orchestrator`.
- Dispatch optional L3 work only through the runtime subagent dispatch: `$subagents` in Codex, or the Task tool with the plugin agents `app-worker` and `app-reviewer` in Claude Code.
- Keep one current task and finish its review cycle before starting the next sequence item.
- Leave the phase `pending` when either workflow MCP server is unavailable.
- Never use a JSON workflow-state fallback.

## Method

1. Call `project_status`, `workflow_state`, and `topological_plan` with the bound project and wave.
2. Implement the first dependency-ready sequence item directly or through one bounded `app-worker` assignment.
3. Call `task_record_change` with exact changed local file refs and the current CAS fields.
4. Review the returned change digest directly or through one read-only `app-reviewer`.
5. Call `review_record`; record `changes_requested` findings before any correction.
6. Call `correction_record` with exact evidence, then record a new change digest and a new approval.
7. Repeat sequentially, write `waves/<wave_id>/dev.md`, and call `phase_record` once.

## Completion

- Require every active task to be `done`, latest approval to match its current change digest, and every correction to be closed.
- Return task, review, correction, commit, artifact, process-record, revision, and digest refs.
- Never let an L3 write workflow state, self-approve, push, merge, or deploy.
