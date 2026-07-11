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
INTENT_FILE = STATE_DIR / f"{PLUGIN}.promotion-intent.json"
LOCK_FILE = STATE_DIR / f"{PLUGIN}.lock"
MIRROR = STATE_DIR / "repository.git"
GIT = "/usr/bin/git"
CODEX = "/usr/local/bin/codex"
SHA_RE = re.compile(r"[0-9a-f]{40}")
FINGERPRINT_RE = re.compile(r"[0-9a-f]{64}")
VERSION_RE = re.compile(r"\d+\.\d+\.\d+\+codex\.\d{14}")
DEPLOY_RECEIPT_SCHEMA = "bears-plugin-deploy-state.v1"
PROMOTION_INTENT_SCHEMA = "bears-plugin-promotion-intent.v1"
RECEIPT_MAX_BYTES = 16 * 1024
INTENT_MAX_BYTES = 16 * 1024
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
}
FIXED_MARKETPLACE_SOURCE = {"sourceType": "git", "source": REPOSITORY}


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
    if (
        not isinstance(value, dict)
        or value.get("schema") != DEPLOY_RECEIPT_SCHEMA
        or value.get("repository") != REPOSITORY
        or value.get("marketplace") != MARKETPLACE
        or value.get("plugin") != PLUGIN
        or not SHA_RE.fullmatch(str(value.get("sha", "")))
        or not VERSION_RE.fullmatch(str(value.get("version", "")))
        or not FINGERPRINT_RE.fullmatch(str(value.get("payload_fingerprint", "")))
    ):
        raise DeployError("deployment receipt identity is invalid", error_code="receipt-corruption")
    return value


def validate_intent(value: Any) -> dict[str, Any]:
    """Validate one bounded journal entry and its prior convergence state."""
    fields = {
        "schema",
        "repository",
        "marketplace",
        "plugin",
        "requested_sha",
        "previous_receipt",
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
    receipt_fields = {
        "schema",
        "repository",
        "marketplace",
        "plugin",
        "sha",
        "version",
        "payload_fingerprint",
    }
    if previous is not None and (
        not isinstance(previous, dict)
        or set(previous) != receipt_fields
        or previous.get("schema") != DEPLOY_RECEIPT_SCHEMA
        or previous.get("repository") != REPOSITORY
        or previous.get("marketplace") != MARKETPLACE
        or previous.get("plugin") != PLUGIN
        or not isinstance(previous.get("sha"), str)
        or not SHA_RE.fullmatch(previous["sha"])
        or previous["sha"] == value["requested_sha"]
        or not isinstance(previous.get("version"), str)
        or not VERSION_RE.fullmatch(previous["version"])
        or not isinstance(previous.get("payload_fingerprint"), str)
        or not FINGERPRINT_RE.fullmatch(previous["payload_fingerprint"])
    ):
        raise DeployError(
            "promotion intent prior convergence state is invalid",
            error_code="receipt-corruption",
        )
    return value


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


def save_intent(
    state_directory: int,
    requested: str,
    previous: dict[str, Any] | None,
) -> dict[str, Any]:
    """Atomically persist and fsync the convergence journal before activation."""
    value = validate_intent(
        {
            "schema": PROMOTION_INTENT_SCHEMA,
            "repository": REPOSITORY,
            "marketplace": MARKETPLACE,
            "plugin": PLUGIN,
            "requested_sha": requested,
            "previous_receipt": dict(previous) if previous is not None else None,
        }
    )
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


def clear_intent(state_directory: int) -> None:
    """Durably clear the journal only after verified convergence."""
    try:
        os.unlink(INTENT_FILE.name, dir_fd=state_directory)
    except FileNotFoundError:
        pass
    os.fsync(state_directory)


def save_state(state_directory: int, sha: str, version: str, fingerprint: str) -> None:
    value = {
        "schema": DEPLOY_RECEIPT_SCHEMA,
        "repository": REPOSITORY,
        "marketplace": MARKETPLACE,
        "plugin": PLUGIN,
        "sha": sha,
        "version": version,
        "payload_fingerprint": fingerprint,
    }
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


def restore_receipted_install(state_directory: int, state: dict[str, Any]) -> None:
    sha = str(state["sha"])
    version = str(state["version"])
    fingerprint = str(state["payload_fingerprint"])
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
    save_state(state_directory, sha, version, fingerprint)
    verify_receipted_install(state)


def disable_and_verify(state_directory: int) -> None:
    try:
        run_json([CODEX, "plugin", "disable", f"{PLUGIN}@{MARKETPLACE}", "--json"])
    except Exception:
        pass
    verify_disabled()
    clear_state(state_directory)


def converge_promotion_intent(
    state_directory: int,
    intent: dict[str, Any],
) -> str:
    """Converge one catchable or crash-recovered promotion to a verified state."""
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
        except Exception:
            pass
        else:
            clear_intent(state_directory)
            return "requested"

    previous = intent["previous_receipt"]
    if previous is not None:
        try:
            restore_receipted_install(state_directory, previous)
        except Exception:
            pass
        else:
            clear_intent(state_directory)
            return "previous"

    disable_and_verify(state_directory)
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
        if requested == current:
            return "already-deployed"
        if is_ancestor(MIRROR, requested, current):
            return "skipped-older-ancestor"
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
        fingerprint = verify_install(requested, version)
        save_state(state_directory, requested, version, fingerprint)
        durable_state = load_state(state_directory)
        if (
            durable_state is None
            or durable_state["sha"] != requested
            or durable_state["version"] != version
            or durable_state["payload_fingerprint"] != fingerprint
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
