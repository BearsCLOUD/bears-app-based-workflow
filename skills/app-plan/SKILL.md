---
name: app-plan
description: Detect unbuilt Bears app functionality and create graph-linked wave plans and ledger tasks. Use when Codex must decompose specified waves into dependencies, ready tasks, owner roles, target paths, and app-dev handoff payloads.
---

# App Plan

## Delegation first

As the solo L2 analogue, decompose the stage payload below, then follow `$subagents` for each concrete L3 assignment before any data access.

## Stage payload

- Wave index, research, and specification refs.
- Functional graph and task ledger refs.
- Delegated implemented-state facts.
- Target wave ids and known dependencies.

## L3 output

The selected L3 writes `waves/<wave-id>/plan.md` and updates `docs/app-functional-graph.v1.json` plus `docs/app-task-ledger.v1.json`.

For each specified requirement it records graph coverage and `built`, `partial`, `missing`, or `drifted` state. It creates or updates ledger tasks only for missing or drifted behavior, with exact dependencies, target paths, owner-role requirement, lane, and proof requirement.

## Stage rules

- Create no task for an unresolved product decision.
- Create no task without `functionality_refs` and `graph_node_refs`.
- Keep each task inside one repo boundary and one exact target set.
- Mark decision-dependent work `blocked_by_decision` and route it to `app-specify`.
- Mark work `ready` only when its decisions and dependencies are closed.
- Route ready ledger work to `app-dev`.
- Use `instruction-hardening` only as a separate delegated pass.
