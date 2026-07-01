# Decision ledger

The decision ledger is the compact machine-readable record for governance-impacting changes in the `@Bears` plugin.

## Scope

`assets/catalog/decision-ledger.v1.json` stores redacted records for policy, workflow, role, schema, hook, validation, and artifact decisions.

## Blocking rules

- Every changed `assets/catalog/**`, `assets/schemas/**`, `hooks/**`, or `scripts/**` path needs one accepted decision record, except the ledger catalog itself.
- Accepted records must have empty `unresolved_inputs` and empty `contradictions`.
- Records must use `redaction: "safe"` and must not contain restricted markers.
- Missing or unsafe decisions block pre-commit and closeout for the affected scope.

## Commands

```bash
python3 scripts/decision_ledger.py validate
python3 scripts/decision_ledger.py check-required --staged
python3 scripts/decision_ledger.py emit-report --json
```

## Storage rule

Keep records compact. Store only issue, role, affected paths, decision, rationale, and unresolved/contradiction flags. Do not store secrets, raw logs, credentials, private chat text, or production data.
