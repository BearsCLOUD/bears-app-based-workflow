---
name: subagents
description: Prepare bounded sequential subagent delegation packets for Bears app-dev orchestration. Use when Codex must turn ready graph-backed ledger tasks into L2/L3 worker, critic, helper, and completion-criteria packets.
---

# Subagents

## Purpose

Create delegation packets for sequential L2 lane orchestrators, L3 workers, critics, and helper subagents.

## Packet fields

- `role`
- `scope`
- `handoff_order`
- `task_ids`
- `constitution_refs`
- `research_refs`
- `graph_node_refs`
- `repo`
- `target_set`
- `allowed_paths`
- `forbidden_paths`
- `inputs_to_read`
- `expected_edits_or_read_only_output`
- `completion_criteria`
- `automation_evidence_policy`
- `closeout_format`

## Rules

- Create a subagent packet for every bounded specialized handoff.
- Keep handoffs sequential unless a later plugin version explicitly changes the workflow contract.
- Include exact task ids, constitution refs, research refs, and graph refs for app-dev work.
- Do not ask a subagent to infer missing functional decisions.
- Require subagents to list changed files or state `read-only`.
- Tell subagents they are not alone in the codebase and must not revert external edits.
- Do not change functional truth, task scope, graph ids, or dependency order.
- Do not ask agents to run validation, test, audit, route, cache, cachebuster, quick-validate, or plugin-validate scripts manually.
- Subagent closeout reads generated automation evidence only after it exists.
