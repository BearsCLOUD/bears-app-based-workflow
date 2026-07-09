---
name: app-dev
description: Run sequential Bears app development handoff from ready graph nodes with complete constitution, research, and plan lineage through role-matched packets, optional subagents, read-only hardening, and ledger updates.
---

# App Dev

## Purpose

Execute only ledger tasks whose graph nodes have complete lineage.

## Inputs

- `docs/app-task-ledger.v1.json`
- `docs/app-functional-graph.v1.json`
- `waves/<wave-id>/plan.md`
- `waves/<wave-id>/research.md`
- `docs/role-catalog.md`
- Optional `role-packet.v1`, `dispatch-packet.v1`, and `hardening-output.v1` support packets.

## Orchestration model

- `L1`: parent coordinator selects the next ready graph-backed task.
- `L2`: one sequential handoff with bounded target paths.
- `L3`: worker or critic owns one bounded task packet when subagents are available.

## Dispatch packet

Each packet must include:

- `schema: dispatch-packet.v1`
- `role`
- `scope`
- `handoff_order`
- `wave_id`
- `task_id`
- `constitution_refs`
- `research_refs`
- `plan_task_refs`
- `graph_node_refs`
- `target_paths`
- `allowed_paths`
- `forbidden_paths`
- `owner_role`
- `critic_role`
- `dependencies`
- `inputs_to_read`
- `expected_edits_or_read_only_output`
- `completion_criteria`
- `definition_of_done`
- `proof_requirement`
- `automation_evidence_policy`
- `ledger_update_contract`
- `closeout_format`
- `drift_notes`
- `next_skill`

## Rules

- Do not start a task with missing constitution refs, research refs, plan task refs, or graph refs.
- Do not start a task whose dependencies are not closed.
- Execute handoffs sequentially by default.
- Confirm owner and critic roles with `subagents-roles` before dispatch.
- Use `subagents` to create one bounded dispatch packet for the current next task.
- If subagents are unavailable, execute the same packet locally and record the fallback in closeout.
- Instruction hardening must be read-only and must not create tasks, change functional decisions, run scripts, or override execution constraints.
- `automation_evidence_policy` may reference existing generated automation evidence or say `none-required`; it must not request new validation tooling by default.
- Do not ask agents to run validation, test, audit, route, cache, cachebuster, quick-validate, or plugin-validate scripts manually.
- Close by updating ledger status and handing the wave to `app-analyze`.
