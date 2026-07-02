#!/usr/bin/env python3
"""Validate goal-orchestrator state packets for @Bears."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = ("BEGIN PRIVATE KEY", "raw_secret=", ".env=", "credential=")
REQUIRED_STATE_FIELDS = ("schema", "goal_id", "delivery_id", "state", "source", "source_ref", "decision_graph", "question_graph", "role_plan")


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


def resolve_state_ref(state_path: Path, value: Any) -> Path:
    ref = Path(str(value))
    if ref.is_absolute():
        return ref
    candidate = PLUGIN_ROOT / ref
    if candidate.exists():
        return candidate
    return state_path.parent / ref.name


def validate_goal_state(path_value: str) -> list[str]:
    path = Path(path_value)
    if not path.is_absolute():
        path = PLUGIN_ROOT / path
    try:
        packet = load(path)
    except Exception as exc:
        return [f"goal state read error: {exc}"]
    errors: list[str] = []
    if packet.get("schema") != "bears-goal-state.v1":
        errors.append("goal state schema must be bears-goal-state.v1")
    for field in REQUIRED_STATE_FIELDS:
        if not packet.get(field):
            errors.append(f"goal state missing {field}")
    if packet.get("state") not in {"queued", "ready", "running", "blocked", "complete", "closed"}:
        errors.append("goal state value is invalid")
    for field in ("decision_graph", "question_graph", "role_plan"):
        if packet.get(field) and not resolve_state_ref(path, packet[field]).exists():
            errors.append(f"goal state reference missing: {field}={packet[field]}")
    if has_forbidden(packet):
        errors.append("goal state contains forbidden data marker")
    return errors


def print_packet(packet: dict[str, Any]) -> None:
    print(json.dumps(packet, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate_state = sub.add_parser("validate-state")
    validate_state.add_argument("state")
    sub.add_parser("validate")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        print_packet({"schema": "bears-goal-orchestrator-validation.v1", "status": "pass", "errors": []})
        return 0
    if args.command == "validate-state":
        errors = validate_goal_state(args.state)
        print_packet({"schema": "bears-goal-state-validation.v1", "status": "pass" if not errors else "fail", "errors": errors})
        return 0 if not errors else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
