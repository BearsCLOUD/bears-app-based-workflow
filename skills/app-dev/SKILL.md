---
name: app-dev
description: Run Bears app development orchestration from ready graph-linked ledger tasks. Use when Codex must prepare hardened dispatch packets and dispatch L2 lanes, L3 workers, and critics through subagents for dependency-ready waves without inventing tasks outside the ledger.
---

# App Dev

## Purpose

Execute only ready ledger tasks that have valid functional graph references.

## Inputs

- `docs/app-task-ledger.v1.json`
- `docs/app-functional-graph.v1.json`
- `waves/<wave-id>/plan.md`
- `waves/<wave-id>/spec.md`
- Role coverage from local Codex skills when available.

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

## Optional hardening pass

When the operator allows subagents in the current run, start one read-only `$instruction-hardening` subagent before dispatch. The packet must include the wave plan, candidate L2/L3 packets, target `AGENTS.md` or contracts, and completion criteria: return compressed packet text, removed-content summary, and authority or drift note.

## Rules

- Do not start a task with missing graph refs.
- Do not start a task whose dependencies are not closed.
- Do not run parallel lanes that write the same repo path or target set.
- Start L2 and L3 work only when the operator allows delegation in the current run.
- Select owner roles and critic roles before dispatch, using local Codex role skills when available.
- Instruction hardening must be read-only and must not create tasks, change product decisions, or override `AGENTS.md` and contracts.
- Close by updating ledger status and handing the wave back to `app-analyze`.
