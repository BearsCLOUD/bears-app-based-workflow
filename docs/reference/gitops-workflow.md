# GitOps workflow gates

`gitops_workflow` is the machine gate for @bears delivery state.

## States

`planned`, `committed`, `validated`, `synced`, `degraded`, `rollback_required`, `rolled_back`, `manual_review`, `closed`.

## Degradation signals

`gitops_degradation scan` emits bounded JSON events for missing cache sync, missing hook proof, failed validation, routing mismatch, tracked runtime files, release gate gaps, authority mismatch, stale manifest, and issue closeout failure.

## Closeout rule

A delivery in `degraded` or `rollback_required` cannot close. Workflow, hook, validation, and autostart mutations require rollback policy evidence before closeout.

## Commands

```text
scripts/gitops_workflow.py validate
scripts/gitops_workflow.py state --delivery-id <id> --json
scripts/gitops_workflow.py transition --packet <path>
scripts/gitops_degradation.py scan --delivery-id <id> --json
scripts/gitops_degradation.py doctor --json
```
