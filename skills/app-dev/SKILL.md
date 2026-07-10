---
name: app-dev
description: Orchestrate fixed L1 and L2 app-development lanes, then dispatch concrete L3 assignments. Use when graph-linked ledger work is dependency-ready and bounded by exact targets.
---

# App Dev

## Ownership boundary

For work already classified `DELEGATED`, `app-dev` owns fixed L1-to-L2 orchestration, ready-task partitioning, L2 decomposition, lane isolation, and wave closeout. Each L2 follows `$subagents` as the instruction procedure for selecting and dispatching L3 agents for its concrete assignments. `$subagents` is not a task recipient or runtime. `DIRECT` work never enters this procedure.

L1 and L2 coordinate from compact packets. They do not access files, logs, terminal, Git, scripts, MCP, runtime, or network state.

## Required input

Start from canonical `app-stage-handoff.v1` status `plan-ready` produced by `app-plan` or status `ready` produced by `app-analyze` re-entry. Each carries every common field defined by `app-functional-graph` plus `task_records`, each a complete canonical executable ledger task. Each candidate task needs:

- `task_id`, `wave_id`, `requirement_refs`, `functionality_refs`, and `graph_node_refs`;
- `target_paths`, `allowed_files`, `owner_role`, and `lane`;
- `depends_on`, closed `decision_state`, and `ready` status;
- `definition_of_done`, `proof_requirement`, and `ledger_update_contract`;
- constitution, research, specification, and plan refs plus existing autoCI evidence refs.

## Fixed L1 orchestration

The parent activating `app-dev` takes the fixed L1 role; it does not create an L1 subagent.

1. Start one persistent `role-selector` under the `$subagents` selector lifecycle and keep its agent reference through wave closeout.
2. Accept only tasks reported ready with closed decisions, closed dependencies, and valid graph refs.
3. If readiness facts are absent, open one read-only L2 discovery lane with exact refs; that L2 follows `$subagents` for the concrete evidence assignment.
4. Partition known ready tasks into L2 lanes with non-overlapping repo paths, runtime targets, and mutable state.
5. Start each L2 with exact task ids, target bounds, dependencies, completion criteria, and the shared selector reference. Keep capacity for its L3; otherwise return `DELEGATION_BLOCKED` for that lane.
6. Combine compact L2 results, route decision or planning gaps, and send completed waves to `app-analyze`.

L1 never treats `$subagents` as a recipient for a stage, wave, or lane.

## Fixed L2 orchestration

1. Own one lane or wave partition supplied by L1; do not change its task set or bounds.
2. Decompose each lane task into concrete, sequential L3 assignments without expanding its targets or dependencies.
3. For each assignment, follow `$subagents`: send `role-request.v1` to the shared selector, use its `role-selection.v1`, build `dispatch-packet.v1`, manage the L3 lifecycle, and accept `result-packet.v1`.
4. Run at most one L3 helper, worker, or critic at a time. A helper precedes its worker; a critic follows it.
5. Package each L3 assignment by exact result to produce. Do not package by word count, predicate count, cachebuster, Git step, or wait step.
6. Use separate assignments only for distinct deliverables; Git closeout remains in the assignment and coherent workstream that produced the result, and Git, cachebuster, or wait operations must never become their own assignment or workstream. Reuse the same selected role through follow-up assignments in the same coherent workstream unless terminal failure, changed competence, or a true scope split requires replacement.
7. Use at most one critic for one combined diff or acceptance surface. When that critic requests fixes, the same critic re-reviews the follow-up result unless one of the allowed replacement conditions applies.
8. Return completed behavior, exact changed-file refs, ledger transition, unresolved risk, evidence refs, and the next handoff to L1.

L2 never starts L4, never redecomposes an L3 assignment inside L3, and never executes the assignment itself.

## Solo parent

A solo parent with one bounded task acts as the L2 analogue. It decomposes that task into concrete L3 assignments, creates or reuses one selector, and follows `$subagents` for each assignment. It does not create an L1 or an L2 subagent.

## Stage rules

- Do not start a task with missing graph refs, open decisions, or open dependencies.
- Do not invent implementation work outside the ledger.
- Do not overlap mutable target paths, runtime targets, or state across lanes.
- Keep every L3 assignment inside one exact task and target set.
- Return product decision gaps to `app-specify` and planning gaps to `app-plan`.
- Never write the functional graph, graph anchors, wave plan, or analysis artifact.
- Update only ledger fields named by the task's `ledger_update_contract`, through a concrete L3 assignment. Use only `ready -> in_progress -> done|failed`.
- Return a canonical `app-stage-handoff.v1` with every common field and the fields for its status: `implemented` adds `completed_task_refs` and `result_refs` and targets `app-analyze`; `needs-plan` adds `source_handoff_ref`, `ledger_coverage_refs`, and `implementation_state_by_requirement` and targets `app-plan`; `needs-spec` adds `source_handoff_ref` and `question_refs`, populates common decision and requirement refs, and targets `app-specify`; `blocked` adds `blocker_refs` and `operator_action_refs` and targets `none`. Use `blocked` only for access, credential, unavailable-source, or explicit operator stops.
