#!/usr/bin/env python3
"""Render the typed role IR into Claude Code and Codex agent artifacts.

One source of truth (roles/roles.json) produces both representations:

* claude/agents/<name>.md  - YAML frontmatter (name, description, model, tools) plus role prose.
* agents/<name>.toml       - Codex profile (model, sandbox, developer instructions, MCP policy).

Usage:
    python3 scripts/render_roles.py            # write artifacts
    python3 scripts/render_roles.py --check    # fail if committed artifacts differ from a fresh render
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
IR_PATH = ROOT / "roles/roles.json"
CLAUDE_AGENT_DIR = ROOT / "claude/agents"
CODEX_AGENT_DIR = ROOT / "agents"
PLUGIN_NAMESPACE = "bears-app-based-workflow@bears-app-based-workflow"
CLAUDE_TOOL_PREFIX = "mcp__plugin_bears-app-based-workflow_"
MAINTAINER_SERVER = "app-workflow-maintainer"
KINDS = {"worker", "critic", "reader"}
SANDBOXES = {"read-only", "workspace-write"}
ROLE_NAME_PATTERN = re.compile(r"[a-z][a-z0-9-]*")


class IRError(ValueError):
    """The role IR is malformed or violates a role-authority invariant."""


def load_ir(path: Path = IR_PATH) -> dict:
    ir = json.loads(path.read_text(encoding="utf-8"))
    servers = ir["servers"]
    names = set()
    for role in ir["roles"]:
        name = role["name"]
        if name in names:
            raise IRError(f"duplicate role name: {name}")
        # The name becomes a filename under agents/ and claude/agents/. Anything outside this
        # alphabet could escape those directories or collide with a path separator.
        if not ROLE_NAME_PATTERN.fullmatch(name):
            raise IRError(f"unsafe role name: {name!r}")
        names.add(name)
        if role["kind"] not in KINDS:
            raise IRError(f"{name}: unknown role kind {role['kind']}")
        if role["sandbox"] not in SANDBOXES:
            raise IRError(f"{name}: unknown sandbox {role['sandbox']}")
        for server, tools in role.get("mcp", {}).items():
            if server not in servers:
                raise IRError(f"{name}: unknown MCP server {server}")
            unknown = sorted(set(tools) - set(servers[server]))
            if unknown:
                raise IRError(f"{name}: unknown tools on {server}: {unknown}")
            if len(set(tools)) != len(tools):
                raise IRError(f"{name}: duplicate tools on {server}")
        if role.get("mcp", {}).get(MAINTAINER_SERVER):
            raise IRError(f"{name}: bounded roles must never enable the maintainer server")
        if role["kind"] == "worker" and role.get("mcp"):
            raise IRError(f"{name}: worker roles must not enable any MCP server")
        if role["kind"] != "worker" and role["sandbox"] != "read-only":
            raise IRError(f"{name}: non-worker roles must be read-only")
        for field in ("description", "dispatch_note", "claude_model", "codex_model", "reasoning_effort", "identity", "final_message", "instructions", "claude_tools"):
            if not role.get(field):
                raise IRError(f"{name}: missing {field}")
        # Both renderers emit plain text: TOML basic strings and multi-line strings, and YAML
        # frontmatter values that the loaders read as one line. Reject anything needing escaping
        # instead of silently producing an unparseable artifact.
        for text in [role["description"], role["dispatch_note"], role["identity"], role["final_message"], *role["instructions"]]:
            if '"""' in text or "\\" in text or "\n" in text:
                raise IRError(f"{name}: text is not safely renderable: {text!r}")
        for text in [name, role["description"], role["claude_model"], role["codex_model"], role["reasoning_effort"], role["dispatch_note"]]:
            if '"' in text:
                raise IRError(f"{name}: single-line field must not contain a quote: {text!r}")
        # These land in YAML frontmatter as unquoted plain scalars on a `key: value` line.
        # A colon-space makes the block unparseable; a hash silently truncates the value.
        for text in [role["description"], role["dispatch_note"], role["claude_model"]]:
            if ": " in text or "#" in text:
                raise IRError(f"{name}: frontmatter field must not contain ': ' or '#': {text!r}")
        # Defense in depth: the maintainer server must be unreachable through the free-form
        # Claude tool list as well as through the validated `mcp` map.
        for token in role["claude_tools"]:
            if MAINTAINER_SERVER in token or token.startswith("mcp__"):
                raise IRError(f"{name}: claude_tools must not carry MCP tokens: {token!r}")
    return ir


