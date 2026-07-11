---
name: app-specify
description: Interact with the user to clarify Bears app waves and expand them into detailed functional documentation. Use when a wave has open product decisions, unclear flows, actors, data, errors, or acceptance criteria.
---

# App Specify

## Delegation first

For work already classified `DELEGATED`, act as the solo L2 analogue: decompose the stage payload below, then apply deterministic `$subagents` selection and `dispatch-packet.v2` for each concrete L3 assignment before any data access. Each assignment starts one matching L3 and returns `result-packet.v1`. `DIRECT` work never enters `$subagents`.

## Clarification loop

1. Create one bounded read-only assignment for the delegated research and evidence refs. Route ordinary workspace reads to `explorer`, public current-claim research to `primary-source-researcher`, and runtime-backed evidence to `runtime-evidence-reader`; return only unresolved product decisions.
2. Parent asks the user concrete questions grouped by blocking decision.
3. Create a fresh bounded mutation assignment carrying sanitized answer refs, deterministically select `worker`, and dispatch the specification update.
4. Repeat only while acceptance criteria, data ownership, or required behavior remain undecided.

Parent may ask questions but does not inspect source data. No agent reference crosses an assignment boundary.

## Stage payload

- Every stage-generated input uses the canonical `app-stage-handoff.v1` defined by `app-functional-graph` and carries all common fields.
- `research-ready` from `app-research` additionally carries `constitution_ref`, `research_refs`, `question_refs`, and `source_refs`.
- `needs-spec` from `app-functional-graph`, `app-plan`, `app-dev`, or `app-analyze` additionally carries `source_handoff_ref` and `question_refs`; its common decision, requirement, gap, artifact, and evidence fields define the exact unresolved context.
- User answers and confirmed decisions.
- Known source and integration refs.
- Exact open questions.

## L3 output

The selected `worker` writes `waves/<wave-id>/spec.md` with actors and permissions, user goals, main and alternate flows, data inputs and ownership, error and empty states, integrations, acceptance criteria, functional graph hints, closed decisions, and open questions, then owns its task-scoped local commit.

When decisions are complete, return canonical `app-stage-handoff.v1` status `spec-ready` with every common field plus `constitution_ref`, `research_refs`, `specification_refs`, `required_behavior_refs`, `dependency_coverage_refs`, `state_coverage_refs`, `api_coverage_refs`, `data_coverage_refs`, `integration_coverage_refs`, and `error_coverage_refs`; target `app-functional-graph`.

## Exit rules

- Stay in `app-specify` while acceptance criteria or data ownership is missing.
- Route only decision-complete behavior to `app-functional-graph`.
- If wave scope changes, return canonical `needs-research` with every common field plus `source_handoff_ref`, `question_refs`, `source_refs`, and `research_unknowns`; populate the exact `scope_delta` and target `app-research`. Do not edit research artifacts in this stage.
- Do not create implementation tasks.
