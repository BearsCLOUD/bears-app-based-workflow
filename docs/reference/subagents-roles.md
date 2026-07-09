# Subagents Roles Governance

`subagents-roles` is the @Bears governance surface for role route/audit, role-safe subagent handoff, and role-principle ledger coverage.

Canonical executable owner:
- `scripts/subagents_roles.py route <target>`
- `scripts/subagents_roles.py audit <target>`
- `scripts/subagents_roles.py ledger-refresh`
- `scripts/subagents_roles.py ledger-audit`
- `scripts/subagents_roles.py ledger-summary`

Manual execution is forbidden unless the operator names the exact command in the
current turn. `autoCI` or local commit validation owns route/audit and ledger
proof for normal agent work.

Tracked evidence:
- `docs/audits/subagents-roles/role-principle-ledger.v1.json`

The ledger stores metadata only: principle id, role profile, target files, executable consumer, executable owner, status, evidence ref, issue ref, and timestamp.
