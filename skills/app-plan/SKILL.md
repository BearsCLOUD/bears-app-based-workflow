---
name: app-plan
description: Create repo-scoped graph-linked implementation and remediation waves. Use when specified behavior or immutable review findings need canonical ledger tasks and an app-dev handoff.
---

# App Plan

## Delegation first

For work already classified `DELEGATED`, act as the solo L2 analogue: decompose the stage payload below, then follow `$subagents` for each concrete L3 assignment before any data access. `DIRECT` work never enters `$subagents`.

## Stage payload

- Every stage-generated input uses the canonical `app-stage-handoff.v1` defined by `app-functional-graph` and carries all common fields.
- `graph-ready` from `app-functional-graph` additionally carries `graph_ref`, `functionality_refs`, `graph_node_refs`, `coverage_refs`, `replacement_refs`, and `graph_anchor_refs`.
- `needs-plan` from `app-dev` or `app-analyze` additionally carries `source_handoff_ref`, `ledger_coverage_refs`, and `implementation_state_by_requirement`.
- `waiting` resume from `app-plan` additionally carries `source_handoff_ref`, `blocked_task_refs`, and `dependency_state_evidence_refs`; `app-plan` owns dependency-state reevaluation and the resume decision.
- A repo L2 may invoke planning at `remediation-anchor.v1` with `repo_ref`, exact repo cwd, the immutable anchor snapshot, failed task refs, one primary review ref, and only deterministically justified specialist review refs. Those failed-task and review refs are the complete remediation source; unrelated findings or later queue admissions are outside that planning assignment.

## L3 output

The selected L3 writes `waves/<wave-id>/plan.md` and creates or updates only executable `tasks` in `docs/app-task-ledger.v1.json`. It never writes `docs/app-functional-graph.v1.json` or ledger `graph_anchors`.

For each specified requirement it records graph revision and coverage plus `built`, `partial`, `missing`, or `drifted` implementation state. It creates or updates canonical executable ledger tasks for `partial`, `missing`, or `drifted` behavior. Each task carries every field defined by `app-functional-graph`, including the complete artifact refs and `ledger_update_contract` required by `app-dev`.

Partition ordinary work by `repo_ref` before assigning `batch_id` or `wave_id`. One batch and one wave contain tasks from exactly one repository. Preserve deterministic `queue_sequence` within each repo wave, and supply the exact repo cwd plus each task's `target_paths` and `allowed_files`; never return a mixed-repo task group.

At `remediation-anchor.v1`, create a new repo-scoped remediation wave, a new batch, and new task ids. Every created task has `task_kind: remediation` and `source_review_refs` containing the primary review ref plus any justified specialist review refs. Trace the failed task refs as remediation sources, but never reopen, renumber, overwrite, or otherwise mutate the original terminal `done|failed` tasks. Preserve this queue order: independent tasks in the anchor snapshot first, the new remediation wave next, and tasks admitted after the anchor last.

Return one canonical `app-stage-handoff.v1` with every common field and the fields for its status:

- `plan-ready`: at least one canonical task has closed decisions, closed dependencies, valid current graph refs, and ledger status `ready`; emit one repo-scoped handoff per `repo_ref`, add only same-repo complete `task_records`, supply their repo cwd and exact targets for `app-task-dispatch.v1`, and target `app-dev`;
- `waiting`: tasks exist but none is ready; add `source_handoff_ref`, `blocked_task_refs`, and `dependency_state_evidence_refs`, populate common dependency refs, and target `app-plan`;
- `no-work`: all specified behavior is built and no executable task remains; add `plan_refs` and target `app-analyze`;
- `needs-graph`: behavior is unmapped, graph refs are stale, or graph meaning drifted; add `source_handoff_ref`, `graph_ref`, and `affected_graph_refs`, populate common requirement, gap, evidence, artifact, and implemented-state fields, and target `app-functional-graph`;
- `needs-spec`: a product decision or required behavior is incomplete; add `source_handoff_ref` and `question_refs`, populate common decision, requirement, gap, artifact, and evidence fields, and target `app-specify`.

## Mutation boundary

This stage may create and update task planning fields and set only `planned`, `blocked_by_decision`, `blocked_by_dependency`, or `ready`. It must not overwrite `in_progress`, `done`, or `failed` execution state. Remediation always uses new tasks rather than changing a terminal task. This stage never changes graph meaning, graph revision, or graph anchors.

## Stage rules

- Create no task for an unresolved product decision.
- Create no task without `functionality_refs` and `graph_node_refs`.
- Keep each task, batch, wave, and `plan-ready` handoff inside one repo boundary and one exact target set.
- Mark decision-dependent work `blocked_by_decision` and route it to `app-specify`.
- Mark work `ready` only when its decisions are closed and every dependency is `done` or otherwise proven closed.
- Return `needs-graph` instead of repairing an unmapped or drifted graph.
- Route ready ledger work to `app-dev` as separate repo-scoped handoffs; never create a generic cross-repo merge.
- Use `instruction-hardening` only as a separate delegated pass.
