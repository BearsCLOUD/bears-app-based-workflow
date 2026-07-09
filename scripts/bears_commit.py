#!/usr/bin/env python3
"""Commit through local_commit_validation and print proof paths."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
LCV = [sys.executable, "scripts/local_commit_validation.py", "run"]
PLUGIN_CACHE_SYNC = [sys.executable, "scripts/plugin_cache_sync.py", "sync-once"]


def run(command: list[str]) -> tuple[int, str, str]:
    """Run a command in the plugin checkout."""
    proc = subprocess.run(command, cwd=PLUGIN_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return proc.returncode, proc.stdout, proc.stderr


def parse_packet(stdout: str) -> dict[str, Any]:
    """Parse a JSON command packet."""
    try:
        packet = json.loads(stdout)
    except json.JSONDecodeError:
        return {}
    return packet if isinstance(packet, dict) else {}


def print_stream(stdout: str, stderr: str) -> None:
    """Relay subprocess output without rewriting it."""
    if stdout:
        print(stdout, end="")
    if stderr:
        print(stderr, end="", file=sys.stderr)


def plugin_cache_sync(commit_sha: str) -> tuple[int, str, str, dict[str, Any]]:
    """Sync the installed Codex cache after a plugin commit."""
    code, stdout, stderr = run([*PLUGIN_CACHE_SYNC, "--commit-sha", commit_sha])
    return code, stdout, stderr, parse_packet(stdout)


def commit(args: argparse.Namespace) -> int:
    """Run staged validation, commit, then write exact-SHA proof."""
    commit_args = list(args.git_args)
    if commit_args and commit_args[0] == "--":
        commit_args = commit_args[1:]
    if not commit_args:
        print("git commit arguments are required", file=sys.stderr)
        return 2

    staged_code, staged_stdout, staged_stderr = run([*LCV, "--staged"])
    print_stream(staged_stdout, staged_stderr)
    staged_packet = parse_packet(staged_stdout)
    if staged_code != 0:
        print(f"LCV staged proof: {staged_packet.get('proof_path', '<missing>')}", file=sys.stderr)
        return staged_code

    commit_code, commit_stdout, commit_stderr = run(["git", "commit", "--no-verify", *commit_args])
    print_stream(commit_stdout, commit_stderr)
    if commit_code != 0:
        return commit_code

    sha_code, sha_stdout, sha_stderr = run(["git", "rev-parse", "--verify", "HEAD"])
    if sha_code != 0:
        print_stream(sha_stdout, sha_stderr)
        return sha_code
    commit_sha = sha_stdout.strip()

    proof_code, proof_stdout, proof_stderr = run([*LCV, "--commit-sha", commit_sha])
    print_stream(proof_stdout, proof_stderr)
    proof_packet = parse_packet(proof_stdout)
    if proof_code != 0:
        print(f"LCV commit proof failed: {proof_packet.get('proof_path', '<missing>')}", file=sys.stderr)
        return proof_code

    if getattr(args, "defer_plugin_cache_sync", False):
        print(json.dumps({
            "schema": "bears-commit-result.v1",
            "status": "pass",
            "commit_sha": commit_sha,
            "staged_proof_path": staged_packet.get("proof_path"),
            "proof_path": proof_packet.get("proof_path"),
            "plugin_cache_sync": {
                "status": "deferred_until_push",
                "state_path": str(PLUGIN_ROOT / "runtime/plugin-cache-sync/plugin-cache-sync-state.v1.json"),
                "delivery_complete": False,
            },
        }, indent=2, sort_keys=True))
        return 0

    sync_code, sync_stdout, sync_stderr, sync_packet = plugin_cache_sync(commit_sha)
    print_stream(sync_stdout, sync_stderr)
    if sync_code != 0:
        print(
            f"Plugin cache sync failed: {sync_packet.get('workflow_defect', {}).get('reason', sync_packet.get('next_action', '<missing>'))}",
            file=sys.stderr,
        )
        print(json.dumps({
            "schema": "bears-commit-result.v1",
            "status": "blocked",
            "failure_class": "plugin_cache_sync_failed",
            "commit_sha": commit_sha,
            "staged_proof_path": staged_packet.get("proof_path"),
            "proof_path": proof_packet.get("proof_path"),
            "plugin_cache_sync": {
                "status": sync_packet.get("cache_sync", {}).get("status", "unknown"),
                "state_path": str(PLUGIN_ROOT / "runtime/plugin-cache-sync/plugin-cache-sync-state.v1.json"),
                "delivery_complete": sync_packet.get("delivery_complete"),
                "errors": sync_packet.get("workflow_defect", {}),
            },
        }, indent=2, sort_keys=True))
        return sync_code

    print(json.dumps({
        "schema": "bears-commit-result.v1",
        "status": "pass",
        "commit_sha": commit_sha,
        "staged_proof_path": staged_packet.get("proof_path"),
        "proof_path": proof_packet.get("proof_path"),
        "plugin_cache_sync": {
            "status": sync_packet.get("cache_sync", {}).get("status", "unknown"),
            "state_path": str(PLUGIN_ROOT / "runtime/plugin-cache-sync/plugin-cache-sync-state.v1.json"),
            "delivery_complete": sync_packet.get("delivery_complete"),
        },
    }, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--defer-plugin-cache-sync", action="store_true", help="Print a pass result after exact LCV; caller must sync plugin cache after push.")
    parser.add_argument("git_args", nargs=argparse.REMAINDER, help="Arguments passed to git commit. Use -- before -m flags.")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the wrapper."""
    return commit(build_parser().parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
