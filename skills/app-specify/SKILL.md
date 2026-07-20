---
name: app-specify
description: Turn charter and evidence into decision-complete behavior and acceptance criteria, without choosing an implementation. Phase 3 of the seven-phase workflow.
---

# App Specify

## Purpose

State what the system must do, precisely enough that a reader can tell whether
a given implementation satisfies it - and precisely enough that the functional
graph and plan phases have nothing left to guess about behavior.

## Done means

- Actors, states, inputs, outputs, failure modes, and compatibility
  expectations are settled.
- Every requirement has acceptance criteria that can be checked as true or
  false.
- `waves/<wave_id>/spec.md` exists for this wave, cites local source refs, and
  lists the decisions that remain unresolved.

## How to think about this phase

- Behavior, not mechanism. Name the observable contract; leave modules, data
  structures, and sequencing to app-plan.
- Decision-complete means no implied choices. If a reader would have to invent
  a rule to build it, the rule belongs in the spec.
- Failure paths deserve the same detail as success paths, including what the
  system does with bad input and partial state.
- Check the blast radius before writing: `graph_search` for constraints
  already established, `impact_analysis` for behavior this wave would disturb.
  Existing behavior you break is a requirement you owe.
- Where research recorded a conflict, resolve it here and say why - or record
  it as unresolved and say what would settle it.
- Do not mutate graph entities and do not create plan tasks.

## Tools and artifact

- Reads: `project_status`, `workflow_state`, `graph_search`, `impact_analysis`.
- Records: `phase_record`.
- Writes exactly one artifact: `waves/<wave_id>/spec.md`.

Workflow state lives only in the MCP servers; never reconstruct it from JSON
artifacts.

## Left to the orchestrator

Phase ordering, gate decisions, retries, and outcome selection
(`completed`, `skipped-current`, `blocked`, or `pending` when a workflow MCP
server is unavailable) belong to the wave owner. Only
the wave owner performs mutations, and every mutation carries `request_id`,
`expected_revision`, and `expected_logical_digest` read fresh from
`project_status`. Subagents never call the maintainer server.

Never emit `audited`, push, merge, or deploy.
