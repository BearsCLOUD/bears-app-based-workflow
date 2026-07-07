---
name: bears-blocker-eval
description: "Classify plugin/non-app Bears workflow-overlay risks, blockers, and unblock paths; emit or validate blocker-review JSON and never act as an app workflow gate."
---

# Bears Blocker Eval

Required: activate this skill only for plugin/non-app workflow-overlay work when raw failure signals, scope concerns, missing artifacts, or risk claims must be separated into true blockers versus advisory risks. App workflow findings belong to `$app-analyze`.

This skill is report-first. It must not stop work by itself unless it is propagating a file-backed `ROLE_COVERAGE_BLOCKER` from the role gate or an explicit higher-priority/user stop.

## Boundary

Do not activate this skill as an app gate, app PASS source, app execution blocker, or replacement for `app-plan`/`app-analyze`.

## Workflow

1. Collect the smallest evidence set for each reported issue.
2. Classify each issue with the blocker taxonomy: `access`, `coverage`, `artifacts`, `runtime`, `abuse`, or `spec`.
3. Mark ordinary implementation risk as advisory `review`, not `blocked`.
4. Emit JSON first using the `bears-workflow-overlay.blocker-review` shape.
5. Validate existing packets against `schemas/blocker-review.schema.json` when that schema is available.
6. Include the minimum reversible unblock action for every blocker or review item.
7. Optionally add a short Markdown summary after the JSON.

## JSON artifact

Emit or validate this JSON artifact first:

```json
{
  "schema": "bears-workflow-overlay.blocker-review",
  "version": "1",
  "status": "review",
  "reviewer": "bears-blocker-eval",
  "blockers": [
    {
      "code": "BOUNDARY_REVIEW_REQUIRED",
      "taxonomy": "artifacts",
      "severity": "medium",
      "description": "Overlay boundary evidence must be inspected before changing shared workflow artifacts.",
      "mitigation": "Read the plugin README and source-boundary contract, then continue with bounded edits."
    }
  ],
  "evidence": [
    "README.md"
  ],
  "recommendation": "Treat as advisory unless a role gate returns ROLE_COVERAGE_BLOCKER."
}
```

Return `status: blocked` only for a propagated `ROLE_COVERAGE_BLOCKER`, explicit user stop, or higher-priority instruction stop. Return `clean`, `review`, or `waived` for non-blocking outcomes.

## Report rules

- Put the JSON packet before prose.
- Do not convert weak evidence, speculation, lint failures, or ordinary risks into hard blockers.
- Do not propose app connector, MCP, production deploy, secret, `.env`, production-data, or raw VPN-config changes.
