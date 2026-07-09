---
name: subagents-roles
description: Map Bears workflow tasks to subagent roles. Use when L2 or L3 packets need role selection, role boundaries, critic coverage, helper coverage, or conflict checks before app-dev dispatch.
---

# Subagents Roles

## Purpose

Map graph-linked work to owner roles, critic roles, helper roles, and lane boundaries.

## Role packet

Return:

- `task_id`
- `domain`
- `owner_role`
- `critic_role`
- `helper_roles`
- `lane`
- `path_scope`
- `target_set`
- `parallel_safe`
- `role_gap`

## Rules

- Choose the narrowest role that matches the target paths and behavior.
- Assign a critic role for security, data, auth, payment, deployment, cross-service, or instruction-authority risk.
- Assign helper roles for planning, hardening, critique, closeout, or evidence reading when the scope is bounded.
- Mark `parallel_safe: true` only when repo, paths, generated artifacts, caches, and evidence outputs do not overlap.
- Mark `parallel_safe: false` when any target path or generated output overlaps.
- Mark `role_gap` instead of assigning an unrelated role.
- Feed results to `bears-agents` and `app-dev`.
- Validation, test, audit, route, cache, cachebuster, quick-validate, and plugin-validate scripts belong to pre-commit autoCI; agents do not run them manually.
