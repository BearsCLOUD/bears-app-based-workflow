---
name: app-dev
description: Orchestrate fixed L1 and L2 app-development lanes, then dispatch concrete L3 assignments. Use when graph-linked ledger work is dependency-ready and bounded by exact targets.
---

# App Dev

## Ownership boundary

`app-dev` owns fixed L1-to-L2 orchestration, ready-task partitioning, L2 decomposition, lane isolation, and wave closeout. Each L2 follows `$subagents` as the instruction procedure for selecting and dispatching L3 agents for its concrete assignments. `$subagents` is not a task recipient or runtime.

L1 and L2 coordinate from compact packets. They do not access files, logs, terminal, Git, scripts, MCP, runtime, or network state.

## Required input

Start from compact ready-work results produced by `app-plan` or `app-analyze`. Each candidate task needs known refs for:

- `task_id` and `wave_id`;
- `functionality_refs` and `graph_node_refs`;
- `target_paths` and allowed files;
- dependencies and ledger status;
- definition of done and proof requirement;
- ledger update contract;
- constitution, research, specification, plan, and existing autoCI evidence.

## Fixed L1 orchestration

The parent activating `app-dev` takes the fixed L1 role; it does not create an L1 subagent.

1. Start one persistent `bears-role-selector-helper` under the `$subagents` selector lifecycle and keep its handle through wave closeout.
2. Accept only tasks reported ready with closed decisions, closed dependencies, and valid graph refs.
3. If readiness facts are absent, open one read-only L2 discovery lane with exact refs; that L2 follows `$subagents` for the concrete evidence assignment.
4. Partition known ready tasks into L2 lanes with non-overlapping repo paths, runtime targets, and mutable state.
5. Start each L2 with exact task ids, target bounds, dependencies, completion criteria, and the shared selector handle. Keep capacity for its L3; otherwise return `DELEGATION_BLOCKED` for that lane.
6. Combine compact L2 results, route decision or planning gaps, and send completed waves to `app-analyze`.

L1 never treats `$subagents` as a recipient for a stage, wave, or lane.

## Fixed L2 orchestration

1. Own one lane or wave partition supplied by L1; do not change its task set or bounds.
2. Decompose each lane task into concrete, sequential L3 assignments without expanding its targets or dependencies.
3. For each assignment, follow `$subagents`: send `role-request.v1` to the shared selector, use its `role-selection.v1`, build `dispatch-packet.v1`, manage the L3 lifecycle, and accept `result-packet.v1`.
4. Run at most one L3 helper, worker, or critic at a time. A helper precedes its worker; a critic follows it.
5. Use separate assignments for implementation, Git, and existing autoCI evidence. Keep a selector-chosen helper, primary agent, and critic in their shared assignment lifecycle; use a separate critic assignment only when critique is the sole outcome.
6. Return completed behavior, exact changed-file refs, ledger transition, unresolved risk, evidence refs, and the next handoff to L1.

L2 never starts L4 and never executes the assignment itself.

## Solo parent

A solo parent with one bounded task acts as the L2 analogue. It decomposes that task into concrete L3 assignments, creates or reuses one selector, and follows `$subagents` for each assignment. It does not create an L1 or an L2 subagent.

## Stage rules

- Do not start a task with missing graph refs, open decisions, or open dependencies.
- Do not invent implementation work outside the ledger.
- Do not overlap mutable target paths, runtime targets, or state across lanes.
- Keep every L3 assignment inside one exact task and target set.
- Return product decision gaps to `app-specify` and planning gaps to `app-plan`.
- Update ledger state only through a concrete L3 assignment, then hand the wave to `app-analyze`.
