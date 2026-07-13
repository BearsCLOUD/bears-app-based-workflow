---
name: app-functional-graph
description: Maintain decision-complete app semantic mappings and typed dependency relations. Use when requirements need functionality, behavior, state, API, data, integration, or error mapping before context indexing and planning.
---

# App Functional Graph

## Delegation first

For work already classified `DELEGATED`, act as the solo L2 analogue: decompose the stage payload below, then follow `$subagents` for each concrete L3 assignment before any data access. `DIRECT` work never enters `$subagents`.

## Stage payload

Accept canonical `app-stage-handoff.v3` status `spec-ready` or `needs-graph`. The envelope is defined only by `contracts/app-stage-handoff.v3.schema.json`; routes and graph semantics come only from `contracts/app-workflow-definition.v2.json`. Require a current `app-context-index-result.v1` and matching source digest before semantic mapping.

## Stage output ownership

In `DIRECT`, the primary creates the stage artifacts and canonical handoff. In `DELEGATED`, the assigned L3 creates them.

The stage creates or updates only `docs/app-functional-map.v2.json` according to `contracts/app-functional-map.v2.schema.json`. It maps stable requirement, functionality, behavior, state, API, data, integration, and error refs; typed relations; seven-dimension coverage; and replacements. Relation kinds must exist in the workflow edge registry. `depends_on` is directed from dependent to prerequisite.

After mapping, invoke `$app-context-index` to rebuild the traceability and process indexes. Return `graph-ready` only with a current digest, `functional_map_ref`, `functionality_refs`, `graph_entity_refs`, `coverage_refs`, and `replacement_refs`.

## Canonical executable ledger task

Every executable ledger task still includes:

- `task_id`, `repo_ref`, `batch_id`, `wave_id`, `queue_sequence`, `task_kind`, and `source_review_refs`;
- `requirement_refs`, `functionality_refs`, and `graph_entity_refs`;
- `target_paths`, `allowed_files`, `owner_role`, `lane`, and `depends_on`;
- `decision_state`, `status`, `definition_of_done`, and `proof_requirement`;
- `ledger_update_contract`, `artifact_refs`, `automation_evidence_refs`, and `result_refs`.

`repo_ref` identifies one repository boundary and resolves to the repo cwd at dispatch. `batch_id` groups one admitted planning batch. `queue_sequence` is the deterministic position inside a repo wave and is unique for `(repo_ref, wave_id)`. `task_kind` is `implementation|remediation`; remediation tasks use new task ids and name their originating review refs in `source_review_refs`. Implementation tasks use `source_review_refs: []` unless review explicitly created them.

`artifact_refs` contains constitution, research, specification, functional map, index, and plan refs. `decision_state` is `open|closed`. Task `status` is `planned|blocked_by_decision|blocked_by_dependency|ready|in_progress|done|failed`. `done` and `failed` are terminal and are never reopened. `ledger_update_contract` names the status transitions and exact task fields that `app-dev` may update; normally these are `status`, `result_refs`, and `automation_evidence_refs` through `ready -> in_progress -> done|failed`.

## Mutation boundary

This skill is the sole semantic writer of `docs/app-functional-map.v2.json`. `$app-context-index` alone owns the two derived indexes. This skill must not create or mutate executable ledger tasks; `app-plan` owns planning fields, `app-dev` owns authorized execution fields, and `app-analyze` reads semantic and index state.

## Stage rules

- Never create a task in this stage.
- Never delete a ref used by a ledger task; record its replacement and add a new ref.
- Add a typed graph entity before planning work for an unmapped requirement.
- Return undecided requirements as canonical `needs-spec` with exact source, decision, requirement, and question refs; never infer a conceptual resolution.

## v3 boundary audit

Run `$app-trace-audit` with profile `semantic` after updating the functional map. Route every finding before handoff. Validate the transition, record the actual stage event through the maintainer, compile with CAS, and emit only `app-stage-handoff.v3` bound to the resulting build and journal digests.
