---
name: app-functional-graph
description: Maintain the Bears app functional graph and graph-to-ledger references. Use when Codex must map wave requirements to functionality ids, graph node refs, dependencies, state transitions, API calls, and task ledger anchors.
---

# App Functional Graph

## Delegation first

For work already classified `DELEGATED`, act as the solo L2 analogue: decompose the stage payload below, then follow `$subagents` for each concrete L3 assignment before any data access. `DIRECT` work never enters `$subagents`.

## Stage payload

- `spec-ready` or `needs-graph` handoff with app id and wave ids.
- Constitution, research, and decision-complete specification refs.
- Existing graph and ledger refs.
- Requirement refs and required behavior, dependency, state, API, data, integration, and error coverage.
- Graph-gap refs and implemented-state evidence when returning from `app-plan`.

## L3 output

The selected L3 creates or updates:

- `docs/app-functional-graph.v1.json`;
- graph anchors in `docs/app-task-ledger.v1.json`.

The graph has these required records:

- top level: `schema`, `app_id`, monotonically increasing `revision`, `functions`, `nodes`, `edges`, `coverage`, and `replacements`;
- function: stable `functionality_id`, `wave_id`, `title`, `requirement_refs`, `node_refs`, and `evidence_refs`;
- node: stable `node_id`, `functionality_id`, `kind`, `title`, `requirement_refs`, `dependency_refs`, `state_refs`, `api_refs`, `data_refs`, `integration_refs`, `error_refs`, `ledger_task_refs`, and `evidence_refs`;
- edge: stable `edge_id`, `from_graph_node_ref`, `to_graph_node_ref`, `kind`, `condition_refs`, and `evidence_refs`;
- coverage: stable `coverage_id`, `requirement_ref`, `dimension`, `functionality_refs`, `graph_node_refs`, `status`, and `evidence_refs`, where `dimension` is `behavior|dependency|state|api|data|integration|error` and `status` is `mapped|decision-gap|evidence-gap`;
- replacement: `old_ref`, `new_refs`, `reason`, `effective_revision`, and `evidence_refs`.

Use `<functionality_id>:<node_id>` for every `graph_node_ref`. A ledger graph anchor contains `graph_node_ref`, `functionality_id`, `wave_id`, `requirement_refs`, `graph_revision`, and `replacement_ref` or `none`.

## Canonical executable ledger task

Every executable ledger task includes:

- `task_id`, `wave_id`, `requirement_refs`, `functionality_refs`, and `graph_node_refs`;
- `target_paths`, `allowed_files`, `owner_role`, `lane`, and `depends_on`;
- `decision_state`, `status`, `definition_of_done`, and `proof_requirement`;
- `ledger_update_contract`, `artifact_refs`, `automation_evidence_refs`, and `result_refs`.

`artifact_refs` contains constitution, research, specification, and plan refs. `decision_state` is `open|closed`. Task `status` is `planned|blocked_by_decision|blocked_by_dependency|ready|in_progress|done|failed`. `ledger_update_contract` names the status transitions and exact task fields that `app-dev` may update; normally these are `status`, `result_refs`, and `automation_evidence_refs` through `ready -> in_progress -> done|failed`.

Return `app-stage-handoff.v1` with status `graph-ready`, the graph and ledger refs, exact graph revision, affected functionality, node, coverage, replacement, and anchor refs, and `next_stage: app-plan`.

## Mutation boundary

This skill is the sole semantic writer of `docs/app-functional-graph.v1.json`. It may update only `graph_anchors` in the ledger and must not create or mutate executable `tasks`. `app-plan` owns task planning fields; `app-dev` owns only execution fields authorized by `ledger_update_contract`; `app-analyze` reads graph and ledger state.

## Stage rules

- Never create a task without graph refs.
- Never delete an id referenced by a ledger task; record its replacement and add a new id.
- Add a graph node before planning work for an unmapped requirement.
- Return undecided requirements as `needs-spec` with exact decision and requirement refs to `app-specify`.
