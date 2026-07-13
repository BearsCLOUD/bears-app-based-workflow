#!/usr/bin/env python3
"""Validate JSON role definitions and render the fixed safe Codex TOML subset."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import tomllib
from typing import Any


PLUGIN_ID = "bears-app-based-workflow"
DEFINITION_SCHEMA = "app-role-profile-definition.v1"
CATALOG_SCHEMA = "app-role-capability-catalog.v1"
SECTIONS = ("allowed", "forbidden", "required", "ask", "escalate", "conflict", "acceptance", "result", "example")
NAME_RE = re.compile(r"[a-z][a-z0-9-]{0,63}")
SAFE_TOP_LEVEL = {
    "name", "description", "model", "model_reasoning_effort", "sandbox_mode",
    "developer_instructions", "allow_login_shell", "tools", "apps", "mcp_servers",
    "skills", "sandbox_workspace_write",
}


class RoleDefinitionError(ValueError):
    """A bounded validation failure safe to expose to CI and the gateway."""


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_bytes())
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RoleDefinitionError(f"invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise RoleDefinitionError(f"JSON root must be an object: {path}")
    return value


def _exact(value: dict[str, Any], fields: set[str], label: str) -> None:
    if set(value) != fields:
        raise RoleDefinitionError(f"{label} has unknown or missing fields")


def _strings(value: Any, allowed: set[str], label: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise RoleDefinitionError(f"{label} must be an array of non-empty strings")
    if len(value) != len(set(value)) or set(value) - allowed:
        raise RoleDefinitionError(f"{label} contains duplicate or unknown capabilities")
    return sorted(value)


def validate_catalog(value: dict[str, Any]) -> dict[str, Any]:
    _exact(value, {"schema", "plugin_id", "models", "reasoning_efforts", "native_tools", "skills", "mcp_servers"}, "capability catalog")
    if value.get("schema") != CATALOG_SCHEMA or value.get("plugin_id") != PLUGIN_ID:
        raise RoleDefinitionError("unsupported capability catalog")
    for field in ("models", "reasoning_efforts", "native_tools", "skills"):
        items = value.get(field)
        if not isinstance(items, list) or not items or any(not isinstance(item, str) or not item for item in items) or len(items) != len(set(items)):
            raise RoleDefinitionError(f"catalog {field} is invalid")
    servers = value.get("mcp_servers")
    if not isinstance(servers, dict) or set(servers) != {"app-graph", "app-graph-maintainer"}:
        raise RoleDefinitionError("catalog MCP server set is not exact")
    for server, item in servers.items():
        if not isinstance(item, dict):
            raise RoleDefinitionError(f"catalog MCP server is invalid: {server}")
        _exact(item, {"classification", "tools"}, f"catalog MCP server {server}")
        if item["classification"] not in {"read-only", "maintainer"}:
            raise RoleDefinitionError(f"catalog MCP classification is invalid: {server}")
        tools = item["tools"]
        if not isinstance(tools, list) or not tools or any(not isinstance(tool, str) or not tool for tool in tools) or len(tools) != len(set(tools)):
            raise RoleDefinitionError(f"catalog MCP tools are invalid: {server}")
    return value


def validate_definition(value: dict[str, Any], catalog: dict[str, Any], *, expected_name: str | None = None) -> dict[str, Any]:
    _exact(value, {"schema", "name", "description", "identity", "model", "runtime_controls", "capability_requirements", "behavior"}, "role definition")
    name = value.get("name")
    if value.get("schema") != DEFINITION_SCHEMA or not isinstance(name, str) or not NAME_RE.fullmatch(name) or (expected_name and name != expected_name):
        raise RoleDefinitionError("role definition identity is invalid")
    description = value.get("description")
    if not isinstance(description, str) or not 1 <= len(description) <= 1024 or "\n" in description or "\r" in description:
        raise RoleDefinitionError(f"role description is invalid: {name}")
    identity = value.get("identity")
    if not isinstance(identity, dict):
        raise RoleDefinitionError(f"role identity is invalid: {name}")
    _exact(identity, {"level", "role_kind"}, f"role identity {name}")
    if identity["level"] not in {"L1", "L2", "L3"} or identity["role_kind"] not in {"orchestrator", "mutation-worker", "specialist"}:
        raise RoleDefinitionError(f"role identity values are invalid: {name}")
    model = value.get("model")
    if not isinstance(model, dict):
        raise RoleDefinitionError(f"role model is invalid: {name}")
    _exact(model, {"id", "reasoning_effort"}, f"role model {name}")
    if model["id"] not in catalog["models"] or model["reasoning_effort"] not in catalog["reasoning_efforts"]:
        raise RoleDefinitionError(f"role model is not catalogued: {name}")
    runtime = value.get("runtime_controls")
    if not isinstance(runtime, dict):
        raise RoleDefinitionError(f"role runtime controls are invalid: {name}")
    _exact(runtime, {"sandbox_mode", "web_search", "view_image"}, f"role runtime controls {name}")
    if runtime["sandbox_mode"] not in {"read-only", "workspace-write"} or runtime["web_search"] not in {"disabled", "live"} or not isinstance(runtime["view_image"], bool):
        raise RoleDefinitionError(f"unsafe role runtime controls: {name}")
    requirements = value.get("capability_requirements")
    if not isinstance(requirements, dict):
        raise RoleDefinitionError(f"role capabilities are invalid: {name}")
    _exact(requirements, {"native_tools", "plugins"}, f"role capabilities {name}")
    requirements["native_tools"] = _strings(requirements["native_tools"], set(catalog["native_tools"]), f"native tools for {name}")
    plugins = requirements["plugins"]
    if not isinstance(plugins, list) or len(plugins) > 1:
        raise RoleDefinitionError(f"only the self plugin is supported: {name}")
    normalized_plugins = []
    for plugin in plugins:
        if not isinstance(plugin, dict):
            raise RoleDefinitionError(f"plugin requirement is invalid: {name}")
        _exact(plugin, {"id", "skills", "mcp_servers"}, f"plugin requirement {name}")
        if plugin["id"] != PLUGIN_ID:
            raise RoleDefinitionError(f"external plugin is not catalogued: {name}")
        skills = _strings(plugin["skills"], set(catalog["skills"]), f"skills for {name}")
        servers = plugin["mcp_servers"]
        if not isinstance(servers, list) or len(servers) > len(catalog["mcp_servers"]):
            raise RoleDefinitionError(f"MCP requirements are invalid: {name}")
        normalized_servers = []
        seen_servers: set[str] = set()
        for server in servers:
            if not isinstance(server, dict):
                raise RoleDefinitionError(f"MCP requirement is invalid: {name}")
            _exact(server, {"id", "tools"}, f"MCP requirement {name}")
            server_id = server["id"]
            if server_id in seen_servers or server_id not in catalog["mcp_servers"]:
                raise RoleDefinitionError(f"unknown or duplicate MCP server: {name}")
            seen_servers.add(server_id)
            tools = _strings(server["tools"], set(catalog["mcp_servers"][server_id]["tools"]), f"MCP tools for {name}/{server_id}")
            normalized_servers.append({"id": server_id, "tools": tools})
        normalized_plugins.append({"id": PLUGIN_ID, "skills": skills, "mcp_servers": sorted(normalized_servers, key=lambda item: item["id"])})
    requirements["plugins"] = normalized_plugins
    if identity["level"] == "L3" and any(server["id"] == "app-graph-maintainer" for plugin in normalized_plugins for server in plugin["mcp_servers"]):
        raise RoleDefinitionError(f"L3 roles cannot require the graph maintainer: {name}")
    if runtime["web_search"] == "live" and not {"web.search_query", "web.open"}.issubset(requirements["native_tools"]):
        raise RoleDefinitionError(f"live web search lacks explicit native requirements: {name}")
    behavior = value.get("behavior")
    if not isinstance(behavior, dict):
        raise RoleDefinitionError(f"role behavior is invalid: {name}")
    _exact(behavior, set(SECTIONS), f"role behavior {name}")
    for section in SECTIONS:
        rules = behavior[section]
        if not isinstance(rules, list) or not rules:
            raise RoleDefinitionError(f"behavior section {section} is empty: {name}")
        seen: set[str] = set()
        normalized = []
        for rule in rules:
            if not isinstance(rule, dict):
                raise RoleDefinitionError(f"behavior rule is invalid: {name}/{section}")
            _exact(rule, {"id", "text"}, f"behavior rule {name}/{section}")
            rule_id, text = rule["id"], rule["text"]
            if not isinstance(rule_id, str) or not NAME_RE.fullmatch(rule_id) or rule_id in seen or not isinstance(text, str) or not 1 <= len(text) <= 4096 or any(ord(char) < 9 for char in text):
                raise RoleDefinitionError(f"behavior rule is unsafe: {name}/{section}")
            seen.add(rule_id); normalized.append({"id": rule_id, "text": text.strip()})
        behavior[section] = sorted(normalized, key=lambda item: item["id"])
    return value


def _dependencies(definition: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    native = definition["capability_requirements"]["native_tools"]
    plugins = definition["capability_requirements"]["plugins"]
    skills = sorted(skill for plugin in plugins for skill in plugin["skills"])
    mcps = sorted(f"{server['id']}[{','.join(server['tools'])}]" for plugin in plugins for server in plugin["mcp_servers"])
    return native, skills, mcps


def developer_instructions(definition: dict[str, Any]) -> str:
    native, skills, mcps = _dependencies(definition)
    plugin_ids = [plugin["id"] for plugin in definition["capability_requirements"]["plugins"]]
    name = definition["name"]; identity = definition["identity"]
    lines = [
        "Required native tools: " + (", ".join(native) if native else "none") + ".",
        "Required skills: " + (", ".join(skills) if skills else "none") + ".",
        "Required plugins: " + (", ".join(plugin_ids) if plugin_ids else "none") + ".",
        "Required MCP servers: " + (", ".join(mcps) if mcps else "none") + ".",
        "",
        f"Role identity: profile={name}; level={identity['level']}; role_kind={identity['role_kind']}. Before any tool call, require typed dispatch with `agent_type` equal to this profile and packet identity equal to this line; a missing explicit agent type or any identity mismatch is `PACKET_REJECTED`.",
        "Capability boundary: native tool and plugin requirements are declarative where Codex has no per-agent allowlist; sandbox, typed dispatch, and these instructions remain authoritative. Omitted parent capabilities are not permission to use them.",
    ]
    for section in SECTIONS:
        title = section.capitalize()
        lines.append("")
        lines.append(f"{title}: " + " ".join(rule["text"] for rule in definition["behavior"][section]))
    return "\n".join(lines).strip() + "\n"


def _quoted(value: str) -> str:
    if any(ord(char) < 9 or char in "\x0b\x0c" for char in value):
        raise RoleDefinitionError("TOML string contains a forbidden control character")
    return json.dumps(value, ensure_ascii=False)


def render_profile(definition: dict[str, Any], catalog: dict[str, Any], version: str) -> bytes:
    definition = validate_definition(json.loads(json.dumps(definition)), catalog, expected_name=definition.get("name"))
    runtime = definition["runtime_controls"]
    lines = [
        f"name = {_quoted(definition['name'])}",
        f"description = {_quoted(definition['description'])}",
        f"model = {_quoted(definition['model']['id'])}",
        f"model_reasoning_effort = {_quoted(definition['model']['reasoning_effort'])}",
        f"sandbox_mode = {_quoted(runtime['sandbox_mode'])}",
        f"developer_instructions = {_quoted(developer_instructions(definition))}",
    ]
    # 0.3.1 is the exact compatibility release accepted by the predecessor gateway.
    if version != "0.3.1":
        lines.extend(["allow_login_shell = false", "", "[tools]", f"web_search = {'true' if runtime['web_search'] == 'live' else 'false'}", f"view_image = {'true' if runtime['view_image'] else 'false'}", "", "[apps._default]", "enabled = false"])
        if runtime["sandbox_mode"] == "workspace-write":
            lines.extend(["", "[sandbox_workspace_write]", "network_access = false"])
        requested_servers = {server["id"]: set(server["tools"]) for plugin in definition["capability_requirements"]["plugins"] for server in plugin["mcp_servers"]}
        for server_id in sorted(catalog["mcp_servers"]):
            enabled = requested_servers.get(server_id, set())
            all_tools = set(catalog["mcp_servers"][server_id]["tools"])
            lines.extend(["", f"[mcp_servers.{_quoted(server_id)}]", f"enabled = {'true' if enabled else 'false'}", f"required = {'true' if enabled else 'false'}", "enabled_tools = [" + ", ".join(_quoted(tool) for tool in sorted(enabled)) + "]", "disabled_tools = [" + ", ".join(_quoted(tool) for tool in sorted(all_tools - enabled)) + "]"])
        enabled_skills = {skill for plugin in definition["capability_requirements"]["plugins"] for skill in plugin["skills"]}
        for skill in sorted(catalog["skills"]):
            lines.extend(["", "[[skills.config]]", f"path = {_quoted('../skills/' + skill + '/SKILL.md')}", f"enabled = {'true' if skill in enabled_skills else 'false'}"])
    payload = ("\n".join(lines) + "\n").encode("utf-8")
    try:
        parsed = tomllib.loads(payload.decode("utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise RoleDefinitionError("renderer produced invalid TOML") from exc
    expected = {"name", "description", "model", "model_reasoning_effort", "sandbox_mode", "developer_instructions"} if version == "0.3.1" else SAFE_TOP_LEVEL - ({"sandbox_workspace_write"} if runtime["sandbox_mode"] != "workspace-write" else set())
    if set(parsed) != expected:
        raise RoleDefinitionError("renderer produced an unexpected TOML key set")
    return payload


def render_directory(root: Path, version: str, *, check: bool = False) -> dict[str, Any]:
    catalog = validate_catalog(_read_json(root / "role-definitions" / "capability-catalog.v1.json"))
    definitions = []
    for path in sorted((root / "role-definitions").glob("*.json")):
        if path.name == "capability-catalog.v1.json":
            continue
        definitions.append((path, validate_definition(_read_json(path), catalog, expected_name=path.stem)))
    if not definitions:
        raise RoleDefinitionError("role definition catalog is empty")
    expected_names = {definition["name"] for _, definition in definitions}
    current_names = {path.stem for path in (root / "agents").glob("*.toml")}
    if check and current_names != expected_names:
        raise RoleDefinitionError("generated role file set drifted from definitions")
    output_digests: dict[str, str] = {}
    definition_digests: dict[str, str] = {}
    for path, definition in definitions:
        rendered = render_profile(definition, catalog, version)
        output = root / "agents" / f"{definition['name']}.toml"
        if check:
            try:
                current = output.read_bytes()
            except OSError as exc:
                raise RoleDefinitionError(f"generated role is missing: {output.name}") from exc
            if current != rendered:
                raise RoleDefinitionError(f"generated role drifted: {output.name}")
        else:
            output.write_bytes(rendered)
        output_digests[definition["name"]] = hashlib.sha256(rendered).hexdigest()
        definition_digests[definition["name"]] = hashlib.sha256(canonical(definition)).hexdigest()
    build = {
        "schema": "app-role-profile-build.v1",
        "version": version,
        "catalog_digest": hashlib.sha256(canonical(catalog)).hexdigest(),
        "definition_digests": definition_digests,
        "output_digests": output_digests,
    }
    build["generation"] = hashlib.sha256(canonical(build)).hexdigest()
    return build


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--version", required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        build = render_directory(args.root.resolve(), args.version, check=args.check)
    except RoleDefinitionError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(canonical(build).decode("utf-8"), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
