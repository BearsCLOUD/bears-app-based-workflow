---
name: app-functional-graph
description: Maintain the Bears app functional graph and graph-to-ledger references. Use when Codex must map wave requirements to functionality ids, graph node refs, dependencies, state transitions, API calls, and task ledger anchors.
---

# App Functional Graph

## Delegation first

For work already classified `DELEGATED`, act as the solo L2 analogue: decompose the stage payload below, then follow `$subagents` for each concrete L3 assignment before any data access. `DIRECT` work never enters `$subagents`.

## Stage payload

- Every stage-generated input is the canonical `app-stage-handoff.v1` below. Accept `spec-ready` from `app-specify` or `needs-graph` from `app-plan`.
- `spec-ready` adds constitution, research, and specification refs plus required-behavior and dimension-coverage refs.
- `needs-graph` adds `source_handoff_ref`, `graph_ref`, and `affected_graph_refs`; its common requirement, gap, evidence, and implemented-state fields identify the exact repair scope.

## Canonical stage handoff

`app-stage-handoff.v1` is the only inter-stage envelope for all seven `app-*` stages. Every stage-generated input and output carries every common field below plus the fields for its status. Direct user entry into `app-constitution` is not an inter-stage handoff.

Common fields:

- `source_stage`, `target_stage`, `status`, `app_id`, and `wave_ids`;
- `artifact_refs`, `requirement_refs`, `graph_revision`, and `ledger_ref`;
- `gap_refs`, `evidence_refs`, `dependency_refs`, and `decision_refs`;
- `scope_delta` and `implemented_state_refs`.

All common fields are mandatory. `wave_ids` and every common `*_refs` field are arrays of stable refs; use `[]` when refs do not yet exist or do not apply, never omit the field or substitute `none`. Use `graph_revision: none` and `ledger_ref: none` before those artifacts exist. Use `scope_delta: none` when scope did not change. `implemented_state_refs: []` means no implemented-state evidence is available yet. `target_stage: none` is valid only for terminal `pass` or paused `blocked`; `source_stage`, `status`, and `app_id` are never `none`. Do not guess an unavailable early-stage value.

Status-specific fields and routes:

- `constitution-ready` adds `app_repo_or_path`, `constitution_ref`, `constraint_refs`, `research_unknowns`, and `wave_creation_basis`; target `app-research`.
- `research-ready` adds `constitution_ref`, `research_refs`, `question_refs`, and `source_refs`; target `app-specify`.
- `spec-ready` adds `constitution_ref`, `research_refs`, `specification_refs`, `required_behavior_refs`, `dependency_coverage_refs`, `state_coverage_refs`, `api_coverage_refs`, `data_coverage_refs`, `integration_coverage_refs`, and `error_coverage_refs`; target `app-functional-graph`.
- `graph-ready` adds `graph_ref`, `functionality_refs`, `graph_node_refs`, `coverage_refs`, `replacement_refs`, and `graph_anchor_refs`; target `app-plan`.
- `plan-ready` adds `task_records`, each a complete canonical executable ledger task; it is emitted only by `app-plan` and targets `app-dev`.
- `ready` adds `task_records`, each a complete canonical executable ledger task; it is reserved for `app-analyze` re-entry and targets `app-dev`.
- `waiting` adds `source_handoff_ref`, `blocked_task_refs`, and `dependency_state_evidence_refs`; target `app-plan`.
- `no-work` adds `plan_refs`; target `app-analyze`.
- `implemented` adds `completed_task_refs` and `result_refs`; target `app-analyze`.
- `pass` adds `analysis_refs`; target `none`.
- `needs-research` adds `source_handoff_ref`, `question_refs`, `source_refs`, and `research_unknowns`; target `app-research`.
- `needs-spec` adds `source_handoff_ref` and `question_refs`; its common decision, requirement, gap, artifact, and evidence fields define the unresolved product scope; target `app-specify`.
- `needs-graph` adds `source_handoff_ref`, `graph_ref`, and `affected_graph_refs`; its common requirement, gap, evidence, and implemented-state fields define the semantic graph repair; target `app-functional-graph`.
- `needs-plan` adds `source_handoff_ref`, `ledger_coverage_refs`, and `implementation_state_by_requirement`; target `app-plan`.
- `blocked` adds `blocker_refs` and `operator_action_refs`; target `none`.

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

Return the canonical `app-stage-handoff.v1` with status `graph-ready`, every common field, and the `graph-ready` fields defined above.

## Mutation boundary

This skill is the sole semantic writer of `docs/app-functional-graph.v1.json`. It may update only `graph_anchors` in the ledger and must not create or mutate executable `tasks`. `app-plan` owns task planning fields; `app-dev` owns only execution fields authorized by `ledger_update_contract`; `app-analyze` reads graph and ledger state.

## Stage rules

- Never create a task without graph refs.
- Never delete an id referenced by a ledger task; record its replacement and add a new id.
- Add a graph node before planning work for an unmapped requirement.
- Return undecided requirements as canonical `needs-spec` with every common field plus `source_handoff_ref` and `question_refs`; populate exact decision and requirement refs and target `app-specify`.
