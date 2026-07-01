#!/usr/bin/env python3
"""Collect and render metadata-only agent action ledgers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = PLUGIN_ROOT / "assets/catalog/agent-action-ledger.v1.json"
RESTRICTED = ("raw_secret", "BEGIN PRIVATE KEY", ".env=", "raw log", "raw chat", "raw vpn config", "production data")


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_strings(item))
        return out
    if isinstance(value, dict):
        out: list[str] = []
        for item in value.values():
            out.extend(_strings(item))
        return out
    return []


def _restricted(value: Any) -> bool:
    text = "\n".join(_strings(value)).casefold()
    return any(marker.casefold() in text for marker in RESTRICTED)


def collect_runtime(runtime_dir: Path) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    packets: dict[str, Any] = {}
    for path in sorted(runtime_dir.glob("*.json")):
        packets[path.stem] = load_json(path)
    for required in load_json(CATALOG_PATH)["required_packets"]:
        if required not in packets:
            errors.append(f"missing required packet: {required}")
    if "heartbeat" in packets and not packets["heartbeat"].get("status"):
        errors.append("heartbeat.status is required")
    validation = packets.get("validation")
    closeout = packets.get("closeout")
    if closeout is not None and not isinstance(validation, dict):
        errors.append("closeout requires validation packet")
    if isinstance(validation, dict):
        commands = validation.get("commands")
        if not isinstance(commands, list) or not commands:
            errors.append("validation.commands must be a non-empty list")
    forbidden = set(load_json(CATALOG_PATH)["forbidden_actions"])
    actions = packets.get("actions", {}).get("items", []) if isinstance(packets.get("actions"), dict) else []
    for action in actions:
        if isinstance(action, dict) and action.get("action") in forbidden:
            errors.append(f"forbidden action recorded: {action.get('action')}")
    if _restricted(packets):
        errors.append("runtime packets contain restricted data marker")
    return packets, errors


def render_markdown(packets: dict[str, Any]) -> str:
    assignment = packets.get("assignment", {}) if isinstance(packets.get("assignment"), dict) else {}
    evidence = packets.get("evidence", {}) if isinstance(packets.get("evidence"), dict) else {}
    validation = packets.get("validation", {}) if isinstance(packets.get("validation"), dict) else {}
    closeout = packets.get("closeout", {}) if isinstance(packets.get("closeout"), dict) else {}
    blockers = closeout.get("blockers", []) if isinstance(closeout.get("blockers", []), list) else []
    lines = [
        "# Agent Action Ledger",
        "",
        "## Assignment",
        f"- role: {assignment.get('role', 'unknown')}",
        f"- task: {assignment.get('task_id', 'unknown')}",
        "",
        "## Evidence",
        f"- refs: {', '.join(evidence.get('refs', [])) if isinstance(evidence.get('refs'), list) else 'none'}",
        "",
        "## Validation",
    ]
    for row in validation.get("commands", []) if isinstance(validation.get("commands"), list) else []:
        if isinstance(row, dict):
            lines.append(f"- {row.get('command')}: exit {row.get('exit_code')}")
    lines.extend(["", "## Blockers"])
    if blockers:
        lines.extend(f"- {item}" for item in blockers)
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def validate_catalog() -> list[str]:
    data = load_json(CATALOG_PATH)
    errors: list[str] = []
    if data.get("schema") != "bears-agent-action-ledger.v1":
        errors.append("catalog schema mismatch")
    for field in ("goal", "worker", "role", "assignment", "allowed actions", "forbidden actions", "tool evidence", "changed files", "validation", "closeout"):
        joined = json.dumps(data).replace("_", " ")
        if field not in joined:
            errors.append(f"catalog missing field family: {field}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    collect = sub.add_parser("collect")
    collect.add_argument("--runtime-dir", required=True)
    render = sub.add_parser("render-markdown")
    render.add_argument("--runtime-dir", required=True)
    render.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if args.command == "validate":
        errors = validate_catalog()
        if errors:
            print("\n".join(errors), file=sys.stderr)
            return 1
        print("agent action ledger ok")
        return 0
    packets, errors = collect_runtime(Path(args.runtime_dir))
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    if args.command == "collect":
        print(json.dumps(packets, indent=2))
        return 0
    Path(args.out).write_text(render_markdown(packets), encoding="utf-8")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
