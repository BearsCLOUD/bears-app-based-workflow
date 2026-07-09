#!/usr/bin/env python3
"""Compact bounded state evidence for parent agents."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = PLUGIN_ROOT / "assets/schemas/evidence-compaction-packet.v1.schema.json"
GOOD = PLUGIN_ROOT / "tests/fixtures/deterministic_runners/good/evidence.json"
BAD = PLUGIN_ROOT / "tests/fixtures/deterministic_runners/bad/forbidden.json"
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema

FORBIDDEN_PATH_PARTS = (".env", "secret", "credential", "chat", "vpn")


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_packet(packet: dict[str, Any], label: str = "packet") -> list[str]:
    errors = validate_json_schema(packet, SCHEMA, label)
    if len(packet.get("state_files", [])) > int(packet.get("max_files", 0)):
        errors.append(f"{label}: state_files exceeds max_files")
    for item in packet.get("state_files", []):
        lowered = str(item).casefold()
        if any(part in lowered for part in FORBIDDEN_PATH_PARTS):
            errors.append(f"{label}: forbidden state path: {item}")
    return errors


def validate_all() -> list[str]:
    errors = validate_packet(load(GOOD), "good")
    if not validate_packet(load(BAD), "bad"):
        errors.append("bad fixture unexpectedly passed")
    return errors


def run_packet(packet: dict[str, Any]) -> dict[str, Any]:
    errors = validate_packet(packet)
    entries: list[dict[str, Any]] = []
    if not errors:
        for item in packet.get("state_files", []):
            path = (PLUGIN_ROOT / item).resolve() if not Path(item).is_absolute() else Path(item)
            data = load(path)
            entries.append({"path": str(item), "schema": data.get("schema"), "status": data.get("status"), "commit_sha": data.get("commit_sha"), "summary": data.get("sanitized_summary") or data.get("reason") or "state packet"})
    result = {"schema": "bears-deterministic-runner-result.v1", "runner": "evidence_compactor", "command_id": packet.get("command_id"), "status": "pass" if not errors else "fail", "exit_code": 0 if not errors else 1, "affected_files": list(packet.get("state_files", [])), "evidence": entries, "sanitized_summary": "evidence compacted" if not errors else "; ".join(errors)[:800]}
    path = PLUGIN_ROOT / "runtime/deterministic-runners/evidence" / f"{packet.get('command_id', 'unknown')}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    run = sub.add_parser("run")
    run.add_argument("--packet", required=True)
    args = parser.parse_args(argv)
    if args.command == "validate":
        errors = validate_all()
        print(json.dumps({"schema": "bears-runner-validation.v1", "status": "pass" if not errors else "fail", "errors": errors}, indent=2, sort_keys=True))
        return 0 if not errors else 1
    result = run_packet(load(Path(args.packet)))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
