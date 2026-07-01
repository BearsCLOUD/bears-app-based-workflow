#!/usr/bin/env python3
"""Deterministic cache sync gate runner."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = PLUGIN_ROOT / "assets/schemas/cache-sync-runner-packet.v1.schema.json"
GOOD = PLUGIN_ROOT / "tests/fixtures/deterministic_runners/good/cache-sync.json"
BAD = PLUGIN_ROOT / "tests/fixtures/deterministic_runners/bad/forbidden.json"
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema
from scripts import plugin_cache_sync


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_packet(packet: dict[str, Any], label: str = "packet") -> list[str]:
    errors = validate_json_schema(packet, SCHEMA, label)
    if packet.get("require_validation_pass") is not True:
        errors.append(f"{label}: require_validation_pass must be true")
    return errors


def validate_all() -> list[str]:
    errors = validate_packet(load(GOOD), "good")
    if not validate_packet(load(BAD), "bad"):
        errors.append("bad fixture unexpectedly passed")
    return errors


def run_packet(packet: dict[str, Any]) -> dict[str, Any]:
    errors = validate_packet(packet)
    validation, validation_error = plugin_cache_sync.read_validation_gate(plugin_cache_sync.DEFAULT_VALIDATION_STATE_ROOT, plugin_cache_sync.DEFAULT_LOCAL_VALIDATION_ROOT, str(packet.get("commit_sha")))
    if validation_error:
        errors.append(validation_error)
    verify = plugin_cache_sync.verify_cache(Path(str(packet.get("cache_path"))), str(packet.get("commit_sha"))) if not errors else {"status": "not_run"}
    if verify.get("status") != "pass" and not errors:
        errors.append("cache verification failed")
    result = {"schema": "bears-deterministic-runner-result.v1", "runner": "cache_sync_runner", "command_id": packet.get("command_id"), "status": "pass" if not errors else "fail", "exit_code": 0 if not errors else 1, "affected_files": [], "sanitized_summary": "cache sync gate passed" if not errors else "; ".join(errors)[:800]}
    path = PLUGIN_ROOT / "runtime/deterministic-runners/cache-sync" / f"{packet.get('command_id', 'unknown')}.json"
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
