# Old backlog reconciliation

This surface closes #411.

## Rule
Old issues are closed only when the reconciliation row contains exact proof commit or proof path. Issues without proof stay open as `phase_2`, `blocked`, `manual_review`, `partial`, or `out_of_scope`.

## Commands
- `scripts/old_backlog_reconciliation.py build --json`
- `scripts/old_backlog_reconciliation.py validate`
- `scripts/old_backlog_reconciliation.py doctor --json`

Runtime evidence path: `runtime/issue-reconciliation/old-open-backlog.v1.json`.
