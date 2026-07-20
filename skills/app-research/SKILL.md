---
name: app-research
description: Reconcile primary evidence for one registered app wave and separate fact from inference. Phase 2 of the seven-phase workflow.
---

# App Research

## Purpose

Resolve the questions the constitution left open by reading primary sources,
and record what is actually known before anyone specifies behavior. Research
produces evidence, not decisions.

## Done means

- The open questions from the charter are answered, or explicitly recorded as
  still unanswered with the reason.
- `waves/<wave_id>/research.md` exists for this wave and cites local source
  refs (files, symbols, graph entities) for every claim.

## How to think about this phase

- Keep four categories apart: observed facts, inferences drawn from them,
  conflicts between sources, and open questions. Blurring them is the main
  failure mode of this phase.
- Prefer primary sources - the code, the schema, the contract, the log - over
  summaries and over memory.
- A claim without a local ref is not evidence. Cite where it came from.
- Record conflicts rather than silently picking a winner; choosing is the job
  of app-specify.
- Read the existing graph before searching the tree: `graph_search` and
  `graph_open` show what earlier waves already established.
- Do not decide product behavior here, and do not mutate the graph.

## Tools and artifact

- Reads: `project_status`, `workflow_state`, `graph_search`, `graph_open`.
- Records: `phase_record`.
- Writes exactly one artifact: `waves/<wave_id>/research.md`.

Workflow state lives only in the MCP servers; never reconstruct it from JSON
artifacts.

## Left to the orchestrator

Phase ordering, gate decisions, retries, and outcome selection
(`completed`, `skipped-current`, `blocked`, or `pending` when a workflow MCP
server is unavailable) belong to the wave owner - including whether the recorded input digest still matches the source set
closely enough for `skipped-current`. Only the wave owner performs mutations,
and every mutation carries `request_id`, `expected_revision`, and
`expected_logical_digest` read fresh from `project_status`. Subagents never
call the maintainer server.

Never emit `audited`, push, merge, or deploy.
