#!/usr/bin/env python3
"""Validate and adapt sanitized bears-infra evidence into GitOps degradation events."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = PLUGIN_ROOT / "assets/schemas/cross-repo-infra-evidence.v1.schema.json"
EVENT_SCHEMA = PLUGIN_ROOT / "assets/schemas/gitops-degradation-event.v1.schema.json"
CATALOG = PLUGIN_ROOT / "assets/catalog/cross-repo-infra-evidence.v1.json"
GITOPS_CATALOG = PLUGIN_ROOT / "assets/catalog/gitops-workflow.v1.json"
SOURCE_REPO = "BearsCLOUD/bears-infra"
DEFAULT_DELIVERY_ID = "bears-governance-kernel-v1"

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def print_json(packet: dict[str, Any]) -> None:
    print(json.dumps(packet, indent=2, sort_keys=True))


def catalog() -> dict[str, Any]:
    return load(CATALOG)


def git_head(root: Path) -> str | None:
    proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(root), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=20)
    return proc.stdout.strip() if proc.returncode == 0 and proc.stdout.strip() else None


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [part for item in value for part in strings(item)]
    if isinstance(value, dict):
        return [part for item in value.values() for part in strings(item)]
    return []


def marker_errors(value: Any, label: str) -> list[str]:
    text = "\n".join(strings(value)).casefold()
    errors: list[str] = []
    for marker in catalog().get("forbidden_markers", []):
        if str(marker).casefold() in text:
            errors.append(f"{label}: forbidden marker present: {marker}")
    return errors


def normalize_status(data: Any) -> str:
    if not isinstance(data, dict):
        return "manual_review"
    for key in ("status", "result", "policy_status"):
        value = str(data.get(key, "")).lower()
        if value in {"pass", "fail", "missing", "stale", "manual_review"}:
            return value
        if value in {"ok", "passed", "healthy"}:
            return "pass"
        if value in {"failed", "error", "degraded", "blocked"}:
            return "fail"
    errors = data.get("errors")
    if isinstance(errors, list) and errors:
        return "fail"
    return "manual_review"


def row_errors(data: Any) -> list[str]:
    if isinstance(data, dict) and isinstance(data.get("errors"), list):
        return [str(item) for item in data["errors"]]
    return []


def find_candidate(repo_root: Path, candidates: list[str]) -> Path | None:
    for candidate in candidates:
        path = repo_root / candidate
        if path.exists() and path.is_file():
            return path
    return None


def scan(repo_root: Path, application: str, delivery_id: str = DEFAULT_DELIVERY_ID) -> dict[str, Any]:
    cfg = catalog()
    evidence_rows: list[dict[str, Any]] = []
    packet_errors: list[str] = []
    for item in cfg.get("required_packets", []):
        path = find_candidate(repo_root, [str(x) for x in item.get("artifact_candidates", [])])
        if not path:
            evidence_rows.append({
                "packet_type": item["packet_type"],
                "source_issue": item["source_issue"],
                "status": "missing",
                "artifact_path": None,
                "artifact_sha256": None,
                "sanitized": True,
                "errors": ["required infra evidence packet missing"],
            })
            continue
        try:
            data = load(path)
        except Exception as exc:
            data = {"status": "manual_review", "errors": [f"invalid json: {exc}"]}
        errors = marker_errors(data, rel(path, repo_root)) + row_errors(data)
        status = "fail" if errors else normalize_status(data)
        evidence_rows.append({
            "packet_type": item["packet_type"],
            "source_issue": item["source_issue"],
            "status": status,
            "artifact_path": rel(path, repo_root),
            "artifact_sha256": sha256(path),
            "sanitized": not errors,
            "errors": errors,
        })
        packet_errors.extend(errors)
    packet = {
        "schema": "bears-cross-repo-infra-evidence.v1",
        "delivery_id": delivery_id,
        "source_repo": SOURCE_REPO,
        "source_commit_sha": git_head(repo_root),
        "application": application,
        "evidence_packets": evidence_rows,
        "degradation_events": [],
        "safe_for_autostart": not packet_errors,
    }
    packet["degradation_events"] = to_degradation(packet)["events"]
    return packet


def validate_packet(packet: dict[str, Any], label: str) -> list[str]:
    errors = validate_json_schema(packet, SCHEMA, label)
    errors.extend(marker_errors(packet, label))
    expected = {row["packet_type"]: row["source_issue"] for row in catalog().get("required_packets", [])}
    seen: set[str] = set()
    for index, row in enumerate(packet.get("evidence_packets", [])):
        if not isinstance(row, dict):
            continue
        packet_type = str(row.get("packet_type", ""))
        seen.add(packet_type)
        if expected.get(packet_type) != row.get("source_issue"):
            errors.append(f"evidence_packets[{index}] source_issue mismatch for {packet_type}")
        if row.get("sanitized") is not True:
            errors.append(f"evidence_packets[{index}] sanitized must be true")
        if row.get("status") in {"fail", "missing", "stale", "manual_review"} and not row.get("errors"):
            errors.append(f"evidence_packets[{index}] degraded status requires errors")
    missing = sorted(set(expected) - seen)
    errors.extend(f"missing required packet_type: {item}" for item in missing)
    return errors


def event_for(packet: dict[str, Any], row: dict[str, Any], signal: str) -> dict[str, Any]:
    delivery_id = str(packet.get("delivery_id", DEFAULT_DELIVERY_ID))
    commit_sha = packet.get("source_commit_sha")
    artifact_path = row.get("artifact_path") or f"{SOURCE_REPO}:{row.get('packet_type')}"
    manifest = f"runtime/deliveries/{delivery_id}/delivery-manifest.v1.json"
    ledger = f"runtime/commit-usage-ledger/{commit_sha or 'unknown'}.json"
    return {
        "schema": "bears-gitops-degradation-event.v1",
        "event_id": f"{delivery_id}:{signal}:{row.get('source_issue')}",
        "delivery_id": delivery_id,
        "commit_sha": commit_sha,
        "signal": signal,
        "gitops_state": "degraded",
        "remediation": "manual_review" if row.get("status") == "manual_review" else "retry",
        "delivery_manifest": manifest,
        "commit_usage_ledger": ledger,
        "evidence_paths": [artifact_path],
        "errors": [str(item) for item in row.get("errors", [])] or [f"infra evidence {row.get('status')}"]
    }


def signal_for(row: dict[str, Any]) -> str:
    cfg = catalog()
    mapping = {item["packet_type"]: item for item in cfg.get("required_packets", [])}
    item = mapping.get(str(row.get("packet_type")), {})
    status = row.get("status")
    if status == "missing":
        return str(item.get("missing_signal", "infra_evidence_missing"))
    if status == "stale":
        return "infra_evidence_stale"
    return str(item.get("fail_signal", "infra_validator_failed"))


def to_degradation(packet: dict[str, Any]) -> dict[str, Any]:
    bad = set(catalog().get("bad_statuses", ["fail", "missing", "stale", "manual_review"]))
    events = [event_for(packet, row, signal_for(row)) for row in packet.get("evidence_packets", []) if isinstance(row, dict) and row.get("status") in bad]
    errors: list[str] = []
    for row in events:
        errors.extend(validate_json_schema(row, EVENT_SCHEMA, str(row.get("event_id"))))
    return {
        "schema": "bears-cross-repo-infra-degradation.v1",
        "delivery_id": packet.get("delivery_id"),
        "status": "degraded" if events else "pass",
        "events": events,
        "errors": errors,
    }


def validate_catalog() -> list[str]:
    errors: list[str] = []
    cfg = catalog()
    if cfg.get("schema") != "bears-cross-repo-infra-evidence-catalog.v1":
        errors.append("catalog schema mismatch")
    required_types = {
        "infra_validation_matrix",
        "opencode_bundle_provenance",
        "opencode_public_route_policy",
        "opencode_rollout_diagnostics",
        "opencode_runtime_egress_policy",
        "opencode_runtime_health_policy",
    }
    seen = {str(row.get("packet_type")) for row in cfg.get("required_packets", []) if isinstance(row, dict)}
    if seen != required_types:
        errors.append("required packet types mismatch")
    workflow = load(GITOPS_CATALOG)
    signals = set(workflow.get("degradation_signals", []))
    for row in cfg.get("required_packets", []):
        for key in ("missing_signal", "fail_signal"):
            signal = row.get(key)
            if signal not in signals:
                errors.append(f"gitops workflow missing signal: {signal}")
    return sorted(set(errors))


def doctor() -> dict[str, Any]:
    errors = validate_catalog()
    fixture = {
        "schema": "bears-cross-repo-infra-evidence.v1",
        "delivery_id": "doctor-fixture",
        "source_repo": SOURCE_REPO,
        "source_commit_sha": None,
        "application": "opencode-server",
        "evidence_packets": [
            {
                "packet_type": row["packet_type"],
                "source_issue": row["source_issue"],
                "status": "pass",
                "artifact_path": f"runtime/opencode/{row['packet_type']}.json",
                "artifact_sha256": "0" * 64,
                "sanitized": True,
                "errors": [],
            }
            for row in catalog().get("required_packets", [])
        ],
        "degradation_events": [],
        "safe_for_autostart": True,
    }
    errors.extend(validate_packet(fixture, "doctor-fixture"))
    return {"schema": "bears-cross-repo-infra-evidence-doctor.v1", "status": "pass" if not errors else "fail", "errors": errors}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate"); v.add_argument("--packet", required=True); v.add_argument("--json", action="store_true")
    s = sub.add_parser("scan"); s.add_argument("--repo-root", required=True); s.add_argument("--application", required=True); s.add_argument("--delivery-id", default=DEFAULT_DELIVERY_ID); s.add_argument("--json", action="store_true")
    t = sub.add_parser("to-degradation"); t.add_argument("--packet", required=True); t.add_argument("--json", action="store_true")
    d = sub.add_parser("doctor"); d.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.cmd == "validate":
        packet = load(Path(args.packet)); errors = validate_packet(packet, args.packet); result = {"schema": "bears-cross-repo-infra-evidence-validation.v1", "status": "pass" if not errors else "fail", "errors": errors}
        print_json(result) if args.json else print(result["status"]); return 0 if result["status"] == "pass" else 1
    if args.cmd == "scan":
        packet = scan(Path(args.repo_root).resolve(), args.application, args.delivery_id)
        print_json(packet) if args.json else print("pass" if not packet["degradation_events"] else "degraded")
        return 0 if packet.get("safe_for_autostart") is True else 1
    if args.cmd == "to-degradation":
        packet = to_degradation(load(Path(args.packet)))
        print_json(packet) if args.json else print(packet["status"]); return 0 if not packet["errors"] else 1
    if args.cmd == "doctor":
        packet = doctor(); print_json(packet) if args.json else print(packet["status"]); return 0 if packet["status"] == "pass" else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
