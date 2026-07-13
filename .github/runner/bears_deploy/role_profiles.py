"""Pinned role catalog materialization and desired config rendering boundaries."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import tomllib
from typing import Any

from .constants import (
    BEGIN_ROLE_MARKER,
    CONFIG_MAX_BYTES,
    END_ROLE_MARKER,
    LEGACY_ARCHIVE_DIRECTORY,
    LEGACY_ARCHIVE_FILES,
    LEGACY_ROLE_BLOCK_LENGTH,
    LEGACY_ROLE_COUNT,
    LEGACY_ROLE_MANAGED_DIGEST,
    LEGACY_ROLE_NAMES,
    LEGACY_ROLE_PATHS,
    LEGACY_ROLE_RECEIPT_LENGTH,
    LEGACY_ROLE_RECEIPT_SCHEMA,
    LEGACY_ROLE_RECEIPT_SHA256,
    LEGACY_ROLE_VERSION,
    PLUGIN,
    PROFILE_MAX_BYTES,
    ROLE_GENERATIONS_DIR,
)
from .marketplace import verified_git_blob_record
from .models import DeployError
from .process import git
from .role_renderer import RoleDefinitionError, render_profile, validate_catalog, validate_definition


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
    profile_relatives = sorted(
        relative
        for relative in tree_paths
        if relative.startswith("agents/")
        and relative.count("/") == 1
        and relative.endswith(".toml")
    )
    expected_tree_paths = {"agents/README.md", *profile_relatives}
    if (
        tree_paths != expected_tree_paths
        or len(tree) != len(expected_tree_paths)
        or not 1 <= len(profile_relatives) <= 64
    ):
        raise DeployError("cached agents tree is not the exact canonical file set")

    definition_tree = git(
        cache,
        "ls-tree",
        "-r",
        "--format=%(objectmode) %(objecttype) %(objectname)\t%(path)",
        requested,
        "--",
        "role-definitions",
    ).stdout.splitlines()
    definition_paths: set[str] = set()
    for row in definition_tree:
        try:
            metadata, relative = row.split("\t", 1)
        except ValueError as exc:
            raise DeployError("cached role definition tree is malformed") from exc
        fields = metadata.split()
        if len(fields) != 3 or fields[0] != "100644" or fields[1] != "blob":
            raise DeployError("cached role definition tree contains a non-regular blob")
        definition_paths.add(relative)
    expected_definition_paths = {
        "role-definitions/capability-catalog.v1.json",
        *(f"role-definitions/{Path(relative).stem}.json" for relative in profile_relatives),
    }
    if definition_paths != expected_definition_paths or len(definition_tree) != len(expected_definition_paths):
        raise DeployError("cached role definition tree is not the exact canonical file set")

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
        or set(entries) != {Path(path).name for path in expected_tree_paths}
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
    definition_records = {
        relative: verified_git_blob_record(cache, requested, relative, PROFILE_MAX_BYTES)
        for relative in sorted(definition_paths)
    }
    source_blobs.update(definition_records)
    try:
        catalog_value = validate_catalog(
            json.loads(definition_records["role-definitions/capability-catalog.v1.json"]["data"])
        )
    except (UnicodeError, json.JSONDecodeError, RoleDefinitionError) as exc:
        raise DeployError("cached role capability catalog is malformed") from exc
    profiles: dict[str, dict[str, Any]] = {}
    for relative in profile_relatives:
        path = entries[Path(relative).name]
        name = path.stem
        record = verified_git_blob_record(cache, requested, relative, PROFILE_MAX_BYTES)
        definition_record = definition_records[f"role-definitions/{name}.json"]
        try:
            definition = validate_definition(
                json.loads(definition_record["data"]), catalog_value, expected_name=name
            )
            expected_profile = render_profile(definition, catalog_value, expected_version)
            profile = tomllib.loads(record["data"].decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError, tomllib.TOMLDecodeError, RoleDefinitionError) as exc:
            raise DeployError(f"cached role profile {name} is malformed") from exc
        if profile.get("name") != name or record["data"] != expected_profile:
            raise DeployError(f"cached role profile {name} drifted from its authoritative JSON definition")
        resolved = path.resolve(strict=True)
        if resolved.parent != agents_real:
            raise DeployError(f"cached role profile {name} escapes the exact cache")
        source_blobs[relative] = record
        profiles[name] = record
    generation = hashlib.sha256(
        json.dumps(
            {name: profiles[name]["sha256"] for name in sorted(profiles)},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return {
        "generation": generation,
        "role_names": tuple(sorted(profiles)),
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
    role_names = tuple(bundle["role_names"])
    expected = {f"{name}.toml" for name in role_names}
    if names != expected:
        raise DeployError("materialized role generation has an unexpected file set")
    for name in role_names:
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
                for name in bundle["role_names"]:
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
            for name in bundle["role_names"]
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


def strict_json_loads(data: bytes, label: str) -> Any:
    """Decode JSON while rejecting duplicate object keys at every depth."""

    def object_without_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate JSON object key")
            value[key] = item
        return value

    try:
        return json.loads(data, object_pairs_hook=object_without_duplicates)
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise DeployError(f"{label} is malformed") from exc


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


def legacy_role_receipt_value() -> dict[str, Any]:
    """Return the sole live v1 receipt admitted by registration migration."""
    return {
        "schema": LEGACY_ROLE_RECEIPT_SCHEMA,
        "plugin": PLUGIN,
        "version": LEGACY_ROLE_VERSION,
        "status": "installed",
        "changed": True,
        "role_count": LEGACY_ROLE_COUNT,
        "managed_digest": LEGACY_ROLE_MANAGED_DIGEST,
        "managed_joiner_added": False,
        "archives": [
            {
                "count": len(LEGACY_ARCHIVE_FILES),
                "directory": LEGACY_ARCHIVE_DIRECTORY,
                "files": list(LEGACY_ARCHIVE_FILES),
            }
        ],
    }


def legacy_role_receipt_bytes() -> bytes:
    """Return the exact serialized live v1 receipt, not a generic v1 encoding."""
    payload = (json.dumps(legacy_role_receipt_value(), indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    if (
        len(payload) != LEGACY_ROLE_RECEIPT_LENGTH
        or not secrets.compare_digest(
            hashlib.sha256(payload).hexdigest(), LEGACY_ROLE_RECEIPT_SHA256
        )
    ):
        raise DeployError("pinned legacy role receipt fingerprint is internally inconsistent")
    return payload


def legacy_role_block() -> bytes:
    """Return the exact nine-row live predecessor registration block."""
    block = role_block(LEGACY_ROLE_VERSION, LEGACY_ROLE_PATHS)
    if (
        len(block) != LEGACY_ROLE_BLOCK_LENGTH
        or not secrets.compare_digest(
            hashlib.sha256(block).hexdigest(), LEGACY_ROLE_MANAGED_DIGEST
        )
    ):
        raise DeployError("pinned legacy role block fingerprint is internally inconsistent")
    return block


def validate_legacy_role_receipt(value: Any, raw: bytes) -> dict[str, Any]:
    """Admit only the exact registration-only live predecessor receipt."""
    expected = legacy_role_receipt_value()
    archives = value.get("archives") if isinstance(value, dict) else None
    archive = archives[0] if isinstance(archives, list) and len(archives) == 1 else None
    if (
        not isinstance(value, dict)
        or set(value) != set(expected)
        or value.get("changed") is not True
        or value.get("managed_joiner_added") is not False
        or not isinstance(value.get("role_count"), int)
        or isinstance(value.get("role_count"), bool)
        or not isinstance(archive, dict)
        or set(archive) != {"count", "directory", "files"}
        or not isinstance(archive.get("count"), int)
        or isinstance(archive.get("count"), bool)
        or not isinstance(archive.get("directory"), str)
        or not isinstance(archive.get("files"), list)
        or any(not isinstance(name, str) for name in archive.get("files", []))
        or value != expected
        or len(raw) != LEGACY_ROLE_RECEIPT_LENGTH
        or not secrets.compare_digest(raw, legacy_role_receipt_bytes())
        or not secrets.compare_digest(
            hashlib.sha256(raw).hexdigest(), LEGACY_ROLE_RECEIPT_SHA256
        )
    ):
        raise DeployError("unknown legacy shared role receipt is not migratable")
    return value


def validate_legacy_registration_payload(config: bytes, receipt: bytes) -> str:
    """Authenticate only registration bytes; never inspect legacy profile files."""
    value = validate_legacy_role_receipt(
        strict_json_loads(receipt, "legacy shared role receipt"), receipt
    )
    _, span = config_without_owned_roles(config)
    if span is None:
        raise DeployError("exact legacy managed role block is missing")
    block = config[span[0] : span[1]]
    expected_block = legacy_role_block()
    if (
        len(block) != LEGACY_ROLE_BLOCK_LENGTH
        or not secrets.compare_digest(block, expected_block)
        or not secrets.compare_digest(
            hashlib.sha256(block).hexdigest(), LEGACY_ROLE_MANAGED_DIGEST
        )
        or not secrets.compare_digest(str(value["managed_digest"]), LEGACY_ROLE_MANAGED_DIGEST)
    ):
        raise DeployError("legacy managed role block is not the exact live predecessor")
    agents = parse_config(block, "legacy managed role block").get("agents")
    if not isinstance(agents, dict) or set(agents) != set(LEGACY_ROLE_NAMES):
        raise DeployError("legacy managed role block catalog is not exact")
    for name in LEGACY_ROLE_NAMES:
        if agents.get(name) != {"config_file": LEGACY_ROLE_PATHS[name]}:
            raise DeployError("legacy managed role registration path is not exact")
    return hashlib.sha256(
        b"bears-v1-registration\0" + block + b"\0" + receipt
    ).hexdigest()


def config_without_owned_roles(data: bytes) -> tuple[bytes, tuple[int, int] | None]:
    parse_config(data, "Codex config")
    span = managed_role_span(data)
    outside = data if span is None else data[: span[0]] + data[span[1] :]
    outside_agents = parse_config(outside, "Codex config outside the managed role block").get(
        "agents", {}
    )
    if not isinstance(outside_agents, dict):
        raise DeployError("global agent registrations have an unsupported shape")
    return outside, span


def desired_role_config(data: bytes, version: str, catalog: dict[str, str]) -> bytes:
    outside, _ = config_without_owned_roles(data)
    outside_agents = parse_config(outside, "Codex config outside the managed role block").get("agents", {})
    collisions = set(outside_agents).intersection(catalog)
    if collisions:
        names = ", ".join(sorted(collisions))
        raise DeployError(f"owned role registration collides outside the managed block: {names}")
    block = role_block(version, catalog)
    desired = config_with_role_block(data, block)
    verify_role_config(desired, catalog)
    return desired


def config_with_role_block(data: bytes, block: bytes) -> bytes:
    outside, span = config_without_owned_roles(data)
    if span is not None:
        desired = data[: span[0]] + block + data[span[1] :]
    else:
        separator = b"" if not data or data.endswith((b"\n", b"\r")) else b"\n"
        desired = data + separator + block
    if len(desired) > CONFIG_MAX_BYTES:
        raise DeployError("reconciled Codex config would exceed the bounded size")
    return desired


def verify_role_config(data: bytes, catalog: dict[str, str]) -> None:
    _, span = config_without_owned_roles(data)
    if span is None:
        raise DeployError("Codex config is missing the managed role block")
    agents = parse_config(data[span[0] : span[1]], "managed role block").get("agents")
    role_names = tuple(sorted(catalog))
    if not 1 <= len(role_names) <= 64:
        raise DeployError("role catalog size is outside 1..64")
    if not isinstance(agents, dict) or set(agents) != set(role_names):
        raise DeployError("managed role block does not contain the exact canonical role set")
    configured_paths: list[str] = []
    for name, expected_path in catalog.items():
        row = agents.get(name)
        if not isinstance(row, dict) or set(row) != {"config_file"}:
            raise DeployError(f"Codex role {name} has an ambiguous registration")
        configured = row["config_file"]
        if not isinstance(configured, str) or configured != expected_path or not Path(configured).is_absolute():
            raise DeployError(f"Codex role {name} does not target the exact cached profile")
        configured_paths.append(configured)
    if len(set(configured_paths)) != len(role_names):
        raise DeployError("Codex role registrations contain path aliases")
