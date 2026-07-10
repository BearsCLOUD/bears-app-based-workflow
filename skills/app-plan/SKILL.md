---
name: app-plan
description: Detect unbuilt Bears app functionality and create graph-linked wave plans and ledger tasks. Use when Codex must decompose specified waves into dependencies, ready tasks, owner roles, target paths, and app-dev handoff payloads.
---

# App Plan

## Delegation first

For work already classified `DELEGATED`, act as the solo L2 analogue: decompose the stage payload below, then follow `$subagents` for each concrete L3 assignment before any data access. `DIRECT` work never enters `$subagents`.

## Stage payload

- `graph-ready` or `needs-plan` handoff with app id, wave ids, and artifact refs.
- Functional graph ref and revision plus task-ledger ref.
- Delegated implemented-state facts classified by requirement when available.
- Target wave ids and known dependencies.

## L3 output

The selected L3 writes `waves/<wave-id>/plan.md` and creates or updates only executable `tasks` in `docs/app-task-ledger.v1.json`. It never writes `docs/app-functional-graph.v1.json` or ledger `graph_anchors`.

For each specified requirement it records graph revision and coverage plus `built`, `partial`, `missing`, or `drifted` implementation state. It creates or updates canonical executable ledger tasks for `partial`, `missing`, or `drifted` behavior. Each task carries every field defined by `app-functional-graph`, including the complete artifact refs and `ledger_update_contract` required by `app-dev`.

Return one `app-stage-handoff.v1` status:

- `ready`: at least one canonical task has closed decisions, closed dependencies, valid current graph refs, and status `ready`; include its complete compact task record and use `next_stage: app-dev`;
- `waiting`: tasks exist but none is ready; include dependency refs and keep `next_stage: app-plan`;
- `no-work`: all specified behavior is built and no executable task remains; use `next_stage: app-analyze`;
- `needs-graph`: behavior is unmapped, graph refs are stale, or graph meaning drifted; include requirement, graph-gap, evidence, and current artifact refs and use `next_stage: app-functional-graph`;
- `needs-spec`: a product decision or required behavior is incomplete; include exact decision and requirement refs and use `next_stage: app-specify`.

## Mutation boundary

This stage may create and update task planning fields and set only `planned`, `blocked_by_decision`, `blocked_by_dependency`, or `ready`. It must not overwrite `in_progress`, `done`, or `failed` execution state. It never changes graph meaning, graph revision, or graph anchors.

## Stage rules

- Create no task for an unresolved product decision.
- Create no task without `functionality_refs` and `graph_node_refs`.
- Keep each task inside one repo boundary and one exact target set.
- Mark decision-dependent work `blocked_by_decision` and route it to `app-specify`.
- Mark work `ready` only when its decisions are closed and every dependency is `done` or otherwise proven closed.
- Return `needs-graph` instead of repairing an unmapped or drifted graph.
- Route ready ledger work to `app-dev`.
- Use `instruction-hardening` only as a separate delegated pass.
