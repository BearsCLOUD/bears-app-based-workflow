---
name: subagents
description: Dispatch one bounded L3 assignment to app-worker, app-reviewer, or app-analyst through Claude Code subagents. Use only when the wave owner chooses delegation.
---

# Subagents

## Purpose

Claude is the sole orchestrator and the sole writer of a wave. Delegation exists
to buy isolation and parallelism for work that can be stated as a single bounded
result, not to hand off ownership. Every subagent is a leaf: it reads or edits
what it was pointed at, returns facts, and ends.

## Dispatch

Delegate through the Task tool with one of three roles.

- `app-worker` for one current task. No workflow MCP access at all.
- `app-reviewer` for one immutable change digest. Reader tools limited to
  exactly `project_status`, `graph_open`, `dependency_slice`,
  `impact_analysis`, and `workflow_state`.
- `app-analyst` for one semantic snapshot slice. All reader tools except
  `project_list`.

Multi-repository work is not a lane hierarchy. Open a separate Claude session
per repository; each session is the wave owner for its own repository.

## Bounding an assignment

An assignment names the snapshot it was cut against and the single result it
must produce. Include `project_ref`, `wave_id`, the owner session ref, the
revision and logical digest, the target refs, and the one expected output. Give
the child the context it needs to do the work and nothing more; a child that has
to guess which wave it is in will guess wrong.

Require the child to return bounded result facts and exact evidence refs, not
narration.

## Recording the result

Child work never reserves a database revision, so the snapshot the child was
given may be stale by the time it answers. Re-read `project_status` before
recording anything a child produced, and record it yourself.

Reject a result outright when the project, wave, snapshot, assignment, role, or
target identity has drifted from what was dispatched. A drifted result is
re-dispatched, not repaired.

## Boundaries

- The wave owner is the sole writer. Only the owner calls
  `app-workflow-maintainer`.
- No L3 role touches the maintainer server, chooses a phase, mutates workflow
  state, pushes, merges, or deploys.
- One assignment produces one result. Widening scope mid-assignment is a new
  assignment.
