---
name: app-analyze
description: Analyze repo-scoped app results, immutable reviews, remediation, and exact autoCI evidence against wave artifacts and implemented state.
---

# App Analyze

## Delegation first

For work already classified `DELEGATED`, act as the solo L2 analogue: decompose the stage payload below, then follow `$subagents` for each concrete L3 assignment before any data access. `DIRECT` work never enters `$subagents`.

## Stage payload

- Every stage-generated input uses canonical `app-stage-handoff.v2` and carries current traceability/process index refs, source digest, and context-index result.
- Each repo-scoped `implemented` handoff from `app-dev` additionally carries `repo_ref`, `completed_task_refs`, `failed_task_refs`, `task_result_refs`, `review_result_refs`, `commit_range_refs`, and `remediation_task_refs`. Never combine these refs across repositories.
- `no-work` from `app-plan` additionally carries `plan_refs`.
- A direct diagnostic request is not an inter-stage handoff; it must still identify the target app and waves plus constitution, research, specification, graph, ledger, plan, implemented-state, and existing autoCI evidence refs.

## Stage output ownership

In `DIRECT`, the primary creates the analysis artifact and canonical handoff. In `DELEGATED`, the assigned L3 creates them.

Refresh `$app-context-index` before assessment. The stage writes `waves/<wave-id>/analysis.md` with the repo and wave inputs assessed; requirement, functional-map, trace, process, and ledger coverage; completed and failed tasks; task results; immutable review results and commit ranges; remediation state; implemented-state comparison; `built|partial|missing|drifted` classification by requirement; every detected violation gathered in one pass; unavailable automation evidence listed separately; and an exact handoff. The functional map, indexes, and ledger are read-only during analysis.

Use read-only `graph_trace`, `graph_diagnostics`, and `workflow_state` MCP queries against the exact handoff digest. Treat MCP errors or stale digests as analysis gaps; MCP output never substitutes for source artifacts, immutable review, or autoCI evidence.

It sets one status:

- `pass`: documentation, functional map, traceability index, process index, ledger, implementation, required immutable reviews, and completed remediation agree, every required source-to-evidence path is complete, and exact current-wave `automation-status.v1` evidence for the commit identified by `commit_range_refs` is `passed`.
- `ready`: one or more existing canonical implementation or remediation tasks are `ready`, have current graph refs, and require execution.
- `needs-plan`: specified behavior is `partial`, `missing`, `drifted`, absent from the ledger, or requires a repair that has no canonical remediation task.
- `needs-spec`: flows, actors, data, errors, decisions, or acceptance criteria are incomplete.
- `blocked`: access, credentials, unavailable source, or an explicit operator decision prevents progress.

## Stage rules

- Do not fix implementation during analysis.
- Require the primary immutable review for each repo-wave commit range and any specialist review justified by its deterministic security trigger. Missing required reviews, unresolved findings, failed tasks without represented remediation, or noncanonical repair work are planning gaps; route them through `needs-plan`.
- Do not treat expected `failed_task_refs` as a global workflow failure when their dependents are gated and their remediation is represented. Continue analysis from the independent completed and remediation state.
- Acceptance remains `not_run` until autoCI validates the exact current-wave commit. Pending, missing, stale, range-mismatched, or other-commit evidence is not `pass`; unavailable automation evidence stays a reported limitation and is never converted into agent-generated acceptance.
- Return canonical `app-stage-handoff.v2` with the current digest/index fields and the fields for its status. `ready` adds complete canonical `task_records` and targets `app-dev`. `needs-plan` adds `source_handoff_ref`, `ledger_coverage_refs`, and `implementation_state_by_requirement`, populates gap, evidence, and implemented-state refs, and targets `app-plan`. `needs-spec` adds `source_handoff_ref` and `question_refs`, populates decision and requirement refs, and targets `app-specify`. `pass` adds `analysis_refs` and targets `none`; `blocked` adds `blocker_refs` and `operator_action_refs` and targets `none`.
- If graph refs are missing or graph meaning drifted, report them inside `needs-plan`; `app-plan` returns the required `needs-graph` handoff without editing the graph.
- Do not use `blocked` for ordinary risk or incomplete work.
