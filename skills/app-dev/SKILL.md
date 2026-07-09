---
name: app-dev
description: Run Bears app development orchestration from ready graph-linked ledger tasks. Use when Codex must dispatch L2 lanes, L3 workers, and critics through subagents for dependency-ready waves without inventing tasks outside the ledger.
---

# App Dev

## Purpose

Execute only ready ledger tasks that have valid functional graph references.

## Inputs

- `docs/app-task-ledger.v1.json`
- `docs/app-functional-graph.v1.json`
- `waves/<wave-id>/plan.md`
- `waves/<wave-id>/spec.md`
- Role coverage from `bears-agents`.

## Orchestration model

- `L1`: parent coordinator selects ready waves and closes the wave.
- `L2`: lane orchestrator owns one wave partition with non-overlapping target paths.
- `L3`: worker or critic owns one bounded task packet.

## Dispatch packet

Each L3 packet must include:

- `task_id`
- `wave_id`
- `functionality_refs`
- `graph_node_refs`
- `target_paths`
- `allowed_files`
- `owner_role`
- `dependencies`
- `definition_of_done`
- `proof_requirement`
- `ledger_update_contract`

## Rules

- Do not start a task with missing graph refs.
- Do not start a task whose dependencies are not closed.
- Do not run parallel lanes that write the same repo path or target set.
- Use `subagents` to start L2 and L3 work when the operator allows delegation in the current run.
- Use `bears-agents` before dispatch to select owner roles and critic roles.
- Close by updating ledger status and handing the wave back to `app-analyze`.
