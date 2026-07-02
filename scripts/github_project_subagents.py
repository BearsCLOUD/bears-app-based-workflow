#!/usr/bin/env python3
"""Validate @Bears GitHub Project subagent governance packets."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CATALOG = PLUGIN_ROOT / "assets/catalog/github-project-subagents.v1.json"
SCHEMA = PLUGIN_ROOT / "assets/schemas/github-project-subagents.v1.schema.json"
FORBIDDEN = ("BEGIN PRIVATE KEY", "raw_secret=", ".env=", "credential=")
REQUIRED_SURFACES = {
    "projects_v2",
    "issues",
    "sub_issues",
    "pull_requests",
    "actions_checks",
    "releases_tags_packages",
    "discussions_wiki_pages",
    "code_security_metadata",
    "deployments_environments",
    "repository_collaboration_metadata",
}
ALLOWED_ASSIGNMENT_LANES = {"l2", "l3"}
ASSIGNMENT_REQUIRED_FIELDS = {
    "lane",
    "role",
    "model",
    "reasoning",
    "github_project_item",
    "github_issue",
    "repo",
    "target",
    "route_audit_evidence",
    "metadata_mutation_authorized",
    "allowed_actions",
    "forbidden_actions",
    "acceptance_criteria",
    "validation",
    "completion_criteria",
    "closeout_updates",
}

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


def validate_catalog(path: Path = CATALOG) -> list[str]:
    try:
        packet = load(path)
    except Exception as exc:
        return [f"cannot read catalog: {exc}"]
    errors = validate_json_schema(packet, SCHEMA, path.name)
    if packet.get("owner_role") != "bears-github-project-issues-orchestrator":
        errors.append("owner_role must be bears-github-project-issues-orchestrator")
    if packet.get("l2_orchestrator", {}).get("role") != "bears-github-project-issues-orchestrator":
        errors.append("l2_orchestrator role mismatch")
    if packet.get("l2_orchestrator", {}).get("model") != "gpt-5.5":
        errors.append("l2_orchestrator model must be gpt-5.5")
    if packet.get("l2_orchestrator", {}).get("reasoning") != "medium":
        errors.append("l2_orchestrator reasoning must be medium")
    if packet.get("l3_worker", {}).get("model") != "gpt-5.4-mini":
        errors.append("l3_worker model must be gpt-5.4-mini")
    if packet.get("l3_worker", {}).get("reasoning") != "high":
        errors.append("l3_worker reasoning must be high")
    surfaces = {str(item.get("name")) for item in packet.get("github_surfaces", []) if isinstance(item, dict)}
    missing = sorted(REQUIRED_SURFACES - surfaces)
    if missing:
        errors.append(f"required GitHub surfaces missing: {', '.join(missing)}")
    for lane_name in ("parent_lane", "l2_orchestrator"):
        lane = packet.get(lane_name, {})
        forbidden = "\n".join(lane.get("forbidden_actions", [])) if isinstance(lane, dict) else ""
        for marker in ("implementation", "git add", "secret"):
            if marker not in forbidden:
                errors.append(f"{lane_name} forbidden actions must mention {marker}")
    if has_forbidden(packet):
        errors.append("catalog contains forbidden data marker")
    return errors


def validate_assignment(path: Path) -> list[str]:
    try:
        packet = load(path)
    except Exception as exc:
        return [f"cannot read assignment packet: {exc}"]
    errors: list[str] = []
    role = str(packet.get("role", ""))
    lane = str(packet.get("lane", ""))
    model = str(packet.get("model", ""))
    reasoning = str(packet.get("reasoning", ""))
    missing = sorted(field for field in ASSIGNMENT_REQUIRED_FIELDS if field not in packet or packet.get(field) in ("", [], {}))
    if missing:
        errors.append(f"assignment missing required fields: {', '.join(missing)}")
    if lane not in ALLOWED_ASSIGNMENT_LANES:
        errors.append(f"assignment lane must be one of: {', '.join(sorted(ALLOWED_ASSIGNMENT_LANES))}")
    if lane == "l2" and model != "gpt-5.5":
        errors.append("L2 packet model must be gpt-5.5")
    if lane == "l3" and model != "gpt-5.4-mini":
        errors.append("L3 packet model must be gpt-5.4-mini")
    if lane == "l2" and reasoning != "medium":
        errors.append("L2 packet reasoning must be medium")
    if lane == "l3" and reasoning != "high":
        errors.append("L3 packet reasoning must be high")
    if lane == "l2" and role != "bears-github-project-issues-orchestrator":
        errors.append("L2 packet role must be bears-github-project-issues-orchestrator")
    if not isinstance(packet.get("metadata_mutation_authorized"), bool):
        errors.append("assignment metadata_mutation_authorized must be boolean")
    for field in ("allowed_actions", "forbidden_actions"):
        if packet.get(field) and not isinstance(packet.get(field), list):
            errors.append(f"assignment {field} must be a list")
    forbidden_text = "\n".join(strings(packet.get("forbidden_actions", []))).casefold()
    if lane == "l2" and "implementation" not in forbidden_text:
        errors.append(f"{lane} packet must forbid implementation")
    if "secret" not in forbidden_text:
        errors.append("assignment forbidden_actions must mention secret boundaries")
    allowed_text = "\n".join(strings(packet.get("allowed_actions", []))).casefold()
    forbidden_mutations = ("branch protection", "repository settings", "secret", "webhook", "environment protection")
    for marker in forbidden_mutations:
        if marker in allowed_text:
            errors.append(f"assignment allowed_actions must not include forbidden mutation: {marker}")
    if has_forbidden(packet):
        errors.append("assignment contains forbidden data marker")
    return errors


def print_packet(packet: dict[str, Any]) -> None:
    print(json.dumps(packet, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--catalog", default=str(CATALOG))
    assignment = sub.add_parser("validate-assignment")
    assignment.add_argument("packet")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        errors = validate_catalog(Path(args.catalog))
        print_packet({"schema": "bears-github-project-subagents-validation.v1", "status": "pass" if not errors else "fail", "errors": errors})
        return 0 if not errors else 1
    if args.command == "validate-assignment":
        errors = validate_assignment(Path(args.packet))
        print_packet({"schema": "bears-github-project-subagents-assignment-validation.v1", "status": "pass" if not errors else "fail", "errors": errors})
        return 0 if not errors else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
