#!/usr/bin/env python3
"""Promote one verified main SHA through a fixed Codex marketplace gateway.

Entry point: ``main``. Boundary: run as ``ai1``; invoke only fixed Git and
Codex binaries; never execute files from the repository checkout.
"""

from __future__ import annotations

import base64
import binascii
import ctypes
import errno
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
import tomllib
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
INTENT_FILE = STATE_DIR / f"{PLUGIN}.promotion-intent.json"
LOCK_FILE = STATE_DIR / f"{PLUGIN}.lock"
ROLE_GENERATIONS_DIR = STATE_DIR / "role-generations"
ROLE_RECEIPT_DIR = CODEX_HOME / "state"
ROLE_RECEIPT_FILE = ROLE_RECEIPT_DIR / f"{PLUGIN}-role-sync.json"
MIRROR = STATE_DIR / "repository.git"
GIT = "/usr/bin/git"
CODEX = "/usr/local/bin/codex"
SHA_RE = re.compile(r"[0-9a-f]{40}")
FINGERPRINT_RE = re.compile(r"[0-9a-f]{64}")
VERSION_RE = re.compile(r"\d+\.\d+\.\d+\+codex\.\d{14}")
LEGACY_DEPLOY_RECEIPT_SCHEMA = "bears-plugin-deploy-state.v1"
DEPLOY_RECEIPT_SCHEMA = "bears-plugin-deploy-state.v2"
PROMOTION_INTENT_SCHEMA = "bears-plugin-promotion-intent.v3"
LEGACY_ROLE_RECEIPT_SCHEMA = "bears-role-install-receipt.v1"
ROLE_RECEIPT_SCHEMA = "bears-role-install-receipt.v2"
EXPECTED_ROLE_COUNT = 11
CANONICAL_ROLE_NAMES = (
    "app-worker",
    "diagnostic-command-runner",
    "domain-lane-orchestrator",
    "explorer",
    "primary-source-researcher",
    "role-profile-architect",
    "runtime-evidence-reader",
    "security-analysis-critic",
    "wave-change-critic",
    "worker",
    "workflow-orchestrator",
)
LEGACY_ROLE_VERSION = "0.1.0+codex.20260711144358"
LEGACY_ROLE_NAMES = (
    "diagnostic-command-runner",
    "domain-lane-orchestrator",
    "explorer",
    "primary-source-researcher",
    "role-profile-architect",
    "runtime-evidence-reader",
    "security-analysis-critic",
    "worker",
    "workflow-orchestrator",
)
LEGACY_ROLE_SHA256 = {
    "diagnostic-command-runner": "4ce047462f8f56d945494df90a685c7390c24ba5327e290dac93a3b100031b26",
    "domain-lane-orchestrator": "a55e4f0be243d1ac3db643dbe3c6caba26451dcea2b731895d30909436a73ccf",
    "explorer": "7fefdd33d132c136d7ac4cc458abdcbfe06a3921d343dcb10a00ec654cdbee04",
    "primary-source-researcher": "93a9a36c82b5e496d59ea1d3da57210f1163d6a641c921a469cbda804ce13921",
    "role-profile-architect": "310ba40757b04847d6bd80e98c34dfd728d17eab96e31f2896e4eb293f1f61d9",
    "runtime-evidence-reader": "f1f194a3c6424a2237e27a270b545ea673361568ad988683419bc91aceda5961",
    "security-analysis-critic": "8e1c41b5988155c77dcd356d4f274084a9f8c476fbffde827662b768edb89be2",
    "worker": "2e6a3faf9c948ce425aa221c6f1e1a80510691489d3d23943937609ed06ebfcb",
    "workflow-orchestrator": "7d27b39cb78f1e8f8baa531ac129ec6191f62bc0fd42b06957203e136bc437c7",
}
PROFILE_FIELDS = frozenset(
    {"name", "description", "model", "model_reasoning_effort", "sandbox_mode", "developer_instructions"}
)
AGENTS_TREE_PATHS = frozenset(
    {"agents/README.md", *(f"agents/{name}.toml" for name in CANONICAL_ROLE_NAMES)}
)
BEGIN_ROLE_MARKER = b"# >>> bears-app-based-workflow agent roles (managed by ./install)"
END_ROLE_MARKER = b"# <<< bears-app-based-workflow agent roles (managed by ./install)"
CONFIG_LOCK_NAME = ".config.toml.coordination.lock"
CONFIG_MAX_BYTES = 1024 * 1024
PROFILE_MAX_BYTES = 256 * 1024
ROLE_RECEIPT_MAX_BYTES = 64 * 1024
RECEIPT_MAX_BYTES = 64 * 1024
INTENT_MAX_BYTES = 2 * 1024 * 1024
SUBPROCESS_DIAGNOSTIC_LIMIT = 512
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
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_TERMINAL_PROMPT": "0",
}
FIXED_MARKETPLACE_SOURCE = {"sourceType": "git", "source": REPOSITORY}
RENAME_NOREPLACE = 1
RENAME_EXCHANGE = 2
SNAPSHOT_METADATA_FIELDS = frozenset(
    {"dev", "ino", "mode", "uid", "gid", "nlink", "size", "mtime_ns"}
)


class DeployError(RuntimeError):
    """A promotion invariant failed without authorizing a state advance."""

    def __init__(self, message: str, *, error_code: str | None = None):
        super().__init__(message)
        self.error_code = error_code


class FilePublication:
    """One renameat2 publication whose displaced preimage remains recoverable."""

    def __init__(
        self,
        *,
        directory: int,
        target: str,
        exchange_name: str,
        expected: tuple[bytes, os.stat_result] | None,
        published: tuple[bytes, os.stat_result],
        reader: Any,
        label: str,
        retained: bool,
        created: bool,
    ):
        self.directory = directory
        self.target = target
        self.exchange_name = exchange_name
        self.expected = expected
        self.published = published
        self.reader = reader
        self.label = label
        self.retained = retained
        self.created = created


class DeployContext:
    """Sanitized state used to classify one gateway outcome."""

    def __init__(self, sha: str):
        self.sha = sha
        self.version = "unknown"
        self.phase = "pre-mutation"
        self.activation_mutated = False


def begin_activation_mutation(context: DeployContext) -> None:
    """Mark the point after which any failure requires proven recovery."""
    context.phase = "mutation"
    context.activation_mutated = True


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


def normalized_diagnostic(value: str) -> str:
    """Return one bounded ASCII diagnostic without control characters."""
    normalized = " ".join(
        "".join(
            character if character.isascii() and character.isprintable() else " "
            for character in value
        ).split()
    )
    if not normalized:
        return "no diagnostic output"
    if len(normalized) > SUBPROCESS_DIAGNOSTIC_LIMIT:
        return normalized[: SUBPROCESS_DIAGNOSTIC_LIMIT - 3] + "..."
    return normalized


def command_label(argv: list[str]) -> str:
    return "git" if argv[0] == GIT else "codex"


def run(argv: list[str], *, ok: tuple[int, ...] = (0,)) -> subprocess.CompletedProcess[str]:
    if not argv or argv[0] not in {GIT, CODEX}:
        raise DeployError("only the fixed git and codex binaries may be invoked")
    try:
        result = subprocess.run(argv, env=ENV, text=True, capture_output=True, check=False)
    except OSError as exc:
        raise DeployError(
            f"{command_label(argv)} invocation failed: {normalized_diagnostic(str(exc))}"
        ) from exc
    if result.returncode not in ok:
        detail = normalized_diagnostic(result.stderr or result.stdout)
        raise DeployError(
            f"{command_label(argv)} command failed with exit {result.returncode}: {detail}"
        )
    return result


