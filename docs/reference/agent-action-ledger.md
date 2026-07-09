# Agent Action Ledger

Canonical catalog: `assets/catalog/agent-action-ledger.v1.json`.

The ledger records assignment, tool evidence, changed files, validation results, closeout status, and blockers from metadata-only runtime packets. It rejects missing heartbeat packets, closeout packets without validation, forbidden action records, and restricted-data markers.

Commands:

```bash
python3 scripts/agent_action_ledger.py validate
python3 scripts/agent_action_ledger.py collect --runtime-dir <dir>
python3 scripts/agent_action_ledger.py render-markdown --runtime-dir <dir> --out <file>
```
