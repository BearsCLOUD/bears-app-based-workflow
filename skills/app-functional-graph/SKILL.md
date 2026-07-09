---
name: app-functional-graph
description: Maintain the Bears app functional graph and graph-to-ledger references. Use when Codex must map wave requirements to functionality ids, graph node refs, dependencies, state transitions, API calls, and task ledger anchors.
---

# App Functional Graph

## Purpose

Create or update the app-local functional graph and task-ledger anchors.

## Files

- `docs/app-functional-graph.v1.json`
- `docs/app-task-ledger.v1.json`

## Functional graph shape

Use stable ids. Keep this minimum structure:

```json
{
  "schema": "app-functional-graph.v1",
  "app": "<app-id>",
  "functions": [
    {
      "functionality_id": "<stable-id>",
      "wave_id": "<wave-id>",
      "title": "<user-visible behavior>",
      "nodes": [
        {
          "node_id": "<stable-node>",
          "kind": "ui|api|state|job|integration|data|error",
          "requirement_refs": ["<spec-section>"],
          "depends_on": [],
          "ledger_task_refs": []
        }
      ],
      "edges": [],
      "evidence_refs": []
    }
  ]
}
```

## Ledger reference shape

Every executable ledger task needs:

- `task_id`
- `wave_id`
- `functionality_refs`
- `graph_node_refs`
- `target_paths`
- `owner_role`
- `lane`
- `depends_on`
- `decision_state`
- `proof_requirement`
- `status`

`graph_node_refs` use `<functionality_id>:<node_id>`.

## Rules

- Never create a task without graph refs.
- Never delete graph ids that existing ledger tasks reference; mark replacement and add a new id.
- Use role-matched graph subagents for independent functionality groups, API groups, UI flows, data flows, state transitions, or integration edges.
- Keep graph subagent scopes disjoint by functionality id, node group, or target path set.
- If a requirement has no graph home, add a graph node before planning tasks.
- If a graph node lacks a decision-complete requirement, return it to `app-specify`.
- Validation, test, audit, route, cache, cachebuster, quick-validate, and plugin-validate scripts belong to pre-commit autoCI; agents do not run them manually.
