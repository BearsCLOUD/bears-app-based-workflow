---
name: subagents-roles
description: Map graph-backed Bears workflow tasks to self-contained sequential owner, critic, and helper roles. Use when a dispatch packet needs role selection, role boundaries, critic coverage, helper coverage, or conflict checks before app-dev handoff.
---

# Subagents Roles

## Purpose

Confirm graph-backed work roles using `docs/role-catalog.md`. Do not require an external role inventory.

## Role packet

Return `role-packet.v1` with:

- `schema: role-packet.v1`
- `wave_id`
- `task_id`
- `constitution_refs`
- `research_refs`
- `plan_task_refs`
- `graph_node_refs`
- `target_paths`
- `depends_on`
- `owner_role`
- `critic_role`
- `helper_roles`
- `role_gap`
- `sequential_ready`
- `next_skill`

## Rules

- Choose the narrowest role from `docs/role-catalog.md` that matches target paths and behavior.
- Confirm planned roles from the ledger when they fit the catalog and task risk.
- Assign a critic role for security, data, auth, payment, deployment, cross-service, or functional lineage risk.
- Assign helper roles for hardening, packet review, critique, closeout, or evidence reading when the scope is bounded.
- Mark `sequential_ready: true` only when dependencies are closed and lineage is complete.
- Mark `role_gap` instead of assigning an unrelated role.
- Feed results to `subagents` or directly to `app-dev` when subagents are unavailable.
- Do not change functional decisions, plan task scope, graph ids, dependency order, or execution constraints.
- Do not ask agents to run validation, test, audit, route, cache, cachebuster, quick-validate, or plugin-validate scripts manually.
