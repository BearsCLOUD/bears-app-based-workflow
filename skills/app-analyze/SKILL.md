---
name: app-analyze
description: Audit repo-scoped implementation convergence and route semantic or process findings without claiming product acceptance.
---

# App Analyze

## Boundary

Consume `app-stage-handoff.v3` and the exact build, snapshot, and journal digests it names. The functional map, ledger, sources, indexes, and journal are read-only during analysis. Semantic diagnostics do not execute tests and do not replace autoCI product acceptance.

## Procedure

1. Refresh `$app-context-index` and reject stale handoffs.
2. Run `$app-trace-audit` with profile `convergence`, following every opaque cursor to completion.
3. Run `$app-process-audit` with profile `terminal`, following every opaque cursor to completion.
4. Gather every finding in one bounded result and route it: missing source to `needs-research`; product or decision conflict to `needs-spec`; semantic ref or cycle gap to `needs-graph`; task, implementation, evidence, review, or remediation gap to `needs-plan`; credential, access, or operator stop to `blocked`.
5. When findings are routable, return the canonical remediation handoff and let `app-plan` create or update ledger tasks. Repeat after remediation.
6. Emit `audited` only for the exact snapshot when both audits are complete, no result is truncated, no routable finding remains, and no remediation task is open. Validate the transition, record the actual terminal event, compile once more, and return a build-bound handoff.

`audited` means only that structured semantics and recorded process agree. Preserve independent `automation_status: unavailable|not_run|passed|failed`; only autoCI owns product acceptance.
