---
name: bears-deploy-gate
description: "Use to assess deploy, rollback, runtime, and secret impact for Bears workflow-overlay changes; emits or validates deploy-gate JSON before report-first review."
---

# Bears Deploy Gate

Use this skill before Bears workflow-overlay changes that may affect deploy behavior, runtime surfaces, rollback complexity, or secret handling.

This skill does not mutate deploy state. It is report-first and advisory unless a role gate returns `ROLE_COVERAGE_BLOCKER` or a higher-priority/user instruction stops the work.

## Workflow

1. Classify scope as `overlay-only`, `workspace-control`, `project-local`, or `cross-project`.
2. Rate deploy, rollback, secret, and runtime impact as `none`, `low`, `medium`, or `high`; rollback may also be `required`.
3. Confirm that no secrets, `.env` values, production data, raw logs, or raw VPN configs are introduced.
4. Emit JSON first using the `bears-workflow-overlay.deploy-gate` shape.
5. Validate existing packets against `schemas/deploy-gate.schema.json` when that schema is available.
6. Recommend exact validation and rollback notes.
7. Optionally add a short Markdown summary after the JSON.

## Kubernetes deploy-core rule

Kubernetes deploy-core policy is split into two machine-readable contracts owned by `@Bears`:

1. Git policy: `assets/catalog/git-deploy-contract.v1.json` owns branch, merge-request, and target mapping.
2. CD policy: `assets/catalog/cd-kube-deploy-contract.v1.json` owns what deploys, from where, and the ordered Kubernetes actions.
3. Executor: `scripts/bears_auto_cd.py` runs only the fixed local `@Bears` CD sequence from `main`.
   The ordered sequence is `build_local_image` -> `load_local_image_to_k3d` -> `local_cd` apply -> rollout evidence.
4. Production Kubernetes mutation is allowed only from the local `@Bears` CD path after the Git contract resolves the `main` target.
   Runner `kubectl` path setup is executor-owned; agents must not discover kube tool paths or use manual `kubectl apply` as PASS evidence.
5. The CD contract must not contain merge policy, branch policy, pull-request policy, or manual approval gates.
6. Human control for production promotion is the Git merge request from `dev` to `main`; it is not a CD contract field.

If any contract, role route, manifest safety check, or required CI secret is missing, mark only the dependent deploy step blocked. Governance docs, route mappings, validators, tests, and future-lane registrations may continue inside their exact roles.

## JSON artifact

Emit or validate this JSON artifact first:

```json
{
  "schema": "bears-workflow-overlay.deploy-gate",
  "version": "1",
  "status": "not-applicable",
  "scope": "overlay-only",
  "impact": {
    "deploy": "none",
    "rollback": "none",
    "secret": "none",
    "runtime": "none"
  },
  "risk_owner": "Bears workflow-overlay platform engineer",
  "rollback_plan": "Revert the bounded Telegram skill-bundle file changes if validation fails.",
  "approvals": [],
  "evidence": [
    "/srv/bears/plugins/bears/README.md"
  ]
}
```

Prefer `not-applicable` for skill, README, template, or workflow-only edits with no runtime effect. Use `needs-review` when impact is uncertain. Use `blocked` only for a propagated `ROLE_COVERAGE_BLOCKER` or explicit stop.

## Report rules

- Put the JSON packet before prose.
- Separate deploy impact from validation failures; a failed local validation is not a production deploy impact by itself.
- Do not add app connector, MCP, secret, `.env`, production-data, raw logs, kubeconfig output, or raw VPN-config behavior.
