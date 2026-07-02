#!/usr/bin/env python3
"""Main-only Bears plugin cache sync after exact validation PASS."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPO = "BearsCLOUD/bears_plugin"
DEFAULT_BRANCH = "main"
DEFAULT_STATE_PATH = PLUGIN_ROOT / "runtime/plugin-cache-sync/plugin-cache-sync-state.v1.json"
DEFAULT_LOCAL_VALIDATION_ROOT = PLUGIN_ROOT / "runtime/local-commit-validation"
DEFAULT_VALIDATION_STATE_ROOT = PLUGIN_ROOT / "runtime/validation-state"
DEFAULT_CACHE_PATH = Path.home() / ".codex/plugins/cache/bears-workflow-plugin/bears/0.1.0"
DEFAULT_MARKETPLACE_ROOT = Path.home() / ".codex/.tmp/marketplaces/bears-workflow-plugin"
DEFAULT_PLUGIN_MANIFEST = DEFAULT_CACHE_PATH / ".codex-plugin/plugin.json"
SCHEMA = "bears-plugin-cache-sync-state.v1"
WORKSPACE_HYGIENE_POLICY = "assets/catalog/workspace-hygiene.v1.json"
DEFAULT_POLL_INTERVAL_SECONDS = 15
DEFAULT_COMMIT_TIMEOUT_SECONDS = 20 * 60
DEFAULT_MAX_SYNC_ATTEMPTS = 3
REQUIRED_HOOKS_VALUE = "./hooks.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_command(command: list[str], *, cwd: Path | None = None, timeout: int = 120) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        return 127, "", str(exc)
    except subprocess.TimeoutExpired as exc:
        return 124, exc.stdout or "", exc.stderr or "timeout"
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def write_state(path: Path, packet: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    packet.setdefault("schema", SCHEMA)
    packet.setdefault("updated_at", utc_now())
    path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def compact_error(stderr: str, stdout: str = "") -> str:
    text = (stderr or stdout or "").replace(os.environ.get("HOME", ""), "$HOME")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return " | ".join(lines[:4])[:800]


def get_main_sha(repo: str, branch: str) -> tuple[str | None, str | None]:
    code, stdout, stderr = run_command(["git", "ls-remote", f"https://github.com/{repo}.git", f"refs/heads/{branch}"], timeout=60)
    if code != 0:
        return None, compact_error(stderr, stdout)
    first = stdout.splitlines()[0].split()[0] if stdout.splitlines() else ""
    return (first if first else None), None if first else "main ref not found"


def cache_sha(cache_path: Path) -> str | None:
    code, stdout, _stderr = run_command(["git", "-C", str(cache_path), "rev-parse", "HEAD"], timeout=30)
    return stdout.strip() if code == 0 and stdout.strip() else None


def read_manifest_hooks(manifest_path: Path) -> str | None:
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    hooks = data.get("hooks")
    return hooks if isinstance(hooks, str) else None


def verify_cache(cache_path: Path, expected_sha: str) -> dict[str, Any]:
    manifest = cache_path / ".codex-plugin/plugin.json"
    hooks_json = cache_path / "hooks.json"
    hooks_dir = cache_path / "hooks"
    actual_sha = cache_sha(cache_path)
    hooks_value = read_manifest_hooks(manifest)
    errors: list[str] = []
    if actual_sha != expected_sha:
        errors.append("installed cache SHA does not match passed main SHA")
    if hooks_value != REQUIRED_HOOKS_VALUE:
        errors.append("plugin manifest hooks entry missing or wrong")
    if not hooks_json.is_file():
        errors.append("hooks.json missing from installed cache")
    if not hooks_dir.is_dir():
        errors.append("hooks directory missing from installed cache")
    return {
        "installed_cache_sha": actual_sha,
        "expected_sha": expected_sha,
        "manifest_hooks": hooks_value,
        "hooks_json_present": hooks_json.is_file(),
        "hooks_dir_present": hooks_dir.is_dir(),
        "status": "pass" if not errors else "fail",
        "errors": errors,
    }


def copy_marketplace_snapshot_to_cache(expected_sha: str, cache_path: Path) -> dict[str, Any]:
    snapshot_sha = cache_sha(DEFAULT_MARKETPLACE_ROOT)
    record: dict[str, Any] = {
        "method": "marketplace_snapshot_cache_replace",
        "marketplace_root": str(DEFAULT_MARKETPLACE_ROOT),
        "snapshot_sha": snapshot_sha,
        "expected_sha": expected_sha,
    }
    if snapshot_sha != expected_sha:
        record["status"] = "skipped"
        record["summary"] = "marketplace snapshot SHA does not match expected main SHA"
        return record
    tmp_path = cache_path.parent / f".{cache_path.name}.tmp-sync"
    backup_path = cache_path.parent / f".{cache_path.name}.backup"
    try:
        if tmp_path.exists():
            shutil.rmtree(tmp_path)
        shutil.copytree(DEFAULT_MARKETPLACE_ROOT, tmp_path, symlinks=True)
        if backup_path.exists():
            shutil.rmtree(backup_path)
        if cache_path.exists():
            cache_path.rename(backup_path)
        tmp_path.rename(cache_path)
        if backup_path.exists():
            shutil.rmtree(backup_path)
        record["status"] = "ok"
        record["summary"] = "installed cache replaced from verified marketplace snapshot"
    except Exception as exc:  # pragma: no cover - defensive runtime branch
        record["status"] = "fail"
        record["summary"] = str(exc)[:800]
        if tmp_path.exists():
            shutil.rmtree(tmp_path, ignore_errors=True)
        if backup_path.exists() and not cache_path.exists():
            backup_path.rename(cache_path)
    return record


def copy_source_commit_to_cache(expected_sha: str, cache_path: Path) -> dict[str, Any]:
    """Replace installed cache from the canonical local source commit only."""

    record: dict[str, Any] = {
        "method": "source_commit_cache_replace",
        "source_root": str(PLUGIN_ROOT),
        "expected_sha": expected_sha,
    }
    code, stdout, stderr = run_command(
        ["git", "-C", str(PLUGIN_ROOT), "cat-file", "-e", f"{expected_sha}^{{commit}}"],
        timeout=30,
    )
    if code != 0:
        record["status"] = "skipped"
        record["summary"] = compact_error(stderr, stdout) or "expected commit missing from canonical source checkout"
        return record

    tmp_path = cache_path.parent / f".{cache_path.name}.tmp-source-sync"
    backup_path = cache_path.parent / f".{cache_path.name}.backup"
    try:
        if tmp_path.exists():
            shutil.rmtree(tmp_path)
        code, stdout, stderr = run_command(
            ["git", "clone", "--quiet", "--no-checkout", str(PLUGIN_ROOT), str(tmp_path)],
            timeout=120,
        )
        if code != 0:
            record["status"] = "fail"
            record["summary"] = compact_error(stderr, stdout)
            return record
        code, stdout, stderr = run_command(
            ["git", "-C", str(tmp_path), "checkout", "--quiet", "--detach", expected_sha],
            timeout=120,
        )
        if code != 0:
            record["status"] = "fail"
            record["summary"] = compact_error(stderr, stdout)
            return record
        if backup_path.exists():
            shutil.rmtree(backup_path)
        if cache_path.exists():
            cache_path.rename(backup_path)
        tmp_path.rename(cache_path)
        if backup_path.exists():
            shutil.rmtree(backup_path)
        record["status"] = "ok"
        record["summary"] = "installed cache replaced from canonical local source commit"
    except Exception as exc:  # pragma: no cover - defensive runtime branch
        record["status"] = "fail"
        record["summary"] = str(exc)[:800]
        if tmp_path.exists():
            shutil.rmtree(tmp_path, ignore_errors=True)
        if backup_path.exists() and not cache_path.exists():
            backup_path.rename(cache_path)
    return record


def sync_cache(expected_sha: str, cache_path: Path, *, max_attempts: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    attempts: list[dict[str, Any]] = []
    commands = [
        ["codex", "plugin", "marketplace", "upgrade", "bears-workflow-plugin", "--json"],
        ["codex", "plugin", "add", "bears@bears-workflow-plugin", "--json"],
    ]
    for attempt in range(1, max_attempts + 1):
        attempt_record: dict[str, Any] = {"attempt": attempt, "commands": []}
        for command in commands:
            code, stdout, stderr = run_command(command, timeout=180)
            attempt_record["commands"].append(
                {
                    "argv": command,
                    "exit_code": code,
                    "summary": compact_error(stderr, stdout) if code else "ok",
                }
            )
            if code != 0:
                break
        verify = verify_cache(cache_path, expected_sha)
        if verify["status"] != "pass":
            source_fallback = copy_source_commit_to_cache(expected_sha, cache_path)
            attempt_record["source_fallback"] = source_fallback
            verify = verify_cache(cache_path, expected_sha)
        if verify["status"] != "pass":
            attempt_record["fallback"] = copy_marketplace_snapshot_to_cache(expected_sha, cache_path)
            verify = verify_cache(cache_path, expected_sha)
        attempt_record["verify"] = verify
        attempts.append(attempt_record)
        if verify["status"] == "pass":
            return verify, attempts
        time.sleep(min(2 * attempt, 10))
    return verify_cache(cache_path, expected_sha), attempts


def local_validation_proof_path(proof_root: Path, sha: str) -> Path:
    return proof_root / f"{sha}.json"


def read_local_validation_proof(proof_root: Path, sha: str) -> tuple[dict[str, Any] | None, str | None]:
    path = local_validation_proof_path(proof_root, sha)
    if not path.is_file():
        return None, f"local commit validation proof missing for exact main SHA: {path}"
    try:
        packet = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, f"local commit validation proof JSON parse failed: {exc}"
    if packet.get("schema") != "bears-local-commit-validation.v1":
        return packet, "local commit validation proof schema mismatch"
    if packet.get("commit_sha") != sha:
        return packet, "local commit validation proof commit_sha mismatch"
    if packet.get("status") != "pass":
        return packet, "local commit validation proof status is not pass"
    return packet, None


def validation_state_path(state_root: Path, sha: str) -> Path:
    return state_root / sha / "validation-state.v1.json"


def read_async_validation_state(state_root: Path, sha: str) -> tuple[dict[str, Any] | None, str | None]:
    path = validation_state_path(state_root, sha)
    if not path.is_file():
        return None, None
    try:
        packet = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, f"async validation state JSON parse failed: {exc}"
    if packet.get("schema") != "bears-validation-state.v1":
        return packet, "async validation state schema mismatch"
    if packet.get("commit_sha") != sha:
        return packet, "async validation state commit_sha mismatch"
    if packet.get("status") != "pass":
        return packet, f"async validation state is {packet.get('status')}"
    return packet, None



def read_github_push_ci_gate(repo: str, sha: str) -> tuple[dict[str, Any] | None, str | None]:
    """Return PASS when GitHub push diagnostics passed for the exact SHA."""

    code, stdout, stderr = run_command(
        [
            "gh",
            "run",
            "list",
            "--repo",
            repo,
            "--workflow",
            "validate",
            "--branch",
            DEFAULT_BRANCH,
            "--limit",
            "20",
            "--json",
            "databaseId,headSha,status,conclusion,event,url",
        ],
        timeout=60,
    )
    if code != 0:
        return None, compact_error(stderr, stdout) or "GitHub push CI status unavailable"
    try:
        runs = json.loads(stdout or "[]")
    except json.JSONDecodeError as exc:
        return None, f"GitHub push CI JSON parse failed: {exc}"
    if not isinstance(runs, list):
        return None, "GitHub push CI response must be a list"
    exact_runs = [run for run in runs if isinstance(run, dict) and run.get("headSha") == sha and run.get("event") == "push"]
    for run in exact_runs:
        if run.get("status") == "completed" and run.get("conclusion") == "success":
            return {
                "schema": "bears-validation-state.v1",
                "status": "pass",
                "commit_sha": sha,
                "source": "github_actions_push",
                "run_id": run.get("databaseId"),
                "run_url": run.get("url"),
                "selected_tests": ["github_actions_validate"],
                "local_commit_validation_proof": run.get("url"),
            }, None
    if exact_runs:
        latest = exact_runs[0]
        return latest, f"GitHub push CI is {latest.get('status')}:{latest.get('conclusion')}"
    return None, "GitHub push CI pass missing for exact main SHA"

def read_validation_gate(state_root: Path, proof_root: Path, sha: str, *, repo: str = DEFAULT_REPO) -> tuple[dict[str, Any] | None, str | None]:
    """Return a passing local, async, or GitHub push validation packet."""
    async_packet, async_error = read_async_validation_state(state_root, sha)
    if async_packet is not None and async_error is None:
        return async_packet, None
    local_packet, local_error = read_local_validation_proof(proof_root, sha)
    if local_error is None:
        return local_packet, None
    github_packet, github_error = read_github_push_ci_gate(repo, sha)
    if github_packet is not None and github_error is None:
        return github_packet, None
    if async_packet is not None or async_error:
        return async_packet, async_error
    return local_packet, local_error


def compact_local_validation(packet: dict[str, Any] | None, *, status: str, proof_root: Path, sha: str | None, error: str | None = None) -> dict[str, Any]:
    proof_path = str(local_validation_proof_path(proof_root, sha)) if sha else None
    if not packet:
        return {"status": status, "proof_path": proof_path, "error": error}
    if packet.get("schema") == "bears-validation-state.v1":
        return {
            "status": packet.get("status", status),
            "proof_path": packet.get("local_commit_validation_proof") or proof_path,
            "commit_sha": packet.get("commit_sha"),
            "selector_confidence": "async",
            "tests": packet.get("selected_tests", []),
            "slow_tests_deferred": [],
            "error": error,
        }
    return {
        "status": packet.get("status", status),
        "proof_path": proof_path,
        "commit_sha": packet.get("commit_sha"),
        "selector_confidence": packet.get("selector_confidence"),
        "tests": packet.get("tests", []),
        "slow_tests_deferred": packet.get("slow_tests_deferred", []),
        "error": error,
    }


def build_defect_state(
    *,
    state_path: Path,
    sha: str | None,
    status: str,
    action: str,
    reason: str,
    proof_root: Path | None = None,
    proof_packet: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = proof_root or DEFAULT_LOCAL_VALIDATION_ROOT
    return {
        "schema": SCHEMA,
        "updated_at": utc_now(),
        "repository": DEFAULT_REPO,
        "branch": DEFAULT_BRANCH,
        "main_sha": sha,
        "local_commit_validation": compact_local_validation(proof_packet, status=status, proof_root=root, sha=sha, error=reason),
        "cache_sync": {"status": "not_run", "action": "cache_unchanged"},
        "workspace_hygiene_policy": WORKSPACE_HYGIENE_POLICY,
        "delivery_complete": False,
        "workflow_defect": {
            "status": "open",
            "action": action,
            "reason": reason,
            "tech_debt_matrix_ref": "assets/catalog/tech-debt-matrix.v1.json",
        },
        "next_action": "L1 may create only a remediation scope while this state blocks plugin closeout.",
    }


def sync_once(args: argparse.Namespace) -> int:
    state_path = Path(args.state)
    cache_path = Path(args.cache_path)
    proof_root = Path(args.local_validation_root)
    validation_state_root = Path(args.validation_state_root)
    sha = args.commit_sha
    if not sha:
        sha, error = get_main_sha(args.repo, args.branch)
        if error:
            packet = build_defect_state(
                state_path=state_path,
                sha=None,
                status="unknown",
                action="block_workflow",
                reason=error,
                proof_root=proof_root,
            )
            write_state(state_path, packet)
            print(json.dumps(packet, indent=2, sort_keys=True))
            return 2
    proof_packet, proof_error = read_validation_gate(validation_state_root, proof_root, sha, repo=args.repo)
    if proof_error:
        packet = build_defect_state(
            state_path=state_path,
            sha=sha,
            status="fail" if proof_packet else "missing",
            action="workflow_defect",
            reason=proof_error,
            proof_root=proof_root,
            proof_packet=proof_packet,
        )
        write_state(state_path, packet)
        print(json.dumps(packet, indent=2, sort_keys=True))
        return 4
    verify, attempts = sync_cache(sha, cache_path, max_attempts=int(args.max_attempts))
    if verify["status"] != "pass":
        packet = {
            "schema": SCHEMA,
            "updated_at": utc_now(),
            "repository": args.repo,
            "branch": args.branch,
            "main_sha": sha,
            "local_commit_validation": compact_local_validation(proof_packet, status="pass", proof_root=proof_root, sha=sha),
            "cache_sync": {
                "status": "fail",
                "action": "block_workflow",
                "attempts": attempts,
                "verify": verify,
            },
            "workspace_hygiene_policy": WORKSPACE_HYGIENE_POLICY,
            "delivery_complete": False,
            "workflow_defect": {
                "status": "open",
                "action": "block_workflow",
                "reason": "Exact validation passed but local plugin cache did not sync to exact SHA with hooks proof.",
                "tech_debt_matrix_ref": "assets/catalog/tech-debt-matrix.v1.json",
            },
            "next_action": "L1 may create only a plugin-cache remediation scope.",
        }
        write_state(state_path, packet)
        print(json.dumps(packet, indent=2, sort_keys=True))
        return 5
    packet = {
        "schema": SCHEMA,
        "updated_at": utc_now(),
        "repository": args.repo,
        "branch": args.branch,
        "main_sha": sha,
        "local_commit_validation": compact_local_validation(proof_packet, status="pass", proof_root=proof_root, sha=sha),
        "cache_sync": {"status": "success", "action": "cache_synced", "attempts": attempts, "verify": verify},
        "workspace_hygiene_policy": WORKSPACE_HYGIENE_POLICY,
        "effective_hooks_proof": {
            "status": "manifest_and_files_present",
            "manifest_hooks": verify["manifest_hooks"],
            "hooks_json_present": verify["hooks_json_present"],
            "hooks_dir_present": verify["hooks_dir_present"],
        },
        "delivery_complete": True,
        "workflow_defect": {
            "status": "closed",
            "action": "continue",
            "reason": "exact main SHA validation PASS and cache hooks proof recorded",
        },
        "next_action": "Plugin workflow task may close.",
    }
    write_state(state_path, packet)
    print(json.dumps(packet, indent=2, sort_keys=True))
    return 0


def watch(args: argparse.Namespace) -> int:
    deadline = time.monotonic() + int(args.timeout_seconds)
    while True:
        result = sync_once(args)
        if result in {0, 4, 5}:
            return result
        if time.monotonic() >= deadline:
            sha, _ = get_main_sha(args.repo, args.branch)
            packet = build_defect_state(
                state_path=Path(args.state),
                sha=sha,
                status="timeout",
                action="workflow_defect",
                reason="timeout waiting for exact main commit local validation proof",
                proof_root=Path(args.local_validation_root),
            )
            write_state(Path(args.state), packet)
            print(json.dumps(packet, indent=2, sort_keys=True))
            return 6
        time.sleep(int(args.interval_seconds))


def status(args: argparse.Namespace) -> int:
    state_path = Path(args.state)
    if not state_path.is_file():
        packet = {"schema": SCHEMA, "status": "missing", "state_path": str(state_path)}
    else:
        packet = json.loads(state_path.read_text(encoding="utf-8"))
    print(json.dumps(packet, indent=2, sort_keys=True))
    return 0


def validate_state(args: argparse.Namespace) -> int:
    state_path = Path(args.state)
    errors: list[str] = []
    if not state_path.is_file():
        errors.append("state file missing")
        packet: dict[str, Any] = {}
    else:
        try:
            packet = json.loads(state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"state JSON parse failed: {exc}")
            packet = {}
    if packet.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA}")
    for key in (
        "updated_at",
        "repository",
        "branch",
        "main_sha",
        "local_commit_validation",
        "cache_sync",
        "delivery_complete",
        "workflow_defect",
    ):
        if key not in packet:
            errors.append(f"missing {key}")
    if packet.get("delivery_complete") is True:
        if packet.get("local_commit_validation", {}).get("status") != "pass":
            errors.append("delivery_complete requires local_commit_validation.status=pass")
        if packet.get("local_commit_validation", {}).get("commit_sha") != packet.get("main_sha"):
            errors.append("delivery_complete requires local_commit_validation.commit_sha=main_sha")
        if packet.get("cache_sync", {}).get("status") != "success":
            errors.append("delivery_complete requires cache_sync.status=success")
        hooks_proof = packet.get("effective_hooks_proof")
        if not isinstance(hooks_proof, dict):
            errors.append("delivery_complete requires effective_hooks_proof object")
        else:
            if hooks_proof.get("status") != "manifest_and_files_present":
                errors.append("delivery_complete requires effective_hooks_proof.status=manifest_and_files_present")
            if hooks_proof.get("manifest_hooks") != REQUIRED_HOOKS_VALUE:
                errors.append("delivery_complete requires effective_hooks_proof.manifest_hooks=./hooks.json")
            if hooks_proof.get("hooks_json_present") is not True:
                errors.append("delivery_complete requires effective_hooks_proof.hooks_json_present=true")
            if hooks_proof.get("hooks_dir_present") is not True:
                errors.append("delivery_complete requires effective_hooks_proof.hooks_dir_present=true")
    print(json.dumps({"schema": SCHEMA, "status": "pass" if not errors else "fail", "errors": errors}, indent=2, sort_keys=True))
    return 0 if not errors else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--branch", default=DEFAULT_BRANCH)
    parser.add_argument("--state", default=str(DEFAULT_STATE_PATH))
    parser.add_argument("--local-validation-root", default=str(DEFAULT_LOCAL_VALIDATION_ROOT))
    parser.add_argument("--validation-state-root", default=str(DEFAULT_VALIDATION_STATE_ROOT))
    parser.add_argument("--cache-path", default=str(DEFAULT_CACHE_PATH))
    parser.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_SYNC_ATTEMPTS)
    sub = parser.add_subparsers(dest="command", required=True)
    once = sub.add_parser("sync-once")
    once.add_argument("--commit-sha", default="")
    once.set_defaults(func=sync_once)
    watch_parser = sub.add_parser("watch")
    watch_parser.add_argument("--commit-sha", default="")
    watch_parser.add_argument("--interval-seconds", type=int, default=DEFAULT_POLL_INTERVAL_SECONDS)
    watch_parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_COMMIT_TIMEOUT_SECONDS)
    watch_parser.set_defaults(func=watch)
    status_parser = sub.add_parser("status")
    status_parser.set_defaults(func=status)
    validate = sub.add_parser("validate-state")
    validate.add_argument("--state", dest="state", default=str(DEFAULT_STATE_PATH))
    validate.set_defaults(func=validate_state)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