def run_json(argv: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(run(argv).stdout)
    except json.JSONDecodeError as exc:
        raise DeployError(f"invalid JSON from {command_label(argv)}") from exc
    if not isinstance(value, dict):
        raise DeployError(f"unexpected JSON shape from {command_label(argv)}")
    return value


def git(repo: Path, *args: str, ok: tuple[int, ...] = (0,)) -> subprocess.CompletedProcess[str]:
    return run(
        [
            GIT,
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "protocol.file.allow=never",
            "-C",
            str(repo),
            *args,
        ],
        ok=ok,
    )


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


def configured_marketplace_row() -> dict[str, Any] | None:
    payload = run_json([CODEX, "plugin", "marketplace", "list", "--json"])
    rows = payload.get("marketplaces", [])
    if not isinstance(rows, list) or any(not isinstance(item, dict) for item in rows):
        raise DeployError("unexpected marketplace list shape")
    matches = [item for item in rows if item.get("name") == MARKETPLACE]
    if len(matches) > 1:
        raise DeployError("fixed marketplace has duplicate configuration rows")
    return matches[0] if matches else None


def verify_fixed_marketplace_row(row: dict[str, Any]) -> None:
    if row.get("marketplaceSource") != FIXED_MARKETPLACE_SOURCE:
        raise DeployError("configured marketplace does not use the fixed Git repository")
    if Path(str(row.get("root", ""))).resolve() != MARKETPLACE_ROOT.resolve():
        raise DeployError("configured marketplace root is not the fixed Codex path")


def marketplace_row(*, create: bool, context: DeployContext | None = None) -> dict[str, Any]:
    row = configured_marketplace_row()
    if row is None and create:
        if context is not None:
            begin_activation_mutation(context)
        add_error: DeployError | OSError | None = None
        try:
            run_json(
                [
                    CODEX,
                    "plugin",
                    "marketplace",
                    "add",
                    REPOSITORY,
                    "--ref",
                    "main",
                    "--json",
                ]
            )
        except (DeployError, OSError) as exc:
            add_error = exc
        if context is not None:
            context.phase = "post-mutation"
        row = configured_marketplace_row()
        if row is None:
            if add_error is not None:
                raise add_error
            raise DeployError("fixed marketplace is absent after add")
    if not isinstance(row, dict):
        raise DeployError("fixed marketplace is not configured")
    verify_fixed_marketplace_row(row)
    return row


def payload_fingerprint(repo: Path, sha: str) -> str:
    listing = git(repo, "ls-tree", "-r", "--full-tree", sha, "--", *PAYLOAD_PATHS).stdout
    return hashlib.sha256(listing.encode()).hexdigest()


def plugin_rows() -> list[dict[str, Any]]:
    payload = run_json([CODEX, "plugin", "list", "--available", "--json"])
    installed = payload.get("installed")
    available = payload.get("available")
    if isinstance(installed, list) and isinstance(available, list):
        rows = [*installed, *available]
    else:
        rows = payload.get("plugins")
    if not isinstance(rows, list):
        raise DeployError("Codex plugin state has an unsupported shape")
    matches = [
        item
        for item in rows
        if isinstance(item, dict) and item.get("pluginId") == f"{PLUGIN}@{MARKETPLACE}"
    ]
    if any(item.get("marketplaceSource") != FIXED_MARKETPLACE_SOURCE for item in matches):
        raise DeployError("plugin state reports a non-fixed marketplace source")
    if any(
        not isinstance(item.get("installed"), bool) or not isinstance(item.get("enabled"), bool)
        for item in matches
    ):
        raise DeployError("plugin state has unsupported activation fields")
    return matches


def installed_row() -> dict[str, Any]:
    matches = [item for item in plugin_rows() if item["installed"]]
    if len(matches) != 1:
        raise DeployError("fixed plugin is absent from Codex plugin state")
    return matches[0]


def verify_disabled() -> None:
    if any(item["enabled"] for item in plugin_rows()):
        raise DeployError("fixed plugin remains enabled after recovery")


def verify_install(requested: str, expected_version: str) -> str:
    row = installed_row()
    if not row.get("installed") or not row.get("enabled") or row.get("version") != expected_version:
        raise DeployError("installed plugin is disabled or has the wrong version")
    cache = CODEX_HOME / "plugins/cache" / MARKETPLACE / PLUGIN / expected_version
    try:
        cache_stat = cache.lstat()
        git_stat = (cache / ".git").lstat()
    except OSError as exc:
        raise DeployError("installed plugin cache is missing or unsafe") from exc
    if (
        not stat.S_ISDIR(cache_stat.st_mode)
        or not stat.S_ISDIR(git_stat.st_mode)
        or cache.is_symlink()
        or (cache / ".git").is_symlink()
    ):
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


def plugin_cache(expected_version: str) -> Path:
    return CODEX_HOME / "plugins/cache" / MARKETPLACE / PLUGIN / expected_version


def read_regular_bytes(path: Path, label: str, maximum: int) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = -1
    try:
        descriptor = os.open(path, flags)
        file_stat = os.fstat(descriptor)
        if (
            not stat.S_ISREG(file_stat.st_mode)
            or file_stat.st_nlink != 1
            or file_stat.st_size > maximum
        ):
            raise DeployError(f"{label} is not a bounded private regular file")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(64 * 1024, maximum + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > maximum:
                raise DeployError(f"{label} is oversized")
        return b"".join(chunks)
    except DeployError:
        raise
    except OSError as exc:
        raise DeployError(f"{label} is missing or unsafe") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def verified_git_blob_record(repo: Path, sha: str, relative: str, maximum: int) -> dict[str, Any]:
    if relative.startswith("/") or ".." in Path(relative).parts:
        raise DeployError("cached role path is unsafe")
    entry = git_text(
        repo,
        "ls-tree",
        "--format=%(objectmode) %(objecttype) %(objectname)",
        sha,
        "--",
        relative,
    ).split()
    if len(entry) != 3 or entry[0] != "100644" or entry[1] != "blob":
        raise DeployError(f"cached {relative} is not one pinned regular Git blob")
    object_format = git_text(repo, "rev-parse", "--show-object-format")
    if object_format not in {"sha1", "sha256"}:
        raise DeployError("cached repository object format is unsupported")
    expected_length = 40 if object_format == "sha1" else 64
    if not re.fullmatch(rf"[0-9a-f]{{{expected_length}}}", entry[2]):
        raise DeployError("cached Git blob identity is malformed")
    data = read_regular_bytes(repo / relative, f"cached {relative}", maximum)
    digest = hashlib.new(
        object_format,
        b"blob " + str(len(data)).encode("ascii") + b"\0" + data,
    ).hexdigest()
    if not secrets.compare_digest(digest, entry[2]):
        raise DeployError(f"cached {relative} disagrees with its pinned Git blob")
    return {
        "data": data,
        "git_oid": entry[2],
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def verified_git_blob(repo: Path, sha: str, relative: str, maximum: int) -> bytes:
    return verified_git_blob_record(repo, sha, relative, maximum)["data"]


def pinned_role_bundle(cache: Path, requested: str, expected_version: str) -> dict[str, Any]:
    tree = git(
        cache,
        "ls-tree",
        "-r",
        "--format=%(objectmode) %(objecttype) %(objectname)\t%(path)",
        requested,
        "--",
        "agents",
    ).stdout.splitlines()
    tree_paths: set[str] = set()
    for row in tree:
        try:
            metadata, relative = row.split("\t", 1)
        except ValueError as exc:
            raise DeployError("cached agents Git tree is malformed") from exc
        fields = metadata.split()
        if len(fields) != 3 or fields[0] != "100644" or fields[1] != "blob":
            raise DeployError("cached agents tree contains a non-regular blob")
        tree_paths.add(relative)
    if tree_paths != AGENTS_TREE_PATHS or len(tree) != len(AGENTS_TREE_PATHS):
        raise DeployError("cached agents tree is not the exact canonical file set")

    manifest_record = verified_git_blob_record(
        cache,
        requested,
        ".codex-plugin/plugin.json",
        PROFILE_MAX_BYTES,
    )
    try:
        manifest_value = json.loads(manifest_record["data"])
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise DeployError("cached plugin manifest is malformed") from exc
    if (
        not isinstance(manifest_value, dict)
        or manifest_value.get("name") != PLUGIN
        or manifest_value.get("version") != expected_version
    ):
        raise DeployError("cached plugin manifest identity is inconsistent")

    agents = cache / "agents"
    try:
        agents_stat = agents.lstat()
        cache_real = cache.resolve(strict=True)
        agents_real = agents.resolve(strict=True)
        entries = {path.name: path for path in agents.iterdir()}
    except OSError as exc:
        raise DeployError("cached role catalog is missing or unsafe") from exc
    if (
        not stat.S_ISDIR(agents_stat.st_mode)
        or agents.is_symlink()
        or agents_real.parent != cache_real
        or set(entries) != {Path(path).name for path in AGENTS_TREE_PATHS}
    ):
        raise DeployError("cached role catalog is not the exact canonical filesystem tree")

    source_blobs: dict[str, dict[str, Any]] = {
        ".codex-plugin/plugin.json": manifest_record,
        "agents/README.md": verified_git_blob_record(
            cache,
            requested,
            "agents/README.md",
            PROFILE_MAX_BYTES,
        ),
    }
    profiles: dict[str, dict[str, Any]] = {}
    for name in CANONICAL_ROLE_NAMES:
        path = entries[f"{name}.toml"]
        relative = f"agents/{path.name}"
        record = verified_git_blob_record(cache, requested, relative, PROFILE_MAX_BYTES)
        try:
            profile = tomllib.loads(record["data"].decode("utf-8"))
        except (UnicodeError, tomllib.TOMLDecodeError) as exc:
            raise DeployError(f"cached role profile {name} is malformed") from exc
        if (
            not isinstance(profile, dict)
            or set(profile) != PROFILE_FIELDS
            or profile.get("name") != name
            or any(not isinstance(profile[field], str) or not profile[field] for field in PROFILE_FIELDS)
        ):
            raise DeployError(f"cached role profile {name} violates the fixed profile schema")
        resolved = path.resolve(strict=True)
        if resolved.parent != agents_real:
            raise DeployError(f"cached role profile {name} escapes the exact cache")
        source_blobs[relative] = record
        profiles[name] = record
    generation = hashlib.sha256(
        json.dumps(
            {name: profiles[name]["sha256"] for name in CANONICAL_ROLE_NAMES},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return {
        "generation": generation,
        "profiles": profiles,
        "source_blobs": source_blobs,
    }


def validate_generation_directory(descriptor: int) -> None:
    directory_stat = os.fstat(descriptor)
    if (
        not stat.S_ISDIR(directory_stat.st_mode)
        or directory_stat.st_uid != os.geteuid()
        or stat.S_IMODE(directory_stat.st_mode) != 0o700
    ):
        raise DeployError("materialized role generation directory is unsafe")


def read_generation_profile(directory: int, name: str) -> bytes:
    descriptor = -1
    try:
        descriptor = os.open(
            f"{name}.toml",
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=directory,
        )
        profile_stat = os.fstat(descriptor)
        if (
            not stat.S_ISREG(profile_stat.st_mode)
            or profile_stat.st_nlink != 1
            or profile_stat.st_uid != os.geteuid()
            or stat.S_IMODE(profile_stat.st_mode) != 0o600
            or profile_stat.st_size > PROFILE_MAX_BYTES
        ):
            raise DeployError("materialized role profile is unsafe")
        data = bytearray()
        while len(data) <= PROFILE_MAX_BYTES:
            chunk = os.read(descriptor, min(64 * 1024, PROFILE_MAX_BYTES + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
        if len(data) > PROFILE_MAX_BYTES:
            raise DeployError("materialized role profile is oversized")
        return bytes(data)
    except OSError as exc:
        raise DeployError("materialized role profile is missing or unsafe") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def verify_role_generation(directory: int, bundle: dict[str, Any]) -> None:
    validate_generation_directory(directory)
    try:
        names = set(os.listdir(directory))
    except OSError as exc:
        raise DeployError("materialized role generation is unreadable") from exc
    expected = {f"{name}.toml" for name in CANONICAL_ROLE_NAMES}
    if names != expected:
        raise DeployError("materialized role generation has an unexpected file set")
    for name in CANONICAL_ROLE_NAMES:
        data = read_generation_profile(directory, name)
        if not secrets.compare_digest(hashlib.sha256(data).hexdigest(), bundle["profiles"][name]["sha256"]):
            raise DeployError("materialized role generation content is inconsistent")


def materialize_role_generation(state_directory: int, bundle: dict[str, Any]) -> dict[str, str]:
    try:
        os.mkdir("role-generations", 0o700, dir_fd=state_directory)
    except FileExistsError:
        pass
    parent = os.open(
        "role-generations",
        os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
        dir_fd=state_directory,
    )
    validate_generation_directory(parent)
    generation = str(bundle["generation"])
    temporary = f".{generation}.{secrets.token_hex(16)}.tmp"
    generation_fd = -1
    created = False
    try:
        try:
            generation_fd = os.open(
                generation,
                os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=parent,
            )
        except FileNotFoundError:
            os.mkdir(temporary, 0o700, dir_fd=parent)
            created = True
            staging = os.open(
                temporary,
                os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=parent,
            )
            validate_generation_directory(staging)
            try:
                for name in CANONICAL_ROLE_NAMES:
                    profile_fd = os.open(
                        f"{name}.toml",
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
                        0o600,
                        dir_fd=staging,
                    )
                    try:
                        data = bundle["profiles"][name]["data"]
                        offset = 0
                        while offset < len(data):
                            advanced = os.write(profile_fd, data[offset:])
                            if advanced <= 0:
                                raise DeployError("materialized role write did not advance")
                            offset += advanced
                        os.fsync(profile_fd)
                    finally:
                        os.close(profile_fd)
                os.fsync(staging)
                verify_role_generation(staging, bundle)
            finally:
                os.close(staging)
            os.rename(temporary, generation, src_dir_fd=parent, dst_dir_fd=parent)
            created = False
            os.fsync(parent)
            generation_fd = os.open(
                generation,
                os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                dir_fd=parent,
            )
        verify_role_generation(generation_fd, bundle)
        return {
            name: str(ROLE_GENERATIONS_DIR / generation / f"{name}.toml")
            for name in CANONICAL_ROLE_NAMES
        }
    finally:
        if generation_fd >= 0:
            os.close(generation_fd)
        if created:
            try:
                staging = os.open(
                    temporary,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
                    dir_fd=parent,
                )
                try:
                    for name in os.listdir(staging):
                        os.unlink(name, dir_fd=staging)
                finally:
                    os.close(staging)
                os.rmdir(temporary, dir_fd=parent)
            except FileNotFoundError:
                pass
        os.close(parent)


def parse_config(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = tomllib.loads(data.decode("utf-8")) if data else {}
    except (UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise DeployError(f"{label} is not valid TOML") from exc
    if not isinstance(value, dict):
        raise DeployError(f"{label} has an unsupported shape")
    return value


def managed_role_span(data: bytes) -> tuple[int, int] | None:
    begins: list[tuple[int, int]] = []
    ends: list[tuple[int, int]] = []
    offset = 0
    for line in data.splitlines(keepends=True):
        content = line.rstrip(b"\r\n")
        target = begins if content == BEGIN_ROLE_MARKER else ends if content == END_ROLE_MARKER else None
        if target is not None:
            target.append((offset, offset + len(line)))
        offset += len(line)
    if not begins and not ends:
        return None
    if len(begins) != 1 or len(ends) != 1 or begins[0][0] >= ends[0][0]:
        raise DeployError("managed role block markers are malformed or ambiguous")
    return begins[0][0], ends[0][1]


def role_block(version: str, catalog: dict[str, str]) -> bytes:
    lines = [BEGIN_ROLE_MARKER.decode(), f"# plugin_version = {json.dumps(version)}"]
    for name, path in sorted(catalog.items()):
        lines.extend((f"[agents.{json.dumps(name)}]", f"config_file = {json.dumps(path)}"))
    lines.append(END_ROLE_MARKER.decode())
    return ("\n".join(lines) + "\n").encode("utf-8")


def config_without_owned_roles(data: bytes) -> tuple[bytes, tuple[int, int] | None]:
    parse_config(data, "Codex config")
    span = managed_role_span(data)
    outside = data if span is None else data[: span[0]] + data[span[1] :]
    outside_agents = parse_config(outside, "Codex config outside the managed role block").get(
        "agents", {}
    )
    if not isinstance(outside_agents, dict):
        raise DeployError("global agent registrations have an unsupported shape")
    collisions = set(outside_agents).intersection(CANONICAL_ROLE_NAMES)
    if collisions:
        names = ", ".join(sorted(collisions))
        raise DeployError(f"owned role registration collides outside the managed block: {names}")
    return outside, span


def desired_role_config(data: bytes, version: str, catalog: dict[str, str]) -> bytes:
    block = role_block(version, catalog)
    desired = config_with_role_block(data, block)
    verify_role_config(desired, catalog)
    return desired


def config_with_role_block(data: bytes, block: bytes) -> bytes:
    outside, span = config_without_owned_roles(data)
    if span is not None:
        desired = data[: span[0]] + block + data[span[1] :]
    else:
        separator = b"" if not data or data.endswith(b"\n\n") else b"\n" if data.endswith(b"\n") else b"\n\n"
        desired = data + separator + block
    if len(desired) > CONFIG_MAX_BYTES:
        raise DeployError("reconciled Codex config would exceed the bounded size")
    return desired


def verify_role_config(data: bytes, catalog: dict[str, str]) -> None:
    _, span = config_without_owned_roles(data)
    if span is None:
        raise DeployError("Codex config is missing the managed role block")
    agents = parse_config(data[span[0] : span[1]], "managed role block").get("agents")
    if not isinstance(agents, dict) or set(agents) != set(CANONICAL_ROLE_NAMES):
        raise DeployError("managed role block does not contain the exact canonical role set")
    if set(catalog) != set(CANONICAL_ROLE_NAMES) or len(catalog) != EXPECTED_ROLE_COUNT:
        raise DeployError("role catalog is not the exact canonical role set")
    configured_paths: list[str] = []
    for name, expected_path in catalog.items():
        row = agents.get(name)
        if not isinstance(row, dict) or set(row) != {"config_file"}:
            raise DeployError(f"Codex role {name} has an ambiguous registration")
        configured = row["config_file"]
        if not isinstance(configured, str) or configured != expected_path or not Path(configured).is_absolute():
            raise DeployError(f"Codex role {name} does not target the exact cached profile")
        configured_paths.append(configured)
    if len(set(configured_paths)) != EXPECTED_ROLE_COUNT:
        raise DeployError("Codex role registrations contain path aliases")


def open_role_config_lock() -> tuple[int, int]:
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        home_fd = os.open(CODEX_HOME, flags)
        home_stat = os.fstat(home_fd)
        if (
            not stat.S_ISDIR(home_stat.st_mode)
            or home_stat.st_uid != os.geteuid()
            or stat.S_IMODE(home_stat.st_mode) & 0o022
        ):
            raise DeployError("fixed Codex home is unsafe")
        lock_flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        lock_fd = os.open(CONFIG_LOCK_NAME, lock_flags, 0o600, dir_fd=home_fd)
        lock_stat = os.fstat(lock_fd)
        if (
            not stat.S_ISREG(lock_stat.st_mode)
            or lock_stat.st_nlink != 1
            or lock_stat.st_uid != os.geteuid()
            or stat.S_IMODE(lock_stat.st_mode) != 0o600
        ):
            raise DeployError("role config coordination lock is unsafe")
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        return home_fd, lock_fd
    except Exception:
        if "lock_fd" in locals():
            os.close(lock_fd)
        if "home_fd" in locals():
            os.close(home_fd)
        raise


def read_config_name_at(home_fd: int, name: str) -> tuple[bytes, os.stat_result] | None:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = -1
    try:
        descriptor = os.open(name, flags, dir_fd=home_fd)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise DeployError("Codex config is missing or unsafe") from exc
    try:
        config_stat = os.fstat(descriptor)
        if (
            not stat.S_ISREG(config_stat.st_mode)
            or config_stat.st_nlink != 1
            or config_stat.st_uid != os.geteuid()
            or stat.S_IMODE(config_stat.st_mode) & 0o077
            or config_stat.st_size > CONFIG_MAX_BYTES
        ):
            raise DeployError("Codex config is not a bounded private regular file")
        data = b""
        while True:
            chunk = os.read(descriptor, min(64 * 1024, CONFIG_MAX_BYTES + 1 - len(data)))
            if not chunk:
                break
            data += chunk
            if len(data) > CONFIG_MAX_BYTES:
                raise DeployError("Codex config is oversized")
        return data, config_stat
    finally:
        os.close(descriptor)


def read_config_at(home_fd: int) -> tuple[bytes, os.stat_result] | None:
    return read_config_name_at(home_fd, "config.toml")


def open_role_receipt_directory(home_fd: int) -> int:
    try:
        os.mkdir("state", 0o700, dir_fd=home_fd)
    except FileExistsError:
        pass
    try:
        descriptor = os.open(
            "state",
            os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=home_fd,
        )
        directory_stat = os.fstat(descriptor)
        if (
            not stat.S_ISDIR(directory_stat.st_mode)
            or directory_stat.st_uid != os.geteuid()
            or stat.S_IMODE(directory_stat.st_mode) & 0o077
        ):
            raise DeployError("shared role receipt directory is unsafe")
        return descriptor
    except Exception:
        if "descriptor" in locals():
            os.close(descriptor)
        raise


def read_role_receipt_name_at(directory: int, name: str) -> tuple[bytes, os.stat_result] | None:
    descriptor = -1
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=directory,
        )
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise DeployError("shared role receipt is missing or unsafe") from exc
    try:
        receipt_stat = os.fstat(descriptor)
        if (
            not stat.S_ISREG(receipt_stat.st_mode)
            or receipt_stat.st_nlink != 1
            or receipt_stat.st_uid != os.geteuid()
            or stat.S_IMODE(receipt_stat.st_mode) != 0o600
            or receipt_stat.st_size > ROLE_RECEIPT_MAX_BYTES
        ):
            raise DeployError("shared role receipt is not a bounded private regular file")
        data = bytearray()
        while len(data) <= ROLE_RECEIPT_MAX_BYTES:
            chunk = os.read(
                descriptor,
                min(4096, ROLE_RECEIPT_MAX_BYTES + 1 - len(data)),
            )
            if not chunk:
                break
            data.extend(chunk)
        if len(data) > ROLE_RECEIPT_MAX_BYTES:
            raise DeployError("shared role receipt is oversized")
        return bytes(data), receipt_stat
    finally:
        os.close(descriptor)


def read_role_receipt_at(directory: int) -> tuple[bytes, os.stat_result] | None:
    return read_role_receipt_name_at(directory, ROLE_RECEIPT_FILE.name)


def parse_role_receipt(snapshot: tuple[bytes, os.stat_result] | None) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    try:
        value = json.loads(snapshot[0])
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise DeployError("shared role receipt is malformed") from exc
    required = {
        "schema",
        "plugin",
        "version",
        "status",
        "changed",
        "role_count",
        "managed_digest",
        "managed_joiner_added",
        "managed_profiles",
        "archives",
    }
    legacy_required = required - {"managed_profiles"}
    status = value.get("status") if isinstance(value, dict) else None
    role_count = value.get("role_count") if isinstance(value, dict) else None
    digest = value.get("managed_digest") if isinstance(value, dict) else None
    profiles = value.get("managed_profiles") if isinstance(value, dict) else None
    if (
        not isinstance(value, dict)
        or value.get("schema") not in {LEGACY_ROLE_RECEIPT_SCHEMA, ROLE_RECEIPT_SCHEMA}
        or (
            set(value) != required
            and not (
                value.get("schema") == LEGACY_ROLE_RECEIPT_SCHEMA
                and set(value) == legacy_required
            )
        )
        or value.get("plugin") != PLUGIN
        or not VERSION_RE.fullmatch(str(value.get("version", "")))
        or status not in {"installed", "uninstalled"}
        or not isinstance(value.get("changed"), bool)
        or not isinstance(role_count, int)
        or isinstance(role_count, bool)
        or not isinstance(value.get("managed_joiner_added"), bool)
        or (profiles is not None and not isinstance(profiles, list))
        or not isinstance(value.get("archives"), list)
    ):
        raise DeployError("shared role receipt identity is invalid")
    if value["schema"] == LEGACY_ROLE_RECEIPT_SCHEMA:
        if value["version"] != LEGACY_ROLE_VERSION or role_count != len(LEGACY_ROLE_NAMES):
            raise DeployError("unknown legacy shared role receipt is not migratable")
    elif role_count != EXPECTED_ROLE_COUNT or profiles is None:
        raise DeployError("shared role receipt role catalog is invalid")
    if status == "installed":
        if not isinstance(digest, str) or not FINGERPRINT_RE.fullmatch(digest):
            raise DeployError("installed shared role receipt digest is invalid")
    elif digest is not None or profiles:
        raise DeployError("uninstalled shared role receipt retains managed ownership")
    return value


def validate_owned_role_state(
    config: bytes,
    receipt: tuple[bytes, os.stat_result] | None,
) -> dict[str, Any] | None:
    outside, span = config_without_owned_roles(config)
    del outside
    value = parse_role_receipt(receipt)
    if span is None:
        if value is not None and value.get("status") == "installed":
            raise DeployError("shared role receipt claims a missing managed block")
        return value
    if value is None or value.get("status") != "installed":
        raise DeployError("managed role block has no shared ownership receipt")
    block = config[span[0] : span[1]]
    digest = hashlib.sha256(block).hexdigest()
    records = value.get("managed_profiles")
    legacy = value.get("schema") == LEGACY_ROLE_RECEIPT_SCHEMA
    expected_names = LEGACY_ROLE_NAMES if legacy else CANONICAL_ROLE_NAMES
    if (
        value.get("managed_digest") != digest
        or not isinstance(value.get("role_count"), int)
        or isinstance(value.get("role_count"), bool)
        or value["role_count"] != len(expected_names)
    ):
        raise DeployError("managed role block disagrees with its shared receipt")
    block_agents = parse_config(block, "managed role block").get("agents")
    if not isinstance(block_agents, dict) or set(block_agents) != set(expected_names):
        raise DeployError("managed role block is not the exact receipted role catalog")
    if records is None:
        if not legacy:
            raise DeployError("current shared role receipt omits profile ownership")
        records = [
            {
                "name": name,
                "config_file": block_agents[name].get("config_file")
                if isinstance(block_agents[name], dict)
                else None,
                "sha256": LEGACY_ROLE_SHA256[name],
            }
            for name in expected_names
        ]
    if not isinstance(records, list) or [record.get("name") for record in records if isinstance(record, dict)] != list(expected_names):
        raise DeployError("shared role receipt profile catalog is not canonical")
    recorded: dict[str, tuple[str, str]] = {}
    for record in records:
        if not isinstance(record, dict) or set(record) != {"name", "config_file", "sha256"}:
            raise DeployError("shared role receipt profile entry is invalid")
        name, path, content_digest = record["name"], record["config_file"], record["sha256"]
        if (
            not isinstance(name, str)
            or name not in expected_names
            or name in recorded
            or not isinstance(path, str)
            or not Path(path).is_absolute()
            or not isinstance(content_digest, str)
            or not FINGERPRINT_RE.fullmatch(content_digest)
        ):
            raise DeployError("shared role receipt profile ownership is invalid")
        if legacy and (
            Path(path).name != f"{name}.toml"
            or not secrets.compare_digest(content_digest, LEGACY_ROLE_SHA256[name])
        ):
            raise DeployError("legacy shared role receipt does not match the allowlisted catalog")
        row = block_agents.get(name)
        if not isinstance(row, dict) or row != {"config_file": path}:
            raise DeployError("shared role receipt does not own the managed registration")
        data = read_regular_bytes(Path(path), f"owned role profile {name}", PROFILE_MAX_BYTES)
        if not secrets.compare_digest(hashlib.sha256(data).hexdigest(), content_digest):
            raise DeployError("owned role profile content drifted from its shared receipt")
        recorded[name] = (path, content_digest)
    if set(recorded) != set(block_agents):
        raise DeployError("managed role block has ambiguous shared ownership")
    return value


def build_role_receipt(
    version: str,
    block: bytes,
    catalog: dict[str, str],
    bundle: dict[str, Any],
    previous: dict[str, Any] | None,
    *,
    added_joiner: bool,
) -> bytes:
    value = {
        "schema": ROLE_RECEIPT_SCHEMA,
        "plugin": PLUGIN,
        "version": version,
        "status": "installed",
        "changed": True,
        "role_count": EXPECTED_ROLE_COUNT,
        "managed_digest": hashlib.sha256(block).hexdigest(),
        "managed_joiner_added": added_joiner,
        "managed_profiles": [
            {
                "name": name,
                "config_file": catalog[name],
                "sha256": bundle["profiles"][name]["sha256"],
            }
            for name in CANONICAL_ROLE_NAMES
        ],
        "archives": [] if previous is None else previous["archives"],
    }
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def build_uninstalled_role_receipt(previous: dict[str, Any]) -> bytes:
    value = {
        "schema": ROLE_RECEIPT_SCHEMA,
        "plugin": PLUGIN,
        "version": previous["version"],
        "status": "uninstalled",
        "changed": True,
        "role_count": EXPECTED_ROLE_COUNT,
        "managed_digest": None,
        "managed_joiner_added": False,
        "managed_profiles": [],
        "archives": previous["archives"],
    }
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def same_config_snapshot(
    left: tuple[bytes, os.stat_result] | None,
    right: tuple[bytes, os.stat_result] | None,
) -> bool:
    if left is None or right is None:
        return left is right
    left_stat, right_stat = left[1], right[1]
    return left[0] == right[0] and (
        left_stat.st_dev,
        left_stat.st_ino,
        left_stat.st_mode,
        left_stat.st_uid,
        left_stat.st_gid,
        left_stat.st_nlink,
        left_stat.st_size,
        left_stat.st_mtime_ns,
    ) == (
        right_stat.st_dev,
        right_stat.st_ino,
        right_stat.st_mode,
        right_stat.st_uid,
        right_stat.st_gid,
        right_stat.st_nlink,
        right_stat.st_size,
        right_stat.st_mtime_ns,
    )


def snapshot_metadata(snapshot: tuple[bytes, os.stat_result] | None) -> dict[str, int] | None:
    if snapshot is None:
        return None
    file_stat = snapshot[1]
    return {
        "dev": file_stat.st_dev,
        "ino": file_stat.st_ino,
        "mode": file_stat.st_mode,
        "uid": file_stat.st_uid,
        "gid": file_stat.st_gid,
        "nlink": file_stat.st_nlink,
        "size": file_stat.st_size,
        "mtime_ns": file_stat.st_mtime_ns,
    }


def matches_snapshot_metadata(
    snapshot: tuple[bytes, os.stat_result] | None,
    expected: dict[str, Any] | None,
) -> bool:
    return snapshot_metadata(snapshot) == expected


def renameat2(directory: int, source: str, target: str, flags: int) -> None:
    """Invoke Linux renameat2 without falling back to a check-then-replace sequence."""
    libc = ctypes.CDLL(None, use_errno=True)
    operation = getattr(libc, "renameat2", None)
    if operation is None:
        raise OSError(errno.ENOSYS, "renameat2 is unavailable")
    operation.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    operation.restype = ctypes.c_int
    if operation(directory, os.fsencode(source), directory, os.fsencode(target), flags) != 0:
        number = ctypes.get_errno()
        raise OSError(number, os.strerror(number), target)


def write_publication_stage(
    directory: int,
    name: str,
    replacement: bytes,
    mode: int,
    reader: Any,
    label: str,
) -> None:
    existing = reader(directory, name)
    if existing is not None:
        if existing[0] != replacement or stat.S_IMODE(existing[1].st_mode) != mode:
            raise DeployError(f"{label} exchange staging file is ambiguous")
        return
    descriptor = -1
    try:
        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NOFOLLOW", 0)
        )
        descriptor = os.open(name, flags, mode, dir_fd=directory)
        os.fchmod(descriptor, mode)
        written = 0
        while written < len(replacement):
            advanced = os.write(descriptor, replacement[written:])
            if advanced <= 0:
                raise DeployError(f"{label} exchange staging write did not advance")
            written += advanced
        os.fsync(descriptor)
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def publish_file_cas(
    directory: int,
    target: str,
    exchange_name: str,
    expected: tuple[bytes, os.stat_result] | None,
    replacement: bytes,
    reader: Any,
    label: str,
    *,
    phase: str,
) -> FilePublication:
    current = reader(directory, target)
    if (
        expected is not None
        and current is not None
        and current[0] == replacement
        and same_config_snapshot(expected, current)
    ):
        staged = reader(directory, exchange_name)
        if staged is not None:
            if staged[0] != replacement:
                raise DeployError(f"{label} no-op publication has ambiguous staging data")
            os.unlink(exchange_name, dir_fd=directory)
            os.fsync(directory)
        return FilePublication(
            directory=directory,
            target=target,
            exchange_name=exchange_name,
            expected=current,
            published=current,
            reader=reader,
            label=label,
            retained=False,
            created=False,
        )
    if current is not None and current[0] == replacement:
        retained = reader(directory, exchange_name)
        if expected is None:
            if retained is not None:
                raise DeployError(f"{label} absent-preimage publication retained an unexpected inode")
            return FilePublication(
                directory=directory,
                target=target,
                exchange_name=exchange_name,
                expected=None,
                published=current,
                reader=reader,
                label=label,
                retained=False,
                created=True,
            )
        if retained is None:
            if phase != "committed":
                raise DeployError(f"{label} lost its retained preimage before commit")
            return FilePublication(
                directory=directory,
                target=target,
                exchange_name=exchange_name,
                expected=expected,
                published=current,
                reader=reader,
                label=label,
                retained=False,
                created=False,
            )
        if not same_config_snapshot(expected, retained):
            raise DeployError(f"{label} retained preimage disagrees with its journal")
        return FilePublication(
            directory=directory,
            target=target,
            exchange_name=exchange_name,
            expected=expected,
            published=current,
            reader=reader,
            label=label,
            retained=True,
            created=False,
        )
    if phase != "prepared" or not same_config_snapshot(expected, current):
        raise DeployError(f"{label} is outside the publication transaction")
    mode = stat.S_IMODE(expected[1].st_mode) if expected is not None else 0o600
    write_publication_stage(directory, exchange_name, replacement, mode, reader, label)
    exchanged = False
    try:
        if expected is None:
            renameat2(directory, exchange_name, target, RENAME_NOREPLACE)
        else:
            renameat2(directory, exchange_name, target, RENAME_EXCHANGE)
            exchanged = True
            displaced = reader(directory, exchange_name)
            if not same_config_snapshot(expected, displaced):
                raise DeployError(f"{label} publication displaced an unexpected inode")
        os.fsync(directory)
        published = reader(directory, target)
        if published is None or published[0] != replacement:
            raise DeployError(f"{label} publication is unproven")
        return FilePublication(
            directory=directory,
            target=target,
            exchange_name=exchange_name,
            expected=expected,
            published=published,
            reader=reader,
            label=label,
            retained=expected is not None,
            created=expected is None,
        )
    except Exception as exc:
        if exchanged:
            try:
                renameat2(directory, exchange_name, target, RENAME_EXCHANGE)
                os.fsync(directory)
                exchanged = False
            except Exception as restore_error:
                raise DeployError(
                    f"{label} publication race restoration is unproven",
                    error_code="recovery-failure",
                ) from restore_error
        try:
            staged = reader(directory, exchange_name)
            if staged is not None and staged[0] == replacement:
                os.unlink(exchange_name, dir_fd=directory)
                os.fsync(directory)
        except FileNotFoundError:
            pass
        raise exc


def finalize_publication(publication: FilePublication) -> None:
    current = publication.reader(publication.directory, publication.target)
    if not same_config_snapshot(publication.published, current):
        raise DeployError(f"{publication.label} changed before combined commit finalization")
    if publication.retained:
        retained = publication.reader(publication.directory, publication.exchange_name)
        if not same_config_snapshot(publication.expected, retained):
            raise DeployError(f"{publication.label} retained preimage changed before finalization")
        os.unlink(publication.exchange_name, dir_fd=publication.directory)
        os.fsync(publication.directory)
        publication.retained = False


def rollback_publication(publication: FilePublication) -> None:
    if publication.retained:
        renameat2(
            publication.directory,
            publication.exchange_name,
            publication.target,
            RENAME_EXCHANGE,
        )
        os.fsync(publication.directory)
        displaced = publication.reader(publication.directory, publication.exchange_name)
        restored = publication.reader(publication.directory, publication.target)
        if not same_config_snapshot(publication.published, displaced) or not same_config_snapshot(
            publication.expected, restored
        ):
            renameat2(
                publication.directory,
                publication.exchange_name,
                publication.target,
                RENAME_EXCHANGE,
            )
            os.fsync(publication.directory)
            raise DeployError(
                f"{publication.label} rollback encountered a same-user publication race",
                error_code="recovery-failure",
            )
        os.unlink(publication.exchange_name, dir_fd=publication.directory)
        os.fsync(publication.directory)
        publication.retained = False
        return
    if not publication.created:
        current = publication.reader(publication.directory, publication.target)
        if publication.expected is not None and same_config_snapshot(publication.expected, current):
            return
        raise DeployError(f"{publication.label} finalized preimage cannot be rolled back")
    renameat2(
        publication.directory,
        publication.target,
        publication.exchange_name,
        RENAME_NOREPLACE,
    )
    os.fsync(publication.directory)
    displaced = publication.reader(publication.directory, publication.exchange_name)
    if not same_config_snapshot(publication.published, displaced):
        renameat2(
            publication.directory,
            publication.exchange_name,
            publication.target,
            RENAME_NOREPLACE,
        )
        os.fsync(publication.directory)
        raise DeployError(
            f"{publication.label} rollback encountered a same-user publication race",
            error_code="recovery-failure",
        )
    os.unlink(publication.exchange_name, dir_fd=publication.directory)
    os.fsync(publication.directory)
    publication.created = False


def atomic_config_replace(
    home_fd: int,
    expected: tuple[bytes, os.stat_result] | None,
    replacement: bytes,
) -> tuple[bytes, os.stat_result]:
    publication = publish_file_cas(
        home_fd,
        "config.toml",
        f".config.toml.bears-gateway.{secrets.token_hex(16)}",
        expected,
        replacement,
        read_config_name_at,
        "Codex config",
        phase="prepared",
    )
    finalize_publication(publication)
    return publication.published


def atomic_role_receipt_replace(
    directory: int,
    expected: tuple[bytes, os.stat_result] | None,
    replacement: bytes,
) -> tuple[bytes, os.stat_result]:
    publication = publish_file_cas(
        directory,
        ROLE_RECEIPT_FILE.name,
        f".{PLUGIN}-role-sync.{secrets.token_hex(16)}.tmp",
        expected,
        replacement,
        read_role_receipt_name_at,
        "shared role receipt",
        phase="prepared",
    )
    finalize_publication(publication)
    return publication.published


def rollback_role_receipt(
    directory: int,
    before: tuple[bytes, os.stat_result] | None,
    attempted: bytes,
) -> None:
    current = read_role_receipt_at(directory)
    if same_config_snapshot(before, current):
        return
    if current is None or current[0] != attempted:
        raise DeployError("shared role receipt changed outside the attempted mutation")
    if before is None:
        publication = FilePublication(
            directory=directory,
            target=ROLE_RECEIPT_FILE.name,
            exchange_name=f".{PLUGIN}-role-sync.{secrets.token_hex(16)}.rollback",
            expected=None,
            published=current,
            reader=read_role_receipt_name_at,
            label="shared role receipt",
            retained=False,
            created=True,
        )
        rollback_publication(publication)
    else:
        atomic_role_receipt_replace(directory, current, before[0])


def atomic_config_remove(home_fd: int, expected: tuple[bytes, os.stat_result]) -> None:
    publication = FilePublication(
        directory=home_fd,
        target="config.toml",
        exchange_name=f".config.toml.bears-gateway.{secrets.token_hex(16)}.rollback",
        expected=None,
        published=expected,
        reader=read_config_name_at,
        label="Codex config",
        retained=False,
        created=True,
    )
    rollback_publication(publication)


def rollback_role_config(
    home_fd: int,
    before: tuple[bytes, os.stat_result] | None,
    current: tuple[bytes, os.stat_result],
) -> None:
    if before is None:
        atomic_config_remove(home_fd, current)
    else:
        restored = atomic_config_replace(home_fd, current, before[0])
        if restored[0] != before[0] or stat.S_IMODE(restored[1].st_mode) != stat.S_IMODE(before[1].st_mode):
            raise DeployError("Codex config role rollback is unproven")


def rollback_attempted_config(
    home_fd: int,
    before: tuple[bytes, os.stat_result] | None,
    attempted: bytes,
) -> None:
    current = read_config_at(home_fd)
    if same_config_snapshot(before, current):
        return
    if current is None or current[0] != attempted:
        raise DeployError("Codex config changed outside the attempted role mutation")
    rollback_role_config(home_fd, before, current)


def publish_journaled_file(
    directory: int,
    target: str,
    exchange_name: str,
    preimage: bytes,
    preimage_present: bool,
    preimage_metadata: dict[str, Any] | None,
    replacement: bytes,
    reader: Any,
    label: str,
    *,
    phase: str,
) -> FilePublication:
    current = reader(directory, target)
    current_bytes = None if current is None else current[0]
    expected_bytes = preimage if preimage_present else None
    if current_bytes == expected_bytes:
        if preimage_present and not matches_snapshot_metadata(current, preimage_metadata):
            raise DeployError(f"{label} preimage inode disagrees with its journal")
        if not preimage_present and preimage_metadata is not None:
            raise DeployError(f"{label} absent preimage retains metadata")
        return publish_file_cas(
            directory,
            target,
            exchange_name,
            current if preimage_present else None,
            replacement,
            reader,
            label,
            phase=phase,
        )
    if current_bytes != replacement:
        raise DeployError(f"{label} is outside the journaled publication states")
    if not preimage_present:
        return publish_file_cas(
            directory,
            target,
            exchange_name,
            None,
            replacement,
            reader,
            label,
            phase=phase,
        )
    retained = reader(directory, exchange_name)
    if retained is None:
        if phase != "committed":
            raise DeployError(f"{label} prepared transaction lost its retained preimage")
        return FilePublication(
            directory=directory,
            target=target,
            exchange_name=exchange_name,
            expected=None,
            published=current,
            reader=reader,
            label=label,
            retained=False,
            created=False,
        )
    if retained[0] != preimage or not matches_snapshot_metadata(retained, preimage_metadata):
        raise DeployError(f"{label} retained preimage is not the journaled inode")
    return publish_file_cas(
        directory,
        target,
        exchange_name,
        retained,
        replacement,
        reader,
        label,
        phase=phase,
    )


def role_deployment_record(
    fingerprint: str,
    bundle: dict[str, Any],
    catalog: dict[str, str],
    role_receipt: bytes,
) -> dict[str, Any]:
    return {
        "payload_fingerprint": fingerprint,
        "role_generation": bundle["generation"],
        "role_count": EXPECTED_ROLE_COUNT,
        "role_catalog_sha256": bundle["generation"],
        "role_receipt_sha256": hashlib.sha256(role_receipt).hexdigest(),
        "role_source_blobs": {
            relative: {
                "git_oid": record["git_oid"],
                "sha256": record["sha256"],
            }
            for relative, record in sorted(bundle["source_blobs"].items())
        },
        "role_profiles": [
            {
                "name": name,
                "config_file": catalog[name],
                "git_oid": bundle["profiles"][name]["git_oid"],
                "sha256": bundle["profiles"][name]["sha256"],
            }
            for name in CANONICAL_ROLE_NAMES
        ],
    }


def reconcile_roles(
    requested: str,
    expected_version: str,
    state_directory: int,
    intent: dict[str, Any] | None,
) -> dict[str, Any]:
    if intent is None or intent.get("requested_sha") != requested:
        raise DeployError("promotion intent does not target the reconciled role revision")
    fingerprint = verify_install(requested, expected_version)
    cache = plugin_cache(expected_version)
    bundle = pinned_role_bundle(cache, requested, expected_version)
    catalog = materialize_role_generation(state_directory, bundle)
    home_fd, lock_fd = open_role_config_lock()
    receipt_directory = -1
    before: tuple[bytes, os.stat_result] | None = None
    receipt_before: tuple[bytes, os.stat_result] | None = None
    config_publication: FilePublication | None = None
    receipt_publication: FilePublication | None = None
    desired = b""
    desired_receipt = b""
    phase = "prepared"
    combined_published = False
    try:
        receipt_directory = open_role_receipt_directory(home_fd)
        before = read_config_at(home_fd)
        receipt_before = read_role_receipt_at(receipt_directory)
        original = b"" if before is None else before[0]
        block = role_block(expected_version, catalog)
        transaction = intent.get("role_transaction")
        if transaction is None:
            previous_role_receipt = validate_owned_role_state(original, receipt_before)
            desired = desired_role_config(original, expected_version, catalog)
            existing_span = managed_role_span(original)
            added_joiner = (
                bool(previous_role_receipt.get("managed_joiner_added", False))
                if existing_span is not None and previous_role_receipt is not None
                else existing_span is None
                and bool(original)
                and not original.endswith((b"\n", b"\r"))
            )
            desired_receipt = build_role_receipt(
                expected_version,
                block,
                catalog,
                bundle,
                previous_role_receipt,
                added_joiner=added_joiner,
            )
            record = role_deployment_record(fingerprint, bundle, catalog, desired_receipt)
            intent = save_role_intent(
                state_directory,
                intent,
                config_preimage=before,
                desired_block=block,
                role_receipt_preimage=receipt_before,
                role_receipt=desired_receipt,
                role_record=record,
            )
            transaction = intent["role_transaction"]
        else:
            if transaction.get("operation") != "install":
                raise DeployError("promotion intent contains a non-install role transaction")
            preimage = decode_journal_bytes(
                transaction["config_preimage_b64"],
                CONFIG_MAX_BYTES,
                "config preimage",
            )
            journaled_block = decode_journal_bytes(
                transaction["desired_block_b64"],
                CONFIG_MAX_BYTES,
                "desired role block",
            )
            desired_receipt = decode_journal_bytes(
                transaction["role_receipt_b64"],
                ROLE_RECEIPT_MAX_BYTES,
                "desired role receipt",
            )
            desired = config_with_role_block(preimage, journaled_block)
            record = role_deployment_record(fingerprint, bundle, catalog, desired_receipt)
            if journaled_block != block or transaction["role_record"] != record:
                raise DeployError("journaled role transaction disagrees with the exact cached role data")
            preimage_matches = (
                before is not None and original == preimage
                if transaction["config_preimage_present"]
                else before is None
            )
            desired_matches = before is not None and original == desired
            if not preimage_matches and not desired_matches:
                raise DeployError("live Codex config is outside the journaled role transaction")
            receipt_preimage_value = transaction["role_receipt_preimage_b64"]
            receipt_preimage = (
                None
                if receipt_preimage_value is None
                else decode_journal_bytes(
                    receipt_preimage_value,
                    ROLE_RECEIPT_MAX_BYTES,
                    "role receipt preimage",
                )
            )
            receipt_bytes = None if receipt_before is None else receipt_before[0]
            if receipt_bytes == desired_receipt and desired_matches:
                validate_owned_role_state(desired, receipt_before)
            elif receipt_bytes == receipt_preimage and preimage_matches:
                validate_owned_role_state(preimage, receipt_before)
            elif receipt_bytes not in {receipt_preimage, desired_receipt}:
                raise DeployError("shared role receipt is outside the journaled transaction")
        phase = str(transaction["phase"])
        preimage = decode_journal_bytes(
            transaction["config_preimage_b64"],
            CONFIG_MAX_BYTES,
            "config preimage",
        )
        receipt_preimage_value = transaction["role_receipt_preimage_b64"]
        receipt_preimage = (
            b""
            if receipt_preimage_value is None
            else decode_journal_bytes(
                receipt_preimage_value,
                ROLE_RECEIPT_MAX_BYTES,
                "role receipt preimage",
            )
        )
        config_publication = publish_journaled_file(
            home_fd,
            "config.toml",
            transaction["config_exchange_name"],
            preimage,
            transaction["config_preimage_present"],
            transaction["config_preimage_metadata"],
            desired,
            read_config_name_at,
            "Codex config",
            phase=phase,
        )
        receipt_publication = publish_journaled_file(
            receipt_directory,
            ROLE_RECEIPT_FILE.name,
            transaction["receipt_exchange_name"],
            receipt_preimage,
            receipt_preimage_value is not None,
            transaction["role_receipt_preimage_metadata"],
            desired_receipt,
            read_role_receipt_name_at,
            "shared role receipt",
            phase=phase,
        )
        published = config_publication.published
        receipt_published = receipt_publication.published
        verify_role_config(published[0], catalog)
        validate_owned_role_state(published[0], receipt_published)
        if verify_install(requested, expected_version) != fingerprint:
            raise DeployError("installed plugin changed during role reconciliation")
        if pinned_role_bundle(cache, requested, expected_version) != bundle:
            raise DeployError("cached role catalog changed during reconciliation")
        final = read_config_at(home_fd)
        final_receipt = read_role_receipt_at(receipt_directory)
        if final is None or final[0] != desired:
            raise DeployError("live Codex role registration changed after reconciliation")
        if final_receipt is None or final_receipt[0] != desired_receipt:
            raise DeployError("shared live role receipt changed after reconciliation")
        verify_role_config(final[0], catalog)
        validate_owned_role_state(final[0], final_receipt)
        combined_published = True
        if phase == "prepared":
            intent = mark_role_transaction_committed(state_directory, intent)
            phase = "committed"
        finalize_publication(receipt_publication)
        finalize_publication(config_publication)
        return record
    except Exception as exc:
        rollback_failure: Exception | None = None
        if phase != "committed" and not combined_published and receipt_publication is not None:
            try:
                rollback_publication(receipt_publication)
            except Exception as failure:
                rollback_failure = failure
        if phase != "committed" and not combined_published and config_publication is not None:
            try:
                rollback_publication(config_publication)
            except Exception as failure:
                rollback_failure = rollback_failure or failure
        if rollback_failure is not None:
            raise DeployError(
                "role reconciliation failed and combined rollback is unproven",
                error_code="recovery-failure",
            ) from rollback_failure
        raise exc
    finally:
        if receipt_directory >= 0:
            os.close(receipt_directory)
        os.close(lock_fd)
        os.close(home_fd)


def rollback_journaled_roles(intent: dict[str, Any]) -> None:
    transaction = intent.get("role_transaction")
    if transaction is None:
        return
    validate_intent(intent)
    if transaction.get("operation") != "install":
        raise DeployError("role-removal transaction must converge forward")
    preimage = decode_journal_bytes(
        transaction["config_preimage_b64"],
        CONFIG_MAX_BYTES,
        "config preimage",
    )
    block = decode_journal_bytes(
        transaction["desired_block_b64"],
        CONFIG_MAX_BYTES,
        "desired role block",
    )
    desired = config_with_role_block(preimage, block)
    desired_receipt = decode_journal_bytes(
        transaction["role_receipt_b64"],
        ROLE_RECEIPT_MAX_BYTES,
        "desired role receipt",
    )
    receipt_preimage_value = transaction["role_receipt_preimage_b64"]
    receipt_preimage = (
        None
        if receipt_preimage_value is None
        else decode_journal_bytes(
            receipt_preimage_value,
            ROLE_RECEIPT_MAX_BYTES,
            "role receipt preimage",
        )
    )
    home_fd, lock_fd = open_role_config_lock()
    receipt_directory = -1
    try:
        receipt_directory = open_role_receipt_directory(home_fd)
        current = read_config_at(home_fd)
        current_bytes = None if current is None else current[0]
        expected_preimage = preimage if transaction["config_preimage_present"] else None
        if current_bytes not in {expected_preimage, desired}:
            raise DeployError("live Codex config cannot be rolled back from its role journal")
        current_receipt = read_role_receipt_at(receipt_directory)
        current_receipt_bytes = None if current_receipt is None else current_receipt[0]
        if current_receipt_bytes not in {receipt_preimage, desired_receipt}:
            raise DeployError("shared role receipt cannot be rolled back from its journal")
        if current_receipt_bytes != receipt_preimage:
            retained = read_role_receipt_name_at(
                receipt_directory, transaction["receipt_exchange_name"]
            )
            if (
                receipt_preimage is not None
                and retained is not None
                and retained[0] == receipt_preimage
                and matches_snapshot_metadata(
                    retained, transaction["role_receipt_preimage_metadata"]
                )
            ):
                rollback_publication(
                    FilePublication(
                        directory=receipt_directory,
                        target=ROLE_RECEIPT_FILE.name,
                        exchange_name=transaction["receipt_exchange_name"],
                        expected=retained,
                        published=current_receipt,
                        reader=read_role_receipt_name_at,
                        label="shared role receipt",
                        retained=True,
                        created=False,
                    )
                )
            elif receipt_preimage is None:
                rollback_role_receipt(receipt_directory, None, desired_receipt)
            else:
                atomic_role_receipt_replace(
                    receipt_directory,
                    current_receipt,
                    receipt_preimage,
                )
        if current_bytes != expected_preimage:
            retained = read_config_name_at(home_fd, transaction["config_exchange_name"])
            if (
                expected_preimage is not None
                and retained is not None
                and retained[0] == expected_preimage
                and matches_snapshot_metadata(retained, transaction["config_preimage_metadata"])
            ):
                rollback_publication(
                    FilePublication(
                        directory=home_fd,
                        target="config.toml",
                        exchange_name=transaction["config_exchange_name"],
                        expected=retained,
                        published=current,
                        reader=read_config_name_at,
                        label="Codex config",
                        retained=True,
                        created=False,
                    )
                )
            elif expected_preimage is None:
                if current is None:
                    raise DeployError("journaled Codex config rollback state is ambiguous")
                atomic_config_remove(home_fd, current)
            else:
                atomic_config_replace(home_fd, current, expected_preimage)
        restored = read_config_at(home_fd)
        restored_receipt = read_role_receipt_at(receipt_directory)
        restored_bytes = None if restored is None else restored[0]
        restored_receipt_bytes = None if restored_receipt is None else restored_receipt[0]
        if restored_bytes != expected_preimage or restored_receipt_bytes != receipt_preimage:
            raise DeployError("journaled role rollback did not converge")
        for directory, exchange_name, reader, replacement, label in (
            (
                home_fd,
                transaction["config_exchange_name"],
                read_config_name_at,
                desired,
                "Codex config",
            ),
            (
                receipt_directory,
                transaction["receipt_exchange_name"],
                read_role_receipt_name_at,
                desired_receipt,
                "shared role receipt",
            ),
        ):
            staged = reader(directory, exchange_name)
            if staged is not None:
                if staged[0] != replacement:
                    raise DeployError(f"{label} rollback exchange file is ambiguous")
                os.unlink(exchange_name, dir_fd=directory)
                os.fsync(directory)
        validate_owned_role_state(b"" if restored is None else restored[0], restored_receipt)
    finally:
        if receipt_directory >= 0:
            os.close(receipt_directory)
        os.close(lock_fd)
        os.close(home_fd)


def clear_owned_roles(state_directory: int, intent: dict[str, Any]) -> dict[str, Any]:
    home_fd, lock_fd = open_role_config_lock()
    receipt_directory = -1
    before: tuple[bytes, os.stat_result] | None = None
    receipt_before: tuple[bytes, os.stat_result] | None = None
    config_publication: FilePublication | None = None
    receipt_publication: FilePublication | None = None
    outside = b""
    desired_receipt = b""
    phase = "prepared"
    combined_published = False
    try:
        receipt_directory = open_role_receipt_directory(home_fd)
        before = read_config_at(home_fd)
        receipt_before = read_role_receipt_at(receipt_directory)
        current_config = b"" if before is None else before[0]
        transaction = intent.get("role_transaction")
        if transaction is None or transaction.get("operation") == "install":
            previous = validate_owned_role_state(current_config, receipt_before)
            if before is None and previous is None:
                return intent
            outside, span = config_without_owned_roles(current_config)
            if span is None:
                return intent
            if previous is None:
                raise DeployError("managed role removal lacks a shared ownership receipt")
            desired_receipt = build_uninstalled_role_receipt(previous)
            intent = save_role_removal_intent(
                state_directory,
                intent,
                config_preimage=before,
                desired_config=outside,
                role_receipt_preimage=receipt_before,
                role_receipt=desired_receipt,
            )
            transaction = intent["role_transaction"]
        elif transaction.get("operation") != "remove":
            raise DeployError("promotion intent contains an unknown role transition")
        preimage = decode_journal_bytes(
            transaction["config_preimage_b64"], CONFIG_MAX_BYTES, "config preimage"
        )
        outside = decode_journal_bytes(
            transaction["desired_config_b64"], CONFIG_MAX_BYTES, "desired config"
        )
        desired_receipt = decode_journal_bytes(
            transaction["role_receipt_b64"], ROLE_RECEIPT_MAX_BYTES, "uninstalled role receipt"
        )
        receipt_preimage_value = transaction["role_receipt_preimage_b64"]
        receipt_preimage = (
            b""
            if receipt_preimage_value is None
            else decode_journal_bytes(
                receipt_preimage_value,
                ROLE_RECEIPT_MAX_BYTES,
                "role receipt preimage",
            )
        )
        phase = transaction["phase"]
        current_config_bytes = None if before is None else before[0]
        current_receipt_bytes = None if receipt_before is None else receipt_before[0]
        expected_config = preimage if transaction["config_preimage_present"] else None
        expected_receipt = None if receipt_preimage_value is None else receipt_preimage
        if current_config_bytes not in {expected_config, outside}:
            raise DeployError("Codex config is outside the journaled removal transition")
        if current_receipt_bytes not in {expected_receipt, desired_receipt}:
            raise DeployError("shared role receipt is outside the journaled removal transition")
        config_publication = publish_journaled_file(
            home_fd,
            "config.toml",
            transaction["config_exchange_name"],
            preimage,
            transaction["config_preimage_present"],
            transaction["config_preimage_metadata"],
            outside,
            read_config_name_at,
            "Codex config removal",
            phase=phase,
        )
        receipt_publication = publish_journaled_file(
            receipt_directory,
            ROLE_RECEIPT_FILE.name,
            transaction["receipt_exchange_name"],
            receipt_preimage,
            receipt_preimage_value is not None,
            transaction["role_receipt_preimage_metadata"],
            desired_receipt,
            read_role_receipt_name_at,
            "shared role receipt removal",
            phase=phase,
        )
        published = config_publication.published
        receipt_published = receipt_publication.published
        _, remaining_span = config_without_owned_roles(published[0])
        if remaining_span is not None:
            raise DeployError("managed role block remains after journaled removal")
        parsed_receipt = parse_role_receipt(receipt_published)
        if (
            parsed_receipt is None
            or parsed_receipt.get("schema") != ROLE_RECEIPT_SCHEMA
            or parsed_receipt.get("status") != "uninstalled"
        ):
            raise DeployError("shared role receipt did not converge to uninstalled")
        combined_published = True
        if phase == "prepared":
            intent = mark_role_transaction_committed(state_directory, intent)
            phase = "committed"
        finalize_publication(receipt_publication)
        finalize_publication(config_publication)
        return intent
    except Exception as exc:
        rollback_failure: Exception | None = None
        if phase != "committed" and not combined_published and receipt_publication is not None:
            try:
                rollback_publication(receipt_publication)
            except Exception as failure:
                rollback_failure = failure
        if phase != "committed" and not combined_published and config_publication is not None:
            try:
                rollback_publication(config_publication)
            except Exception as failure:
                rollback_failure = rollback_failure or failure
        if rollback_failure is not None:
            raise DeployError(
                "managed role removal failed and rollback is unproven",
                error_code="recovery-failure",
            ) from rollback_failure
        raise exc
    finally:
        if receipt_directory >= 0:
            os.close(receipt_directory)
        os.close(lock_fd)
        os.close(home_fd)


def validate_directory_component(
    descriptor: int,
    *,
    require_user_owner: bool,
    require_private_mode: bool,
) -> None:
    """Require a trusted directory component opened without link traversal."""
    component_stat = os.fstat(descriptor)
    mode = stat.S_IMODE(component_stat.st_mode)
    trusted_owners = {os.geteuid()} if require_user_owner else {0, os.geteuid()}
    unsafe_mode = mode != 0o700 if require_private_mode else bool(mode & 0o022)
    if (
        not stat.S_ISDIR(component_stat.st_mode)
        or component_stat.st_uid not in trusted_owners
        or unsafe_mode
    ):
        raise DeployError("deployment state path component owner, mode, or type is unsafe")


def open_state_directory() -> int:
    """Open and validate every fixed path component without following links."""
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
    descriptor = os.open("/", flags)
    components = STATE_DIR.parts[1:]
    home_depth = len(CODEX_HOME.parts) - 1
    try:
        validate_directory_component(
            descriptor,
            require_user_owner=False,
            require_private_mode=False,
        )
        for depth, component in enumerate(components, start=1):
            try:
                child = os.open(component, flags, dir_fd=descriptor)
            except FileNotFoundError:
                if depth <= home_depth:
                    raise DeployError("fixed Codex state path is incomplete")
                os.mkdir(component, mode=0o700, dir_fd=descriptor)
                os.fsync(descriptor)
                child = os.open(component, flags, dir_fd=descriptor)
            except OSError as exc:
                raise DeployError("deployment state path component is unsafe") from exc
            try:
                validate_directory_component(
                    child,
                    require_user_owner=depth >= home_depth,
                    require_private_mode=depth == len(components),
                )
            except Exception:
                os.close(child)
                raise
            os.close(descriptor)
            descriptor = child
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def validate_private_regular(descriptor: int, label: str, *, error_code: str | None = None) -> os.stat_result:
    file_stat = os.fstat(descriptor)
    if (
        not stat.S_ISREG(file_stat.st_mode)
        or file_stat.st_uid != os.geteuid()
        or stat.S_IMODE(file_stat.st_mode) != 0o600
        or file_stat.st_nlink != 1
    ):
        raise DeployError(f"{label} owner, mode, type, or link count is unsafe", error_code=error_code)
    return file_stat


def open_lock_file(state_directory: int) -> int:
    descriptor = os.open(
        LOCK_FILE.name,
        os.O_CREAT | os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW,
        0o600,
        dir_fd=state_directory,
    )
    try:
        validate_private_regular(descriptor, "deployment lock")
    except Exception:
        os.close(descriptor)
        raise
    return descriptor


def validate_deploy_receipt(value: Any) -> dict[str, Any]:
    base_fields = {
        "schema",
        "repository",
        "marketplace",
        "plugin",
        "sha",
        "version",
        "payload_fingerprint",
    }
    if (
        not isinstance(value, dict)
        or value.get("schema") not in {LEGACY_DEPLOY_RECEIPT_SCHEMA, DEPLOY_RECEIPT_SCHEMA}
        or value.get("repository") != REPOSITORY
        or value.get("marketplace") != MARKETPLACE
        or value.get("plugin") != PLUGIN
        or not SHA_RE.fullmatch(str(value.get("sha", "")))
        or not VERSION_RE.fullmatch(str(value.get("version", "")))
        or not FINGERPRINT_RE.fullmatch(str(value.get("payload_fingerprint", "")))
    ):
        raise DeployError("deployment receipt identity is invalid", error_code="receipt-corruption")
    if value["schema"] == LEGACY_DEPLOY_RECEIPT_SCHEMA:
        if set(value) != base_fields:
            raise DeployError("legacy deployment receipt shape is invalid", error_code="receipt-corruption")
        return value
    role_fields = {
        "role_generation",
        "role_count",
        "role_catalog_sha256",
        "role_receipt_sha256",
        "role_source_blobs",
        "role_profiles",
    }
    if set(value) != base_fields | role_fields:
        raise DeployError("deployment receipt shape is invalid", error_code="receipt-corruption")
    generation = value.get("role_generation")
    blobs = value.get("role_source_blobs")
    profiles = value.get("role_profiles")
    expected_sources = {".codex-plugin/plugin.json", *AGENTS_TREE_PATHS}
    if (
        not isinstance(generation, str)
        or not FINGERPRINT_RE.fullmatch(generation)
        or value.get("role_count") != EXPECTED_ROLE_COUNT
        or value.get("role_catalog_sha256") != generation
        or not FINGERPRINT_RE.fullmatch(str(value.get("role_receipt_sha256", "")))
        or not isinstance(blobs, dict)
        or set(blobs) != expected_sources
        or not isinstance(profiles, list)
        or len(profiles) != EXPECTED_ROLE_COUNT
    ):
        raise DeployError("deployment role receipt identity is invalid", error_code="receipt-corruption")
    for relative, record in blobs.items():
        if (
            not isinstance(record, dict)
            or set(record) != {"git_oid", "sha256"}
            or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", str(record.get("git_oid", "")))
            or not FINGERPRINT_RE.fullmatch(str(record.get("sha256", "")))
        ):
            raise DeployError("deployment role blob record is invalid", error_code="receipt-corruption")
    for name, record in zip(CANONICAL_ROLE_NAMES, profiles, strict=True):
        expected_path = str(ROLE_GENERATIONS_DIR / generation / f"{name}.toml")
        source = blobs[f"agents/{name}.toml"]
        if (
            not isinstance(record, dict)
            or set(record) != {"name", "config_file", "git_oid", "sha256"}
            or record.get("name") != name
            or record.get("config_file") != expected_path
            or record.get("git_oid") != source["git_oid"]
            or record.get("sha256") != source["sha256"]
        ):
            raise DeployError("deployment role profile record is invalid", error_code="receipt-corruption")
    return value


def load_state(state_directory: int) -> dict[str, Any] | None:
    try:
        descriptor = os.open(
            STATE_FILE.name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=state_directory,
        )
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise DeployError("deployment receipt is unsafe", error_code="receipt-corruption") from exc
    try:
        file_stat = validate_private_regular(
            descriptor, "deployment receipt", error_code="receipt-corruption"
        )
        if file_stat.st_size > RECEIPT_MAX_BYTES:
            raise DeployError("deployment receipt is oversized", error_code="receipt-corruption")
        payload = bytearray()
        while len(payload) <= RECEIPT_MAX_BYTES:
            chunk = os.read(descriptor, min(4096, RECEIPT_MAX_BYTES + 1 - len(payload)))
            if not chunk:
                break
            payload.extend(chunk)
        if len(payload) > RECEIPT_MAX_BYTES:
            raise DeployError("deployment receipt is oversized", error_code="receipt-corruption")
        value = json.loads(payload.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DeployError("deployment receipt is unreadable", error_code="receipt-corruption") from exc
    finally:
        os.close(descriptor)
    return validate_deploy_receipt(value)


def valid_snapshot_metadata(value: Any, *, present: bool) -> bool:
    if not present:
        return value is None
    return (
        isinstance(value, dict)
        and set(value) == SNAPSHOT_METADATA_FIELDS
        and all(isinstance(item, int) and not isinstance(item, bool) and item >= 0 for item in value.values())
    )


def validate_intent(value: Any) -> dict[str, Any]:
    """Validate one bounded journal entry and its recoverable publication states."""
    fields = {
        "schema",
        "repository",
        "marketplace",
        "plugin",
        "requested_sha",
        "previous_receipt",
        "role_transaction",
    }
    if (
        not isinstance(value, dict)
        or set(value) != fields
        or value.get("schema") != PROMOTION_INTENT_SCHEMA
        or value.get("repository") != REPOSITORY
        or value.get("marketplace") != MARKETPLACE
        or value.get("plugin") != PLUGIN
        or not isinstance(value.get("requested_sha"), str)
        or not SHA_RE.fullmatch(value["requested_sha"])
    ):
        raise DeployError("promotion intent identity is invalid", error_code="receipt-corruption")
    previous = value["previous_receipt"]
    if previous is not None:
        try:
            validate_deploy_receipt(previous)
        except DeployError as exc:
            raise DeployError(
                "promotion intent prior convergence state is invalid",
                error_code="receipt-corruption",
            ) from exc
    transaction = value["role_transaction"]
    if transaction is not None:
        common_fields = {
            "operation",
            "phase",
            "config_preimage_b64",
            "config_preimage_present",
            "config_preimage_sha256",
            "config_preimage_metadata",
            "config_exchange_name",
            "role_receipt_b64",
            "role_receipt_preimage_b64",
            "role_receipt_preimage_metadata",
            "role_receipt_sha256",
            "receipt_exchange_name",
            "role_count",
        }
        install_fields = {
            "desired_block_b64",
            "desired_block_sha256",
            "role_generation",
            "role_record",
        }
        remove_fields = {"desired_config_b64", "desired_config_sha256"}
        role_record_fields = {
            "payload_fingerprint",
            "role_generation",
            "role_count",
            "role_catalog_sha256",
            "role_receipt_sha256",
            "role_source_blobs",
            "role_profiles",
        }
        role_record = transaction.get("role_record") if isinstance(transaction, dict) else None
        operation = transaction.get("operation") if isinstance(transaction, dict) else None
        expected_fields = common_fields | (install_fields if operation == "install" else remove_fields)
        preimage_present = transaction.get("config_preimage_present") if isinstance(transaction, dict) else None
        receipt_preimage_value = (
            transaction.get("role_receipt_preimage_b64") if isinstance(transaction, dict) else None
        )
        if (
            not isinstance(transaction, dict)
            or operation not in {"install", "remove"}
            or set(transaction) != expected_fields
            or transaction.get("phase") not in {"prepared", "committed"}
            or not FINGERPRINT_RE.fullmatch(str(transaction.get("config_preimage_sha256", "")))
            or not FINGERPRINT_RE.fullmatch(str(transaction.get("role_receipt_sha256", "")))
            or transaction.get("role_count") != EXPECTED_ROLE_COUNT
            or not isinstance(preimage_present, bool)
            or not isinstance(transaction.get("config_preimage_b64"), str)
            or not isinstance(transaction.get("role_receipt_b64"), str)
            or not valid_snapshot_metadata(
                transaction.get("config_preimage_metadata"), present=bool(preimage_present)
            )
            or not valid_snapshot_metadata(
                transaction.get("role_receipt_preimage_metadata"),
                present=receipt_preimage_value is not None,
            )
            or not re.fullmatch(
                r"\.config\.toml\.bears-gateway\.[0-9a-f]{32}",
                str(transaction.get("config_exchange_name", "")),
            )
            or not re.fullmatch(
                rf"\.{re.escape(PLUGIN)}-role-sync\.[0-9a-f]{{32}}\.tmp",
                str(transaction.get("receipt_exchange_name", "")),
            )
            or (
                receipt_preimage_value is not None
                and not isinstance(receipt_preimage_value, str)
            )
        ):
            raise DeployError("promotion role transaction is invalid", error_code="receipt-corruption")
        if operation == "install" and (
            not isinstance(transaction.get("desired_block_b64"), str)
            or not FINGERPRINT_RE.fullmatch(str(transaction.get("desired_block_sha256", "")))
            or not FINGERPRINT_RE.fullmatch(str(transaction.get("role_generation", "")))
            or not isinstance(role_record, dict)
            or set(role_record) != role_record_fields
        ):
            raise DeployError("promotion install transaction is invalid", error_code="receipt-corruption")
        if operation == "remove" and (
            not isinstance(transaction.get("desired_config_b64"), str)
            or not FINGERPRINT_RE.fullmatch(str(transaction.get("desired_config_sha256", "")))
        ):
            raise DeployError("promotion removal transaction is invalid", error_code="receipt-corruption")
        try:
            config_preimage = decode_journal_bytes(
                transaction["config_preimage_b64"],
                CONFIG_MAX_BYTES,
                "config preimage",
            )
            desired_payload = decode_journal_bytes(
                transaction["desired_block_b64" if operation == "install" else "desired_config_b64"],
                CONFIG_MAX_BYTES,
                "desired role block" if operation == "install" else "desired config",
            )
            role_receipt = decode_journal_bytes(
                transaction["role_receipt_b64"],
                ROLE_RECEIPT_MAX_BYTES,
                "desired role receipt",
            )
            if receipt_preimage_value is not None:
                decode_journal_bytes(
                    receipt_preimage_value,
                    ROLE_RECEIPT_MAX_BYTES,
                    "role receipt preimage",
                )
        except DeployError as exc:
            raise DeployError(
                "promotion role transaction payload is invalid",
                error_code="receipt-corruption",
            ) from exc
        if (
            hashlib.sha256(config_preimage).hexdigest()
            != transaction["config_preimage_sha256"]
            or hashlib.sha256(desired_payload).hexdigest()
            != transaction[
                "desired_block_sha256" if operation == "install" else "desired_config_sha256"
            ]
            or hashlib.sha256(role_receipt).hexdigest()
            != transaction["role_receipt_sha256"]
            or (not preimage_present and config_preimage != b"")
        ):
            raise DeployError(
                "promotion role transaction payload digest is invalid",
                error_code="receipt-corruption",
            )
        if operation == "install":
            try:
                validate_deploy_receipt(
                    {
                        "schema": DEPLOY_RECEIPT_SCHEMA,
                        "repository": REPOSITORY,
                        "marketplace": MARKETPLACE,
                        "plugin": PLUGIN,
                        "sha": value["requested_sha"],
                        "version": "0.0.0+codex.00000000000000",
                        **role_record,
                    }
                )
            except DeployError as exc:
                raise DeployError(
                    "promotion role transaction record is invalid",
                    error_code="receipt-corruption",
                ) from exc
            if (
                transaction["role_generation"] != role_record["role_generation"]
                or transaction["role_receipt_sha256"] != role_record["role_receipt_sha256"]
                or transaction["role_count"] != role_record["role_count"]
            ):
                raise DeployError(
                    "promotion role transaction disagrees with its role record",
                    error_code="receipt-corruption",
                )
    return value


def encode_journal_bytes(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def decode_journal_bytes(value: str, maximum: int, label: str) -> bytes:
    if len(value) > ((maximum + 2) // 3) * 4:
        raise DeployError(f"journaled {label} is oversized")
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise DeployError(f"journaled {label} is malformed") from exc
    if len(decoded) > maximum:
        raise DeployError(f"journaled {label} is oversized")
    return decoded


def load_intent(state_directory: int) -> dict[str, Any] | None:
    """Load a secure durable promotion journal without following links."""
    try:
        descriptor = os.open(
            INTENT_FILE.name,
            os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
            dir_fd=state_directory,
        )
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise DeployError("promotion intent is unsafe", error_code="receipt-corruption") from exc
    try:
        file_stat = validate_private_regular(
            descriptor, "promotion intent", error_code="receipt-corruption"
        )
        if file_stat.st_size > INTENT_MAX_BYTES:
            raise DeployError("promotion intent is oversized", error_code="receipt-corruption")
        payload = bytearray()
        while len(payload) <= INTENT_MAX_BYTES:
            chunk = os.read(descriptor, min(4096, INTENT_MAX_BYTES + 1 - len(payload)))
            if not chunk:
                break
            payload.extend(chunk)
        if len(payload) > INTENT_MAX_BYTES:
            raise DeployError("promotion intent is oversized", error_code="receipt-corruption")
        value = json.loads(payload.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DeployError("promotion intent is unreadable", error_code="receipt-corruption") from exc
    finally:
        os.close(descriptor)
    return validate_intent(value)


def persist_intent(state_directory: int, value: dict[str, Any]) -> dict[str, Any]:
    value = validate_intent(value)
    payload = (json.dumps(value, sort_keys=True) + "\n").encode("utf-8")
    if len(payload) > INTENT_MAX_BYTES:
        raise DeployError("promotion intent is oversized")
    temporary = f".{PLUGIN}.promotion-intent.{secrets.token_hex(16)}.tmp"
    descriptor = -1
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
            dir_fd=state_directory,
        )
        os.fchmod(descriptor, 0o600)
        validate_private_regular(descriptor, "temporary promotion intent")
        offset = 0
        while offset < len(payload):
            written = os.write(descriptor, payload[offset:])
            if written <= 0:
                raise DeployError("temporary promotion intent write did not advance")
            offset += written
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        os.replace(
            temporary,
            INTENT_FILE.name,
            src_dir_fd=state_directory,
            dst_dir_fd=state_directory,
        )
        temporary = ""
        os.fsync(state_directory)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary:
            try:
                os.unlink(temporary, dir_fd=state_directory)
            except FileNotFoundError:
                pass
    return value


def save_intent(
    state_directory: int,
    requested: str,
    previous: dict[str, Any] | None,
) -> dict[str, Any]:
    """Atomically persist and fsync the convergence journal before activation."""
    return persist_intent(
        state_directory,
        {
            "schema": PROMOTION_INTENT_SCHEMA,
            "repository": REPOSITORY,
            "marketplace": MARKETPLACE,
            "plugin": PLUGIN,
            "requested_sha": requested,
            "previous_receipt": dict(previous) if previous is not None else None,
            "role_transaction": None,
        },
    )


def save_role_intent(
    state_directory: int,
    intent: dict[str, Any],
    *,
    config_preimage: tuple[bytes, os.stat_result] | None,
    desired_block: bytes,
    role_receipt_preimage: tuple[bytes, os.stat_result] | None,
    role_receipt: bytes,
    role_record: dict[str, Any],
) -> dict[str, Any]:
    value = dict(intent)
    config_bytes = b"" if config_preimage is None else config_preimage[0]
    receipt_bytes = None if role_receipt_preimage is None else role_receipt_preimage[0]
    value["role_transaction"] = {
        "operation": "install",
        "phase": "prepared",
        "config_preimage_b64": encode_journal_bytes(config_bytes),
        "config_preimage_present": config_preimage is not None,
        "config_preimage_sha256": hashlib.sha256(config_bytes).hexdigest(),
        "config_preimage_metadata": snapshot_metadata(config_preimage),
        "config_exchange_name": f".config.toml.bears-gateway.{secrets.token_hex(16)}",
        "desired_block_b64": encode_journal_bytes(desired_block),
        "desired_block_sha256": hashlib.sha256(desired_block).hexdigest(),
        "role_generation": role_record["role_generation"],
        "role_receipt_b64": encode_journal_bytes(role_receipt),
        "role_receipt_preimage_b64": (
            None if receipt_bytes is None else encode_journal_bytes(receipt_bytes)
        ),
        "role_receipt_preimage_metadata": snapshot_metadata(role_receipt_preimage),
        "role_receipt_sha256": role_record["role_receipt_sha256"],
        "receipt_exchange_name": f".{PLUGIN}-role-sync.{secrets.token_hex(16)}.tmp",
        "role_count": role_record["role_count"],
        "role_record": role_record,
    }
    return persist_intent(state_directory, value)


def save_role_removal_intent(
    state_directory: int,
    intent: dict[str, Any],
    *,
    config_preimage: tuple[bytes, os.stat_result] | None,
    desired_config: bytes,
    role_receipt_preimage: tuple[bytes, os.stat_result] | None,
    role_receipt: bytes,
) -> dict[str, Any]:
    value = dict(intent)
    config_bytes = b"" if config_preimage is None else config_preimage[0]
    receipt_bytes = None if role_receipt_preimage is None else role_receipt_preimage[0]
    value["role_transaction"] = {
        "operation": "remove",
        "phase": "prepared",
        "config_preimage_b64": encode_journal_bytes(config_bytes),
        "config_preimage_present": config_preimage is not None,
        "config_preimage_sha256": hashlib.sha256(config_bytes).hexdigest(),
        "config_preimage_metadata": snapshot_metadata(config_preimage),
        "config_exchange_name": f".config.toml.bears-gateway.{secrets.token_hex(16)}",
        "desired_config_b64": encode_journal_bytes(desired_config),
        "desired_config_sha256": hashlib.sha256(desired_config).hexdigest(),
        "role_receipt_b64": encode_journal_bytes(role_receipt),
        "role_receipt_preimage_b64": (
            None if receipt_bytes is None else encode_journal_bytes(receipt_bytes)
        ),
        "role_receipt_preimage_metadata": snapshot_metadata(role_receipt_preimage),
        "role_receipt_sha256": hashlib.sha256(role_receipt).hexdigest(),
        "receipt_exchange_name": f".{PLUGIN}-role-sync.{secrets.token_hex(16)}.tmp",
        "role_count": EXPECTED_ROLE_COUNT,
    }
    return persist_intent(state_directory, value)


def mark_role_transaction_committed(
    state_directory: int,
    intent: dict[str, Any],
) -> dict[str, Any]:
    value = dict(intent)
    transaction = dict(value["role_transaction"])
    transaction["phase"] = "committed"
    value["role_transaction"] = transaction
    return persist_intent(state_directory, value)


def clear_intent(state_directory: int) -> None:
    """Durably clear the journal only after verified convergence."""
    try:
        os.unlink(INTENT_FILE.name, dir_fd=state_directory)
    except FileNotFoundError:
        pass
    os.fsync(state_directory)


def save_state(
    state_directory: int,
    sha: str,
    version: str,
    role_record: dict[str, Any],
) -> None:
    value = {
        "schema": DEPLOY_RECEIPT_SCHEMA,
        "repository": REPOSITORY,
        "marketplace": MARKETPLACE,
        "plugin": PLUGIN,
        "sha": sha,
        "version": version,
        **role_record,
    }
    validate_deploy_receipt(value)
    payload = (json.dumps(value, sort_keys=True) + "\n").encode("utf-8")
    temporary = f".{PLUGIN}.{secrets.token_hex(16)}.tmp"
    descriptor = -1
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
            0o600,
            dir_fd=state_directory,
        )
        os.fchmod(descriptor, 0o600)
        validate_private_regular(descriptor, "temporary deployment receipt")
        offset = 0
        while offset < len(payload):
            written = os.write(descriptor, payload[offset:])
            if written <= 0:
                raise DeployError("temporary deployment receipt write did not advance")
            offset += written
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        os.replace(
            temporary,
            STATE_FILE.name,
            src_dir_fd=state_directory,
            dst_dir_fd=state_directory,
        )
        temporary = ""
        os.fsync(state_directory)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary:
            try:
                os.unlink(temporary, dir_fd=state_directory)
            except FileNotFoundError:
                pass


def clear_state(state_directory: int) -> None:
    try:
        os.unlink(STATE_FILE.name, dir_fd=state_directory)
    except FileNotFoundError:
        return
    os.fsync(state_directory)


def verify_receipted_install(state: dict[str, Any]) -> None:
    fingerprint = verify_install(str(state["sha"]), str(state["version"]))
    if fingerprint != state["payload_fingerprint"]:
        raise DeployError("active plugin disagrees with its deployment receipt", error_code="receipt-corruption")


def reconcile_receipted_roles(
    state_directory: int,
    state: dict[str, Any],
    intent: dict[str, Any],
) -> dict[str, Any]:
    role_record = reconcile_roles(
        str(state["sha"]),
        str(state["version"]),
        state_directory,
        intent,
    )
    if role_record["payload_fingerprint"] != state["payload_fingerprint"]:
        raise DeployError(
            "live roles disagree with the exact deployment receipt",
            error_code="receipt-corruption",
        )
    if state.get("schema") == DEPLOY_RECEIPT_SCHEMA:
        for field, value in role_record.items():
            if state.get(field) != value:
                raise DeployError(
                    "deployment role receipt disagrees with the exact cached generation",
                    error_code="receipt-corruption",
                )
    return role_record


def restore_receipted_install(
    state_directory: int,
    state: dict[str, Any],
) -> None:
    sha = str(state["sha"])
    version = str(state["version"])
    fingerprint = str(state["payload_fingerprint"])
    restore_intent = save_intent(state_directory, sha, state)
    marketplace_row(create=False)
    exact_remote(MARKETPLACE_ROOT)
    git(MARKETPLACE_ROOT, "reset", "--hard", sha)
    git(MARKETPLACE_ROOT, "clean", "-ffdx", "--", *PAYLOAD_PATHS)
    if git_text(MARKETPLACE_ROOT, "rev-parse", "HEAD") != sha:
        raise DeployError("recovery marketplace checkout is not the receipted SHA")
    dirty_payload = git(
        MARKETPLACE_ROOT, "status", "--porcelain=v1", "--untracked-files=all", "--", *PAYLOAD_PATHS
    ).stdout
    if dirty_payload or manifest(MARKETPLACE_ROOT, sha).get("version") != version:
        raise DeployError("recovery marketplace checkout is inconsistent")
    if payload_fingerprint(MARKETPLACE_ROOT, sha) != fingerprint:
        raise DeployError("recovery marketplace payload disagrees with its receipt")
    run_json([CODEX, "plugin", "add", f"{PLUGIN}@{MARKETPLACE}", "--json"])
    verify_receipted_install(state)
    role_record = reconcile_receipted_roles(state_directory, state, restore_intent)
    save_state(state_directory, sha, version, role_record)
    durable = load_state(state_directory)
    if (
        durable is None
        or durable.get("schema") != DEPLOY_RECEIPT_SCHEMA
        or durable.get("sha") != sha
        or durable.get("version") != version
        or any(durable.get(field) != value for field, value in role_record.items())
    ):
        raise DeployError("recovered deployment receipt is not durably role-complete")
    verify_receipted_install(durable)


def disable_and_verify(state_directory: int, intent: dict[str, Any]) -> None:
    try:
        run_json([CODEX, "plugin", "disable", f"{PLUGIN}@{MARKETPLACE}", "--json"])
    except Exception:
        pass
    verify_disabled()
    clear_owned_roles(state_directory, load_intent(state_directory) or intent)
    clear_state(state_directory)


def converge_promotion_intent(
    state_directory: int,
    intent: dict[str, Any],
) -> str:
    """Converge one catchable or crash-recovered promotion to a verified state."""
    durable_intent = load_intent(state_directory)
    if durable_intent is not None:
        intent = durable_intent
    transaction = intent.get("role_transaction")
    if transaction is not None and transaction.get("operation") == "remove":
        disable_and_verify(state_directory, intent)
        clear_intent(state_directory)
        return "disabled"
    requested = str(intent["requested_sha"])
    state: dict[str, Any] | None
    try:
        state = load_state(state_directory)
    except DeployError as exc:
        if exc.error_code != "receipt-corruption":
            raise
        state = None
    if state is not None and state["sha"] == requested:
        try:
            verify_receipted_install(state)
            role_record = reconcile_receipted_roles(state_directory, state, intent)
            save_state(
                state_directory,
                str(state["sha"]),
                str(state["version"]),
                role_record,
            )
            durable = load_state(state_directory)
            if (
                durable is None
                or durable.get("schema") != DEPLOY_RECEIPT_SCHEMA
                or any(durable.get(field) != value for field, value in role_record.items())
            ):
                raise DeployError("recovered requested receipt is not durably role-complete")
            verify_receipted_install(durable)
        except Exception:
            pass
        else:
            clear_intent(state_directory)
            return "requested"

    previous = intent["previous_receipt"]
    if previous is not None:
        try:
            rollback_journaled_roles(load_intent(state_directory) or intent)
            restore_receipted_install(state_directory, previous)
        except Exception:
            pass
        else:
            clear_intent(state_directory)
            return "previous"

    active_intent = load_intent(state_directory) or intent
    rollback_journaled_roles(active_intent)
    disable_and_verify(state_directory, active_intent)
    clear_intent(state_directory)
    return "disabled"


def recover_promotion_intent(state_directory: int) -> None:
    """Recover an unfinished durable intent before ordinary receipt handling."""
    intent = load_intent(state_directory)
    if intent is None:
        return
    try:
        converge_promotion_intent(state_directory, intent)
    except Exception as exc:
        raise DeployError(
            "unfinished promotion recovery convergence is unproven",
            error_code="recovery-failure",
        ) from exc


def fail_after_recovery(
    state_directory: int,
    intent: dict[str, Any],
    failure: Exception,
) -> None:
    try:
        outcome = converge_promotion_intent(state_directory, intent)
    except Exception as recovery_failure:
        raise DeployError(
            "promotion failed after activation and recovery convergence is unproven",
            error_code="recovery-failure",
        ) from recovery_failure
    if outcome == "requested":
        message = "promotion failed after activation; requested revision is durably receipted and active"
    elif outcome == "previous":
        message = "promotion failed after activation; previous receipted revision was restored"
    else:
        message = "promotion failed after activation; plugin was disabled"
    raise DeployError(
        message,
        error_code="recovery-activated",
    ) from failure


def promote(requested: str, context: DeployContext, state_directory: int) -> str:
    recover_promotion_intent(state_directory)
    main_sha = prepare_mirror(requested)
    requested_manifest = manifest(MIRROR, requested)
    context.version = str(requested_manifest["version"])
    validate_marketplace(MIRROR, requested)
    state = load_state(state_directory)
    previous: dict[str, Any] | None = None
    if state is not None:
        current = str(state["sha"])
        if not is_ancestor(MIRROR, current, main_sha):
            raise DeployError("receipted SHA is not on fixed main", error_code="receipt-corruption")
        verify_receipted_install(state)
        early_status: str | None = None
        if requested == current:
            early_status = "already-deployed"
        elif is_ancestor(MIRROR, requested, current):
            early_status = "skipped-older-ancestor"
        if early_status is not None:
            repair_intent = save_intent(state_directory, current, state)
            try:
                role_record = reconcile_receipted_roles(
                    state_directory,
                    state,
                    repair_intent,
                )
                save_state(
                    state_directory,
                    current,
                    str(state["version"]),
                    role_record,
                )
                repaired = load_state(state_directory)
                if repaired is None or repaired.get("schema") != DEPLOY_RECEIPT_SCHEMA:
                    raise DeployError("repaired deployment receipt is not durable")
                verify_receipted_install(repaired)
                clear_intent(state_directory)
            except Exception as exc:
                fail_after_recovery(state_directory, repair_intent, exc)
            return early_status
        if not is_ancestor(MIRROR, current, requested):
            raise DeployError("non-fast-forward promotion requires a separate rollback authorization")
        previous = state
    else:
        verify_disabled()

    intent = save_intent(state_directory, requested, previous)
    try:
        marketplace_row(create=True, context=context)
        begin_activation_mutation(context)
        run_json([CODEX, "plugin", "marketplace", "upgrade", MARKETPLACE, "--json"])
        context.phase = "post-mutation"
        marketplace_row(create=False)
        exact_remote(MARKETPLACE_ROOT)
        snapshot_sha = git_text(MARKETPLACE_ROOT, "rev-parse", "HEAD")
        if snapshot_sha != requested:
            raise DeployError("marketplace snapshot is not the exact requested GitHub SHA")
        begin_activation_mutation(context)
        run_json([CODEX, "plugin", "add", f"{PLUGIN}@{MARKETPLACE}", "--json"])
        context.phase = "post-mutation"
        version = str(requested_manifest["version"])
        role_record = reconcile_roles(requested, version, state_directory, intent)
        save_state(state_directory, requested, version, role_record)
        durable_state = load_state(state_directory)
        if (
            durable_state is None
            or durable_state["sha"] != requested
            or durable_state["version"] != version
            or any(durable_state.get(field) != value for field, value in role_record.items())
        ):
            raise DeployError("durable deployment receipt disagrees with the verified promotion")
        verify_receipted_install(durable_state)
        clear_intent(state_directory)
    except Exception as exc:
        fail_after_recovery(state_directory, intent, exc)
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
    state_directory = -1
    descriptor = -1
    try:
        state_directory = open_state_directory()
        descriptor = open_lock_file(state_directory)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        status = promote(sys.argv[1], context, state_directory)
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
        if state_directory >= 0:
            os.close(state_directory)
    print(json.dumps({"plugin": PLUGIN, "sha": sys.argv[1], "status": status}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
