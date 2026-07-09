---
name: bears-agents
description: Select Bears role coverage for app-dev orchestration. Use inside Bears App-Based Workflow when ledger tasks need owner roles, critic roles, helper roles, L2 lane coverage, or L3 worker assignment before subagent dispatch.
---

# Bears Agents

## Purpose

Select Bears role coverage for graph-linked app-dev tasks and helper work.

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
      "helper_roles": ["<role>"],
      "task_ids": ["<task-id>"],
      "target_set": ["<path-or-target>"],
      "parallel_safe": true,
      "coverage_status": "covered|missing-role|conflict"
    }
  ]
}
```

## Rules

- Pick roles from task domain, target paths, graph refs, and proof requirements.
- Keep owner and critic roles separate when risk is non-trivial.
- Include helper roles for planning, instruction hardening, packet review, and closeout when bounded work exists.
- Maximize covered lanes across disjoint repo, path, target, generated-artifact, cache, and evidence-output sets.
- Report `missing-role` instead of inventing authority.
- Report `conflict` when two lanes would write overlapping paths or generated outputs.
- Feed the packet to `subagents` and `app-dev` before subagent dispatch.
- Validation, test, audit, route, cache, cachebuster, quick-validate, and plugin-validate scripts belong to pre-commit autoCI; agents do not run them manually.
