# Roadmap State Transition Authority

Issue: #517.

`workflow_roadmap.py reconcile` must not promote roadmap nodes to `validated` only because files listed in `evidence_paths[]` exist.

Rules:

- `manual_review` and `disabled` autostart policies are preserved.
- Seller, cutover, migration, GitLab, production-data, DNS, credential, kubeconfig, rollback, destructive, and imported-repo nodes require manual review.
- File existence is evidence of a path only; it is not transition authority.
- `validated` requires a typed transition packet: `bears-roadmap-state-transition-authority-transition.v1`.
- Reconcile reports blocked transitions instead of silently rewriting unsafe state.

Transition packet contract:

- `schema`: `bears-roadmap-state-transition-authority-transition.v1`.
- `status`: `pass`.
- `node_id`, `issue_ref`, and `from_state` must match the current roadmap node.
- `to_state` must be `validated`.
- `source_hash` must match the current roadmap node hash.
- `validator_command_result.status` must be `pass`.
- `required_gate_refs[]` must name the checks that produced the packet.

Commands:

```bash
python3 scripts/roadmap_state_transition_authority.py validate
python3 scripts/roadmap_state_transition_authority.py reconcile-check --roadmap assets/catalog/workflow-roadmap.v1.json --json
python3 scripts/roadmap_state_transition_authority.py doctor --json
cp assets/catalog/workflow-roadmap.v1.json /tmp/workflow-roadmap.reconcile-check.json
python3 scripts/workflow_roadmap.py --roadmap /tmp/workflow-roadmap.reconcile-check.json reconcile --json
python3 scripts/workflow_roadmap.py validate
```

## Resource-conflict authority

`resource_conflict_status` is optional in the roadmap schema, but required before any evidence-backed node becomes `validated` or executable-ready through `next --json`.

Allowed packet on a node:

```json
{
  "resource_conflict_status": {
    "status": "allow",
    "mode": "exclusive",
    "checked_ref": "resource-conflict:<packet-or-validator>",
    "gate_refs": ["resource-conflict:<allow-proof>"],
    "active_elsewhere": false,
    "approval_refs": ["approval:<ref>"],
    "evidence_refs": ["evidence:<ref>"]
  }
}
```

Blocking reasons:

- `missing_resource_conflict_status` — no resource gate or no gate refs.
- `stale_resource_conflict_status` — resource gate is stale.
- `blocked_resource_conflict_status` — resource gate blocks the transition.
- `exclusive_resource_active_elsewhere` — exclusive resource is still active elsewhere.

Hazard nodes require both `resource_conflict_status.status == "allow"` and a valid transition packet with approval/evidence gate refs.
