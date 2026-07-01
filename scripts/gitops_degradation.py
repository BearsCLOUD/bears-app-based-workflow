#!/usr/bin/env python3
"""Emit bounded GitOps degradation events for Bears deliveries."""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
EVENT_SCHEMA = PLUGIN_ROOT / "assets/schemas/gitops-degradation-event.v1.schema.json"
CATALOG = PLUGIN_ROOT / "assets/catalog/gitops-workflow.v1.json"
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema

def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))

def rel(path: Path) -> str:
    try:
        return str(path.relative_to(PLUGIN_ROOT))
    except ValueError:
        return str(path)

def git_head() -> str | None:
    proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(PLUGIN_ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=20)
    return proc.stdout.strip() if proc.returncode == 0 and proc.stdout.strip() else None

def delivery_manifest_path(delivery_id: str, root: Path = PLUGIN_ROOT) -> Path:
    return root / "runtime/deliveries" / delivery_id / "delivery-manifest.v1.json"

def event(delivery_id: str, signal: str, remediation: str, *, commit_sha: str | None, errors: list[str], root: Path = PLUGIN_ROOT) -> dict[str, Any]:
    manifest = delivery_manifest_path(delivery_id, root)
    ledger = root / "runtime/commit-usage-ledger" / f"{commit_sha or 'unknown'}.json"
    return {
        "schema": "bears-gitops-degradation-event.v1",
        "event_id": f"{delivery_id}:{signal}",
        "delivery_id": delivery_id,
        "commit_sha": commit_sha,
        "signal": signal,
        "gitops_state": "degraded",
        "remediation": remediation,
        "delivery_manifest": rel(manifest),
        "commit_usage_ledger": rel(ledger),
        "evidence_paths": [rel(manifest), rel(ledger)],
        "errors": errors,
    }

def scan(delivery_id: str, *, root: Path = PLUGIN_ROOT, infra_evidence: Path | None = None) -> dict[str, Any]:
    catalog = load(CATALOG)
    remediation = catalog.get("remediation_policy", {})
    commit_sha = git_head() if root == PLUGIN_ROOT else None
    events: list[dict[str, Any]] = []
    manifest = delivery_manifest_path(delivery_id, root)
    if not manifest.exists():
        events.append(event(delivery_id, "stale_delivery_manifest", remediation.get("stale_delivery_manifest", "retry"), commit_sha=commit_sha, errors=["delivery manifest missing"], root=root))
    cache = root / "runtime/plugin-cache-sync/plugin-cache-sync-state.v1.json"
    if not cache.exists():
        events.append(event(delivery_id, "cache_sync_missing", remediation.get("cache_sync_missing", "retry"), commit_sha=commit_sha, errors=["plugin cache sync state missing"], root=root))
    hook = root / "runtime/effective-hooks/plugins_bears/effective-hooks-proof.v1.json"
    if not hook.exists():
        events.append(event(delivery_id, "hook_proof_missing", remediation.get("hook_proof_missing", "manual_review"), commit_sha=commit_sha, errors=["effective hook proof missing"], root=root))
    if infra_evidence is not None:
        from scripts import cross_repo_infra_evidence
        infra_packet = load(infra_evidence)
        infra_result = cross_repo_infra_evidence.to_degradation(infra_packet)
        events.extend(infra_result.get("events", []))
    for row in events:
        row_errors = validate_json_schema(row, EVENT_SCHEMA, row["event_id"])
        row.setdefault("errors", []).extend(row_errors)
    errors = [err for row in events for err in row.get("errors", [])]
    return {"schema":"bears-gitops-degradation-scan.v1", "delivery_id":delivery_id, "status":"degraded" if events else "pass", "events":events, "errors":errors}

def doctor() -> dict[str, Any]:
    from scripts import gitops_workflow
    errors = gitops_workflow.validate_all()
    return {"schema":"bears-gitops-degradation-doctor.v1", "status":"pass" if not errors else "fail", "errors":errors}

def print_json(packet: dict[str, Any]) -> None:
    print(json.dumps(packet, indent=2, sort_keys=True))

def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="cmd", required=True)
    s=sub.add_parser("scan"); s.add_argument("--delivery-id", required=True); s.add_argument("--root"); s.add_argument("--infra-evidence"); s.add_argument("--json", action="store_true")
    d=sub.add_parser("doctor"); d.add_argument("--json", action="store_true")
    args=parser.parse_args(argv)
    if args.cmd == "scan":
        packet=scan(args.delivery_id, root=Path(args.root).resolve() if args.root else PLUGIN_ROOT, infra_evidence=Path(args.infra_evidence).resolve() if args.infra_evidence else None); print_json(packet) if args.json else print(packet["status"]); return 0 if packet["status"]=="pass" else 1
    if args.cmd == "doctor":
        packet=doctor(); print_json(packet) if args.json else print(packet["status"]); return 0 if packet["status"]=="pass" else 1
    return 2
if __name__ == "__main__":
    raise SystemExit(main())
