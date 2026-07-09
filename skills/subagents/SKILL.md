---
name: subagents
description: Prepare bounded subagent delegation packets for Bears app-dev orchestration. Use when Codex must split ready ledger work into L2 lanes, L3 worker tasks, critic tasks, helper tasks, and completion criteria.
---

# Subagents

## Purpose

Create delegation packets for L2 lane orchestrators, L3 workers, critics, and helper subagents.

## Packet fields

- `role`
- `scope`
- `task_ids`
- `functionality_refs`
- `graph_node_refs`
- `repo`
- `target_set`
- `allowed_paths`
- `forbidden_paths`
- `inputs_to_read`
- `expected_edits_or_read_only_output`
- `completion_criteria`
- `autoCI_evidence_policy`
- `closeout_format`

## Rules

- Create a subagent packet for every bounded specialized work item.
- Use helper subagents for planning, role mapping, hardening, critique, and closeout when the helper scope is bounded.
- Maximize parallel packets across disjoint repo, path, target, generated-artifact, cache, and evidence-output sets.
- Keep write scopes disjoint across parallel packets.
- Include exact task ids and graph refs for app-dev work.
- Do not ask a subagent to infer missing product decisions.
- Require subagents to list changed files or state `read-only`.
- Tell subagents they are not alone in the codebase and must not revert parallel edits.
- Validation, test, audit, route, cache, cachebuster, quick-validate, and plugin-validate scripts belong to pre-commit autoCI; agents do not run them manually.
- Subagent closeout reads generated autoCI or local-commit-validation evidence only after it exists.
