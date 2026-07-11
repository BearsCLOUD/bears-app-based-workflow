#!/usr/bin/env python3
"""Promote one verified main SHA through a fixed Codex marketplace gateway.

Entry point: ``main``. Boundary: run as ``ai1``; invoke only fixed Git and
Codex binaries; never execute files from the repository checkout.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import pwd
import re
import secrets
import stat
import subprocess
import sys
from typing import Any
from urllib import parse, request

PLUGIN = "bears-app-based-workflow"
MARKETPLACE = "bears-app-based-workflow"
REPOSITORY = "https://github.com/BearsCLOUD/bears-app-based-workflow.git"
REPOSITORY_SHORTHAND = "BearsCLOUD/bears-app-based-workflow"
MAIN_REF = "refs/remotes/origin/main"
CODEX_HOME = Path("/srv/bears/codex/ai1")
MARKETPLACE_ROOT = CODEX_HOME / ".tmp/marketplaces" / MARKETPLACE
STATE_DIR = CODEX_HOME / ".local/state/bears-plugin-deploy"
STATE_FILE = STATE_DIR / f"{PLUGIN}.json"
LOCK_FILE = STATE_DIR / f"{PLUGIN}.lock"
MIRROR = STATE_DIR / "repository.git"
GIT = "/usr/bin/git"
CODEX = "/usr/local/bin/codex"
SHA_RE = re.compile(r"[0-9a-f]{40}")
VERSION_RE = re.compile(r"\d+\.\d+\.\d+\+codex\.\d{14}")
DEPLOY_RECEIPT_SCHEMA = "bears-plugin-deploy-state.v1"
SENTRY_DSN_FILE = Path("/home/ai1/.config/bears-app-based-workflow/credentials/sentry-dsn")
SENTRY_SERVICE = "bears-app-based-workflow"
SENTRY_COMPONENT = "deploy-plugin-gateway"
SENTRY_TIMEOUT_SECONDS = 2
ACTIONABLE_ERROR_CODES = frozenset(
    {
        "unhandled-exception",
        "receipt-corruption",
        "mutation-failure-after-start",
        "post-mutation-failure",
        "recovery-activated",
        "recovery-failure",
    }
)
PAYLOAD_PATHS = (
    ".codex-plugin",
    "agents",
    "skills",
    "scripts",
    "hooks",
    "assets",
    ".app.json",
    ".mcp.json",
    "AGENTS.md",
    "install",
)
ENV = {
    "HOME": "/home/ai1",
    "CODEX_HOME": str(CODEX_HOME),
    "PATH": "/usr/local/bin:/usr/bin:/bin",
    "LANG": "C.UTF-8",
}


class DeployError(RuntimeError):
    """A promotion invariant failed without authorizing a state advance."""

    def __init__(self, message: str, *, error_code: str | None = None):
        super().__init__(message)
        self.error_code = error_code


class DeployContext:
    """Sanitized state used to classify one gateway outcome."""

    def __init__(self, sha: str):
        self.sha = sha
        self.version = "unknown"
        self.phase = "pre-mutation"


def sentry_event(error_code: str, context: DeployContext) -> dict[str, Any]:
    """Build one normalized event without exception or process payload data."""
    if error_code not in ACTIONABLE_ERROR_CODES:
        raise ValueError("non-actionable event code")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
    workflow_run = f"{run_id}:{run_attempt}" if run_id.isdigit() and run_attempt.isdigit() else "unknown"
    fields = {
        "error_code": error_code,
        "service": SENTRY_SERVICE,
        "component": SENTRY_COMPONENT,
        "operation": "promote",
        "repository": REPOSITORY_SHORTHAND,
        "plugin": PLUGIN,
        "git_sha": context.sha if SHA_RE.fullmatch(context.sha) else "unknown",
        "plugin_version": context.version if VERSION_RE.fullmatch(context.version) else "unknown",
        "workflow_run": workflow_run,
        "receipt_schema": DEPLOY_RECEIPT_SCHEMA,
    }
    event_id = secrets.token_hex(16)
    return {
        "event_id": event_id,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "level": "error",
        "logger": "bears.plugin.deploy",
        "message": "actionable deployment failure",
        "platform": "other",
        "fingerprint": [SENTRY_SERVICE, SENTRY_COMPONENT, error_code],
        "tags": fields,
        "contexts": {"deployment": fields},
    }


def sentry_request(dsn: str, event: dict[str, Any]) -> request.Request:
    """Encode one Sentry envelope; callers retain the DSN only in memory."""
    parsed = parse.urlsplit(dsn)
    path_parts = parsed.path.rstrip("/").rsplit("/", 1)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or not parsed.username
        or len(path_parts) != 2
        or not path_parts[1].isdigit()
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("invalid DSN")
    host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    if parsed.port is not None:
        host = f"{host}:{parsed.port}"
    endpoint = parse.urlunsplit(
        ("https", host, f"{path_parts[0]}/api/{path_parts[1]}/envelope/", "", "")
    )
    auth = f"Sentry sentry_version=7, sentry_client=bears-plugin-gateway/1, sentry_key={parse.unquote(parsed.username)}"
    if parsed.password:
        auth += f", sentry_secret={parse.unquote(parsed.password)}"
    header = json.dumps({"event_id": event["event_id"]}, separators=(",", ":"))
    item = json.dumps({"type": "event", "content_type": "application/json"}, separators=(",", ":"))
    payload = json.dumps(event, sort_keys=True, separators=(",", ":"))
    return request.Request(
        endpoint,
        data=f"{header}\n{item}\n{payload}".encode(),
        headers={"Content-Type": "application/x-sentry-envelope", "X-Sentry-Auth": auth},
        method="POST",
    )


def read_sentry_dsn() -> str | None:
    """Read the fixed protected credential without following links."""
    flags = os.O_RDONLY | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(SENTRY_DSN_FILE, flags)
    except OSError:
        return None
    try:
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.geteuid()
            or stat.S_IMODE(metadata.st_mode) != 0o600
        ):
            return None
        raw = os.read(descriptor, 4097)
    finally:
        os.close(descriptor)
    if not raw or len(raw) > 4096:
        return None
    try:
        return raw.decode("utf-8").strip()
    except UnicodeError:
        return None


def report_sentry(error_code: str, context: DeployContext, *, opener: Any = request.urlopen) -> str | None:
    """Deliver best effort without changing the deployment outcome."""
    try:
        dsn = read_sentry_dsn()
        if dsn is None:
            return None
        event = sentry_event(error_code, context)
        with opener(sentry_request(dsn, event), timeout=SENTRY_TIMEOUT_SECONDS) as response:
            response.read(1)
        return f"sentry-event:{event['event_id']}"
    except Exception:
        return None


def run(argv: list[str], *, ok: tuple[int, ...] = (0,)) -> subprocess.CompletedProcess[str]:
    if not argv or argv[0] not in {GIT, CODEX}:
        raise DeployError("only the fixed git and codex binaries may be invoked")
    result = subprocess.run(argv, env=ENV, text=True, capture_output=True, check=False)
    if result.returncode not in ok:
        detail = (result.stderr or result.stdout).strip()
        raise DeployError(f"command failed ({result.returncode}): {argv[1]}: {detail}")
    return result


def run_json(argv: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(run(argv).stdout)
    except json.JSONDecodeError as exc:
        raise DeployError(f"invalid JSON from {argv[1]}") from exc
    if not isinstance(value, dict):
        raise DeployError(f"unexpected JSON shape from {argv[1]}")
    return value


def git(repo: Path, *args: str, ok: tuple[int, ...] = (0,)) -> subprocess.CompletedProcess[str]:
    return run([GIT, "-C", str(repo), *args], ok=ok)


def git_text(repo: Path, *args: str) -> str:
    return git(repo, *args).stdout.strip()


def exact_remote(repo: Path) -> None:
    urls = git_text(repo, "remote", "get-url", "--all", "origin").splitlines()
    if urls != [REPOSITORY]:
        raise DeployError(f"repository origin is not fixed to {REPOSITORY}")


def is_ancestor(repo: Path, older: str, newer: str) -> bool:
    result = git(repo, "merge-base", "--is-ancestor", older, newer, ok=(0, 1))
    return result.returncode == 0


def prepare_mirror(requested: str) -> str:
    if MIRROR.is_symlink():
        raise DeployError("mirror path must not be a symlink")
    if not MIRROR.exists():
        run([GIT, "init", "--bare", str(MIRROR)])
        git(MIRROR, "remote", "add", "origin", REPOSITORY)
    exact_remote(MIRROR)
    git(MIRROR, "fetch", "--force", "--no-tags", "origin", "+refs/heads/main:" + MAIN_REF)
    main_sha = git_text(MIRROR, "rev-parse", MAIN_REF)
    if not is_ancestor(MIRROR, requested, main_sha):
        raise DeployError("requested SHA is not reachable from the fixed repository main branch")
    return main_sha


def manifest(repo: Path, sha: str) -> dict[str, Any]:
    try:
        value = json.loads(git_text(repo, "show", f"{sha}:.codex-plugin/plugin.json"))
    except json.JSONDecodeError as exc:
        raise DeployError("plugin manifest is not valid JSON") from exc
    if (
        not isinstance(value, dict)
        or value.get("name") != PLUGIN
        or value.get("repository") != REPOSITORY.removesuffix(".git")
        or not VERSION_RE.fullmatch(str(value.get("version", "")))
    ):
        raise DeployError("plugin manifest identity, repository, or cachebuster is invalid")
    return value


def validate_marketplace(repo: Path, sha: str) -> None:
    try:
        value = json.loads(git_text(repo, "show", f"{sha}:.agents/plugins/marketplace.json"))
    except json.JSONDecodeError as exc:
        raise DeployError("marketplace catalog is not valid JSON") from exc
    entries = value.get("plugins") if isinstance(value, dict) else None
    if (
        value.get("name") != MARKETPLACE
        or not isinstance(entries, list)
        or len(entries) != 1
        or entries[0].get("name") != PLUGIN
        or entries[0].get("source") != {"source": "local", "path": "."}
    ):
        raise DeployError("marketplace identity or plugin source is not fixed")


def marketplace_row(*, create: bool, context: DeployContext | None = None) -> dict[str, Any]:
    payload = run_json([CODEX, "plugin", "marketplace", "list", "--json"])
    rows = payload.get("marketplaces", [])
    row = next((item for item in rows if item.get("name") == MARKETPLACE), None)
    if row is None and create:
        if context is not None:
            context.phase = "mutation"
        run_json(
            [
                CODEX,
                "plugin",
                "marketplace",
                "add",
                REPOSITORY_SHORTHAND,
                "--ref",
                "main",
                "--json",
            ]
        )
        if context is not None:
            context.phase = "post-mutation"
        return marketplace_row(create=False, context=context)
    if not isinstance(row, dict):
        raise DeployError("fixed marketplace is not configured")
    source = row.get("marketplaceSource")
    if source != {"sourceType": "git", "source": REPOSITORY}:
        raise DeployError("configured marketplace does not use the fixed Git repository")
    if Path(str(row.get("root", ""))).resolve() != MARKETPLACE_ROOT.resolve():
        raise DeployError("configured marketplace root is not the fixed Codex path")
    return row


def payload_fingerprint(repo: Path, sha: str) -> str:
    listing = git(repo, "ls-tree", "-r", "--full-tree", sha, "--", *PAYLOAD_PATHS).stdout
    return hashlib.sha256(listing.encode()).hexdigest()


def installed_row() -> dict[str, Any]:
    payload = run_json([CODEX, "plugin", "list", "--available", "--json"])
    rows = payload.get("plugins", [])
    row = next((item for item in rows if item.get("pluginId") == f"{PLUGIN}@{MARKETPLACE}"), None)
    if not isinstance(row, dict):
        raise DeployError("fixed plugin is absent from Codex plugin state")
    if row.get("marketplaceSource") != {"sourceType": "git", "source": REPOSITORY}:
        raise DeployError("installed plugin reports a non-fixed marketplace source")
    return row


def verify_install(requested: str, expected_version: str) -> str:
    row = installed_row()
    if not row.get("installed") or not row.get("enabled") or row.get("version") != expected_version:
        raise DeployError("installed plugin is disabled or has the wrong version")
    cache = CODEX_HOME / "plugins/cache" / MARKETPLACE / PLUGIN / expected_version
    if cache.is_symlink() or not (cache / ".git").is_dir():
        raise DeployError("installed plugin cache is missing or unsafe")
    exact_remote(cache)
    cache_sha = git_text(cache, "rev-parse", "HEAD")
    if cache_sha != requested:
        raise DeployError("installed plugin cache is not the exact requested SHA")
    dirty_payload = git(
        cache,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        "--",
        *PAYLOAD_PATHS,
    ).stdout
    if dirty_payload:
        raise DeployError("installed runtime payload has staged, modified, or untracked files")
    requested_fingerprint = payload_fingerprint(MIRROR, requested)
    if payload_fingerprint(cache, cache_sha) != requested_fingerprint:
        raise DeployError("installed plugin payload does not match the requested source state")
    if manifest(cache, cache_sha).get("version") != expected_version:
        raise DeployError("installed cache manifest version is inconsistent")
    return requested_fingerprint


def load_state() -> dict[str, Any] | None:
    if not STATE_FILE.exists():
        return None
    try:
        value = json.loads(STATE_FILE.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise DeployError("deployment receipt is unreadable", error_code="receipt-corruption") from exc
    if not isinstance(value, dict) or value.get("schema") != DEPLOY_RECEIPT_SCHEMA:
        raise DeployError("deployment receipt has an invalid schema", error_code="receipt-corruption")
    return value


def save_state(sha: str, version: str, fingerprint: str) -> None:
    value = {
        "schema": DEPLOY_RECEIPT_SCHEMA,
        "repository": REPOSITORY,
        "marketplace": MARKETPLACE,
        "plugin": PLUGIN,
        "sha": sha,
        "version": version,
        "payload_fingerprint": fingerprint,
    }
    temporary = STATE_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True) + "\n")
    os.chmod(temporary, 0o600)
    os.replace(temporary, STATE_FILE)


def promote(requested: str, context: DeployContext) -> str:
    prepare_mirror(requested)
    requested_manifest = manifest(MIRROR, requested)
    context.version = str(requested_manifest["version"])
    validate_marketplace(MIRROR, requested)
    state = load_state()
    if state is not None:
        current = str(state.get("sha", ""))
        current_version = str(state.get("version", ""))
        if not SHA_RE.fullmatch(current) or not VERSION_RE.fullmatch(current_version):
            raise DeployError("deployment receipt identity is invalid", error_code="receipt-corruption")
        if requested == current:
            verify_install(current, current_version)
            return "already-deployed"
        if is_ancestor(MIRROR, requested, current):
            verify_install(current, current_version)
            return "skipped-older-ancestor"
        if not is_ancestor(MIRROR, current, requested):
            raise DeployError("non-fast-forward promotion requires a separate rollback authorization")

    marketplace_row(create=True, context=context)
    context.phase = "mutation"
    run_json([CODEX, "plugin", "marketplace", "upgrade", MARKETPLACE, "--json"])
    context.phase = "post-mutation"
    marketplace_row(create=False)
    exact_remote(MARKETPLACE_ROOT)
    snapshot_sha = git_text(MARKETPLACE_ROOT, "rev-parse", "HEAD")
    if snapshot_sha != requested:
        if is_ancestor(MIRROR, requested, snapshot_sha):
            return "skipped-older-ancestor"
        raise DeployError("marketplace snapshot is not the requested GitHub SHA")

    context.phase = "mutation"
    run_json([CODEX, "plugin", "add", f"{PLUGIN}@{MARKETPLACE}", "--json"])
    context.phase = "post-mutation"
    version = str(requested_manifest["version"])
    fingerprint = verify_install(requested, version)
    context.phase = "mutation"
    save_state(requested, version, fingerprint)
    context.phase = "complete"
    return "deployed"


def main() -> int:
    if pwd.getpwuid(os.geteuid()).pw_name != "ai1" or os.geteuid() == 0:
        print("deploy-plugin: gateway must run as non-root ai1", file=sys.stderr)
        return 2
    if len(sys.argv) != 2 or not SHA_RE.fullmatch(sys.argv[1]):
        print("deploy-plugin: expected one exact lowercase 40-character SHA", file=sys.stderr)
        return 2
    context = DeployContext(sys.argv[1])
    descriptor = -1
    try:
        STATE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor = os.open(
            LOCK_FILE,
            os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
        )
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        status = promote(sys.argv[1], context)
    except (DeployError, OSError) as exc:
        error_code = exc.error_code if isinstance(exc, DeployError) else None
        if error_code is None and context.phase == "mutation":
            error_code = "mutation-failure-after-start"
        elif error_code is None and context.phase == "post-mutation":
            error_code = "post-mutation-failure"
        if error_code in ACTIONABLE_ERROR_CODES:
            report_sentry(error_code, context)
        print(f"deploy-plugin: {exc}", file=sys.stderr)
        return 1
    except Exception:
        report_sentry("unhandled-exception", context)
        print("deploy-plugin: unhandled gateway failure", file=sys.stderr)
        return 1
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    print(json.dumps({"plugin": PLUGIN, "sha": sys.argv[1], "status": status}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
