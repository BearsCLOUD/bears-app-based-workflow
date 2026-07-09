---
name: subagents-roles
description: Map graph-backed Bears workflow tasks to sequential owner, critic, and helper roles. Use when a dispatch packet needs role selection, role boundaries, critic coverage, helper coverage, or conflict checks before app-dev handoff.
---

# Subagents Roles

## Purpose

Map graph-backed work to owner roles, critic roles, helper roles, and sequential handoff boundaries.

## Role packet

Return:

- `task_id`
- `constitution_refs`
- `research_refs`
- `graph_node_refs`
- `domain`
- `owner_role`
- `critic_role`
- `helper_roles`
- `handoff_order`
- `path_scope`
- `target_set`
- `sequential_ready`
- `role_gap`

## Rules

- Choose the narrowest role that matches the target paths and behavior.
- Assign a critic role for security, data, auth, payment, deployment, cross-service, or functional lineage risk.
- Assign helper roles for planning, hardening, critique, closeout, or evidence reading when the scope is bounded.
- Mark `sequential_ready: true` only when dependencies are closed and lineage is complete.
- Mark `role_gap` instead of assigning an unrelated role.
- Feed results to `bears-agents` and `subagents`.
- Do not change functional decisions, plan task scope, graph ids, or host policy.
- Do not ask agents to run validation, test, audit, route, cache, cachebuster, quick-validate, or plugin-validate scripts manually.
