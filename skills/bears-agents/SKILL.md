---
name: bears-agents
description: Select Bears role coverage for app-dev orchestration. Use inside Bears App-Based Workflow when ledger tasks need owner roles, critic roles, L2 lane coverage, or L3 worker assignment before subagent dispatch.
---

# Bears Agents

## Purpose

Select role coverage for graph-linked app-dev tasks.

## Output

Return a role coverage packet:

```json
{
  "wave_id": "<wave-id>",
  "lanes": [
    {
      "lane": "<lane-id>",
      "owner_role": "<role>",
      "critic_role": "<role>",
      "task_ids": ["<task-id>"],
      "coverage_status": "covered|missing-role|conflict"
    }
  ]
}
```

## Rules

- Pick roles from task domain, target paths, and proof requirements.
- Keep owner and critic roles separate when risk is non-trivial.
- Report `missing-role` instead of inventing authority.
- Report `conflict` when two lanes would write overlapping paths.
- Feed the packet to `app-dev` before subagent dispatch.
