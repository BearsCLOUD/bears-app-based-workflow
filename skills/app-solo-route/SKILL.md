---
name: app-solo-route
description: Route one DIRECT primary through app workflow v3 to audited, waiting, or blocked.
---

# App Solo Route

## Boundary

Run only for a `DIRECT` workstream and keep the same primary as the owner of every stage.

Never enter `$subagents` or create an L2 or L3 from this route.

Resolve schemas, statuses, targets, and transitions only from `contracts/app-stage-handoff.v4.schema.json` and `contracts/app-workflow-definition.v3.json`.

## Procedure

1. Invoke `$app-context-index` and bind the run to its current build and source snapshot.
2. Resume the earliest incomplete stage in workflow order: constitution, research, specification, functional graph, plan, development, and semantic analysis.
3. Require each stage to call `app-graph.handoff_validate` and return the validated build-bound `app-stage-handoff.v4`.
4. Reject a stale build, invalid status-target pair, missing causal ref, missing stage payload, or incomplete paged result.
5. Stop on `waiting` when its handoff fingerprint is unchanged, on `blocked`, or on a product decision that requires user input.
6. Continue corrective `needs-*` routes only to the target declared by workflow v3.
7. Stop successfully only on `audited` with a complete `app-semantic-analysis-result.v1` and every audited-gate count at zero.

Require the primary stage owner to record only native v3 events that occurred and to reconcile the journal before every outgoing handoff.
