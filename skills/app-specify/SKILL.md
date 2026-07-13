---
name: app-specify
description: Clarify app waves with the user and produce decision-complete functional documentation.
---

# App Specify

## Ownership

- Keep the `DIRECT` primary as the stage owner for user questions, target access, artifact changes, protocol decisions, journal events, and the outgoing handoff.
- Keep one persistent repo-L2 with role `domain-lane-orchestrator` as the stage owner for `DELEGATED` work.
- Require the repo-L2 to invoke every L3 assignment through `$subagents` and consume only its bounded result packet.
- Permit the repo-L2 to ask the user bounded questions without inspecting target content itself.
- Never let an L3 write the journal, select a transition, or emit the stage handoff.

## Input

- Accept only `app-stage-handoff.v4` status `research-ready` or `needs-spec` for the same repo boundary.
- Require a current `$app-context-index` result whose build and source snapshot match the handoff.
- Read routes only from `contracts/app-workflow-definition.v3.json`.
- Require stable refs for every supplied source, decision, requirement, question, finding, and evidence item.

## Clarification

1. Read the bounded source and research refs in `DIRECT` mode or dispatch one read-only L3 through `$subagents` in `DELEGATED` mode.
2. Ask the user questions grouped by one blocking decision at a time.
3. Record each confirmed answer as a stable decision ref.
4. Update the specification in `DIRECT` mode or dispatch one bounded writer L3 through `$subagents` in `DELEGATED` mode.
5. Repeat only while required behavior, data ownership, actor authority, or outcome conditions remain undecided.

## Artifact

Create or update `waves/<wave-id>/spec.md` with actors, permissions, user goals, main flows, alternate flows, data inputs, ownership, states, interfaces, integrations, error behavior, observable outcome conditions, closed decisions, requirements, and open questions.

Represent each confirmed decision and requirement with a stable first-class ref.

Do not create implementation tasks in this stage.

## Completion

1. Return `needs-research` when scope or source coverage changed and include exact question, source, and scope-delta refs.
2. Return `spec-ready` only when required behavior, data ownership, actor authority, and outcome conditions are decision-complete.
3. Put constitution, research, specification, behavior, and seven-dimension hint refs in `stage_payload`.
4. Reconcile changed sources through `$app-context-index` before selecting the transition.
5. Validate the candidate `app-stage-handoff.v4`, record only the actual native v3 stage event, and reconcile the resulting journal.
6. Emit the build-bound handoff with the target resolved from workflow v3.
