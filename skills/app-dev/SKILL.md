---
name: app-dev
description: Run sequential Bears app development handoff from ready graph nodes with complete constitution, research, and plan lineage through role-matched subagents, critics, read-only hardening, and ledger updates.
---

# App Dev

## Purpose

Execute only ledger tasks whose graph nodes have complete lineage.

## Inputs

- `docs/app-task-ledger.v1.json`
- `docs/app-functional-graph.v1.json`
- `waves/<wave-id>/plan.md`
- `waves/<wave-id>/research.md`
- Role coverage from `subagents-roles`, `bears-agents`, and `subagents`.
- Read-only hardening output from `instruction-hardening`.

## Orchestration model

- `L1`: parent coordinator selects the next ready graph-backed task.
- `L2`: lane orchestrator owns one sequential handoff with bounded target paths.
- `L3`: worker or critic owns one bounded task packet.

## Dispatch packet

Each L3 packet must include:

- `task_id`
- `wave_id`
- `constitution_refs`
- `research_refs`
- `graph_node_refs`
- `target_paths`
- `allowed_files`
- `owner_role`
- `critic_role`
- `dependencies`
- `definition_of_done`
- `proof_requirement`
- `ledger_update_contract`
- `automation_evidence_policy`

## Rules

- Do not start a task with missing constitution refs, research refs, plan task refs, or graph refs.
- Do not start a task whose dependencies are not closed.
- Execute handoffs sequentially by default.
- Every implementation, integration, review, or critique handoff goes to a role-matched subagent with bounded scope when subagents are available.
- Select owner and critic roles before dispatch using `subagents-roles` and `bears-agents`.
- Use `subagents` to create dispatch packets before worker handoff.
- Instruction hardening must be read-only and must not create tasks, change functional decisions, run scripts, or override host policy.
- Do not ask agents to run validation, test, audit, route, cache, cachebuster, quick-validate, or plugin-validate scripts manually.
- Close by updating ledger status and handing the wave to `app-analyze`.
