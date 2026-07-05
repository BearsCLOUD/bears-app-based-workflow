---
name: subagents-roles
description: "Use before @Bears role, skill, subagent, plugin governance, compatibility routing, platform, app-zone, deploy, runtime, migration, or handoff work to run route/audit and maintain role-principle coverage."
---

# Subagents Roles Governance

`gate` means an automatic admission check. `autoCI` means an automatic verification line. `autoCD` means an automatic install, update, or deploy line.

This skill owns @Bears role routing, subagent-role coverage, role-principle ledger updates, and well-specified role artifacts.

## Workflow

1. Read `/srv/bears/plugins/bears/AGENTS.md`, `assets/catalog/platform-role-catalog.v1.json`, `assets/catalog/role-gate-methodology.v1.json`, and the target router.
2. Route the requested target:
   - `python3 /srv/bears/plugins/bears/scripts/subagents_roles.py route <target>`
3. Audit the same target before implementation handoff:
   - `python3 /srv/bears/plugins/bears/scripts/subagents_roles.py audit <target>`
4. When role principles or role profiles change, refresh and audit the ledger:
   - `python3 /srv/bears/plugins/bears/scripts/subagents_roles.py ledger-refresh`
   - `python3 /srv/bears/plugins/bears/scripts/subagents_roles.py ledger-audit`
5. Use the returned primary specialist or helper role and keep writes inside its allowed scope.
6. Preserve shared spine order: `auth_core -> bears_gateway -> cd_deploy_stage`.
7. Record missing role coverage as exact role/profile/catalog/ledger work with an issue ref when it cannot be completed in the current change.

## Principles

- `well_specified_agent_artifacts`: use `references/well-specified-artifacts.md` and `references/positive-planning-language.md`.
- `runtime_result_efficiency`: use `references/runtime-result-efficiency.md`.
- `repeatable_process_automation`: use `references/repeatable-process-automation.md`.
- `role_principle_ledger`: use `references/role-principle-ledger.md`.
- `role_start_packet`: use `references/role-start-packet.md`.

## Exact targets

- `/srv/bears/dev` routes to workspace governance only.
- `/srv/bears/dev/control`, `/srv/bears/dev/platform`, `/srv/bears/dev/products`, `/srv/bears/dev/quality`, `/srv/bears/dev/infrastructure`, and `/srv/bears/dev/ops` are group classifiers; route a narrower concrete layer for implementation.
- `kube`, `kubernetes`, `bears-infra`, and `/srv/bears/kubernetes` route to the Kubernetes repo boundary.
- `/srv/bears/dev/app` and `BearsCLOUD/apps` route to the product-app monorepo root.
- `subagent-orchestration-policy` routes to the non-product stage-boundary audit policy.

## Handoff

Return route target, matched primary role or exact coverage gap, supporting reviewer roles, allowed writes, evidence refs, ledger status, issue refs, and next owner.
