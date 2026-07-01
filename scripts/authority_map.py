#!/usr/bin/env python3
"""Validate canonical authority for @Bears plugin topics."""
from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CATALOG = PLUGIN_ROOT / "assets/catalog/authority-map.v1.json"
SCHEMA = PLUGIN_ROOT / "assets/schemas/authority-map.v1.schema.json"
GOOD = PLUGIN_ROOT / "tests/fixtures/authority_map/good"
BAD = PLUGIN_ROOT / "tests/fixtures/authority_map/bad"
OWNER_ROLE = "bears-machine-first-execution-kernel-engineer"
REQUIRED_TOPICS = {
    "artifact_registry",
    "decision_ledger",
    "release_notes_gate",
    "workspace_hygiene",
    "git_hook_bootstrap",
    "delivery_manifest",
    "enterprise_issue_automation_release",
    "commit_closeout",
    "bears_doctor",
    "test_selection",
    "file_context_index",
    "async_validation",
    "sequential_codex_exec",
    "issue_autostart",
}

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def existing_literal(path: str) -> bool:
    if "<" in path or "*" in path:
        return True
    return (PLUGIN_ROOT / path).exists()


def validator_exists(command: str) -> bool:
    try:
        parts = shlex.split(command)
    except ValueError:
        return False
    for part in parts:
        if part.startswith("scripts/") and part.endswith(".py"):
            return (PLUGIN_ROOT / part).exists()
    return False


def validate_map(path: Path = CATALOG, *, require_all_topics: bool = True) -> list[str]:
    try:
        packet = load(path)
    except Exception as exc:
        return [f"cannot read authority map: {exc}"]
    errors = validate_json_schema(packet, SCHEMA, path.name)
    if packet.get("owner_role") != OWNER_ROLE:
        errors.append("owner_role mismatch")
    topics = packet.get("topics", [])
    seen_topics: set[str] = set()
    canonical_sources: set[str] = set()
    for index, topic in enumerate(topics if isinstance(topics, list) else []):
        if not isinstance(topic, dict):
            continue
        name = str(topic.get("topic", ""))
        canonical = str(topic.get("canonical_source", ""))
        validator = str(topic.get("validator", ""))
        secondary = {str(item) for item in topic.get("secondary_docs", [])}
        generated = {str(item) for item in topic.get("generated_outputs", [])}
        deprecated = {str(item) for item in topic.get("deprecated_surfaces", [])}
        if name in seen_topics:
            errors.append(f"duplicate topic: {name}")
        seen_topics.add(name)
        if canonical in canonical_sources:
            errors.append(f"duplicate canonical source: {canonical}")
        canonical_sources.add(canonical)
        if not existing_literal(canonical):
            errors.append(f"topic {name} canonical_source missing: {canonical}")
        if not validator_exists(validator):
            errors.append(f"topic {name} validator script missing: {validator}")
        for doc in secondary:
            if not existing_literal(doc):
                errors.append(f"topic {name} secondary doc missing: {doc}")
        forbidden_active = {canonical} | secondary | generated
        overlap = sorted(deprecated & forbidden_active)
        if overlap:
            errors.append(f"topic {name} deprecated surface is active authority: {', '.join(overlap)}")
        if not topic.get("manifest_claims"):
            errors.append(f"topic {name} manifest_claims missing")
        if topic.get("owning_role") != OWNER_ROLE:
            errors.append(f"topic {name} owning_role mismatch")
    if require_all_topics and not REQUIRED_TOPICS.issubset(seen_topics):
        missing = sorted(REQUIRED_TOPICS - seen_topics)
        errors.append(f"required topics missing: {', '.join(missing)}")
    return errors


def validate_all() -> list[str]:
    errors = validate_map(CATALOG, require_all_topics=True)
    for path in sorted(GOOD.glob("*.json")):
        errors.extend(f"good fixture failed: {item}" for item in validate_map(path, require_all_topics=False))
    for path in sorted(BAD.glob("*.json")):
        if not validate_map(path, require_all_topics=False):
            errors.append(f"bad fixture unexpectedly passed: {path.name}")
    return errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--map", default=str(CATALOG))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    errors = validate_all() if Path(args.map) == CATALOG else validate_map(Path(args.map), require_all_topics=False)
    packet = {"schema": "bears-authority-map-validation.v1", "status": "pass" if not errors else "fail", "errors": errors}
    print(json.dumps(packet, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
