---
name: app-dev
description: Run Bears app development orchestration from ready graph-linked ledger tasks through role-matched L2/L3 subagents, critics, read-only instruction hardening, and maximum disjoint parallel lanes.
---

# App Dev

## Purpose

Execute only ready ledger tasks that have valid functional graph references.

## Inputs

- `docs/app-task-ledger.v1.json`
- `docs/app-functional-graph.v1.json`
- `waves/<wave-id>/plan.md`
- `waves/<wave-id>/spec.md`
- Role coverage from plugin skills `subagents-roles`, `bears-agents`, and `subagents`.
- Read-only hardening output from `instruction-hardening`.

## Orchestration model

- `L1`: parent coordinator selects ready waves, assigns role coverage, integrates results, and closes the wave.
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
- `critic_role`
- `dependencies`
- `definition_of_done`
- `proof_requirement`
- `ledger_update_contract`
- `autoCI_evidence_policy`

## Hardening pass

Start one read-only `$instruction-hardening` subagent before dispatch. The packet must include the wave plan, candidate L2/L3 packets, target `AGENTS.md` or contracts, and completion criteria: return compressed packet text, removed-content summary, and authority or drift note.

## Rules

- Do not start a task with missing graph refs.
- Do not start a task whose dependencies are not closed.
- Every specific implementation, integration, review, or critique task goes to a role-matched subagent with bounded scope.
- Helper subagents support planning, dispatch-packet creation, review, and closeout.
- Maximize parallel L2/L3 execution across disjoint repo, path, and target sets.
- Do not run parallel lanes that share files, generated artifacts, caches, or evidence outputs.
- Select owner roles and critic roles before dispatch using plugin skills `subagents-roles` and `bears-agents`.
- Use `subagents` to create L2/L3 packets before worker dispatch.
- Instruction hardening must be read-only and must not create tasks, change product decisions, run scripts, or override `AGENTS.md` and contracts.
- Validation, test, audit, route, cache, cachebuster, quick-validate, and plugin-validate scripts belong to pre-commit autoCI; agents do not run them manually.
- After commits, read generated autoCI or local-commit-validation evidence only if it exists, then fix known failures in owned files.
- Close by updating ledger status and handing the wave back to `app-analyze`.
