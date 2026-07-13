---
name: app-specify
description: Interact with the user to clarify Bears app waves and expand them into detailed functional documentation. Use when a wave has open product decisions, unclear flows, actors, data, errors, or acceptance criteria.
---

# App Specify

## Delegation first

For work already classified `DELEGATED`, act as the solo L2 analogue: decompose the stage payload below, then apply deterministic `$subagents` selection and `dispatch-packet.v2` for each concrete L3 assignment before any data access. Each assignment starts one matching L3 and returns `result-packet.v1`. `DIRECT` work never enters `$subagents`.

## Clarification loop

In `DIRECT`, the primary reads the stage refs, asks the user concrete questions grouped by blocking decision, writes the specification, and creates the canonical handoff. In `DELEGATED`:

1. Create one bounded read-only assignment for the delegated research and evidence refs, apply the canonical ordered role rules in `$subagents`, and return only unresolved product decisions.
2. Parent asks the user concrete questions grouped by blocking decision.
3. Create a fresh bounded mutation assignment carrying sanitized answer refs, deterministically select `worker`, and dispatch the specification update.
4. Repeat only while acceptance criteria, data ownership, or required behavior remain undecided.

In `DELEGATED`, the parent may ask questions but does not inspect source data. No agent reference crosses an assignment boundary. When `$app-solo-route` invokes this stage, follow its narrower user decision gate.

## Stage payload

- Every stage-generated input uses canonical `app-stage-handoff.v3` from `contracts/app-stage-handoff.v3.schema.json` and carries a current `$app-context-index` result.
- `research-ready` from `app-research` additionally carries `constitution_ref`, `research_refs`, `question_refs`, and `source_refs`.
- `needs-spec` from `app-functional-graph`, `app-plan`, `app-dev`, or `app-analyze` additionally carries `source_handoff_ref` and `question_refs`; its common decision, requirement, gap, artifact, and evidence fields define the exact unresolved context.
- User answers and confirmed decisions.
- Known source and integration refs.
- Exact open questions.

## Stage output ownership

In `DIRECT`, the primary creates the stage artifact and canonical handoff. In `DELEGATED`, the assigned `worker` creates them and owns its task-scoped local commit.

The stage writes `<app-root>/waves/<wave-id>/spec.md` in the consuming app repository with actors and permissions, user goals, main and alternate flows, data inputs and ownership, error and empty states, integrations, acceptance criteria, functional graph hints, closed decisions, and open questions.

Represent accepted decisions and requirements as stable first-class refs. When decisions are complete, refresh `$app-context-index`, then return canonical `app-stage-handoff.v3` status `spec-ready` with the current digest/index fields plus `constitution_ref`, `research_refs`, `specification_refs`, `required_behavior_refs`, `dependency_coverage_refs`, `state_coverage_refs`, `api_coverage_refs`, `data_coverage_refs`, `integration_coverage_refs`, and `error_coverage_refs`; target `app-functional-graph`.

## Exit rules

- Stay in `app-specify` while acceptance criteria or data ownership is missing.
- Route only decision-complete behavior to `app-functional-graph`.
- If wave scope changes, return canonical `needs-research` with every common field plus `source_handoff_ref`, `question_refs`, `source_refs`, and `research_unknowns`; populate the exact `scope_delta` and target `app-research`. Do not edit research artifacts in this stage.
- Do not create implementation tasks.
