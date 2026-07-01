#!/usr/bin/env python3
"""Validate @bears delivery manifest packets."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = PLUGIN_ROOT / "assets/schemas/delivery-manifest.v1.schema.json"
CATALOG = PLUGIN_ROOT / "assets/catalog/delivery-manifest.v1.json"
CLOSEOUT_CATALOG = PLUGIN_ROOT / "assets/catalog/commit-closeout.v1.json"
GOOD = PLUGIN_ROOT / "tests/fixtures/delivery_manifest/good"
BAD = PLUGIN_ROOT / "tests/fixtures/delivery_manifest/bad"
FORBIDDEN = ("BEGIN PRIVATE KEY", "raw_secret", ".env=", "credential=", "raw log", "raw chat", "raw vpn config", "production data")
COVERED_ISSUE_CLASSIFICATIONS = {"closed", "partial", "superseded", "out_of_scope", "blocked", "manual_review"}

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [part for item in value for part in strings(item)]
    if isinstance(value, dict):
        return [part for item in value.values() for part in strings(item)]
    return []


def has_forbidden(value: Any) -> bool:
    text = "\n".join(strings(value)).casefold()
    return any(marker.casefold() in text for marker in FORBIDDEN)


def validate_catalog() -> list[str]:
    errors: list[str] = []
    catalog = load(CATALOG)
    if catalog.get("schema") != "bears-delivery-manifest-contract.v1":
        errors.append("catalog schema mismatch")
    for path in catalog.get("authoritative_artifacts", []):
        if not (PLUGIN_ROOT / str(path)).exists():
            errors.append(f"authoritative artifact missing: {path}")
    for command in (
        "python3 scripts/delivery_manifest.py validate",
        "python3 scripts/issue_intake.py intake --repo <owner/repo> --number <n> --output-root <runtime/deliveries>",
        "python3 scripts/issue_intake.py route --issue <n> --json",
        "python3 scripts/sequential_codex_exec.py execute --plan <path>",
        "python3 scripts/validation_worker.py create-fixer-step --remediation <path> --output <path>",
        "python3 scripts/issue_closeout.py close --manifest <path> --dry-run",
        "python3 scripts/issue_state_reconciler.py reconcile --manifest-root <path> --issues-json <path>",
        "python3 scripts/issue_state_reconciler.py summary --manifest-root <path> --issues-json <path> --json",
        "python3 scripts/issue_state_reconciler.py release-summary --json",
        "python3 scripts/issue_state_reconciler.py repo-summary --json",
        "python3 scripts/issue_state_reconciler.py solved-open --delivery-id <id> --json",
        "python3 scripts/issue_closeout.py close-covered --delivery-id <id>",
        "python3 scripts/issue_closeout.py check-release-gate --delivery-id <id>",
    ):
        if command not in catalog.get("commands", []):
            errors.append(f"catalog missing command: {command}")
    if catalog.get("closeout_gate", {}).get("required_doctor_status") != "pass":
        errors.append("closeout gate must require bears_doctor pass")
    return errors


def canonical_delivery_id() -> str:
    try:
        return str(load(CLOSEOUT_CATALOG).get("canonical_delivery_id", "bears-governance-kernel-v1"))
    except Exception:
        return "bears-governance-kernel-v1"


def issue_delivery_id(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("issue-") and len(value) > len("issue-")


def closeout_state(packet: dict[str, Any]) -> bool:
    return packet.get("state") in {"ready_for_closeout", "closed"} or packet.get("closeout", {}).get("status") in {"ready", "closed"}


def issue_key(issue: dict[str, Any]) -> tuple[str, int]:
    return (str(issue.get("repo") or ""), int(issue.get("number") or 0))


def covered_issues(packet: dict[str, Any]) -> list[dict[str, Any]]:
    """Return canonical covered issue rows with a legacy issues[] fallback."""
    canonical = packet.get("covered_issues")
    if isinstance(canonical, list) and canonical:
        return [row for row in canonical if isinstance(row, dict)]
    rows: list[dict[str, Any]] = []
    for issue in packet.get("issues", []):
        if not isinstance(issue, dict):
            continue
        classification = issue.get("closeout_state")
        if not classification:
            continue
        rows.append({
            "repo": issue.get("repo"),
            "number": issue.get("number"),
            "url": issue.get("url", ""),
            "github_state": issue.get("state", "UNKNOWN"),
            "classification": classification,
            "reason": "legacy issues closeout_state fallback",
        })
    return rows


def doctor_delivery_id(path_value: str) -> str | None:
    if not path_value:
        return None
    path = Path(path_value)
    if not path.is_absolute():
        path = PLUGIN_ROOT / path
    if not path.exists():
        return None
    try:
        packet = load(path)
    except Exception:
        return None
    summary = packet.get("closeout_summary") if isinstance(packet.get("closeout_summary"), dict) else {}
    value = summary.get("delivery_id") or packet.get("delivery_id")
    return str(value) if value else None


def validate_manifest(packet: dict[str, Any], *, label: str = "manifest") -> list[str]:
    errors = validate_json_schema(packet, SCHEMA, label)
    if has_forbidden(packet):
        errors.append(f"{label}: forbidden data marker present")
    if closeout_state(packet) and packet.get("delivery_id") != canonical_delivery_id() and not issue_delivery_id(packet.get("delivery_id")):
        errors.append(f"{label}: delivery_id must equal canonical {canonical_delivery_id()} or issue-scoped issue-* id")
    doctor_id = doctor_delivery_id(str(packet.get("doctor", {}).get("result_path", "")))
    if doctor_id and packet.get("delivery_id") != doctor_id:
        errors.append(f"{label}: delivery_id does not match bears_doctor result")
    if packet.get("state") == "closed" and packet.get("doctor", {}).get("status") != "pass":
        errors.append(f"{label}: closed delivery requires doctor pass")
    if packet.get("state") == "closed" and packet.get("validation", {}).get("status") != "pass":
        errors.append(f"{label}: closed delivery requires validation pass")
    if packet.get("state") == "closed" and packet.get("blocking_debt"):
        errors.append(f"{label}: closed delivery requires no blocking debt")
    canonical_rows = packet.get("covered_issues")
    if canonical_rows is not None:
        covered_keys: set[tuple[str, int]] = set()
        for row in canonical_rows if isinstance(canonical_rows, list) else []:
            if not isinstance(row, dict):
                continue
            classification = row.get("classification")
            if classification not in COVERED_ISSUE_CLASSIFICATIONS:
                errors.append(f"{label}: covered_issues classification invalid")
            if classification in {"closed", "superseded"} and not (row.get("proof_path") or row.get("proof_commit")):
                errors.append(f"{label}: solved covered issue requires proof_path or proof_commit")
            covered_keys.add(issue_key(row))
        for issue in packet.get("issues", []):
            if isinstance(issue, dict) and issue_key(issue) not in covered_keys:
                errors.append(f"{label}: issue missing from covered_issues: {issue_key(issue)[0]}#{issue_key(issue)[1]}")
    if closeout_state(packet) and not covered_issues(packet):
        errors.append(f"{label}: closeout delivery requires covered_issues classifications")
    return errors


def validate_all() -> list[str]:
    errors = validate_catalog()
    for path in sorted(GOOD.glob("*.json")):
        errors.extend(f"good fixture failed: {item}" for item in validate_manifest(load(path), label=path.name))
    for path in sorted(BAD.glob("*.json")):
        if not validate_manifest(load(path), label=path.name):
            errors.append(f"bad fixture unexpectedly passed: {path.name}")
    return errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    check = sub.add_parser("check")
    check.add_argument("--manifest", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    errors = validate_all() if args.command == "validate" else validate_manifest(load(Path(args.manifest)), label=Path(args.manifest).name)
    packet = {"schema": "bears-delivery-manifest-validation.v1", "status": "pass" if not errors else "fail", "errors": errors}
    print(json.dumps(packet, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
