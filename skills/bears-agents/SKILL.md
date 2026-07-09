---
name: bears-agents
description: Select Bears role coverage for sequential app-dev handoffs. Use inside Bears App-Based Workflow when graph-backed ledger tasks need owner roles, critic roles, helper roles, or L3 worker assignment before subagent dispatch.
---

# Bears Agents

## Purpose

Select role coverage for graph-backed app-dev tasks and helper work.

## Output

Return a role coverage packet:

```json
{
  "wave_id": "<wave-id>",
  "handoffs": [
    {
      "handoff_order": 1,
      "task_id": "<task-id>",
      "owner_role": "<role>",
      "critic_role": "<role>",
      "helper_roles": ["<role>"],
      "constitution_refs": ["<constitution-id>"],
      "research_refs": ["<research-ref>"],
      "graph_node_refs": ["<graph-node-ref>"],
      "target_set": ["<path-or-target>"],
      "coverage_status": "covered|missing-role|conflict"
    }
  ]
}
```

## Rules

- Pick roles from task domain, target paths, graph refs, and proof requirements.
- Keep owner and critic roles separate when risk is non-trivial.
- Include helper roles for hardening, packet review, and closeout when bounded work exists.
- Report `missing-role` instead of inventing authority.
- Report `conflict` when the packet conflicts with dependency order, target paths, or host policy notes.
- Feed the packet to `subagents` and `app-dev` before subagent dispatch.
- Do not change functional truth, task scope, graph ids, or execution order.
- Do not ask agents to run validation, test, audit, route, cache, cachebuster, quick-validate, or plugin-validate scripts manually.
