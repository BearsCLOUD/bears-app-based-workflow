#!/usr/bin/env python3
"""Run impacted fast tests at git commit time and write exact-SHA proof."""
from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE_ROOT = PLUGIN_ROOT / "runtime/local-commit-validation"
SCHEMA = "bears-local-commit-validation.v1"
EMPTY_TREE_SHA = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
GIT_HOOK_ENV_KEYS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX", "GIT_COMMON_DIR")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean_git_hook_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in GIT_HOOK_ENV_KEYS:
        env.pop(key, None)
    return env


def run_command(command: list[str], *, timeout: int = 600) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            command,
            cwd=PLUGIN_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout,
            env=clean_git_hook_env(),
        )
    except FileNotFoundError as exc:
        return 127, "", str(exc)
    except subprocess.TimeoutExpired as exc:
        return 124, exc.stdout or "", exc.stderr or "timeout"
    return proc.returncode, proc.stdout, proc.stderr


def compact_output(stdout: str, stderr: str) -> str:
    home = os.environ.get("HOME", "")
    text = (stderr or stdout or "").replace(home, "$HOME")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) > 12:
        lines = lines[:4] + ["..."] + lines[-8:]
    return " | ".join(lines)[:1600]


def command_packet(argv: list[str], exit_code: int, stdout: str = "", stderr: str = "", **extra: Any) -> dict[str, Any]:
    """Return bounded command evidence for the LCV proof."""
    packet: dict[str, Any] = {"argv": argv, "exit_code": exit_code}
    if exit_code != 0:
        packet["summary"] = compact_output(stdout, stderr)
    packet.update(extra)
    return packet


def git_output(args: list[str]) -> str:
    code, stdout, stderr = run_command(["git", *args], timeout=60)
    if code != 0:
        raise RuntimeError(compact_output(stdout, stderr) or f"git {' '.join(args)} failed")
    return stdout.strip()


def resolve_commit_sha(ref: str) -> str:
    return git_output(["rev-parse", "--verify", ref])


def commit_diff_range(commit_sha: str) -> str:
    line = git_output(["rev-list", "--parents", "-n", "1", commit_sha])
    parts = line.split()
    if len(parts) <= 1:
        return f"{EMPTY_TREE_SHA}..{commit_sha}"
    return f"{parts[1]}..{commit_sha}"


def staged_files() -> list[str]:
    code, stdout, stderr = run_command(["git", "diff", "--cached", "--name-only"], timeout=60)
    if code != 0:
        raise RuntimeError(compact_output(stdout, stderr) or "git staged diff failed")
    return [line.strip() for line in stdout.splitlines() if line.strip()]


def diff_files(diff_range: str) -> list[str]:
    """Return changed files for an exact commit range."""
    code, stdout, stderr = run_command(["git", "diff", "--name-only", diff_range], timeout=60)
    if code != 0:
        raise RuntimeError(compact_output(stdout, stderr) or "git commit diff failed")
    return [line.strip() for line in stdout.splitlines() if line.strip()]


def selection_command(args: argparse.Namespace, diff_range: str | None, changed_files: list[str]) -> list[str]:
    command = [sys.executable, "scripts/test_selection.py", "list", "--tier", "fast", "--format", "json"]
    if diff_range:
        command.extend(["--from-git", diff_range])
    for path in changed_files:
        command.extend(["--changed-file", path])
    return command


def pants_impacted_command(
    args: argparse.Namespace,
    diff_range: str | None,
    changed_files: list[str],
) -> list[str]:
    command = [sys.executable, "scripts/pants_test_graph.py", "impacted", "--json"]
    if args.staged:
        command.append("--staged")
    elif diff_range:
        command.extend(["--from-git", diff_range])
    for path in changed_files:
        command.extend(["--changed-file", path])
    return command



def _json_or_error(stdout: str, *, fallback: dict[str, Any]) -> dict[str, Any]:
    try:
        packet = json.loads(stdout)
    except json.JSONDecodeError:
        return fallback
    return packet if isinstance(packet, dict) else fallback


