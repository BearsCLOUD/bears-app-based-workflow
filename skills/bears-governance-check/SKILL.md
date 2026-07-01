---
name: bears-governance-check
description: "Use for Bears workflow-overlay governance routing checks before plugin, workflow, or project-boundary edits; emits or validates policy-packet JSON and a concise advisory summary."
---

# Bears Governance Check

Use this skill when a Bears workflow-overlay task must be routed to the correct workspace, project group, repository boundary, and artifact lane before edits begin.

Do not use it for product implementation, production runtime changes, app connectors, or MCP behavior. It is report-first and advisory unless the role gate reports `ROLE_COVERAGE_BLOCKER`.

## Workflow

1. Read the nearest `AGENTS.md`, the plugin README, and any explicit role packet or allowed-write packet.
2. Classify the task as one of: plugin, workflow, artifact, or role-gate governance.
3. Confirm owner, path, trust boundary, secret exposure, and validation lane from file-backed evidence.
4. Emit JSON first using the `bears-workflow-overlay.policy-packet` shape.
5. If an existing packet is provided, validate it against `schemas/policy-packet.schema.json` when that schema is available.
6. Optionally add a short Markdown summary after the JSON.

## JSON artifact

Emit or validate this JSON artifact first:

```json
{
  "schema": "bears-workflow-overlay.policy-packet",
  "version": "1",
  "status": "review",
  "project_router": "bears-governance-check",
  "policy_id": "workflow-overlay-boundary",
  "owner": {
    "name": "Bears Workspace",
    "team": "platform",
    "contact": "operator"
  },
  "scope": {
    "project_group": "platform",
    "artifact_type": "plugin"
  },
  "updated_at": "2026-06-03T00:00:00Z",
  "evidence": [
    "/srv/bears/AGENTS.md",
    "/srv/bears/plugins/bears/README.md"
  ],
  "recommendation": "Proceed with bounded overlay edits only."
}
```

Allowed `status` values come from the schema: `draft`, `review`, `approved`, `blocked`, or `deprecated`. Prefer `review` until required evidence is complete.

## Report rules

- Put the JSON packet before prose.
- Keep the Markdown summary to route, owner, validation lane, and unresolved risks.
- Do not mutate manifests, app definitions, connectors, MCP servers, secrets, `.env` files, production data, or raw VPN configs.
- Do not claim a blocker unless a role gate returns `ROLE_COVERAGE_BLOCKER` or a higher-priority instruction explicitly stops the work.
