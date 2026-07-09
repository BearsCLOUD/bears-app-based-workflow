---
name: app-plan
description: Create sequential Bears app plan microtasks from constitution-backed research. Use when Codex must turn research explanations into ordered ledger tasks before functional graph modeling.
---

# App Plan

## Purpose

Create only ordered, decision-complete microtasks tied to constitution refs and research refs. Planning happens before graph modeling and must not create graph nodes.

## Inputs

- `docs/app-constitution.md`
- `waves/index.md`
- `waves/<wave-id>/research.md`
- `docs/app-task-ledger.v1.json` when present.
- Current implemented-state notes when present.
- Host policy notes when supplied by the live session.

## Outputs

- `waves/<wave-id>/plan.md`
- Updated `docs/app-task-ledger.v1.json`
- Ordered microtasks for `app-functional-graph`
- `constitution_update_needed` or `research_update_needed` note when planning finds a missing upstream link.

## Planning steps

1. Read `docs/app-constitution.md` and the wave research file.
2. List constitution ids explained by the wave.
3. Confirm every planned item has a source-backed research explanation.
4. Create ordered microtasks only for decision-complete scope.
5. Attach constitution refs, research refs, target paths, definition of done, proof requirement, owner role, critic role, dependencies, and status.
6. Set new decision-complete microtasks to `ready_for_graph`.
7. Route the completed plan to `app-functional-graph`.

## Task rules

- Create no microtask for unresolved decisions.
- Create no microtask without `constitution_refs` and `research_refs`.
- Do not create graph nodes or graph node ids for new scope.
- Keep execution order explicit through `order` and `depends_on`.
- Use `blocked_by_decision` for tasks that need clarification.
- Use `blocked_by_research` for tasks that lack research explanation.
- Host policy can constrain target paths or proof, but it does not replace constitution refs.
- Do not route directly to `app-dev`.
- Do not ask agents to run validation, test, audit, route, cache, cachebuster, quick-validate, or plugin-validate scripts manually.