def _unmatched_from(packet: dict[str, Any]) -> list[str]:
    return sorted({str(path) for path in packet.get("unmatched", []) if str(path)})


def validation_plan(
    *,
    changed_files: list[str],
    selection: dict[str, Any],
    pants_impacted: dict[str, Any],
) -> dict[str, Any]:
    """Build the enforced validation plan from Pants graph and test-selection."""
    pants_unmatched = _unmatched_from(pants_impacted)
    selection_unmatched = _unmatched_from(selection)
    graph_tests = {str(item) for item in pants_impacted.get("tests", [])}
    selection_tests = {str(item) for item in selection.get("tests", [])}
    planned_tests = sorted(graph_tests | selection_tests)
    uncovered = sorted(set(pants_unmatched) | set(selection_unmatched))
    errors: list[str] = []
    if pants_impacted.get("status") != "pass":
        errors.append("pants impacted graph failed")
    if selection.get("selector_confidence") != "high":
        errors.append("test-selection confidence is not high")
    if uncovered:
        errors.append("changed files are not covered by pants graph/test-selection")
    if changed_files and not planned_tests:
        errors.append("validation plan selected no tests for changed files")
    return {
        "schema": "bears-local-commit-validation-plan.v1",
        "status": "pass" if not errors else "fail",
        "changed_files": sorted({path for path in changed_files if path}),
        "pants": {
            "status": pants_impacted.get("status", "unknown"),
            "matched": pants_impacted.get("matched", []),
            "unmatched": pants_unmatched,
            "tests": sorted(graph_tests),
            "pants_targets": pants_impacted.get("pants_targets", []),
            "gates": pants_impacted.get("gates", []),
        },
        "test_selection": {
            "selector_confidence": selection.get("selector_confidence", "unknown"),
            "matched": selection.get("matched", []),
            "unmatched": selection_unmatched,
            "tests": sorted(selection_tests),
            "requires_full_suite": bool(selection.get("requires_full_suite", False)),
        },
        "tests": planned_tests,
        "uncovered_changed_files": uncovered,
        "errors": errors,
    }

def run_tests_command(args: argparse.Namespace, diff_range: str | None, changed_files: list[str]) -> list[str]:
    command = [sys.executable, "scripts/test_selection.py", "run", "--tier", "fast"]
    if args.dry_run:
        command.append("--dry-run")
    if args.allow_low_confidence:
        command.append("--allow-low-confidence")
    if diff_range:
        command.extend(["--from-git", diff_range])
    for path in changed_files:
        command.extend(["--changed-file", path])
    return command


def release_notes_gate_command(diff_range: str | None, changed_files: list[str], *, staged: bool) -> list[str]:
    command = [sys.executable, "scripts/release_notes_gate.py", "check"]
    if staged:
        command.append("--staged")
    elif diff_range:
        command.extend(["--from-git", diff_range])
    for path in changed_files:
        command.extend(["--changed-file", path])
    return command


def authority_map_command() -> list[str]:
    return [sys.executable, "scripts/authority_map.py", "validate"]


