---
name: subagents-roles
description: Map Bears workflow tasks to subagent roles. Use when L2 or L3 packets need role selection, role boundaries, critic coverage, or conflict checks before app-dev dispatch.
---

# Subagents Roles

## Purpose

Map graph-linked work to owner roles, critic roles, and lane boundaries.

## Role packet

Return:

- `task_id`
- `domain`
- `owner_role`
- `critic_role`
- `lane`
- `path_scope`
- `parallel_safe`
- `role_gap`

## Rules

- Choose the narrowest role that matches the target paths and behavior.
- Use a critic role for security, data, auth, payment, deployment, or cross-service risk.
- Mark `parallel_safe: false` when target paths overlap.
- Mark `role_gap` instead of assigning an unrelated role.
- Feed results to `bears-agents` or `app-dev`.
