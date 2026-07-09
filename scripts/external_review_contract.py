#!/usr/bin/env python3
"""Validate external review contract packets with a JSON Schema source of truth."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_CUE = PLUGIN_ROOT / "contracts/external-review-audit.cue"
SCHEMA = PLUGIN_ROOT / "assets/schemas/external-review-audit.v1.schema.json"
FIXTURE_ROOT = PLUGIN_ROOT / "tests/fixtures/external_review_contract"
GOOD_PACKET = FIXTURE_ROOT / "good/closed_with_proof.json"
BAD_PACKETS = (
    FIXTURE_ROOT / "bad/missing_proof.json",
    FIXTURE_ROOT / "bad/missing_changelog.json",
    FIXTURE_ROOT / "bad/missing_decision.json",
)
EXPECTED_SCHEMA_REF = "assets/schemas/external-review-audit.v1.schema.json#/$defs/contract_packet"
SCHEMA_NAME = "bears-external-review-contract-packet.v1"
RESULT_SCHEMA = "bears-external-review-contract-result.v1"
VALIDATION_SCHEMA = "bears-external-review-contract-validation.v1"
VALIDATE_COMMAND = "python3 scripts/external_review_contract.py validate"
CHECK_COMMAND = "python3 scripts/external_review_contract.py check --packet <path> --json"
PILOT_ENV = "BEARS_EXTERNAL_REVIEW_CUE_PILOT"

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema
from scripts import local_json_schema


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(PLUGIN_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def print_json(packet: dict[str, Any]) -> None:
    print(json.dumps(packet, indent=2, sort_keys=True))


def strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [part for item in value for part in strings(item)]
    if isinstance(value, dict):
        return [part for item in value.values() for part in strings(item)]
    return []


def cue_pilot_enabled() -> bool:
    value = os.environ.get(PILOT_ENV, "1").strip().lower()
    return value not in {"0", "false", "off", "disabled", "no"}


def cue_pilot_report() -> dict[str, Any]:
    if not cue_pilot_enabled():
        return {
            "status": "pilot_disabled",
            "binary": None,
            "command": "cue eval contracts/external-review-audit.cue",
            "reason": f"{PILOT_ENV} disabled",
        }
    cue = shutil.which("cue")
    if not cue:
        return {
            "status": "tool_missing",
            "binary": None,
            "command": "cue eval contracts/external-review-audit.cue",
            "reason": "cue binary not found",
        }
    proc = subprocess.run(
        [cue, "eval", str(CONTRACT_CUE)],
        cwd=str(PLUGIN_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=20,
    )
    if proc.returncode != 0:
        reason = proc.stderr.strip() or proc.stdout.strip() or "cue eval failed"
        return {
            "status": "fail",
            "binary": cue,
            "command": "cue eval contracts/external-review-audit.cue",
            "reason": reason,
        }
    return {
        "status": "pass",
        "binary": cue,
        "command": "cue eval contracts/external-review-audit.cue",
        "reason": "cue eval passed",
    }


def schema_errors() -> list[str]:
    errors: list[str] = []
    if not SCHEMA.exists():
        return [f"schema missing: {rel(SCHEMA)}"]
    if not CONTRACT_CUE.exists():
        errors.append(f"cue contract missing: {rel(CONTRACT_CUE)}")
    schema = load(SCHEMA)
    if not isinstance(schema, dict):
        errors.append("schema root must be an object")
        return errors
    expected_keys = {"$schema", "$id", "title", "type", "additionalProperties", "required", "properties"}
    missing = sorted(expected_keys - set(schema))
    errors.extend(f"schema missing field: {item}" for item in missing)
    packet_schema = schema.get("$defs", {}).get("contract_packet", {})
    if not isinstance(packet_schema, dict):
        errors.append("schema missing $defs.contract_packet")
        return errors
    schema_const = packet_schema.get("properties", {}).get("schema", {})
    if not isinstance(schema_const, dict):
        errors.append("contract packet schema const missing")
        return errors
    if schema_const.get("const") != SCHEMA_NAME:
        errors.append("packet schema const mismatch")
    packet_properties = set(packet_schema.get("properties", {}))
    for field in ("schema", "packet_id", "issue", "review_state", "surface", "json_schema_ref", "proof", "changelog", "decision"):
        if field not in packet_properties:
            errors.append(f"schema missing packet field: {field}")
    surface_schema = packet_schema.get("properties", {}).get("surface", {})
    if set(surface_schema.get("required", [])) != {"path", "behavior_changing", "governance_change", "surface_type"}:
        errors.append("surface required fields mismatch")
    for field in ("proof", "changelog", "decision"):
        field_schema = packet_schema.get("properties", {}).get(field, {})
        if field_schema.get("type") != ["object", "null"]:
            errors.append(f"{field} schema type mismatch")
        if set(field_schema.get("required", [])) != {"path", "status"}:
            errors.append(f"{field} required fields mismatch")
    return errors


def packet_errors(packet: dict[str, Any]) -> list[str]:
    schema = load(SCHEMA)
    packet_schema = schema.get("$defs", {}).get("contract_packet", {})
    issues = local_json_schema._validate_schema_node(packet, packet_schema, schema, [])
    errors = [
        f"{packet.get('packet_id', 'external-review-contract')}.{local_json_schema._render_path(issue.path)}: {issue.message}"
        for issue in sorted(issues, key=lambda row: [str(part) for part in row.path])
    ]
    if packet.get("schema") != SCHEMA_NAME:
        errors.append("packet schema mismatch")
    if str(packet.get("json_schema_ref", "")) != EXPECTED_SCHEMA_REF:
        errors.append("json_schema_ref must point at the external review audit contract packet schema")
    review_state = str(packet.get("review_state", ""))
    surface = packet.get("surface", {})
    proof = packet.get("proof")
    changelog = packet.get("changelog")
    decision = packet.get("decision")
    behavior_changing = bool(surface.get("behavior_changing")) if isinstance(surface, dict) else False
    governance_change = bool(surface.get("governance_change")) if isinstance(surface, dict) else False
    if review_state in {"closed", "superseded"}:
        if not isinstance(proof, dict) or not str(proof.get("path", "")).strip():
            errors.append("closed or superseded packet requires proof")
        elif proof.get("status") != "pass":
            errors.append("proof must pass for closed or superseded packet")
    if behavior_changing:
        if not isinstance(changelog, dict) or not str(changelog.get("path", "")).strip():
            errors.append("behavior-changing surface requires changelog")
        elif changelog.get("status") != "pass":
            errors.append("changelog must pass for behavior-changing surface")
    if governance_change:
        if not isinstance(decision, dict) or not str(decision.get("path", "")).strip():
            errors.append("governance change requires decision")
        elif decision.get("status") != "pass":
            errors.append("decision must pass for governance change")
    return errors


def check_packet_path(path: Path) -> dict[str, Any]:
    cue = cue_pilot_report()
    errors: list[str] = []
    packet: dict[str, Any] = {}
    try:
        packet = load(path)
    except Exception as exc:
        errors.append(f"invalid json: {exc}")
    else:
        errors.extend(packet_errors(packet))
    if cue["status"] == "fail":
        errors.append(f"cue pilot failed: {cue['reason']}")
    return {
        "schema": RESULT_SCHEMA,
        "status": "pass" if not errors else "fail",
        "packet_path": rel(path),
        "packet_id": packet.get("packet_id"),
        "review_state": packet.get("review_state"),
        "cue_pilot": cue,
        "errors": errors,
    }


def validate_bundle() -> dict[str, Any]:
    errors = schema_errors()
    good_result = check_packet_path(GOOD_PACKET)
    if good_result["status"] != "pass":
        errors.extend(str(item) for item in good_result.get("errors", []))
    for path in BAD_PACKETS:
        bad_result = check_packet_path(path)
        if bad_result["status"] != "fail":
            errors.append(f"bad fixture unexpectedly passed: {rel(path)}")
    packet = {
        "schema": VALIDATION_SCHEMA,
        "status": "pass" if not errors else "fail",
        "schema_path": rel(SCHEMA),
        "cue_contract_path": rel(CONTRACT_CUE),
        "good_packet": good_result,
        "cue_pilot": cue_pilot_report(),
        "errors": errors,
    }
    return packet


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--json", action="store_true")
    check = sub.add_parser("check")
    check.add_argument("--packet", required=True, type=Path)
    check.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        packet = validate_bundle()
        print_json(packet)
        return 0 if packet["status"] == "pass" else 1
    if args.command == "check":
        packet = check_packet_path(args.packet)
        print_json(packet)
        return 0 if packet["status"] == "pass" else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