def write_proof(state_root: Path, packet: dict[str, Any]) -> Path:
    state_root.mkdir(parents=True, exist_ok=True)
    commit_sha = packet.get("commit_sha")
    filename = f"{commit_sha}.json" if isinstance(commit_sha, str) and commit_sha else "staged-latest.json"
    path = state_root / filename
    text = json.dumps(packet, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")
    (state_root / "local-commit-validation-state.v1.json").write_text(text, encoding="utf-8")
    return path


def run_validation(args: argparse.Namespace) -> int:
    commit_sha: str | None = None
    diff_range: str | None = None
    changed_files: list[str] = []
    try:
        if args.staged:
            changed_files = staged_files()
        else:
            commit_sha = resolve_commit_sha(args.commit_sha)
            diff_range = commit_diff_range(commit_sha)
            changed_files = diff_files(diff_range)
    except RuntimeError as exc:
        packet = {
            "schema": SCHEMA,
            "updated_at": utc_now(),
            "status": "fail",
            "commit_sha": commit_sha,
            "diff_range": diff_range,
            "changed_files": changed_files,
            "error": str(exc),
        }
        path = write_proof(Path(args.state_root), packet)
        print(json.dumps({"status": "fail", "proof_path": str(path), "error": str(exc)}, indent=2, sort_keys=True))
        return 2

    list_cmd = selection_command(args, diff_range, changed_files)
    list_code, list_stdout, list_stderr = run_command(list_cmd, timeout=120)
    selection = _json_or_error(list_stdout, fallback={"selector_confidence": "unknown", "tests": [], "unmatched": changed_files})
    pants_cmd = pants_impacted_command(args, diff_range, changed_files)
    pants_code, pants_stdout, pants_stderr = run_command(pants_cmd, timeout=120)
    pants_impacted = _json_or_error(pants_stdout, fallback={"status": "fail", "errors": ["pants impacted output is not JSON"], "tests": [], "unmatched": changed_files})
    plan = validation_plan(changed_files=changed_files, selection=selection, pants_impacted=pants_impacted)
    if list_code != 0:
        plan["errors"].append("test-selection list failed")
        plan["status"] = "fail"
    if pants_code != 0 and "pants impacted graph failed" not in plan["errors"]:
        plan["errors"].append("pants impacted graph failed")
        plan["status"] = "fail"
    run_cmd = [sys.executable, "-m", "unittest", *plan.get("tests", [])]
    if args.dry_run:
        run_code, run_stdout, run_stderr = 0, "dry-run: " + " ".join(run_cmd), ""
    elif plan.get("status") != "pass":
        run_code, run_stdout, run_stderr = 2, "", "validation plan failed; tests not run"
    elif plan.get("tests"):
        run_code, run_stdout, run_stderr = run_command(run_cmd, timeout=int(args.timeout_seconds))
    else:
        run_code, run_stdout, run_stderr = 0, "no tests selected", ""
    release_cmd = release_notes_gate_command(diff_range, changed_files, staged=bool(args.staged))
    release_code, release_stdout, release_stderr = run_command(release_cmd, timeout=120)
    authority_cmd = authority_map_command()
    authority_code, authority_stdout, authority_stderr = run_command(authority_cmd, timeout=120)
    if args.dry_run and plan.get("status") == "pass" and list_code == 0 and pants_code == 0 and run_code == 0 and release_code == 0 and authority_code == 0:
        status = "dry_run"
    else:
        status = "pass" if plan.get("status") == "pass" and list_code == 0 and pants_code == 0 and run_code == 0 and release_code == 0 and authority_code == 0 else "fail"
    packet = {
        "schema": SCHEMA,
        "updated_at": utc_now(),
        "status": status,
        "repository": "BearsCLOUD/bears-codex-workflow-plugin",
        "branch": "main",
        "commit_sha": commit_sha,
        "diff_range": diff_range,
        "changed_files": plan.get("changed_files", changed_files),
        "selector_confidence": selection.get("selector_confidence", "unknown"),
        "requires_full_suite": bool(selection.get("requires_full_suite", False) or pants_impacted.get("requires_full_suite", False)),
        "full_suite_advisory_only": False,
        "tests": plan.get("tests", []),
        "validation_plan": plan,
        "pants_impacted": pants_impacted,
        "slow_tests_deferred": selection.get("slow_tests_deferred", []),
        "commands": [
            command_packet(list_cmd, list_code, list_stdout, list_stderr),
            command_packet(pants_cmd, pants_code, pants_stdout, pants_stderr),
            command_packet(run_cmd, run_code, run_stdout, run_stderr, source="validation_plan"),
            command_packet(release_cmd, release_code, release_stdout, release_stderr),
            command_packet(authority_cmd, authority_code, authority_stdout, authority_stderr),
        ],
        "closeout_validator": {
            "argv": [sys.executable, "scripts/bears_doctor.py", "validate-closeout", "--from-git", diff_range or "<staged>", "--json"],
            "execution": "closeout_owned",
        },
        "workspace_hygiene_policy": "assets/catalog/workspace-hygiene.v1.json",
        "summary": "dry-run validation plan passed" if status == "dry_run" else (compact_output(pants_stdout + run_stdout + release_stdout + authority_stdout, pants_stderr + run_stderr + release_stderr + authority_stderr) if status == "fail" else "validation plan, impacted tests, release notes gate, and authority map passed"),
    }
    path = write_proof(Path(args.state_root), packet)
    print(json.dumps({"status": status, "proof_path": str(path), "commit_sha": commit_sha, "tests": packet["tests"]}, indent=2, sort_keys=True))
    return 0 if status in {"pass", "dry_run"} else 1


def hook_body(hook_name: str) -> str:
    if hook_name == "pre-commit":
        command = f"python3 scripts/bears_git_hook.py run --hook pre-commit --workspace-root /srv/bears --repo-path {shlex_quote(str(PLUGIN_ROOT))}"
    elif hook_name == "post-commit":
        command = f"python3 scripts/bears_git_hook.py run --hook post-commit --workspace-root /srv/bears --repo-path {shlex_quote(str(PLUGIN_ROOT))}"
    else:
        raise ValueError(f"unsupported hook: {hook_name}")
    return f"""#!/usr/bin/env bash
set -euo pipefail
cd {shlex_quote(str(PLUGIN_ROOT))}
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_PREFIX GIT_COMMON_DIR
{command}
"""


def install_one_hook(hooks_dir: Path, hook_name: str, *, force: bool) -> tuple[int, str]:
    hook_path = hooks_dir / hook_name
    body = hook_body(hook_name)
    if hook_path.exists() and hook_path.read_text(encoding="utf-8") != body and not force:
        return 2, f"hook exists with different content: {hook_path}; rerun with --force"
    hook_path.write_text(body, encoding="utf-8")
    hook_path.chmod(hook_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return 0, str(hook_path)


def install_hook(args: argparse.Namespace) -> int:
    code, stdout, stderr = run_command(["git", "rev-parse", "--git-path", "hooks"], timeout=60)
    if code != 0:
        print(compact_output(stdout, stderr) or "git hook path lookup failed", file=sys.stderr)
        return 2
    hooks_dir = Path(stdout.strip())
    if not hooks_dir.is_absolute():
        hooks_dir = PLUGIN_ROOT / hooks_dir
    hooks_dir.mkdir(parents=True, exist_ok=True)
    installed: list[str] = []
    for hook_name in ("pre-commit", "post-commit"):
        hook_code, message = install_one_hook(hooks_dir, hook_name, force=bool(args.force))
        if hook_code != 0:
            print(message, file=sys.stderr)
            return hook_code
        installed.append(message)
    print("\n".join(installed))
    return 0


def shlex_quote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def validate_proof(args: argparse.Namespace) -> int:
    path = Path(args.proof)
    errors: list[str] = []
    try:
        packet = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        packet = {}
        errors.append(f"cannot read proof: {exc}")
    if packet.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA}")
    if packet.get("status") != "pass":
        errors.append("status must be pass")
    plan = packet.get("validation_plan")
    if isinstance(plan, dict) and plan.get("uncovered_changed_files"):
        errors.append("validation_plan must not contain uncovered changed files")
    if args.commit_sha and packet.get("commit_sha") != args.commit_sha:
        errors.append("commit_sha mismatch")
    if not isinstance(packet.get("tests"), list):
        errors.append("tests must be a list")
    print(json.dumps({"schema": SCHEMA, "status": "pass" if not errors else "fail", "errors": errors}, indent=2, sort_keys=True))
    return 0 if not errors else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--commit-sha", default="HEAD")
    run.add_argument("--staged", action="store_true")
    run.add_argument("--state-root", default=str(DEFAULT_STATE_ROOT))
    run.add_argument("--timeout-seconds", type=int, default=600)
    run.add_argument("--allow-low-confidence", action="store_true")
    run.add_argument("--dry-run", action="store_true")
    run.set_defaults(func=run_validation)
    install = sub.add_parser("install-hook")
    install.add_argument("--force", action="store_true")
    install.set_defaults(func=install_hook)
    validate = sub.add_parser("validate-proof")
    validate.add_argument("--proof", required=True)
    validate.add_argument("--commit-sha", default="")
    validate.set_defaults(func=validate_proof)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
