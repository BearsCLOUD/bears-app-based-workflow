#!/usr/bin/env python3
"""Evaluate default-deny MCP access for Bears agent profiles."""

from __future__ import annotations

import argparse
import fnmatch
import json
import sys
import time
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from scripts.local_json_schema import validate_json_schema
DEFAULT_CATALOG = PLUGIN_ROOT / "assets/catalog/mcp-agent-policy.v1.json"
DEFAULT_SCHEMA = PLUGIN_ROOT / "assets/schemas/mcp-agent-policy.v1.schema.json"
POLICY_SCHEMA = "bears-mcp-agent-policy.v1"
DECISION_PACKET_SCHEMA = "bears-mcp-agent-policy-decision-packet.v1"
RESULT_SCHEMA = "bears-mcp-agent-policy-decision-result.v1"
PERMISSION_SCHEMA = "bears-mcp-agent-policy-opencode-permissions.v1"
DOCTOR_SCHEMA = "bears-mcp-agent-policy-doctor.v1"
VALIDATION_SCHEMA = "bears-mcp-agent-policy-validation.v1"


def load_json(path: Path) -> Any:
    """Load a JSON object from a workspace-local path."""
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(packet: dict[str, Any]) -> None:
    """Write a stable JSON packet to stdout."""
    print(json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True))


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def profiles_by_id(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return profile policy records keyed by profile id."""
    profiles = catalog.get("profiles", [])
    if not isinstance(profiles, list):
        return {}
    return {
        str(profile.get("profile_id")): profile
        for profile in profiles
        if isinstance(profile, dict) and profile.get("profile_id")
    }


def _matches_any(value: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(value, pattern) for pattern in patterns)


def _github_mutation_patterns(catalog: dict[str, Any]) -> list[str]:
    github = catalog.get("tool_rules", {}).get("github_mutation", {})
    patterns = github.get("tool_patterns", []) if isinstance(github, dict) else []
    return [str(pattern) for pattern in patterns if isinstance(pattern, str)]


def is_github_mutation(tool_id: str, catalog: dict[str, Any]) -> bool:
    """Return whether the MCP tool mutates GitHub state."""
    return _matches_any(tool_id, _github_mutation_patterns(catalog))


def _closeout_allowed_tools(catalog: dict[str, Any]) -> set[str]:
    exception = catalog.get("tool_rules", {}).get("github_mutation", {}).get("closeout_exception", {})
    tools = exception.get("allowed_tools", []) if isinstance(exception, dict) else []
    return {str(tool) for tool in tools if isinstance(tool, str)}


def _allowed_by_profile(tool_id: str, profile: dict[str, Any]) -> bool:
    patterns = profile.get("allowed_tool_patterns", [])
    if not isinstance(patterns, list):
        return False
    return _matches_any(tool_id, [str(pattern) for pattern in patterns if isinstance(pattern, str)])


def _packet_allowlist(packet: dict[str, Any], profile: dict[str, Any]) -> set[str]:
    field = "explicit_read_only_allowlist" if profile.get("profile_kind") == "research" else "allowed_mcp_tools"
    values = packet.get(field, [])
    if not isinstance(values, list):
        return set()
    return {str(item) for item in values if isinstance(item, str)}


def _research_read_only_allowlist(profile: dict[str, Any]) -> set[str]:
    values = profile.get("read_only_tool_allowlist", [])
    if not isinstance(values, list):
        return set()
    return {str(item) for item in values if isinstance(item, str)}


def _closeout_gate_passed(packet: dict[str, Any], catalog: dict[str, Any]) -> bool:
    gate = packet.get("closeout_gate")
    exception = catalog.get("tool_rules", {}).get("github_mutation", {}).get("closeout_exception", {})
    if not isinstance(gate, dict) or not isinstance(exception, dict):
        return False
    return gate.get("gate") == exception.get("gate") and gate.get("status") == exception.get("required_status")


def _deny(tool_id: str, reason: str) -> dict[str, str]:
    return {"tool_id": tool_id, "decision": "deny", "reason": reason}


def _allow(tool_id: str, reason: str) -> dict[str, str]:
    return {"tool_id": tool_id, "decision": "allow", "reason": reason}


def validate_catalog(catalog: dict[str, Any] | None = None) -> list[str]:
    """Validate the policy catalog and executable invariants."""
    catalog = catalog or load_json(DEFAULT_CATALOG)
    errors = validate_json_schema(catalog, DEFAULT_SCHEMA, "mcp-agent-policy")
    if catalog.get("schema") != POLICY_SCHEMA:
        errors.append("schema must be bears-mcp-agent-policy.v1")
    commands = set(catalog.get("commands", [])) if isinstance(catalog.get("commands"), list) else set()
    required_commands = {
        "python3 scripts/mcp_agent_policy.py validate",
        "python3 scripts/mcp_agent_policy.py decide --packet <path>",
        "python3 scripts/mcp_agent_policy.py decide --agent-profile <id> --issue <N> --json",
        "python3 scripts/mcp_agent_policy.py render-opencode-permissions --packet <path>",
        "python3 scripts/mcp_agent_policy.py render-opencode-permissions --agent-profile <id>",
        "python3 scripts/mcp_agent_policy.py doctor",
    }
    missing_commands = required_commands - commands
    if missing_commands:
        errors.append("commands missing: " + ", ".join(sorted(missing_commands)))
    if catalog.get("default_mcp_policy", {}).get("mode") != "deny_all":
        errors.append("default_mcp_policy.mode must be deny_all")
    if catalog.get("output_contract", {}).get("json_only") is not True:
        errors.append("output_contract.json_only must be true")

    profiles = profiles_by_id(catalog)
    if len(profiles) != len(catalog.get("profiles", [])):
        errors.append("profiles must have unique profile_id values")
    for profile_id, profile in profiles.items():
        if profile.get("default_mcp_access") != "deny":
            errors.append(f"{profile_id}: default_mcp_access must be deny")
        if profile.get("decision_packet_required") is not True:
            errors.append(f"{profile_id}: decision_packet_required must be true")
        if profile.get("github_mutation_default") != "deny":
            errors.append(f"{profile_id}: github_mutation_default must be deny")
        patterns = profile.get("allowed_tool_patterns", [])
        if "mcp__*" in patterns or "*" in patterns:
            errors.append(f"{profile_id}: wildcard MCP allow patterns are forbidden")
        if profile.get("profile_kind") == "research":
            if profile.get("explicit_read_only_allowlist_required") is not True:
                errors.append(f"{profile_id}: research profile requires explicit read-only allowlist")
            if any(is_github_mutation(tool, catalog) for tool in _research_read_only_allowlist(profile)):
                errors.append(f"{profile_id}: research read-only allowlist contains mutation tool")
    github = catalog.get("tool_rules", {}).get("github_mutation", {})
    if github.get("default") != "deny":
        errors.append("github_mutation.default must be deny")
    if not _closeout_allowed_tools(catalog):
        errors.append("github closeout exception must name allowed_tools")
    return sorted(set(errors))


def validate_decision_packet(packet: dict[str, Any]) -> list[str]:
    """Validate the minimal decision-packet shape before policy evaluation."""
    errors: list[str] = []
    if packet.get("schema") != DECISION_PACKET_SCHEMA:
        errors.append("decision packet schema mismatch")
    if not isinstance(packet.get("profile_id"), str) or not packet.get("profile_id"):
        errors.append("decision packet profile_id is required")
    requested = packet.get("requested_tools")
    if not isinstance(requested, list):
        errors.append("decision packet requested_tools must be a list")
    elif any(not isinstance(tool, str) or not tool for tool in requested):
        errors.append("decision packet requested_tools must contain non-empty strings")
    for field in ("allowed_mcp_tools", "explicit_read_only_allowlist"):
        if field in packet and not isinstance(packet[field], list):
            errors.append(f"decision packet {field} must be a list")
    return errors


def decide(packet: dict[str, Any], catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return an allow/deny decision packet for requested MCP tools."""
    catalog = catalog or load_json(DEFAULT_CATALOG)
    packet_errors = validate_decision_packet(packet)
    requested = packet.get("requested_tools") if isinstance(packet.get("requested_tools"), list) else []
    profile_id = str(packet.get("profile_id", ""))
    profiles = profiles_by_id(catalog)
    profile = profiles.get(profile_id)
    decisions: list[dict[str, str]] = []

    if packet_errors:
        decisions = [_deny(str(tool), "invalid_decision_packet") for tool in requested]
    elif profile is None:
        decisions = [_deny(str(tool), "unknown_profile") for tool in requested]
    else:
        packet_allowlist = _packet_allowlist(packet, profile)
        read_only_allowlist = _research_read_only_allowlist(profile)
        for raw_tool in requested:
            tool_id = str(raw_tool)
            if not tool_id.startswith(catalog.get("tool_rules", {}).get("mcp_tool_prefix", "mcp__")):
                decisions.append(_deny(tool_id, "not_mcp_tool"))
            elif is_github_mutation(tool_id, catalog):
                if (
                    profile.get("closeout_gate_tools_allowed") is True
                    and _allowed_by_profile(tool_id, profile)
                    and tool_id in packet_allowlist
                    and tool_id in _closeout_allowed_tools(catalog)
                    and _closeout_gate_passed(packet, catalog)
                ):
                    decisions.append(_allow(tool_id, "github_closeout_gate_passed"))
                else:
                    decisions.append(_deny(tool_id, "github_mutation_denied_except_closeout_gate"))
            elif not _allowed_by_profile(tool_id, profile):
                decisions.append(_deny(tool_id, "not_allowed_by_profile"))
            elif profile.get("profile_kind") == "research" and tool_id not in read_only_allowlist:
                decisions.append(_deny(tool_id, "not_in_research_read_only_catalog"))
            elif tool_id not in packet_allowlist:
                if profile.get("profile_kind") == "research":
                    reason = "missing_explicit_read_only_allowlist"
                else:
                    reason = "missing_decision_packet_allowlist"
                decisions.append(_deny(tool_id, reason))
            else:
                decisions.append(_allow(tool_id, "profile_and_decision_packet_allow"))

    allowed_tools = [item["tool_id"] for item in decisions if item["decision"] == "allow"]
    denied_tools = [item["tool_id"] for item in decisions if item["decision"] == "deny"]
    if allowed_tools and denied_tools:
        status = "partial"
    elif allowed_tools:
        status = "pass"
    else:
        status = "deny"
    return {
        "schema": RESULT_SCHEMA,
        "created_at": _now(),
        "status": status,
        "profile_id": profile_id or "unknown",
        "allowed_tools": allowed_tools,
        "denied_tools": denied_tools,
        "decisions": decisions,
        "errors": packet_errors,
    }


def render_opencode_permissions(packet: dict[str, Any], catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    """Render an OpenCode permission fragment from a decision packet."""
    catalog = catalog or load_json(DEFAULT_CATALOG)
    decision = decide(packet, catalog)
    permission = dict(catalog.get("opencode_permissions", {}).get("default_fragment", {"mcp_*": "deny"}))
    for tool_id in decision["allowed_tools"]:
        permission[tool_id] = catalog.get("opencode_permissions", {}).get("allowed_value", "allow")
    return {
        "schema": PERMISSION_SCHEMA,
        "created_at": _now(),
        "status": decision["status"],
        "profile_id": decision["profile_id"],
        "permission": permission,
        "allowed_tools": decision["allowed_tools"],
        "denied_tools": decision["denied_tools"],
        "decision_ref": decision,
    }


def doctor(catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return policy health and a default-deny sample decision."""
    catalog = catalog or load_json(DEFAULT_CATALOG)
    errors = validate_catalog(catalog)
    sample = decide(
        {
            "schema": DECISION_PACKET_SCHEMA,
            "profile_id": "unknown",
            "requested_tools": ["mcp__github__create_issue"],
        },
        catalog,
    )
    status = "pass" if not errors and sample["status"] == "deny" else "fail"
    return {
        "schema": DOCTOR_SCHEMA,
        "created_at": _now(),
        "status": status,
        "catalog": str(DEFAULT_CATALOG.relative_to(PLUGIN_ROOT)),
        "default_deny_sample_status": sample["status"],
        "errors": errors,
    }


def _load_packet(path_text: str) -> dict[str, Any]:
    path = Path(path_text)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    packet = load_json(path)
    if not isinstance(packet, dict):
        raise ValueError("packet must be a JSON object")
    return packet


def _validation_packet(errors: list[str]) -> dict[str, Any]:
    return {
        "schema": VALIDATION_SCHEMA,
        "created_at": _now(),
        "status": "pass" if not errors else "fail",
        "errors": errors,
    }


def build_parser() -> argparse.ArgumentParser:
    """Build the command parser for JSON-only policy commands."""
    parser = argparse.ArgumentParser(description="Evaluate Bears MCP agent policy")
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG), help="policy catalog path")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate")
    decide_parser = subparsers.add_parser("decide")
    decide_parser.add_argument("--packet", required=True)
    render_parser = subparsers.add_parser("render-opencode-permissions")
    render_parser.add_argument("--packet", required=True)
    subparsers.add_parser("doctor")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command and emit one JSON result packet."""
    parser = build_parser()
    args = parser.parse_args(argv)
    catalog = load_json(Path(args.catalog))
    try:
        if args.command == "validate":
            packet = _validation_packet(validate_catalog(catalog))
        elif args.command == "decide":
            packet = decide(_load_packet(args.packet), catalog)
        elif args.command == "render-opencode-permissions":
            packet = render_opencode_permissions(_load_packet(args.packet), catalog)
        elif args.command == "doctor":
            packet = doctor(catalog)
        else:
            parser.error("unknown command")
    except Exception as exc:  # noqa: BLE001
        packet = {
            "schema": VALIDATION_SCHEMA,
            "created_at": _now(),
            "status": "fail",
            "errors": [str(exc)],
        }
    write_json(packet)
    return 0 if packet.get("status") in {"pass", "partial", "deny"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
