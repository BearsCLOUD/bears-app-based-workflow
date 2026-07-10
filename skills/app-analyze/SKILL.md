---
name: app-analyze
description: Analyze Bears app workflow artifacts against implemented code state. Use when Codex must compare wave docs, functional graph, task ledger, and current implementation, then return pass, ready, needs-plan, needs-spec, or blocked status.
---

# App Analyze

## Delegation first

For work already classified `DELEGATED`, act as the solo L2 analogue: decompose the stage payload below, then follow `$subagents` for each concrete L3 assignment before any data access. `DIRECT` work never enters `$subagents`.

## Stage payload

- Every stage-generated input uses the canonical `app-stage-handoff.v1` defined by `app-functional-graph` and carries all common fields.
- `implemented` from `app-dev` additionally carries `completed_task_refs` and `result_refs`.
- `no-work` from `app-plan` additionally carries `plan_refs`.
- A direct diagnostic request is not an inter-stage handoff; it must still identify the target app and waves plus constitution, research, specification, graph, ledger, plan, implemented-state, and existing autoCI evidence refs.

## L3 output

The selected L3 writes `waves/<wave-id>/analysis.md` with inputs reviewed, requirement coverage, graph revision and coverage, ledger coverage, implemented-state comparison, `built|partial|missing|drifted` classification by requirement, and an exact handoff. The graph and ledger are read-only in this stage.

It sets one status:

- `pass`: documentation, graph, ledger, and implementation agree, and each required current autoCI check is `PASS`.
- `ready`: one or more existing canonical ledger tasks are `ready`, have current graph refs, and require execution.
- `needs-plan`: specified behavior is `partial`, `missing`, `drifted`, or absent from the ledger.
- `needs-spec`: flows, actors, data, errors, decisions, or acceptance criteria are incomplete.
- `blocked`: access, credentials, unavailable source, or an explicit operator decision prevents progress.

## Stage rules

- Do not fix implementation during analysis.
- Pending or missing required autoCI evidence is not `pass`.
- Return canonical `app-stage-handoff.v1` with every common field and the fields for its status. `ready` adds complete canonical `task_records` and targets `app-dev`. `needs-plan` adds `source_handoff_ref`, `ledger_coverage_refs`, and `implementation_state_by_requirement`, populates common graph revision, gap, evidence, and implemented-state refs, and targets `app-plan`. `needs-spec` adds `source_handoff_ref` and `question_refs`, populates common decision and requirement refs, and targets `app-specify`. `pass` adds `analysis_refs` and targets `none`; `blocked` adds `blocker_refs` and `operator_action_refs` and targets `none`.
- If graph refs are missing or graph meaning drifted, report them inside `needs-plan`; `app-plan` returns the required `needs-graph` handoff without editing the graph.
- Do not use `blocked` for ordinary risk or incomplete work.