def claude_tool_tokens(role: dict) -> list[str]:
    tokens = list(role["claude_tools"])
    for server, tools in sorted(role.get("mcp", {}).items()):
        tokens.extend(f"{CLAUDE_TOOL_PREFIX}{server}__{tool}" for tool in tools)
    return tokens


def render_claude(role: dict) -> str:
    description = f"{role['description']} {role['dispatch_note']}"
    lines = [
        "---",
        f"name: {role['name']}",
        f"description: {description}",
        f"model: {role['claude_model']}",
        f"tools: {', '.join(claude_tool_tokens(role))}",
        "---",
        "",
        role["identity"],
        "",
    ]
    body = list(role["instructions"])
    if role.get("network_access") is False and role["sandbox"] == "workspace-write":
        body.insert(2, "Do not access the network.")
    lines.extend(body)
    lines.extend(["", role["final_message"], ""])
    return "\n".join(lines)


def render_codex(role: dict, servers: dict[str, list[str]]) -> str:
    instructions = "\n".join([role["identity"], *role["instructions"]])
    lines = [
        f'name = "{role["name"]}"',
        f'description = "{role["description"]}"',
        f'model = "{role["codex_model"]}"',
        f'model_reasoning_effort = "{role["reasoning_effort"]}"',
        f'sandbox_mode = "{role["sandbox"]}"',
        'developer_instructions = """',
        instructions,
        '"""',
        "allow_login_shell = false",
    ]
    if role["sandbox"] == "workspace-write":
        lines.extend(["", "[sandbox_workspace_write]", f"network_access = {str(bool(role.get('network_access'))).lower()}"])
    for server, tools in servers.items():
        enabled = list(role.get("mcp", {}).get(server, []))
        disabled = [tool for tool in tools if tool not in set(enabled)]
        lines.extend([
            "",
            f'[plugins."{PLUGIN_NAMESPACE}".mcp_servers."{server}"]',
            f"enabled = {str(bool(enabled)).lower()}",
            f"enabled_tools = {json.dumps(enabled)}",
            f"disabled_tools = {json.dumps(disabled)}",
        ])
    return "\n".join(lines) + "\n"


def render_all(ir: dict) -> dict[Path, str]:
    servers = ir["servers"]
    artifacts: dict[Path, str] = {}
    for role in ir["roles"]:
        artifacts[CLAUDE_AGENT_DIR / f"{role['name']}.md"] = render_claude(role)
        artifacts[CODEX_AGENT_DIR / f"{role['name']}.toml"] = render_codex(role, servers)
    return artifacts


def expected_stems(ir: dict) -> set[str]:
    return {role["name"] for role in ir["roles"]}


def stale_artifacts(ir: dict) -> list[Path]:
    keep = expected_stems(ir)
    stale = [path for path in CLAUDE_AGENT_DIR.glob("*.md") if path.stem not in keep]
    stale += [path for path in CODEX_AGENT_DIR.glob("*.toml") if path.stem not in keep]
    return sorted(stale)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render role artifacts from the typed role IR.")
    parser.add_argument("--check", action="store_true", help="fail if committed artifacts differ from a fresh render")
    args = parser.parse_args(argv)

    ir = load_ir()
    artifacts = render_all(ir)
    drift = stale_artifacts(ir)

    if args.check:
        for path, content in sorted(artifacts.items()):
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                drift.append(path)
        if drift:
            for path in sorted(set(drift)):
                print(f"role artifact drift: {path.relative_to(ROOT)}", file=sys.stderr)
            print("run: python3 scripts/render_roles.py", file=sys.stderr)
            return 1
        print(f"role artifacts up to date ({len(artifacts)} files)")
        return 0

    for path in drift:
        path.unlink()
    for path, content in sorted(artifacts.items()):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    print(f"rendered {len(artifacts)} role artifacts from {IR_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
