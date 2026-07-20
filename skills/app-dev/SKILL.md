---
name: app-dev
description: Execute planned app tasks sequentially with exact change digests, review, and correction records. Use after app-plan.
---

# App Dev

## Purpose

Execute the planned tasks and record what actually happened: the exact change each
task produced, the review verdict against that change, and any correction that
closed a finding.

Done means every active task is `done` - that is, it carries an approval at its
current change digest with no open corrections - and `waves/<wave_id>/dev.md`
records what was built, what review found, and how corrections were resolved.

## How to think about this phase

- The record is about the change, not the intent. `task_record_change` takes the
  exact local file refs that changed; a digest recorded against a guess makes the
  later approval meaningless.
- Approval is bound to a digest. Any further edit to a task invalidates its
  approval, so a task returns to review after every correction. Treat that as the
  cost of touching finished work, not as an obstacle to route around.
- A `changes_requested` finding is recorded before the fix, and the correction
  cites exact evidence. The trail must show the problem, the remedy, and the
  re-approval, in that order.
- Work one task at a time, following the planned sequence. Finishing a task means
  its full review cycle is closed, not that the code compiles.
- Implementation may be delegated to one bounded `app-worker` per task, and review
  to a read-only reviewer. The wave owner still writes every workflow record:
  a subagent reports, it never self-approves and never touches the maintainer
  server.
- A good artifact reads as an honest account of the wave: what changed, what was
  contested, and what remains true at the end.

## Tools and artifact

- Reads: `project_status`, `workflow_state`, `topological_plan`.
- Records: `task_record_change`, `review_record`, `correction_record`, then
  `phase_record`.
- Writes exactly one artifact: `waves/<wave_id>/dev.md`.

Mutations are performed only by the wave owner and carry `request_id`,
`expected_revision`, and `expected_logical_digest` read fresh from `project_status`
on the reader server. There is no JSON workflow-state fallback; if the workflow
servers are unavailable, the phase does not proceed.

## Deferred to the orchestrator

Phase ordering, entry and exit gates, retries after a CAS conflict, when to
delegate versus implement directly, and the decision to advance to app-analyze
belong to the orchestrator, not to this skill. This phase never emits `audited`,
and never pushes, merges, or deploys.
