# Policy invariants

`policy_invariants.py` is the read-only policy gate for Bears closeout and audit safety.

## Commands

```bash
python3 scripts/policy_invariants.py validate
python3 scripts/policy_invariants.py evaluate --input tests/fixtures/policy_invariants/good/pass.json --json
python3 scripts/policy_invariants.py evaluate-closeout --from-git HEAD^..HEAD --json
```

## Blocking rules

- Solved covered issue must not remain open.
- `partial`, `manual_review`, `blocked`, and `out_of_scope` issues must not be auto-closed.
- Behavior-changing files require release-note or changelog coverage.
- Governance files require an accepted decision-ledger record.
- Audit packets must not contain forbidden raw data markers.

`bears_doctor validate-closeout` calls this gate through the `policy_invariants` guard.
