---
name: app-dev
description: Orchestrate fixed L1 and L2 app-development lanes, then dispatch concrete L3 assignments. Use when graph-linked ledger work is dependency-ready and bounded by exact targets.
---

# App Dev

## Ownership boundary

For work already classified `DELEGATED`, `app-dev` owns fixed `workflow-orchestrator` L1 to `domain-lane-orchestrator` L2 orchestration, ready-task partitioning, L2 decomposition, lane isolation, and wave closeout. Each L2 follows `$subagents` for deterministic L3 selection and assignment-bounded dispatch. `$subagents` is not a task recipient or runtime. `DIRECT` work never enters this procedure.

L1 and L2 coordinate from compact packets. They do not access files, logs, terminal, Git, scripts, MCP, runtime, or network state.

## Required input

Start from canonical `app-stage-handoff.v1` status `plan-ready` produced by `app-plan` or status `ready` produced by `app-analyze` re-entry. Each carries every common field defined by `app-functional-graph` plus `task_records`, each a complete canonical executable ledger task. Each candidate task needs:

- `task_id`, `wave_id`, `requirement_refs`, `functionality_refs`, and `graph_node_refs`;
- `target_paths`, `allowed_files`, `owner_role`, and `lane`;
- `depends_on`, closed `decision_state`, and `ready` status;
- `definition_of_done`, `proof_requirement`, and `ledger_update_contract`;
- constitution, research, specification, and plan refs plus existing autoCI evidence refs.

## Fixed L1 orchestration

The parent activating `app-dev` takes fixed `workflow-orchestrator` L1; it does not create an L1 subagent.

1. Accept only tasks reported ready with closed decisions, closed dependencies, and valid graph refs.
2. If readiness facts are absent, open one read-only `domain-lane-orchestrator` L2 discovery lane with exact refs; that L2 follows `$subagents` for the concrete evidence assignment.
3. Partition known ready tasks into non-overlapping `domain-lane-orchestrator` L2 lanes by repo paths, runtime targets, and mutable state.
4. Start each L2 with exact task ids, workstream ids, target bounds, dependencies, completion criteria, and capacity for its L3; otherwise return `DELEGATION_BLOCKED` for that lane.
5. Combine compact L2 results, route decision or planning gaps, and send completed waves to `app-analyze`.

L1 never treats `$subagents` as a recipient for a stage, wave, or lane.

## Fixed L2 orchestration

1. Own one lane or wave partition supplied by L1; do not change its task set or bounds.
2. Decompose each lane task into concrete, sequential L3 assignments without expanding its targets or dependencies.
3. For each assignment, apply the ordered `$subagents` rules, record `selection_basis` and `capability_boundary`, build `dispatch-packet.v2`, start one fresh matching L3, and accept `result-packet.v1`.
4. Run at most one L3 at a time. Dispatch evidence, mutation, or review separately only when the task requires that distinct outcome; never add an automatic helper or critic.
5. Package each L3 assignment by its distinct deliverable. Never create assignments for word counts, predicates, waits, cachebuster-only work, or intermediate Git actions.
6. Use only the canonical ordered role rules and capability boundaries in `$subagents`; do not maintain or infer a lane-local routing summary.
7. Keep every agent reference within one `assignment_id`. A follow-up is allowed only while outcome, role, target scope, and capability boundary remain unchanged; otherwise select and start a new L3.
8. Let each write-capable L3 own its cohesive patch, task-owned diff inspection, exact staging, and one local commit under `$subagents`. Do not create an intermediate or final Git-closeout assignment.
9. Return completed behavior, exact changed-file refs, ledger transition, unresolved risk, evidence refs, and the next handoff to L1.

L2 never starts L4, never redecomposes an L3 assignment inside L3, and never executes the assignment itself.

## Solo parent

A solo parent with one bounded delegated task acts as the L2 analogue. It decomposes that task into concrete L3 assignments and independently applies deterministic `$subagents` selection and `dispatch-packet.v2` for each assignment. It does not create an L1 or an L2 subagent.

## Stage rules

- Do not start a task with missing graph refs, open decisions, or open dependencies.
- Do not invent implementation work outside the ledger.
- Do not overlap mutable target paths, runtime targets, or state across lanes.
- Keep every L3 assignment inside one exact task and target set.
- Return product decision gaps to `app-specify` and planning gaps to `app-plan`.
- Never write the functional graph, graph anchors, wave plan, or analysis artifact.
- Update only ledger fields named by the task's `ledger_update_contract`, through a concrete L3 assignment. Use only `ready -> in_progress -> done|failed`.
- Return a canonical `app-stage-handoff.v1` with every common field and the fields for its status: `implemented` adds `completed_task_refs` and `result_refs` and targets `app-analyze`; `needs-plan` adds `source_handoff_ref`, `ledger_coverage_refs`, and `implementation_state_by_requirement` and targets `app-plan`; `needs-spec` adds `source_handoff_ref` and `question_refs`, populates common decision and requirement refs, and targets `app-specify`; `blocked` adds `blocker_refs` and `operator_action_refs` and targets `none`. Use `blocked` only for access, credential, unavailable-source, or explicit operator stops.
