# Cross-repo infra evidence adapter

Issue: #450.

The adapter converts sanitized `BearsCLOUD/bears-infra` OpenCode evidence packets into local GitOps degradation events.
It is read-only for `bears-infra`. It reads tracked JSON packets from a supplied repo root and never calls Kubernetes, secrets, runners, production resources, or live logs.

## Commands

```text
scripts/cross_repo_infra_evidence.py validate --packet <path> --json
scripts/cross_repo_infra_evidence.py scan --repo-root <path> --application opencode-server --json
scripts/cross_repo_infra_evidence.py to-degradation --packet <path> --json
scripts/cross_repo_infra_evidence.py doctor --json
scripts/gitops_degradation.py scan --delivery-id <id> --infra-evidence <path> --json
```

## Required source packets

| Issue | Packet type | Missing or failed signal |
| --- | --- | --- |
| #117 | `infra_validation_matrix` | `infra_evidence_missing` or `infra_validator_failed` |
| #118 | `opencode_bundle_provenance` | `infra_bundle_provenance_missing` or `infra_plugin_ref_unpinned` |
| #119 | `opencode_public_route_policy` | `infra_evidence_missing` or `infra_public_route_policy_failed` |
| #120 | `opencode_rollout_diagnostics` | `infra_evidence_missing` or `infra_rollout_diagnostics_redaction_failed` |
| #121 | `opencode_runtime_egress_policy` | `infra_evidence_missing` or `infra_runtime_egress_policy_failed` |
| #123 | `opencode_runtime_health_policy` | `infra_evidence_missing` or `infra_runtime_health_policy_failed` |

## Sanitization gate

The adapter rejects evidence containing kubeconfig, token, raw log, Secret manifest, `stringData`, private chat, or production data markers.
