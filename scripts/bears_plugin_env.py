#!/usr/bin/env python3
"""Install, update, and inspect local @Bears plugin environment config."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "bears-plugin-local-paths.v1"
DEFAULT_PLUGIN_ID = "bears@bears-plugin"
MCP_SERVER_NAME = "mcp"
ENV_INSTRUCTION_ROOT = "BEARS_INSTRUCTION_ROOT"
ENV_CODEX_CONFIG = "BEARS_CODEX_CONFIG"
ENV_PERSONAL_AGENTS = "BEARS_PERSONAL_AGENTS"
GIT_ENV_KEYS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX", "GIT_COMMON_DIR")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser().resolve()


def default_config_path() -> Path:
    return codex_home() / "bears-plugin" / "local-paths.v1.json"


def default_codex_config_path() -> Path:
    return codex_home() / "config.toml"


def default_personal_agents_path() -> Path:
    return codex_home() / "AGENTS.md"


def clean_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in GIT_ENV_KEYS:
        env.pop(key, None)
    return env


def run(argv: list[str], *, cwd: Path | None = None, timeout: int = 60) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            argv,
            cwd=str(cwd) if cwd else None,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
            env=clean_env(),
        )
    except FileNotFoundError as exc:
        return 127, "", str(exc)
    except subprocess.TimeoutExpired as exc:
        return 124, exc.stdout or "", exc.stderr or "timeout"
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def git_toplevel(path: Path) -> Path | None:
    code, stdout, _stderr = run(["git", "rev-parse", "--show-toplevel"], cwd=path)
    return Path(stdout).resolve() if code == 0 and stdout else None


def git_sha(path: Path) -> str | None:
    code, stdout, _stderr = run(["git", "rev-parse", "HEAD"], cwd=path)
    return stdout if code == 0 and stdout else None


def infer_workspace_root(plugin_root: Path) -> Path:
    parts = plugin_root.parts
    if len(parts) >= 3 and parts[-2:] == ("plugins", "bears"):
        return plugin_root.parents[1]
    return plugin_root.parent


def build_packet(args: argparse.Namespace) -> dict[str, Any]:
    plugin_root = PLUGIN_ROOT.resolve()
    workspace_root = Path(args.workspace_root).expanduser().resolve() if args.workspace_root else infer_workspace_root(plugin_root)
    cache_root = Path(args.cache_root).expanduser().resolve() if args.cache_root else codex_home() / "plugins" / "cache" / "bears-plugin" / "bears" / "0.1.0"
    codex_config = Path(args.codex_config).expanduser().resolve() if args.codex_config else default_codex_config_path()
    personal_agents = Path(args.personal_agents).expanduser().resolve() if args.personal_agents else default_personal_agents_path()
    packet: dict[str, Any] = {
        "schema": SCHEMA,
        "updated_at": utc_now(),
        "plugin_id": args.plugin_id,
        "plugin_root": str(plugin_root),
        "workspace_root": str(workspace_root),
        "codex_home": str(codex_home()),
        "codex_config": str(codex_config),
        "personal_agents": str(personal_agents),
        "cache_root": str(cache_root),
        "plugin_sha": git_sha(plugin_root),
        "mcp_server": {
            "name": MCP_SERVER_NAME,
            "transport": "stdio",
            "command": "python3",
            "args": [str(plugin_root / "scripts" / "mcp.py")],
            "env_keys": [ENV_INSTRUCTION_ROOT, ENV_CODEX_CONFIG, ENV_PERSONAL_AGENTS],
        },
    }
    return packet


def write_json(path: Path, packet: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def copy_cache(source: Path, cache_root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {"cache_root": str(cache_root), "status": "skipped"}
    if not source.is_dir():
        result["status"] = "fail"
        result["summary"] = "plugin_root is not a directory"
        return result
    cache_root.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache_root.parent / f".{cache_root.name}.tmp-update"
    backup = cache_root.parent / f".{cache_root.name}.backup"
    try:
        if tmp.exists():
            shutil.rmtree(tmp)
        ignore = shutil.ignore_patterns(".git", "runtime", ".knowledge", "__pycache__", ".pytest_cache", ".ruff_cache")
        shutil.copytree(source, tmp, ignore=ignore)
        if backup.exists():
            shutil.rmtree(backup)
        if cache_root.exists():
            cache_root.rename(backup)
        tmp.rename(cache_root)
        if backup.exists():
            shutil.rmtree(backup)
        result["status"] = "ok"
        result["summary"] = "cache refreshed from local plugin checkout"
    except Exception as exc:  # pragma: no cover - defensive runtime path
        result["status"] = "fail"
        result["summary"] = str(exc)[:800]
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)
        if backup.exists() and not cache_root.exists():
            backup.rename(cache_root)
    return result


def register_codex_mcp(packet: dict[str, Any]) -> dict[str, Any]:
    """Register the instruction zones MCP in local Codex config."""
    plugin_root = Path(str(packet["plugin_root"])).expanduser().resolve()
    workspace_root = Path(str(packet["workspace_root"])).expanduser().resolve()
    codex_config = Path(str(packet["codex_config"])).expanduser().resolve()
    personal_agents = Path(str(packet["personal_agents"])).expanduser().resolve()
    command = [
        "codex",
        "mcp",
        "add",
        MCP_SERVER_NAME,
        "--env",
        f"{ENV_INSTRUCTION_ROOT}={workspace_root}",
        "--env",
        f"{ENV_CODEX_CONFIG}={codex_config}",
        "--env",
        f"{ENV_PERSONAL_AGENTS}={personal_agents}",
        "--",
        "python3",
        str(plugin_root / "scripts" / "mcp.py"),
    ]
    remove_code, _remove_stdout, remove_stderr = run(["codex", "mcp", "remove", MCP_SERVER_NAME])
    code, stdout, stderr = run(command)
    result: dict[str, Any] = {
        "name": MCP_SERVER_NAME,
        "status": "ok" if code == 0 else "fail",
        "transport": "stdio",
        "command": "python3",
        "args": [str(plugin_root / "scripts" / "mcp.py")],
        "env_keys": [ENV_INSTRUCTION_ROOT, ENV_CODEX_CONFIG, ENV_PERSONAL_AGENTS],
        "removed_existing": remove_code == 0,
    }
    if remove_code not in (0, 1):
        result["remove_summary"] = (remove_stderr or "")[:300]
    if code != 0:
        result["summary"] = (stderr or stdout or "codex mcp add failed")[:800]
    return result


def install(args: argparse.Namespace) -> int:
    config_path = Path(args.config).expanduser().resolve() if args.config else default_config_path()
    packet = build_packet(args)
    write_json(config_path, packet)
    output = {"status": "ok", "config_path": str(config_path), "plugin_root": packet["plugin_root"], "workspace_root": packet["workspace_root"]}
    if not args.skip_mcp_registration:
        output["mcp_registration"] = register_codex_mcp(packet)
        if output["mcp_registration"].get("status") == "fail":
            output["status"] = "fail"
    if args.update_cache:
        output["cache_update"] = copy_cache(Path(packet["plugin_root"]), Path(packet["cache_root"]))
        if output["cache_update"].get("status") == "fail":
            output["status"] = "fail"
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if output["status"] == "ok" else 1


def update(args: argparse.Namespace) -> int:
    config_path = Path(args.config).expanduser().resolve() if args.config else default_config_path()
    if not config_path.is_file():
        print(json.dumps({"status": "fail", "summary": "local config missing; run install first", "config_path": str(config_path)}, indent=2, sort_keys=True))
        return 2
    packet = load_config(config_path)
    plugin_root = Path(str(packet.get("plugin_root", PLUGIN_ROOT))).expanduser().resolve()
    cache_root = Path(str(packet.get("cache_root", codex_home() / "plugins" / "cache" / "bears-plugin" / "bears" / "0.1.0"))).expanduser().resolve()
    packet.setdefault("codex_home", str(codex_home()))
    packet.setdefault("workspace_root", str(infer_workspace_root(plugin_root)))
    packet.setdefault("codex_config", str(default_codex_config_path()))
    packet.setdefault("personal_agents", str(default_personal_agents_path()))
    packet["mcp_server"] = {
        "name": MCP_SERVER_NAME,
        "transport": "stdio",
        "command": "python3",
        "args": [str(plugin_root / "scripts" / "mcp.py")],
        "env_keys": [ENV_INSTRUCTION_ROOT, ENV_CODEX_CONFIG, ENV_PERSONAL_AGENTS],
    }
    packet["updated_at"] = utc_now()
    packet["plugin_sha"] = git_sha(plugin_root)
    write_json(config_path, packet)
    result = {"status": "ok", "config_path": str(config_path), "cache_update": copy_cache(plugin_root, cache_root)}
    if not args.skip_mcp_registration:
        result["mcp_registration"] = register_codex_mcp(packet)
        if result["mcp_registration"].get("status") == "fail":
            result["status"] = "fail"
    if result["cache_update"].get("status") == "fail":
        result["status"] = "fail"
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "ok" else 1


def doctor(args: argparse.Namespace) -> int:
    config_path = Path(args.config).expanduser().resolve() if args.config else default_config_path()
    packet: dict[str, Any] | None = load_config(config_path) if config_path.is_file() else None
    plugin_root = Path(str(packet.get("plugin_root"))) if packet else PLUGIN_ROOT.resolve()
    cache_root = Path(str(packet.get("cache_root"))) if packet else codex_home() / "plugins" / "cache" / "bears-plugin" / "bears" / "0.1.0"
    result = {
        "status": "ok" if packet else "missing_config",
        "config_path": str(config_path),
        "config_exists": config_path.is_file(),
        "plugin_root_exists": plugin_root.is_dir(),
        "plugin_sha": git_sha(plugin_root) if plugin_root.is_dir() else None,
        "cache_root_exists": cache_root.is_dir(),
        "cache_sha": git_sha(cache_root) if cache_root.is_dir() else None,
        "mcp_server": packet.get("mcp_server") if packet else None,
        "redacted": True,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "ok" else 1


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Manage local @Bears plugin environment config")
    sub = root.add_subparsers(dest="command", required=True)
    for name in ("install", "update", "doctor"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--config")
    install_cmd = sub.choices["install"]
    install_cmd.add_argument("--workspace-root")
    install_cmd.add_argument("--cache-root")
    install_cmd.add_argument("--codex-config")
    install_cmd.add_argument("--personal-agents")
    install_cmd.add_argument("--plugin-id", default=DEFAULT_PLUGIN_ID)
    install_cmd.add_argument("--update-cache", action="store_true")
    for name in ("install", "update"):
        sub.choices[name].add_argument("--skip-mcp-registration", action="store_true")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "install":
        return install(args)
    if args.command == "update":
        return update(args)
    if args.command == "doctor":
        return doctor(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
