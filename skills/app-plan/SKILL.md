---
name: app-plan
description: Replace one wave's graph-linked sequential task plan through MCP. Use after app-functional-graph.
---

# App Plan

## Preconditions

- Keep plan writes with the wave owner.
- Require `project_ref`, `wave_id`, `owner_session_ref`, revision, and logical digest.
- Leave the phase `pending` when either workflow MCP server is unavailable.
- Never write a JSON ledger fallback.

## Method

1. Call `project_status`, `workflow_state`, `graph_search`, `dependency_slice`, `impact_analysis`, and `graph_diagnostics`.
2. Define repository-bounded tasks with stable refs, local source refs, contiguous sequence numbers, and explicit dependencies.
3. Keep implementation execution sequential even when dependency batches expose independent work.
4. Call `plan_replace` once for the complete active plan with current CAS and owner fields.
5. Call `topological_plan`, write `waves/<wave_id>/plan.md`, and call `phase_record` once.

## Completion

- Return task order, dependency batches, new revision and digest, Markdown artifact ref, process-record ref, and next phase.
- Never preserve a stale task implicitly, dispatch workers, emit `audited`, push, merge, or deploy.
