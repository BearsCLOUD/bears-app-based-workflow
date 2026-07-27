---
name: app-plan
description: Replace one wave's graph-linked task plan through MCP. Use after app-functional-graph.
---

# App Plan

## Purpose

Convert the functional graph into a wave task plan: repository-bounded tasks,
each linked to the graph records it realizes and to the local sources it
touches.

## Done means

- The plan covers the work represented by the functional graph.
- Each task has a checkable result, a repository boundary, graph anchors, and
  local source references.
- `waves/<wave_id>/plan.md` explains the task boundaries, dependencies, and
  rationale.

## How to think about this phase

- A task is a unit of change with a checkable result inside this repository. If
  its completion cannot be judged from the diff plus a review, it is too large
  or not a task.
- Dependencies encode what must be true before a task can start, not a
  preferred order of convenience. A cycle signals that two tasks are one task
  or that a boundary is wrong.
- A good breakdown makes each task small enough to review, specific enough to
  implement, and anchored to the graph and local sources it realizes.
- Use `dependency_slice` and `impact_analysis` to size the blast radius. Split
  a task when its impact set is wider than its slice.
- Identify independent work without turning the plan into an execution rule.

## Tools and artifact

- Reads: `project_status`, `workflow_state`, `graph_search`,
  `dependency_slice`, `impact_analysis`, `graph_diagnostics`,
  `topological_plan`.
- Records: `plan_replace`, `phase_record`.
- Writes exactly one artifact: `waves/<wave_id>/plan.md`.

The orchestrator workflow and the maintainer server own `plan_replace`
mechanics. The orchestrator workflow owns execution order, phase gates,
retries, worker dispatch, and the decision to advance to app-dev.

Subagents never touch the maintainer server. There is no JSON ledger fallback;
if the workflow servers are unavailable, the phase does not proceed.

Never emit `audited`, push, merge, or deploy.
