---
name: app-functional-graph
description: Maintain the Bears app functional graph and graph-to-ledger references. Use when Codex must map wave requirements to functionality ids, graph node refs, dependencies, state transitions, API calls, and task ledger anchors.
---

# App Functional Graph

## Delegation first

As the solo L2 analogue, decompose the stage payload below, then follow `$subagents` for each concrete L3 assignment before any data access.

## Stage payload

- App id and wave ids.
- Constitution, research, and specification refs.
- Existing graph and ledger refs.
- Required functionality, dependency, state, API, data, integration, and error coverage.

## L3 output

The selected L3 creates or updates:

- `docs/app-functional-graph.v1.json`;
- graph anchors in `docs/app-task-ledger.v1.json`.

Each function has a stable `functionality_id`, `wave_id`, title, nodes, edges, and evidence refs. Each node has a stable `node_id`, kind, requirement refs, dependencies, and ledger task refs. Use `<functionality_id>:<node_id>` for `graph_node_refs`.

Every executable ledger task includes `task_id`, `wave_id`, `functionality_refs`, `graph_node_refs`, `target_paths`, `owner_role`, `lane`, `depends_on`, `decision_state`, `proof_requirement`, and `status`.

## Stage rules

- Never create a task without graph refs.
- Never delete an id referenced by a ledger task; record its replacement and add a new id.
- Add a graph node before planning work for an unmapped requirement.
- Return undecided requirements to `app-specify`.
