---
name: app-plan
description: Detect unbuilt Bears app functionality and create graph-linked wave plans, ledger tasks, role coverage inputs, hardened dispatch packets, and maximum disjoint parallel app-dev lanes.
---

# App Plan

## Purpose

Find missing or unbuilt functionality and create only decision-complete tasks tied to the functional graph.

## Inputs

- `docs/app-constitution.md`
- Nearest parent and app-local `AGENTS.md` rules.
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
- Role-mapping input for `subagents-roles`.
- L2/L3 lane plan for `app-dev`.
- Constitution gap references for tasks that close `docs/app-constitution.md` gaps.
- `constitution_update_needed` note when planning finds a new important functional gap, drift, or decision.

## Planning steps

1. Read `docs/app-constitution.md` and nearest/app-local `AGENTS.md` before graph or ledger changes.
2. List specified requirements by wave.
3. Compare requirements with constitution core capabilities, constraints, evidence needs, and functional gaps.
4. Match each requirement to graph nodes.
5. Mark built, partial, missing, and drifted functionality.
6. Create or update ledger tasks only for missing or drifted functionality with closed decisions.
7. Attach constitution gap refs, dependencies, target paths, owner role, lane, and proof requirement.
8. Split dependency-ready work into the maximum number of disjoint repo, path, and target sets.
9. Send tasks through `subagents-roles`, `bears-agents`, and `subagents` for role coverage and L2/L3 packets.
10. Apply `$instruction-hardening` as a read-only pass to wave plans and candidate dispatch packets before `app-dev` handoff.

## Task rules

- Create no task for unresolved product decisions.
- Create no task for a constitution gap that needs research, specification, or an AGENTS/contract decision first; route it to the owning skill.
- Create no task without `functionality_refs` and `graph_node_refs`.
- Keep one task inside one repo boundary and one exact target set.
- Use `blocked_by_decision` for tasks that need `app-specify`.
- Use `ready` only when dependencies and decisions are closed.
- Route implementation to `app-dev` only through the ledger.
- Specific planning work goes to role-matched subagents when it has a bounded target set.
- Parallel lanes must not share files, generated artifacts, caches, or evidence outputs.
- `AGENTS.md` and contracts override constitution notes. If they disagree, keep the task within `AGENTS.md` authority and send a drift note to `app-constitution`.
- New important functional gaps belong in `docs/app-constitution.md`, not only in wave prose.
- Instruction hardening must not create tasks, change product decisions, run scripts, or override `AGENTS.md` and contracts.
- Validation, test, audit, route, cache, cachebuster, quick-validate, and plugin-validate scripts belong to pre-commit autoCI; agents do not run them manually.
