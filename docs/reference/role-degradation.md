# Role degradation

This surface closes #420.

## Signals
The detector emits compact events for token regression, context growth, repeated validation failure, repeated fixer failure, invalid role output, scope violation, dirty scope, timeout regression, manual review growth, and same-issue retry loops.

## Commands
- `scripts/role_degradation.py scan --delivery-id <id> --json` checks current delivery surfaces.
- `scripts/role_degradation.py compare --base <sha> --head <sha> --json` converts usage regressions into degradation events.
- `scripts/role_remediation.py plan --event <path> --json` creates a bounded remediation plan.
- `scripts/role_remediation.py validate-plan --plan <path>` validates the plan.
- `scripts/role_degradation.py doctor --json` validates the catalog.

## Gate
Repeated fixer failure blocks auto-fix and requires manual review. Invalid role output requires an audit action before role/profile edits are accepted as material changes.
