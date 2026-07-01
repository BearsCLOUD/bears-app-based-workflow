#!/usr/bin/env python3
"""Validate and render the Bears Telegram Aiogram migration backlog."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BACKLOG = PLUGIN_ROOT / "assets/catalog/telegram-aiogram-migration-backlog.v1.json"
DEFAULT_ROLE_CATALOG = PLUGIN_ROOT / "assets/catalog/platform-role-catalog.v1.json"

sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
from platform_roles import load_json, route_target, validate_catalog as validate_role_catalog  # noqa: E402

REQUIRED_ITEM_FIELDS = {
    "surface",
    "path",
    "role_route_target",
    "owner_group",
    "surface_class",
    "current_framework",
    "current_framework_version",
    "migration_status",
    "aiogram_target",
    "primary_role",
    "supporting_roles",
    "required_skill",
    "readiness_gate",
    "artifact_gate",
    "evidence_source",
    "next_actions",
    "validation_before_code",
    "live_runtime_policy",
    "last_verified",
}
ALLOWED_MIGRATION_STATUS = {
    "already-aiogram3-core-seed",
    "already-aiogram3-hardening",
    "target-aiogram3-upgrade",
    "target-aiogram3-rewrite",
    "not-applicable-non-bot",
    "deferred-missing-source",
}
ALLOWED_AIOGRAM_TARGET = {
    "platform-core-seed",
    "platform-core-consumer",
    "aiogram3-upgrade-required",
    "aiogram3-rewrite-required",
    "no-aiogram-non-bot",
    "deferred-source-required",
}
ALLOWED_ARTIFACT_STATUS = {
    "open",
    "blocked-before-code",
    "not-applicable",
    "deferred-source-required",
}


def load_backlog(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"backlog not found: {path}") from exc
    except OSError as exc:
        raise ValueError(f"cannot read backlog: {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"invalid JSON in backlog: {path}: {exc.msg} (line {exc.lineno} column {exc.colno})"
        ) from exc
    if not isinstance(data, dict):
        raise ValueError(f"backlog root must be an object: {path}")
    return data


def load_role_catalog(path: Path) -> dict[str, Any]:
    try:
        return load_json(path)
    except FileNotFoundError as exc:
        raise ValueError(f"role catalog not found: {path}") from exc
    except OSError as exc:
        raise ValueError(f"cannot read role catalog: {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"invalid JSON in role catalog: {path}: {exc.msg} (line {exc.lineno} column {exc.colno})"
        ) from exc
    except ValueError as exc:
        raise ValueError(f"invalid role catalog: {exc}") from exc


def require_non_empty_list(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, list) or not value:
        errors.append(f"{path} must be a non-empty list")


def validate_backlog(data: dict[str, Any], role_catalog: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if data.get("schema") != "bears-telegram-aiogram-migration-backlog.v1":
        errors.append("schema must be bears-telegram-aiogram-migration-backlog.v1")
    if not data.get("updated"):
        errors.append("updated date is required")

    policy = data.get("policy")
    if not isinstance(policy, dict):
        errors.append("policy must be an object")
    else:
        if policy.get("role_gate_status") != "ROLE_COVERAGE_BLOCKER":
            errors.append("policy.role_gate_status must be ROLE_COVERAGE_BLOCKER")
        require_non_empty_list(policy.get("sequence"), "policy.sequence", errors)
        for key in ("goal", "role_gate", "live_runtime_policy"):
            if not policy.get(key):
                errors.append(f"policy.{key} is required")

    require_non_empty_list(data.get("phases"), "phases", errors)

    role_errors = validate_role_catalog(role_catalog)
    if role_errors:
        errors.append("role catalog is invalid: " + "; ".join(role_errors))
    role_names = {role.get("name") for role in role_catalog.get("roles", []) if isinstance(role, dict)}

    items = data.get("items")
    if not isinstance(items, list) or not items:
        errors.append("items must be a non-empty list")
        return errors

    seen: set[str] = set()
    for index, item in enumerate(items):
        label = f"items[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} must be an object")
            continue
        surface = item.get("surface", index)
        missing = REQUIRED_ITEM_FIELDS - item.keys()
        if missing:
            errors.append(f"surface {surface} missing fields: {sorted(missing)}")
        if isinstance(surface, str):
            if surface in seen:
                errors.append(f"duplicate surface: {surface}")
            seen.add(surface)
        if item.get("migration_status") not in ALLOWED_MIGRATION_STATUS:
            errors.append(f"surface {surface} invalid migration_status: {item.get('migration_status')}")
        if item.get("aiogram_target") not in ALLOWED_AIOGRAM_TARGET:
            errors.append(f"surface {surface} invalid aiogram_target: {item.get('aiogram_target')}")
        primary_role = item.get("primary_role")
        if primary_role not in role_names:
            errors.append(f"surface {surface} primary_role is not registered: {primary_role}")
        supporting = item.get("supporting_roles")
        if not isinstance(supporting, list):
            errors.append(f"surface {surface} supporting_roles must be a list")
        else:
            for role in supporting:
                if role not in role_names:
                    errors.append(f"surface {surface} supporting role is not registered: {role}")
        for field in ("evidence_source", "next_actions", "validation_before_code"):
            require_non_empty_list(item.get(field), f"surface {surface}.{field}", errors)
        artifact_gate = item.get("artifact_gate")
        if not isinstance(artifact_gate, dict):
            errors.append(f"surface {surface}.artifact_gate must be an object")
        else:
            if artifact_gate.get("status") not in ALLOWED_ARTIFACT_STATUS:
                errors.append(
                    f"surface {surface} invalid artifact_gate.status: {artifact_gate.get('status')}"
                )
            if not isinstance(artifact_gate.get("present"), list):
                errors.append(f"surface {surface}.artifact_gate.present must be a list")
            if not isinstance(artifact_gate.get("missing"), list):
                errors.append(f"surface {surface}.artifact_gate.missing must be a list")
        route_target_value = item.get("role_route_target")
        if isinstance(route_target_value, str) and route_target_value:
            route_packet = route_target(role_catalog, route_target_value)
            if route_packet.get("status") != "matched":
                errors.append(f"surface {surface} route_target produced blocker for {route_target_value}")
                continue
            routed_role = route_packet.get("primary_role") or route_packet.get("required_role")
            if routed_role and primary_role != routed_role:
                errors.append(
                    f"surface {surface} primary_role {primary_role} does not match route role {routed_role}"
                )
    return errors


def render_summary(data: dict[str, Any]) -> str:
    lines = [
        f"schema: {data.get('schema')}",
        f"updated: {data.get('updated')}",
        f"role_gate_status: {data.get('policy', {}).get('role_gate_status')}",
        "",
        "items:",
    ]
    for item in data.get("items", []):
        artifact_status = item.get("artifact_gate", {}).get("status")
        lines.append(
            "- {surface}: {migration_status}, target={aiogram_target}, role={primary_role}, artifacts="
            "{artifact_status}".format(artifact_status=artifact_status, **item)
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["validate", "summary", "json"])
    parser.add_argument("--backlog", type=Path, default=DEFAULT_BACKLOG)
    parser.add_argument("--role-catalog", type=Path, default=DEFAULT_ROLE_CATALOG)
    args = parser.parse_args(argv)

    try:
        backlog = load_backlog(args.backlog)
        role_catalog = load_role_catalog(args.role_catalog)
        errors = validate_backlog(backlog, role_catalog)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if args.command == "summary":
        print(render_summary(backlog))
    elif args.command == "json":
        print(json.dumps(backlog, indent=2, ensure_ascii=False))
    else:
        print(f"migration backlog ok: {args.backlog}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
