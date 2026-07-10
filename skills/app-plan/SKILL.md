---
name: app-plan
description: Detect unbuilt Bears app functionality and create graph-linked wave plans and ledger tasks. Use when Codex must decompose specified waves into dependencies, ready tasks, owner roles, target paths, optional instruction-hardening checks, and app-dev handoff packets.
---

# App Plan

## Purpose

Find missing or unbuilt functionality and create only decision-complete tasks tied to the functional graph.

## Inputs

- `waves/index.md`
- `waves/<wave-id>/research.md`
- `waves/<wave-id>/spec.md`
- `docs/app-functional-graph.v1.json`
- `docs/app-task-ledger.v1.json`
- Current implemented-state notes from code reading or `app-analyze`.

## Outputs

- `waves/<wave-id>/plan.md`
- Updated `docs/app-functional-graph.v1.json`
- Updated `docs/app-task-ledger.v1.json`

## Planning steps

1. List specified requirements by wave.
2. Match each requirement to graph nodes.
3. Mark built, partial, missing, and drifted functionality.
4. Create or update ledger tasks only for missing or drifted functionality.
5. Add dependencies, target paths, owner role, lane, and proof requirement.
6. Optionally run `$instruction-hardening` on the wave plan as a read-only pass when the operator allows subagents in the current run.
7. Group dependency-ready tasks into waves or wave partitions for `app-dev`.

## Task rules

- Create no task for unresolved product decisions.
- Create no task without `functionality_refs` and `graph_node_refs`.
- Keep one task inside one repo boundary and one exact target set.
- Use `blocked_by_decision` for tasks that need `app-specify`.
- Use `ready` only when dependencies and decisions are closed.
- Route implementation to `app-dev` only through the ledger.
- Instruction hardening must not create tasks, change product decisions, or override `AGENTS.md` and contracts.
