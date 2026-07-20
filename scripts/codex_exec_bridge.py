#!/usr/bin/env python3
"""Orchestrator-side bridge that runs a bounded assignment through `codex exec`."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from typing import Any, Sequence

VERSION = "0.7.0"
DEFAULT_BINARY = "codex"
DEFAULT_SANDBOX = "workspace-write"
DEFAULT_TIMEOUT_SECONDS = 900
MAX_TIMEOUT_SECONDS = 7200
MAX_BRIEF_BYTES = 256 * 1024
MAX_CAPTURE_BYTES = 512 * 1024
GIT_TIMEOUT_SECONDS = 30
TERMINATION_GRACE_SECONDS = 5
ALLOWED_SANDBOX_MODES = ("read-only", "workspace-write")
FORBIDDEN_SANDBOX_MODES = ("danger-full-access",)
REASONING_EFFORTS = ("minimal", "low", "medium", "high", "xhigh")
# Environment variables carrying orchestrator-local state that must not leak
# into the executor process.
STRIPPED_ENVIRONMENT = ("BEARS_APP_WORKFLOW_STATE_DIR",)
# Config keys a caller may not override: they would undo the sandbox and network
# guarantees this bridge exists to enforce.
PROTECTED_CONFIG_PREFIXES = (
    "sandbox",
    "approval_policy",
    "shell_environment_policy",
    "features.",
    "tools.",
)


class CodexExecError(RuntimeError):
    """A stable caller-facing bridge failure."""

    def __init__(self, code: str, message: str | None = None) -> None:
        super().__init__(message or code)
        self.code = code
        self.message = message or code


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def truncate_text(value: str, limit: int = MAX_CAPTURE_BYTES) -> tuple[str, bool]:
    """Return the text bounded to `limit` bytes plus a truncation flag."""
    encoded = value.encode("utf-8", "replace")
    if len(encoded) <= limit:
        return value, False
    return encoded[:limit].decode("utf-8", "replace"), True


def resolve_binary(binary: str) -> str:
    """Accept either a bare command name on PATH or an explicit executable path."""
    candidate = Path(binary)
    if candidate.is_absolute() or len(candidate.parts) > 1:
        resolved = candidate.expanduser()
        if not resolved.is_file() or not os.access(resolved, os.X_OK):
            raise CodexExecError("CODEX_BINARY_MISSING", str(resolved))
        return str(resolved.resolve())
    found = shutil.which(binary)
    if found is None:
        raise CodexExecError("CODEX_BINARY_MISSING", binary)
    return found


def resolve_target(directory: str | os.PathLike[str]) -> tuple[Path, Path]:
    """Resolve the executor working root and the git root that encloses it.

    Both are returned because they can differ: the assignment may be scoped to a
    subdirectory, but evidence must be collected across the whole repository -
    `git ls-files` run inside a subdirectory only reports that subtree.
    """
    path = Path(directory).expanduser()
    try:
        path = path.resolve(strict=True)
    except OSError as exc:
        raise CodexExecError("TARGET_DIR_INVALID", str(exc)) from None
    if not path.is_dir():
        raise CodexExecError("TARGET_DIR_INVALID", str(path))
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
            check=False,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except OSError as exc:
        raise CodexExecError("TARGET_DIR_INVALID", str(exc)) from None
    except subprocess.TimeoutExpired:
        raise CodexExecError("TARGET_DIR_INVALID", "git root check timed out") from None
    if result.returncode != 0:
        raise CodexExecError("TARGET_NOT_GIT", str(path))
    repository_root = Path(result.stdout.strip())
    try:
        repository_root = repository_root.resolve(strict=True)
    except OSError as exc:
        raise CodexExecError("TARGET_DIR_INVALID", str(exc)) from None
    return path, repository_root


def validate_brief(brief: str) -> str:
    if not isinstance(brief, str) or not brief.strip():
        raise CodexExecError("BRIEF_EMPTY")
    if len(brief.encode("utf-8")) > MAX_BRIEF_BYTES:
        raise CodexExecError("BRIEF_TOO_LARGE")
    return brief


def validate_sandbox(mode: str) -> str:
    if mode in FORBIDDEN_SANDBOX_MODES:
        raise CodexExecError("SANDBOX_MODE_FORBIDDEN", mode)
    if mode not in ALLOWED_SANDBOX_MODES:
        raise CodexExecError("SANDBOX_MODE_INVALID", mode)
    return mode


def validate_timeout(timeout_seconds: float) -> float:
    try:
        value = float(timeout_seconds)
    except (TypeError, ValueError):
        raise CodexExecError("TIMEOUT_INVALID", repr(timeout_seconds)) from None
    if not value > 0 or value > MAX_TIMEOUT_SECONDS:
        raise CodexExecError("TIMEOUT_INVALID", str(value))
    return value


def validate_reasoning_effort(effort: str | None) -> str | None:
    if effort is None:
        return None
    if effort not in REASONING_EFFORTS:
        raise CodexExecError("REASONING_EFFORT_INVALID", effort)
    return effort


def validate_extra_config(overrides: Sequence[str]) -> list[str]:
    """Reject caller config overrides that would weaken the sandbox."""
    checked: list[str] = []
    for override in overrides:
        if "=" not in override:
            raise CodexExecError("CONFIG_OVERRIDE_INVALID", override)
        key = override.split("=", 1)[0].strip().lower()
        if any(key.startswith(prefix) for prefix in PROTECTED_CONFIG_PREFIXES):
            raise CodexExecError("CONFIG_OVERRIDE_FORBIDDEN", override)
        checked.append(override)
    return checked


def git_lines(target: Path, arguments: Sequence[str]) -> list[str]:
    """Run a NUL-delimited read-only git query inside the target repository."""
    try:
        result = subprocess.run(
            ["git", "-C", str(target), *arguments],
            check=False,
            capture_output=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except OSError as exc:
        raise CodexExecError("GIT_SNAPSHOT_FAILED", str(exc)) from None
    except subprocess.TimeoutExpired:
        raise CodexExecError("GIT_SNAPSHOT_FAILED", "git query timed out") from None
    if result.returncode != 0:
        raise CodexExecError("GIT_SNAPSHOT_FAILED", result.stderr.decode("utf-8", "replace").strip())
    return [chunk for chunk in result.stdout.decode("utf-8", "surrogateescape").split("\0") if chunk]


def porcelain_status(target: Path) -> list[str]:
    return git_lines(target, ["status", "--porcelain=v1", "-z", "--untracked-files=all"])


def file_digest(path: Path) -> str:
    """Digest one working-tree file; unreadable entries get a stable marker."""
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError:
        return "unreadable"
    return "sha256:" + digest.hexdigest()


def tree_snapshot(repository_root: Path) -> dict[str, str]:
    """Map every non-ignored working-tree path to a content digest.

    Paths are relative to the repository root, not to the executor working root,
    so an assignment scoped to a subdirectory still surfaces stray edits made
    elsewhere in the repository.

    Tracked-but-absent paths are recorded as `missing` so deletions are visible
    even when the index already knew about them before the run. Gitignored files
    are deliberately outside the evidence set: they are build output, not work
    product.
    """
    paths = git_lines(repository_root, ["ls-files", "-z", "--cached", "--others", "--exclude-standard"])
    snapshot: dict[str, str] = {}
    for relative in sorted(set(paths)):
        absolute = repository_root / relative
        if absolute.is_symlink():
            try:
                snapshot[relative] = "symlink:" + sha256_bytes(os.readlink(absolute).encode("utf-8", "surrogateescape"))
            except OSError:
                snapshot[relative] = "unreadable"
            continue
        if not absolute.exists():
            snapshot[relative] = "missing"
            continue
        if absolute.is_dir():
            # A gitlink (submodule) entry; content lives in another repository.
            snapshot[relative] = "gitlink"
            continue
        if not absolute.is_file():
            # A FIFO or device node: opening it could block forever.
            snapshot[relative] = "special"
            continue
        snapshot[relative] = file_digest(absolute)
    return snapshot


def diff_snapshots(before: dict[str, str], after: dict[str, str]) -> dict[str, list[str]]:
    added: list[str] = []
    modified: list[str] = []
    deleted: list[str] = []
    for relative, digest in after.items():
        previous = before.get(relative)
        if previous is None:
            if digest != "missing":
                added.append(relative)
            continue
        if previous == digest:
            continue
        if digest == "missing":
            deleted.append(relative)
        elif previous == "missing":
            added.append(relative)
        else:
            modified.append(relative)
    for relative, digest in before.items():
        if relative in after or digest == "missing":
            continue
        deleted.append(relative)
    return {
        "added": sorted(added),
        "modified": sorted(modified),
        "deleted": sorted(deleted),
    }


def build_command(
    *,
    binary: str,
    target: Path,
    sandbox: str,
    model: str | None,
    reasoning_effort: str | None,
    network_access: bool,
    json_events: bool,
    last_message_path: Path,
    extra_config: Sequence[str] = (),
) -> list[str]:
    """Assemble the argv for `codex exec`.

    The brief is never interpolated here: `-` tells codex to read instructions
    from stdin, so no shell quoting is involved at any point.
    """
    command = [
        binary,
        "exec",
        "--cd",
        str(target),
        "--sandbox",
        sandbox,
        "--color",
        "never",
        "--output-last-message",
        str(last_message_path),
    ]
    if sandbox == "workspace-write":
        value = "true" if network_access else "false"
        command += ["-c", f"sandbox_workspace_write.network_access={value}"]
    if model:
        command += ["--model", model]
    if reasoning_effort:
        command += ["-c", f'model_reasoning_effort="{reasoning_effort}"']
    for override in extra_config:
        command += ["-c", override]
    if json_events:
        command.append("--json")
    command.append("-")
    return command


def build_environment(codex_home: str | os.PathLike[str] | None) -> dict[str, str]:
    environment = dict(os.environ)
    for name in STRIPPED_ENVIRONMENT:
        environment.pop(name, None)
    if codex_home is not None:
        environment["CODEX_HOME"] = str(Path(codex_home).expanduser())
    environment["CODEX_EXEC_BRIDGE_VERSION"] = VERSION
    return environment


def terminate_process_tree(process: subprocess.Popen[bytes]) -> None:
    """Signal the whole child process group so no executor child is orphaned."""
    if process.poll() is not None:
        return
    try:
        group = os.getpgid(process.pid)
    except OSError:
        group = None
    for sig, wait_seconds in ((signal.SIGTERM, TERMINATION_GRACE_SECONDS), (signal.SIGKILL, TERMINATION_GRACE_SECONDS)):
        try:
            if group is not None:
                os.killpg(group, sig)
            else:
                process.send_signal(sig)
        except (OSError, ProcessLookupError):
            return
        try:
            process.wait(timeout=wait_seconds)
            return
        except subprocess.TimeoutExpired:
            continue


def run_assignment(
    *,
    brief: str,
    target_dir: str | os.PathLike[str],
    sandbox: str = DEFAULT_SANDBOX,
    model: str | None = None,
    reasoning_effort: str | None = None,
    network_access: bool = False,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    binary: str = DEFAULT_BINARY,
    codex_home: str | os.PathLike[str] | None = None,
    json_events: bool = False,
    extra_config: Sequence[str] = (),
) -> dict[str, Any]:
    """Run one bounded assignment through `codex exec` and return evidence.

    Input and precondition problems raise `CodexExecError`. Execution outcomes
    (non-zero exit, timeout) come back as a result with `ok: false` and a code,
    so the caller still receives the captured evidence.
    """
    brief = validate_brief(brief)
    sandbox = validate_sandbox(sandbox)
    reasoning_effort = validate_reasoning_effort(reasoning_effort)
    timeout_seconds = validate_timeout(timeout_seconds)
    extra_config = validate_extra_config(extra_config)
    resolved_binary = resolve_binary(binary)
    target, repository_root = resolve_target(target_dir)

    before_tree = tree_snapshot(repository_root)
    before_status = porcelain_status(repository_root)

    # Scratch state stays outside the target tree so it is never mistaken for
    # an executor-produced change.
    with tempfile.TemporaryDirectory(prefix="codex-exec-bridge-") as scratch_name:
        scratch = Path(scratch_name)
        last_message_path = scratch / "last-message.txt"
        command = build_command(
            binary=resolved_binary,
            target=target,
            sandbox=sandbox,
            model=model,
            reasoning_effort=reasoning_effort,
            network_access=network_access,
            json_events=json_events,
            last_message_path=last_message_path,
            extra_config=extra_config,
        )
        started = time.monotonic()
        timed_out = False
        spawn_error: str | None = None
        exit_status: int | None = None
        stdout_bytes = b""
        stderr_bytes = b""
        try:
            process = subprocess.Popen(
                command,
                cwd=str(scratch),
                env=build_environment(codex_home),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
        except OSError as exc:
            raise CodexExecError("CODEX_SPAWN_FAILED", str(exc)) from None
        try:
            stdout_bytes, stderr_bytes = process.communicate(
                input=brief.encode("utf-8"), timeout=timeout_seconds
            )
            exit_status = process.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            terminate_process_tree(process)
            try:
                stdout_bytes, stderr_bytes = process.communicate(timeout=TERMINATION_GRACE_SECONDS)
            except (subprocess.TimeoutExpired, ValueError, OSError):
                stdout_bytes, stderr_bytes = b"", b""
            exit_status = process.returncode
        except OSError as exc:
            spawn_error = str(exc)
            terminate_process_tree(process)
            exit_status = process.returncode
        finally:
            terminate_process_tree(process)
        duration = time.monotonic() - started
        last_message = ""
        if last_message_path.is_file():
            last_message = last_message_path.read_text(encoding="utf-8", errors="replace")

    # A failed post-run snapshot must not discard the execution evidence that
    # was already captured, so it degrades into a result code instead.
    snapshot_error: str | None = None
    try:
        after_tree = tree_snapshot(repository_root)
        after_status = porcelain_status(repository_root)
        changed = diff_snapshots(before_tree, after_tree)
    except CodexExecError as exc:
        snapshot_error = exc.message
        after_status = []
        changed = {"added": [], "modified": [], "deleted": []}

    stdout_text, stdout_truncated = truncate_text(stdout_bytes.decode("utf-8", "replace"))
    stderr_text, stderr_truncated = truncate_text(stderr_bytes.decode("utf-8", "replace"))
    last_message_text, last_message_truncated = truncate_text(last_message)

    if timed_out:
        code = "CODEX_EXEC_TIMEOUT"
    elif spawn_error is not None:
        code = "CODEX_EXEC_IO_FAILED"
    elif exit_status != 0:
        code = "CODEX_EXEC_FAILED"
    elif snapshot_error is not None:
        code = "GIT_SNAPSHOT_FAILED"
    else:
        code = "OK"

    return {
        "ok": code == "OK",
        "code": code,
        "version": VERSION,
        "command": command,
        "target_dir": str(target),
        "repository_root": str(repository_root),
        "sandbox": sandbox,
        "network_access": bool(network_access) if sandbox == "workspace-write" else False,
        "model": model,
        "reasoning_effort": reasoning_effort,
        "timeout_seconds": timeout_seconds,
        "timed_out": timed_out,
        "exit_status": exit_status,
        "duration_seconds": round(duration, 3),
        "brief_digest": sha256_bytes(brief.encode("utf-8")),
        "stdout": stdout_text,
        "stdout_truncated": stdout_truncated,
        "stderr": stderr_text,
        "stderr_truncated": stderr_truncated,
        "last_message": last_message_text,
        "last_message_truncated": last_message_truncated,
        "error": spawn_error or snapshot_error,
        "changed_files": changed,
        "changed_file_count": len(changed["added"]) + len(changed["modified"]) + len(changed["deleted"]),
        "status_before": before_status,
        "status_after": after_status,
    }


def read_brief(args: argparse.Namespace) -> str:
    if args.brief_file is not None:
        path = Path(args.brief_file).expanduser()
        try:
            return path.read_text(encoding="utf-8")
        except OSError as exc:
            raise CodexExecError("BRIEF_UNREADABLE", str(exc)) from None
    if args.brief is not None:
        return args.brief
    return sys.stdin.read()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    runner = subparsers.add_parser("run", help="run one bounded assignment through codex exec")
    runner.add_argument("--cd", dest="target_dir", required=True, help="executor working root (a git repository)")
    source = runner.add_mutually_exclusive_group()
    source.add_argument("--brief", help="assignment text; omit to read the brief from stdin")
    source.add_argument("--brief-file", help="file holding the assignment text")
    runner.add_argument("--sandbox", choices=ALLOWED_SANDBOX_MODES, default=DEFAULT_SANDBOX)
    runner.add_argument("--model")
    runner.add_argument("--reasoning-effort", choices=REASONING_EFFORTS)
    runner.add_argument("--allow-network", action="store_true", help="permit network access inside workspace-write")
    runner.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    runner.add_argument("--codex-binary", default=DEFAULT_BINARY)
    runner.add_argument("--codex-home")
    runner.add_argument("--json-events", action="store_true", help="ask codex for JSONL event output")
    runner.add_argument("-c", "--config", dest="extra_config", action="append", default=[])
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.command != "run":
        return 2
    try:
        result = run_assignment(
            brief=read_brief(args),
            target_dir=args.target_dir,
            sandbox=args.sandbox,
            model=args.model,
            reasoning_effort=args.reasoning_effort,
            network_access=args.allow_network,
            timeout_seconds=args.timeout,
            binary=args.codex_binary,
            codex_home=args.codex_home,
            json_events=args.json_events,
            extra_config=args.extra_config,
        )
    except CodexExecError as exc:
        print(canonical_json({"ok": False, "code": exc.code, "message": exc.message}))
        return 2
    print(canonical_json(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
