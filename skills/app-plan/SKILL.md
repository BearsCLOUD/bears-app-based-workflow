---
name: app-plan
description: Replace one wave's graph-linked sequential task plan through MCP. Use after app-functional-graph.
---

# App Plan

## Purpose

Convert the functional graph into the wave's task plan: an ordered set of
repository-bounded tasks, each linked to the graph records it realizes and to the
local sources it touches.

Done means the active plan is a complete replacement for the wave, sequences are
contiguous, dependencies are acyclic, `topological_plan` returns the order the
work will actually be done in, and `waves/<wave_id>/plan.md` states that order and
the reasoning behind it.

## How to think about this phase

- A task is a unit of change with a checkable result inside this repository.
  If its completion cannot be judged from the diff plus a review, it is either
  too large or not really a task.
- Dependencies encode what must be true before a task can start, not a preferred
  order of convenience. `plan_replace` requires an acyclic graph, so a cycle is a
  signal that two tasks are one task or that a boundary is drawn wrong.
- `plan_replace` replaces the whole active plan atomically. Nothing survives
  implicitly: a task omitted from the payload is gone. Carry forward deliberately.
- Sequence numbers are contiguous and execution is sequential even when the
  dependency batches expose work that could run in parallel. Use the batches to
  explain the shape of the plan, not to authorize concurrency.
- Use `dependency_slice` and `impact_analysis` to size the blast radius before
  fixing an order; a task whose impact set is much wider than its slice usually
  wants to be split.
- A good artifact tells a reader what will be built, in what order, why that
  order, and where each task is anchored in the graph.

## Tools and artifact

- Reads: `project_status`, `workflow_state`, `graph_search`, `dependency_slice`,
  `impact_analysis`, `graph_diagnostics`, `topological_plan`.
- Records: `plan_replace`, then `phase_record`.
- Writes exactly one artifact: `waves/<wave_id>/plan.md`.

Mutations are performed only by the wave owner and carry `request_id`,
`expected_revision`, and `expected_logical_digest` read fresh from `project_status`
on the reader server. Subagents never touch the maintainer server. There is no
JSON ledger fallback; if the workflow servers are unavailable, the phase does not
proceed.

## Deferred to the orchestrator

Phase ordering, entry and exit gates, retries after a CAS conflict, dispatch of
any worker, and the decision to advance to app-dev belong to the orchestrator,
not to this skill.
