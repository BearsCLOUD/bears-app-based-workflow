---
name: app-functional-graph
description: Build the Bears app functional graph as a dev-stage model from approved plan microtasks. Use when Codex must map constitution-backed research and plan tasks to functionality ids, graph node refs, dependencies, state transitions, API calls, evidence refs, and ledger backlinks.
---

# App Functional Graph

## Purpose

Create or update `docs/app-functional-graph.v1.json` after planning. The graph models future `app-dev` work from approved plan microtasks.

## Inputs

- `docs/app-constitution.md`
- `waves/<wave-id>/research.md`
- `waves/<wave-id>/plan.md`
- `docs/app-task-ledger.v1.json`
- Existing `docs/app-functional-graph.v1.json` when present.

## Outputs

- Updated `docs/app-functional-graph.v1.json`
- Updated graph backlinks in `docs/app-task-ledger.v1.json`

## Graph node requirements

Every graph node needs:

- `node_id`
- function record `functionality_id`
- `kind`
- `dev_model_kind`
- `constitution_refs`
- `research_refs`
- `plan_task_refs`
- `depends_on`
- `evidence_refs`

`graph_node_refs` use `<functionality_id>:<node_id>`.

## Rules

- Build graph nodes only from approved plan microtasks.
- Never create graph nodes directly from research without a plan microtask.
- Every graph node must prove lineage: constitution -> research -> plan.
- Write graph node refs back to matching ledger tasks.
- Never delete graph ids referenced by ledger tasks; supersede and add replacement ids.
- Supersede old nodes when a contract, skill, template, or manifest behavior change makes the old node inaccurate.
- If a microtask has no constitution ref, route to `app-plan` or `app-constitution`.
- If a microtask has no research ref, route to `app-plan` or `app-research`.
- If a required microtask is missing, route to `app-plan`.
- Do not route directly to `app-dev` until lineage is complete.
- After complete lineage and ledger backlinks are written, route the ready graph-backed scope to `app-dev`.
- Do not create validation tooling to prove graph shape.
- Do not ask agents to run validation, test, audit, route, cache, cachebuster, quick-validate, or plugin-validate scripts manually.
