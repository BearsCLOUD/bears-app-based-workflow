#!/usr/bin/env python3
"""GitOps workflow state gates for Bears deliveries."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CATALOG = PLUGIN_ROOT / "assets/catalog/gitops-workflow.v1.json"
SCHEMA = PLUGIN_ROOT / "assets/schemas/gitops-workflow.v1.schema.json"
REQUIRED_STATES = {"planned","committed","validated","synced","degraded","rollback_required","rolled_back","manual_review","closed"}
REQUIRED_SIGNALS = {"post_commit_validation_fail","cache_sync_missing","hook_proof_missing","diagnostics_failed","repo_routing_mismatch","tracked_runtime_file","release_gate_missing","authority_map_mismatch","stale_delivery_manifest","issue_closeout_failed","infra_evidence_missing","infra_evidence_stale","infra_validator_failed","infra_rollout_diagnostics_redaction_failed","infra_bundle_provenance_missing","infra_public_route_policy_failed","infra_runtime_egress_policy_failed","infra_runtime_health_policy_failed","infra_plugin_ref_unpinned"}
REQUIRED_COMMANDS = {
    "scripts/gitops_workflow.py validate",
    "scripts/gitops_workflow.py state --delivery-id <id> --json",
    "scripts/gitops_workflow.py transition --packet <path>",
    "scripts/gitops_degradation.py scan --delivery-id <id> --json",
    "scripts/gitops_degradation.py scan --delivery-id <id> --infra-evidence <path> --json",
    "scripts/gitops_degradation.py doctor --json",
}
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema

def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))

def catalog() -> dict[str, Any]:
    return load(CATALOG)

def validate_all() -> list[str]:
    data = catalog()
    errors = validate_json_schema(data, SCHEMA, "gitops-workflow")
    if set(data.get("states", [])) != REQUIRED_STATES:
        errors.append("states must equal issue #421 GitOps state set")
    if set(data.get("degradation_signals", [])) != REQUIRED_SIGNALS:
        errors.append("degradation_signals must equal issue #421 signal set")
    missing = sorted(REQUIRED_COMMANDS - set(data.get("commands", [])))
    errors.extend(f"missing command: {item}" for item in missing)
    transitions = data.get("transitions", [])
    for idx, row in enumerate(transitions):
        if row.get("from_state") not in REQUIRED_STATES:
            errors.append(f"transitions[{idx}] unknown from_state")
        if row.get("to_state") not in REQUIRED_STATES:
            errors.append(f"transitions[{idx}] unknown to_state")
    rollback = data.get("rollback_policy", {})
    for surface in ("workflow", "hook", "validation", "autostart"):
        if surface not in rollback.get("required_for_surfaces", []):
            errors.append(f"rollback_policy missing surface: {surface}")
    return sorted(set(errors))

def transition(packet: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    data = catalog()
    match = None
    for row in data.get("transitions", []):
        if row.get("from_state") == packet.get("from_state") and row.get("to_state") == packet.get("to_state") and row.get("guard") == packet.get("guard"):
            match = row
            break
    if not match:
        errors.append("transition is not allowed by gitops workflow catalog")
    else:
        missing = sorted(set(match.get("required_evidence", [])) - set(packet.get("evidence", packet.get("required_evidence", []))))
        errors.extend(f"missing evidence: {item}" for item in missing)
    if packet.get("to_state") == "closed" and packet.get("from_state") == "rollback_required":
        errors.append("rollback_required delivery cannot close without rolled_back state")
    if packet.get("to_state") == "closed" and packet.get("gitops_state") in {"degraded", "rollback_required"}:
        errors.append("degraded GitOps state blocks closeout")
    return {"schema":"bears-gitops-transition-result.v1", "status":"pass" if not errors else "blocked", "delivery_id":packet.get("delivery_id"), "from_state":packet.get("from_state"), "to_state":packet.get("to_state"), "errors":errors}

def delivery_manifest_path(delivery_id: str) -> Path:
    candidates = [
        PLUGIN_ROOT / "runtime/deliveries" / delivery_id / "delivery-manifest.v1.json",
        PLUGIN_ROOT / "runtime/deliveries" / f"{delivery_id}/delivery-manifest.v1.json",
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]

def state(delivery_id: str) -> dict[str, Any]:
    from scripts import gitops_degradation
    scan = gitops_degradation.scan(delivery_id)
    degraded = scan.get("status") == "degraded"
    manifest_path = delivery_manifest_path(delivery_id)
    evidence = {
        "delivery_manifest": str(manifest_path.relative_to(PLUGIN_ROOT)) if manifest_path.exists() else None,
        "degradation_events": scan.get("events", []),
    }
    state_value = "degraded" if degraded else ("committed" if not manifest_path.exists() else "synced")
    return {"schema":"bears-gitops-state.v1", "delivery_id":delivery_id, "gitops_state":state_value, "status":"blocked" if degraded else "pass", "evidence":evidence, "errors":scan.get("errors", [])}

def doctor() -> dict[str, Any]:
    errors = validate_all()
    return {"schema":"bears-gitops-workflow-doctor.v1", "status":"pass" if not errors else "fail", "errors":errors, "states":sorted(REQUIRED_STATES), "degradation_signals":sorted(REQUIRED_SIGNALS)}

def print_json(packet: dict[str, Any]) -> None:
    print(json.dumps(packet, indent=2, sort_keys=True))

def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="cmd", required=True)
    v=sub.add_parser("validate"); v.add_argument("--json", action="store_true")
    s=sub.add_parser("state"); s.add_argument("--delivery-id", required=True); s.add_argument("--json", action="store_true")
    t=sub.add_parser("transition"); t.add_argument("--packet", required=True); t.add_argument("--json", action="store_true")
    d=sub.add_parser("doctor"); d.add_argument("--json", action="store_true")
    args=parser.parse_args(argv)
    if args.cmd == "validate":
        packet=doctor(); print_json(packet) if args.json else print(packet["status"]); return 0 if packet["status"]=="pass" else 1
    if args.cmd == "state":
        packet=state(args.delivery_id); print_json(packet) if args.json else print(packet["gitops_state"]); return 0 if packet["status"]=="pass" else 1
    if args.cmd == "transition":
        packet=transition(load(Path(args.packet))); print_json(packet) if args.json else print(packet["status"]); return 0 if packet["status"]=="pass" else 1
    if args.cmd == "doctor":
        packet=doctor(); print_json(packet) if args.json else print(packet["status"]); return 0 if packet["status"]=="pass" else 1
    return 2
if __name__ == "__main__":
    raise SystemExit(main())
