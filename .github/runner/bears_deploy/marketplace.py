"""Pinned manifest, marketplace, plugin cache, and Git blob verification operations."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
from typing import Any

from .constants import (
    CODEX,
    CODEX_HOME,
    FIXED_MARKETPLACE_SOURCE,
    LEGACY_PAYLOAD_PATHS,
    MARKETPLACE,
    MARKETPLACE_ROOT,
    MIRROR,
    PAYLOAD_PATHS,
    PLUGIN,
    REPOSITORY,
    SEMVER_RE,
    VERSION_RE,
)
from .models import DeployContext, DeployError, begin_activation_mutation
from .process import exact_remote, git, git_text, run_json


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
        raise DeployError("plugin manifest identity, repository, or version is invalid")
    return value


def semver_tuple(value: str) -> tuple[int, int, int]:
    """Return one strict plain SemVer tuple admitted for current deployments."""
    if not SEMVER_RE.fullmatch(value):
        raise DeployError("plugin version is not plain SemVer")
    major, minor, patch = value.split(".")
    return int(major), int(minor), int(patch)


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


def marketplace_row(
    *,
    create: bool,
    context: DeployContext | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
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
                ],
                env=env,
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


def legacy_payload_fingerprint(repo: Path, sha: str) -> str:
    """Reproduce the pre-contracts receipt fingerprint during one-way migration."""
    listing = git(repo, "ls-tree", "-r", "--full-tree", sha, "--", *LEGACY_PAYLOAD_PATHS).stdout
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


def verify_removed() -> None:
    if any(item["installed"] or item["enabled"] for item in plugin_rows()):
        raise DeployError("fixed plugin remains installed after recovery")


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
