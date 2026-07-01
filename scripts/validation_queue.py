#!/usr/bin/env python3
"""Queue exact-SHA async validation jobs for @bears."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
JOB_SCHEMA = PLUGIN_ROOT / "assets/schemas/validation-job.v1.schema.json"
STATE_SCHEMA = PLUGIN_ROOT / "assets/schemas/validation-state.v1.schema.json"
DEFAULT_REPO_PATH = PLUGIN_ROOT
DEFAULT_TIMEOUT_SECONDS = 600
STATUSES = {"queued", "running", "pass", "fail", "timeout", "infra_fail", "selector_gap", "cancelled"}
FORBIDDEN = ("BEGIN PRIVATE KEY", "raw_secret", ".env=", "credential=", "production data")
GIT_HOOK_ENV_KEYS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_PREFIX", "GIT_COMMON_DIR")

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in GIT_HOOK_ENV_KEYS:
        env.pop(key, None)
    return env


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, packet: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def repo_id(repo_path: Path) -> str:
    try:
        rel = repo_path.resolve().relative_to(Path("/srv/bears").resolve())
        value = rel.as_posix() or "workspace-root"
    except ValueError:
        value = repo_path.name
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value) or "repo"


def job_id(repo_path: Path, commit_sha: str) -> str:
    return f"{repo_id(repo_path)}-{commit_sha[:12]}"


def job_path(commit_sha: str, jid: str) -> Path:
    return PLUGIN_ROOT / "runtime/validation-jobs" / commit_sha / f"{jid}.json"


def state_path(commit_sha: str) -> Path:
    return PLUGIN_ROOT / "runtime/validation-state" / commit_sha / "validation-state.v1.json"


def remediation_path(commit_sha: str) -> Path:
    return PLUGIN_ROOT / "runtime/validation-state" / commit_sha / "remediation.v1.json"


def strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(strings(item))
        return out
    if isinstance(value, dict):
        out: list[str] = []
        for item in value.values():
            out.extend(strings(item))
        return out
    return []


def forbidden(value: Any) -> bool:
    text = "\n".join(strings(value)).casefold()
    return any(marker.casefold() in text for marker in FORBIDDEN)


def compact(text: str) -> str:
    home = os.environ.get("HOME", "")
    text = text.replace(home, "$HOME")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return " | ".join(lines[:6])[:800]


def changed_files_from_git(repo_path: Path, commit_sha: str) -> list[str]:
    proc = subprocess.run(
        ["git", "show", "--name-only", "--format=", commit_sha],
        cwd=str(repo_path),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=30,
        env=clean_env(),
    )
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def parse_changed_files(value: str, repo_path: Path, commit_sha: str) -> list[str]:
    if not value:
        return changed_files_from_git(repo_path, commit_sha)
    candidate = Path(value)
    if candidate.exists():
        data = json.loads(candidate.read_text(encoding="utf-8"))
    else:
        data = json.loads(value)
    if isinstance(data, list):
        return [str(item) for item in data]
    raise ValueError("changed-files must be a JSON array or path to one")


def select_tests(changed_files: list[str]) -> tuple[list[str], list[str], str]:
    command = [sys.executable, "scripts/test_selection.py", "list", "--tier", "fast", "--format", "json"]
    for item in changed_files:
        command.extend(["--changed-file", item])
    proc = subprocess.run(
        command,
        cwd=str(PLUGIN_ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=60,
        env=clean_env(),
    )
    if proc.returncode != 0:
        return [], command, "selector_gap"
    try:
        packet = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return [], command, "selector_gap"
    tests = [str(item) for item in packet.get("tests", [])]
    confidence = str(packet.get("selector_confidence", "unknown"))
    return tests, command, confidence


def build_state(job: dict[str, Any], *, status: str, exit_code: int | None, summary: str, failure: str = "none", remediation: str | None = None) -> dict[str, Any]:
    return {
        "schema": "bears-validation-state.v1",
        "version": "1",
        "status": status,
        "updated_at": utc_now(),
        "repo_path": job["repo_path"],
        "repo_id": job["repo_id"],
        "commit_sha": job["commit_sha"],
        "job_id": job["job_id"],
        "job_path": str(job_path(job["commit_sha"], job["job_id"])),
        "changed_files": job.get("changed_files", []),
        "selected_tests": job.get("selected_tests", []),
        "validators": job.get("validators", []),
        "shard_id": job.get("shard_id", "main"),
        "timeout_seconds": int(job.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)),
        "exit_code": exit_code,
        "failure_classification": failure,
        "retry_count": int(job.get("retry_count", 0)),
        "sanitized_summary": summary,
        "remediation_packet": remediation,
        "local_commit_validation_proof": str(PLUGIN_ROOT / "runtime/local-commit-validation" / f"{job['commit_sha']}.json") if status == "pass" else None,
    }


def enqueue_job(commit_sha: str, changed_files: list[str], *, repo_path: Path = DEFAULT_REPO_PATH, source: str = "post-commit") -> tuple[Path, Path, dict[str, Any]]:
    tests, selector_command, confidence = select_tests(changed_files)
    jid = job_id(repo_path, commit_sha)
    failure = "selector_gap" if confidence == "selector_gap" else "none"
    status = "selector_gap" if failure == "selector_gap" else "queued"
    job = {
        "schema": "bears-validation-job.v1",
        "version": "1",
        "job_id": jid,
        "status": status,
        "queued_at": utc_now(),
        "repo_path": str(repo_path),
        "repo_id": repo_id(repo_path),
        "commit_sha": commit_sha,
        "changed_files": changed_files,
        "selected_tests": tests,
        "validators": ["scripts/test_selection.py run --tier fast"],
        "shard_id": "main",
        "timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
        "exit_code": None,
        "failure_classification": failure,
        "retry_count": 0,
        "sanitized_summary": f"queued from {source}; selector={confidence}",
        "state_path": str(state_path(commit_sha)),
        "selector_command": selector_command,
    }
    state = build_state(job, status=status, exit_code=None, summary=job["sanitized_summary"], failure=failure)
    if forbidden(job) or forbidden(state):
        raise ValueError("restricted data marker detected")
    jp = write_json(job_path(commit_sha, jid), job)
    sp = write_json(state_path(commit_sha), state)
    return jp, sp, job


def validate_packet(path: Path, schema: Path, label: str) -> list[str]:
    try:
        packet = load_json(path)
    except Exception as exc:
        return [f"{label}: cannot read JSON: {exc}"]
    errors = validate_json_schema(packet, schema, label)
    if forbidden(packet):
        errors.append(f"{label}: restricted data marker detected")
    return errors


def validate_state_for_commit(commit_sha: str) -> list[str]:
    return validate_packet(state_path(commit_sha), STATE_SCHEMA, "state")


def command_enqueue(args: argparse.Namespace) -> int:
    repo_path = Path(args.repo_path).resolve()
    changed = parse_changed_files(args.changed_files, repo_path, args.commit_sha)
    jp, sp, job = enqueue_job(args.commit_sha, changed, repo_path=repo_path, source=args.source)
    print(json.dumps({"schema": "bears-validation-queue-event.v1", "status": job["status"], "commit_sha": args.commit_sha, "job_path": str(jp), "state_path": str(sp)}, indent=2, sort_keys=True))
    return 0 if job["status"] == "queued" else 1


def command_status(args: argparse.Namespace) -> int:
    path = state_path(args.commit_sha)
    packet = load_json(path) if path.exists() else {"schema": "bears-validation-state.v1", "status": "missing", "commit_sha": args.commit_sha}
    print(json.dumps(packet, indent=2, sort_keys=True))
    return 0


def command_validate_state(args: argparse.Namespace) -> int:
    errors = validate_state_for_commit(args.commit_sha)
    print(json.dumps({"schema": "bears-validation-state-validation.v1", "status": "pass" if not errors else "fail", "commit_sha": args.commit_sha, "errors": errors}, indent=2, sort_keys=True))
    return 0 if not errors else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    enqueue = sub.add_parser("enqueue")
    enqueue.add_argument("--commit-sha", required=True)
    enqueue.add_argument("--changed-files", default="")
    enqueue.add_argument("--repo-path", default=str(DEFAULT_REPO_PATH))
    enqueue.add_argument("--source", default="post-commit")
    enqueue.set_defaults(func=command_enqueue)
    status = sub.add_parser("status")
    status.add_argument("--commit-sha", required=True)
    status.set_defaults(func=command_status)
    validate = sub.add_parser("validate-state")
    validate.add_argument("--commit-sha", required=True)
    validate.set_defaults(func=command_validate_state)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
