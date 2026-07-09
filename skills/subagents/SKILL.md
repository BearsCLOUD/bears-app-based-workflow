---
name: subagents
description: Prepare bounded sequential subagent delegation packets for Bears app-dev orchestration. Use when Codex must turn one ready graph-backed ledger task into an L2/L3 worker, critic, helper, or completion-criteria packet.
---

# Subagents

## Purpose

Create one `dispatch-packet.v1` for the current next sequential handoff.

## Packet fields

- `schema: dispatch-packet.v1`
- `role`
- `scope`
- `handoff_order`
- `task_id`
- `wave_id`
- `constitution_refs`
- `research_refs`
- `plan_task_refs`
- `graph_node_refs`
- `repo`
- `target_paths`
- `allowed_paths`
- `forbidden_paths`
- `owner_role`
- `critic_role`
- `dependencies`
- `inputs_to_read`
- `expected_edits_or_read_only_output`
- `completion_criteria`
- `automation_evidence_policy`
- `ledger_update_contract`
- `closeout_format`
- `drift_notes`
- `next_skill`

## Rules

- Create a subagent packet only for the current bounded specialized handoff, not for every possible future handoff.
- Keep handoffs sequential unless a later plugin version explicitly changes the workflow contract.
- Include exact task ids, constitution refs, research refs, plan task refs, and graph refs for app-dev work.
- Do not ask a subagent to infer missing functional decisions.
- Require subagents to list changed files or state `read-only`.
- Tell subagents they are not alone in the codebase and must not revert external edits.
- Set `automation_evidence_policy` to existing generated evidence refs or `none-required`; do not ask for new validation tooling by default.
- Do not change functional truth, task scope, graph ids, or dependency order.
- Do not ask agents to run validation, test, audit, route, cache, cachebuster, quick-validate, or plugin-validate scripts manually.
- Subagent closeout reads generated automation evidence only after it exists.
