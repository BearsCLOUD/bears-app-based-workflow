---
name: app-specify
description: Interact with the user to clarify Bears app waves and expand them into detailed functional documentation. Use when a wave has open product decisions, unclear flows, actors, data, errors, or acceptance criteria.
---

# App Specify

## Purpose

Turn `waves/<wave-id>/research.md` into `waves/<wave-id>/spec.md` through targeted user clarification and source-backed detail.

## Ask policy

Ask the user only for decisions that cannot be recovered from current docs, code, or wave notes. Keep questions concrete and grouped by blocking decision.

## Spec file

Write `waves/<wave-id>/spec.md` with:

- Wave ID and source research file.
- Actors and permissions.
- User goals.
- Main flows.
- Alternate flows.
- Data inputs, outputs, and ownership.
- Error and empty states.
- External integrations.
- Acceptance criteria.
- Functional graph hints.
- Decisions closed in this pass.
- Open questions.

## Exit rules

- If acceptance criteria or data ownership is missing, stay in `app-specify`.
- If requirements are complete enough to map functionality, route to `app-functional-graph`.
- If the user changes wave scope, update the research file and wave registry.
- Do not create implementation tasks here.
