---
name: platform-role-governance
description: "Use before broad Bears platform, compatibility migration routing, Kubernetes deploy-core, Android emulator, Sentry/observability, product app-zone, plugin governance, or subagent delegation work to enforce the canonical plugins/bears role gate and ROLE_COVERAGE_BLOCKER policy."
---

# Platform Role Governance

This is the canonical Bears plugin-owned platform role gate. Use it before compatibility migration routing, platform-part, product app-zone, deploy, runtime, migration, or subagent handoff work.

## Workflow

1. Read `/srv/bears/plugins/bears/AGENTS.md`, `assets/catalog/platform-role-catalog.v1.json`, and `assets/catalog/role-gate-methodology.v1.json`.
2. Route the requested target with:
   - `python3 /srv/bears/plugins/bears/scripts/platform_roles.py route <target>`
3. Audit the same target before implementation handoff:
   - `python3 /srv/bears/plugins/bears/scripts/platform_roles.py audit <target>`
4. Cite local-commit-owned methodology drift validation after role-gate edits:
   - Local commit validation owns `python3 /srv/bears/plugins/bears/scripts/role_gate_methodology.py validate`; manual execution requires operator approval.
5. For compatibility-route drift, also route and audit these targets before handoff:
   - `/srv/bears/dev`
   - `kube`
   - `android-emulator`
   - `sentry`
   - `/srv/bears/dev/app`
   - `BearsCLOUD/apps`
   - `/srv/bears/dev/app/apps`
   - `/srv/bears/dev/apps`
   - `/srv/bears/dev/products/theants`
   - `/srv/bears/projects/theants`
6. If the route/audit matches, use the returned primary specialist or helper role and keep writes inside its allowed scope.
7. If the route/audit returns `ROLE_COVERAGE_BLOCKER`, stop product/platform/runtime/deploy/migration edits. The only allowed next actions are primary-role creation/refinement, exact catalog mapping, validator updates, and forward-test evidence.
8. Preserve spine order: `auth_core -> bears_gateway -> cd_deploy_stage`.
9. Treat `/srv/bears/dev` as a compatibility migration reference. Treat `/srv/bears/projects` as a deprecated transitional source; neither path can authorize child implementation through parent-scope fallback.

## Exact compatibility and platform targets

- `/srv/bears/dev` routes to workspace governance only.
- `/srv/bears/dev/control`, `/srv/bears/dev/platform`, `/srv/bears/dev/products`, `/srv/bears/dev/quality`, `/srv/bears/dev/infrastructure`, and `/srv/bears/dev/ops` are group classifiers; they require a narrower concrete layer.
- `kube`, `kubernetes`, `bears-infra`, and `/srv/bears/kubernetes` route to the Kubernetes repo boundary.
- `android-emulator` routes to The Ants emulator platform `.225` lane.
- `sentry` routes to the `.226` Sentry/observability future lane.
- `/srv/bears/dev/app` and `BearsCLOUD/apps` route to the canonical product-app monorepo root. `/srv/bears/dev/products/theants` and `/srv/bears/projects/theants` are legacy migration/archive inputs only. `/srv/bears/dev/app/apps` and `/srv/bears/dev/apps` must stay unmapped.
- `/srv/bears/dev/registry/projects.v1.json` routes to workspace governance and may provide compatibility evidence for App Target Gate.
- The former target checklist skill is removed from active discovery; use App Target Gate inside `app-*`.
- `subagent-orchestration-policy` routes to the non-product stage-boundary audit policy; legacy post-task wording is alias-only.

## Project artifact gate

Before App Target Gate uses compatibility registry evidence for a `/srv/bears` path:

```bash
cd /srv/bears/plugins/bears
python3 scripts/project_registry_gate.py gate <target-path>
```

If the path is absent from `/srv/bears/dev/registry/projects.v1.json`, return `PROJECT_REGISTRATION_BLOCKER` and do not create target artifacts.

## Non-product closeout gate

For non-product work outside a registered product repo, run the stage-boundary audits required by `assets/catalog/subagent-orchestration-policy.v1.json` before the final report. Accept old post-task wording only as an alias.

When the operator requests subagent mode, keep the main agent orchestration-only. Use lower reasoning than the main agent where appropriate, but keep child reasoning at medium or higher. Nested child spawning is allowed only for the explicit delegation-controller roles in the subagent policy:

- `bears-deploy-platform-engineer` for Kubernetes, Proxmox read-only evidence, network evidence, runtime verification, and rollback review lanes.
- `bears-subagent-orchestration-engineer` for plugin policy, validator, docs placement, and restricted-data safety review lanes.
- `bears-platform-role-governor` for route audit, registry consistency audit, registered-target checklist gate review, and user-information placement lanes.

## Compatibility

`bears-telegram-workflow` is a Telegram workflow skill bundle inside this canonical plugin. Do not recreate a standalone Telegram plugin, product app, connector, MCP server, or runtime surface.

See `references/missing-role-blocker.md` for the standard blocker wording and decomposition rules.
