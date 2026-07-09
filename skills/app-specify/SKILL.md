---
name: app-specify
description: Clarify Bears app research waves when actors, flows, data, errors, acceptance criteria, or product decisions are missing. Use as a helper inside app-research, not as a required main workflow gate.
---

# App Specify

## Purpose

Resolve blocking research questions and fold the clarified result back into `waves/<wave-id>/research.md`.

## Ask policy

Ask the user only for decisions that cannot be recovered from current docs, source observations, wave notes, or host-supplied context. Keep questions concrete and grouped by blocking decision.

## Clarification output

Return or write clarification notes with:

- Wave id and research section.
- Constitution refs affected.
- Actors and permissions.
- Main and alternate flows.
- Data inputs, outputs, and ownership.
- Error and empty states.
- External integrations.
- Acceptance criteria.
- Decisions closed.
- Open questions.

## Exit rules

- Fold clarified details into `waves/<wave-id>/research.md`.
- If acceptance criteria or data ownership is still missing, stay in `app-specify` or record a blocking question.
- If functional truth changes, route to `app-constitution`.
- If research is decision-complete, route to `app-plan`.
- Do not create plan microtasks, graph nodes, or dev packets here.
- Do not ask agents to run validation, test, audit, route, cache, cachebuster, quick-validate, or plugin-validate scripts manually.
