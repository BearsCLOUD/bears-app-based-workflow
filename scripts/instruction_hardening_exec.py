#!/usr/bin/env python3
"""Run instruction-hardening codex-exec rows with prompt-plus-role startup context only."""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "bears.instruction-hardening.exec-runner.v1"
ALLOWED_EFFORTS = ("minimal", "low", "medium", "high")
ALLOWED_SANDBOXES = ("read-only", "workspace-write", "danger-full-access")
DEFAULT_DISABLED_FEATURES = (
    "apps",
    "browser_use",
    "computer_use",
    "image_generation",
    "memories",
    "multi_agent",
    "plugins",
    "tool_suggest",
    "workspace_dependencies",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def startup_prompt(role_path: Path, prompt_path: Path) -> str:
    role_text = read_text(role_path).rstrip()
    prompt_text = read_text(prompt_path).strip()
    return f"{role_text}\n\n{prompt_text}\n"


def usage_from_jsonl(path: Path) -> dict[str, Any]:
    usage: dict[str, Any] = {"kind": "unavailable", "input": None, "cached_input": None, "output": None, "reasoning_output": None, "total": None}
    if not path.exists():
        return usage
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        event_usage = event.get("usage")
        if isinstance(event_usage, dict):
            input_tokens = event_usage.get("input_tokens")
            output_tokens = event_usage.get("output_tokens")
            usage = {
                "kind": "exact",
                "input": input_tokens,
                "cached_input": event_usage.get("cached_input_tokens"),
                "output": output_tokens,
                "reasoning_output": event_usage.get("reasoning_output_tokens"),
                "total": (input_tokens + output_tokens) if isinstance(input_tokens, int) and isinstance(output_tokens, int) else None,
            }
    return usage


def build_command(args: argparse.Namespace, final_path: Path) -> list[str]:
    command = [
        "codex",
        "exec",
        "--json",
        "--ignore-user-config",
        "--ignore-rules",
        "--ephemeral",
        "--skip-git-repo-check",
    ]
    for feature in DEFAULT_DISABLED_FEATURES:
        command.extend(["--disable", feature])
    command.extend([
        "-m",
        args.model,
        "-c",
        f'model_reasoning_effort="{args.reasoning_effort}"',
        "-s",
        args.sandbox,
        "-C",
        str(args.control_cwd),
        "--add-dir",
        str(args.worktree),
        "-o",
        str(final_path),
        "-",
    ])
    if args.output_schema:
        output_index = command.index("-o")
        command[output_index:output_index] = ["--output-schema", str(args.output_schema)]
    return command


def packet(args: argparse.Namespace, command: list[str], *, status: str, start_utc: str, end_utc: str | None = None, returncode: int | None = None, usage: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "run_id": args.run_id,
        "status": status,
        "model": args.model,
        "reasoning_effort": args.reasoning_effort,
        "sandbox": args.sandbox,
        "start_utc": start_utc,
        "end_utc": end_utc,
        "returncode": returncode,
        "startup_context_policy": "prompt_file_plus_role_file_only",
        "startup_context_sources": [str(args.role), str(args.prompt)],
        "disabled_features": list(DEFAULT_DISABLED_FEATURES),
        "forbidden_startup_context": ["user_config", "project_rules", "project_or_plugin_AGENTS_auto_load", "skills_catalog", "plugin_context", "mcp_or_app_context", "multi_agent_tools", "runtime_logs", "session_history"],
        "control_cwd": str(args.control_cwd),
        "target_worktree": str(args.worktree),
        "runner_flags": command[2:-1],
        "command": command,
        "token_usage": usage or {"kind": "unavailable", "input": None, "cached_input": None, "output": None, "reasoning_output": None, "total": None},
    }


def run(args: argparse.Namespace) -> int:
    args.control_cwd.mkdir(parents=True, exist_ok=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = args.output_dir / f"{args.run_id}.jsonl"
    final_path = args.output_dir / f"{args.run_id}.final.txt"
    packet_path = args.output_dir / f"{args.run_id}.runner.json"
    prompt = startup_prompt(args.role, args.prompt)
    command = build_command(args, final_path)
    start = utc_now()
    if args.dry_run:
        run_packet = packet(args, command, status="dry_run", start_utc=start, end_utc=start)
        packet_path.write_text(json.dumps(run_packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(run_packet, indent=2, sort_keys=True))
        return 0
    with jsonl_path.open("w", encoding="utf-8") as stream:
        proc = subprocess.run(command, input=prompt, text=True, stdout=stream, stderr=subprocess.STDOUT, check=False)
    end = utc_now()
    usage = usage_from_jsonl(jsonl_path)
    status = "pass" if proc.returncode == 0 else "fail"
    run_packet = packet(args, command, status=status, start_utc=start, end_utc=end, returncode=proc.returncode, usage=usage)
    packet_path.write_text(json.dumps(run_packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": status, "packet": str(packet_path), "jsonl": str(jsonl_path), "final": str(final_path), "token_usage": usage}, indent=2, sort_keys=True))
    return proc.returncode


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run isolated instruction-hardening codex exec rows")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--prompt", type=Path, required=True)
    parser.add_argument("--role", type=Path, required=True)
    parser.add_argument("--worktree", type=Path, required=True)
    parser.add_argument("--control-cwd", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--reasoning-effort", choices=ALLOWED_EFFORTS, required=True)
    parser.add_argument("--sandbox", choices=ALLOWED_SANDBOXES, default="workspace-write")
    parser.add_argument("--output-schema", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
