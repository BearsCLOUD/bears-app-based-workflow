---
name: app-specify
description: Interact with the user to clarify Bears app waves and expand them into detailed functional documentation. Use when a wave has open product decisions, unclear flows, actors, data, errors, or acceptance criteria.
---

# App Specify

## Delegation first

For work already classified `DELEGATED`, act as the solo L2 analogue: decompose the stage payload below, then follow `$subagents` for each concrete L3 assignment before any data access. `DIRECT` work never enters `$subagents`.

## Clarification loop

1. An L3 helper reads the delegated research and evidence refs and returns only unresolved product decisions.
2. Parent asks the user concrete questions grouped by blocking decision.
3. Parent sends the answers through the persistent selector for an L3 specification update.
4. Repeat only while acceptance criteria, data ownership, or required behavior remain undecided.

Parent may ask questions but does not inspect source data.

## Stage payload

- App id, wave id, constitution ref, and research ref from `research-ready`.
- User answers and confirmed decisions.
- Known source and integration refs.
- Exact open questions.

## L3 output

The selected L3 writes `waves/<wave-id>/spec.md` with actors and permissions, user goals, main and alternate flows, data inputs and ownership, error and empty states, integrations, acceptance criteria, functional graph hints, closed decisions, and open questions.

When decisions are complete, return `app-stage-handoff.v1` with status `spec-ready`, the constitution, research, and specification refs, requirement refs, required behavior, dependency, state, API, data, integration, and error coverage, and `next_stage: app-functional-graph`.

## Exit rules

- Stay in `app-specify` while acceptance criteria or data ownership is missing.
- Route only decision-complete behavior to `app-functional-graph`.
- If wave scope changes, return status `needs-research` with the wave id, current artifact refs, and exact scope delta to `app-research`; do not edit research artifacts in this stage.
- Do not create implementation tasks.
