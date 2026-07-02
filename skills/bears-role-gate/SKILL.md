---
name: bears-role-gate
description: "Use before Bears workflow-overlay edits that require platform role coverage; validates or emits role-coverage JSON and reports ROLE_COVERAGE_BLOCKER only when coverage is missing."
---

# Bears Role Gate

Canonical owner: `/srv/bears/plugins/bears`. `bears-telegram-workflow` is a Telegram workflow skill bundle inside this plugin, not a standalone plugin.

Use this skill before platform-facing Bears workflow-overlay work to prove that the requested platform part has a registered role and bounded write scope. It also checks compatibility routes under `/srv/bears/dev`, the canonical apps monorepo route `/srv/bears/dev/app` plus `BearsCLOUD/apps`, deprecated transitional sources under `/srv/bears/projects`, Kubernetes deploy-core work, Android emulator `.225`, Sentry/observability `.226`, and old app migration/archive surfaces.

This is the only MVP governance skill that can create a hard workflow stop by returning `ROLE_COVERAGE_BLOCKER`. If coverage exists, report advisory guidance and continue to the next gate.

## Workflow

1. Identify the route target from the role packet, owning path, platform part, and requested behavior.
2. Read the platform role catalog, role-gate methodology catalog, and relevant role file from file-backed evidence.
3. Run a deterministic role router when available, for example `python3 plugins/bears/scripts/platform_roles.py route <target>` from `/srv/bears`.
4. Run `python3 plugins/bears/scripts/platform_roles.py audit <target>` before any implementation handoff.
5. Local commit validation owns `python3 plugins/bears/scripts/role_gate_methodology.py validate` after methodology or catalog changes; manual execution requires operator approval.
6. Emit JSON first using the `bears-workflow-overlay.role-coverage` shape.
7. Validate existing packets against `schemas/role-coverage.schema.json` when that schema is available.
8. If no matching primary specialist or helper role exists, if only parent/group coverage exists, or if validation fails, return `ROLE_COVERAGE_BLOCKER` and stop implementation edits. The only allowed next actions are primary-role creation/refinement, exact catalog mapping, validator updates, and forward-test evidence.
9. Optionally add a short Markdown summary after the JSON.

## Compatibility route checks

For `/srv/bears/dev` compatibility routes or The Ants migration work, run these route and audit checks before handoff:

```bash
cd /srv/bears/plugins/bears
python3 scripts/platform_roles.py route /srv/bears/dev
python3 scripts/platform_roles.py audit /srv/bears/dev
python3 scripts/platform_roles.py route kube
python3 scripts/platform_roles.py audit kube
python3 scripts/platform_roles.py route android-emulator
python3 scripts/platform_roles.py audit android-emulator
python3 scripts/platform_roles.py route sentry
python3 scripts/platform_roles.py audit sentry
python3 scripts/platform_roles.py route /srv/bears/dev/app
python3 scripts/platform_roles.py audit /srv/bears/dev/app
python3 scripts/platform_roles.py route BearsCLOUD/apps
python3 scripts/platform_roles.py audit BearsCLOUD/apps
python3 scripts/platform_roles.py route /srv/bears/dev/app/apps
python3 scripts/platform_roles.py route /srv/bears/dev/apps
python3 scripts/platform_roles.py route /srv/bears/dev/products/theants
python3 scripts/platform_roles.py audit /srv/bears/dev/products/theants
python3 scripts/platform_roles.py route /srv/bears/projects/theants
python3 scripts/platform_roles.py audit /srv/bears/projects/theants
```

`/srv/bears/dev/app` plus `BearsCLOUD/apps` is the canonical product-app repo route. `/srv/bears/projects`, `/srv/bears/dev/products/*`, and old child app repositories are deprecated transitional or migration/archive sources. Parent/group coverage from them is not valid implementation coverage. The old `/srv/bears/projects/theants` path must route as legacy app-zone evidence, not as a separate canonical repository or Telegram runtime fallback.

## JSON artifact

Emit or validate this JSON artifact first:

```json
{
  "schema": "bears-workflow-overlay.role-coverage",
  "version": "1",
  "status": "ok",
  "route_target": "bears-workflow-overlay-plugin",
  "coverage_status": "complete",
  "roles": [
    {
      "name": "bears-workflow-overlay-controller",
      "covered": true,
      "owner": "Bears workflow-overlay plugin"
    }
  ],
  "evidence": [
    "/srv/bears/plugins/bears/assets/catalog/platform-role-catalog.v1.json",
    "/srv/bears/plugins/bears/agents/overlay-controller.toml"
  ],
  "recommendation": "Role coverage is present; continue with bounded overlay work."
}
```

For missing coverage, set `status` to `blocked`, `coverage_status` to `missing`, set the missing role with `covered: false`, and include the exact text `ROLE_COVERAGE_BLOCKER` in `recommendation` and the Markdown summary.

## Report rules

- Put the JSON packet before prose.
- Do not infer role coverage from memory; cite files or deterministic command output.
- Do not broaden work into product code, production deploys, app connectors, MCP servers, secrets, `.env` files, production data, or raw VPN configs.
