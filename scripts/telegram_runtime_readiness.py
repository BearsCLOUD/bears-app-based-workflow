#!/usr/bin/env python3
"""Validate and render the Bears Telegram runtime readiness registry."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = PLUGIN_ROOT / "assets/catalog/telegram-runtime-readiness.v1.json"
DEFAULT_BACKLOG = PLUGIN_ROOT / "assets/catalog/telegram-aiogram-migration-backlog.v1.json"
DEFAULT_ROLE_CATALOG = PLUGIN_ROOT / "assets/catalog/platform-role-catalog.v1.json"
BACKLOG_RELATIVE_PATH = "assets/catalog/telegram-aiogram-migration-backlog.v1.json"

sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
from platform_roles import load_json, route_target, validate_catalog as validate_role_catalog  # noqa: E402
from telegram_migration_backlog import load_backlog, validate_backlog  # noqa: E402

REQUIRED_PACKET_FIELDS = {
    "surface",
    "backlog_item",
    "backlog_link",
    "path",
    "backlog_status",
    "backlog_artifact_gate_status",
    "role_route_target",
    "primary_role",
    "supporting_roles",
    "readiness_status",
    "implementation_gate",
    "characterization_tests",
    "behavior_inventory",
    "callback_governance",
    "security_controls",
    "secret_governance",
    "approval_status",
    "security_signoff",
    "validation_plan",
    "rollback_plan",
    "missing_evidence",
    "last_verified",
}
REQUIRED_BEHAVIOR_FIELDS = {
    "status",
    "commands",
    "message_flows",
    "fsm_states",
    "background_jobs",
    "side_effects",
    "evidence",
}
REQUIRED_CHARACTERIZATION_FIELDS = {
    "status",
    "command_flows",
    "callback_flows",
    "rendering_snapshots",
    "startup_import",
    "side_effect_baseline",
    "evidence",
}
REQUIRED_CALLBACK_FIELDS = {
    "status",
    "inventory",
    "schema",
    "privilege_model",
    "integrity",
    "replay_protection",
    "audit_binding",
    "evidence",
}
REQUIRED_SECURITY_FIELDS = {
    "status",
    "trust_boundary",
    "rbac",
    "idempotency",
    "audit_redaction",
    "external_side_effects",
    "evidence",
}
REQUIRED_SECRET_FIELDS = {
    "status",
    "telegram_bot_token_source_class",
    "webhook_secret_source_class",
    "wb_supplier_token_source_class",
    "chat_id_classification",
    "rotation_owner_classification",
}
ALLOWED_READINESS_STATUS = {"blocked", "ready", "exception", "deferred-source-required"}
ALLOWED_IMPLEMENTATION_GATE = {"open", "blocked", "not-applicable", "deferred-source-required"}
ALLOWED_DETAIL_STATUS = {"missing", "blocked", "complete", "not-applicable"}
ALLOWED_APPROVAL_STATUS = {"not-requested", "pending", "approved", "blocked"}
ALLOWED_SECURITY_SIGNOFF = {"required", "not-required", "approved", "blocked"}
ALLOWED_SECRET_SOURCE_CLASSES = {
    "none",
    "env-runtime",
    "vault-reference",
    "operator-single-use",
    "not-applicable",
    "unknown",
}
ALLOWED_CHAT_ID_CLASSES = {
    "private-user",
    "operator-group",
    "service-chat",
    "test-only",
    "not-applicable",
    "unknown",
}
ALLOWED_ROTATION_OWNER_CLASSES = {
    "platform-team",
    "product-team",
    "operator",
    "not-applicable",
    "unknown",
}
PACKET_REQUIRED_BACKLOG_STATUS = {
    "already-aiogram3-core-seed",
    "already-aiogram3-hardening",
    "target-aiogram3-upgrade",
    "target-aiogram3-rewrite",
}
SECRET_LIKE_PATTERNS = (
    re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{10,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{10,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{10,}\b"),
)


def load_registry(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"readiness registry not found: {path}") from exc
    except OSError as exc:
        raise ValueError(f"cannot read readiness registry: {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"invalid JSON in readiness registry: {path}: {exc.msg} (line {exc.lineno} column {exc.colno})"
        ) from exc
    if not isinstance(data, dict):
        raise ValueError(f"readiness registry root must be an object: {path}")
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


def require_list(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, list):
        errors.append(f"{path} must be a list")


def require_non_empty_string(value: Any, path: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{path} must be a non-empty string")


def has_secret_like_value(value: str) -> bool:
    return any(pattern.search(value) for pattern in SECRET_LIKE_PATTERNS)


def validate_text_list(
    value: Any,
    path: str,
    errors: list[str],
    *,
    require_non_empty: bool,
) -> None:
    if not isinstance(value, list):
        errors.append(f"{path} must be a list")
        return
    if require_non_empty and not value:
        errors.append(f"{path} must be a non-empty list")
    for index, item in enumerate(value):
        item_path = f"{path}[{index}]"
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{item_path} must be a non-empty string")
            continue
        if has_secret_like_value(item):
            errors.append(f"{item_path} contains secret-like value")


def validate_detail_block(
    value: Any,
    *,
    label: str,
    fields: set[str],
    errors: list[str],
) -> None:
    if not isinstance(value, dict):
        errors.append(f"{label} must be an object")
        return
    missing = fields - value.keys()
    if missing:
        errors.append(f"{label} missing fields: {sorted(missing)}")
        return
    status = value.get("status")
    if status not in ALLOWED_DETAIL_STATUS:
        errors.append(f"{label}.status must be one of {sorted(ALLOWED_DETAIL_STATUS)}")
    for field in sorted(fields - {"status", "evidence"}):
        if value.get(field) not in ALLOWED_DETAIL_STATUS:
            errors.append(f"{label}.{field} must be one of {sorted(ALLOWED_DETAIL_STATUS)}")
    validate_text_list(value.get("evidence"), f"{label}.evidence", errors, require_non_empty=False)


def validate_secret_governance(value: Any, label: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{label} must be an object")
        return
    missing = REQUIRED_SECRET_FIELDS - value.keys()
    if missing:
        errors.append(f"{label} missing fields: {sorted(missing)}")
        return
    extra = set(value) - REQUIRED_SECRET_FIELDS
    if extra:
        errors.append(f"{label} has unexpected fields: {sorted(extra)}")
    if value.get("status") not in ALLOWED_DETAIL_STATUS:
        errors.append(f"{label}.status must be one of {sorted(ALLOWED_DETAIL_STATUS)}")
    for field in (
        "telegram_bot_token_source_class",
        "webhook_secret_source_class",
        "wb_supplier_token_source_class",
    ):
        if value.get(field) not in ALLOWED_SECRET_SOURCE_CLASSES:
            errors.append(f"{label}.{field} must be one of {sorted(ALLOWED_SECRET_SOURCE_CLASSES)}")
    if value.get("chat_id_classification") not in ALLOWED_CHAT_ID_CLASSES:
        errors.append(f"{label}.chat_id_classification must be one of {sorted(ALLOWED_CHAT_ID_CLASSES)}")
    if value.get("rotation_owner_classification") not in ALLOWED_ROTATION_OWNER_CLASSES:
        errors.append(
            f"{label}.rotation_owner_classification must be one of {sorted(ALLOWED_ROTATION_OWNER_CLASSES)}"
        )


def is_complete_or_not_applicable(value: Any) -> bool:
    return value in {"complete", "not-applicable"}


def require_open_gate_evidence(surface: str, packet: dict[str, Any], backlog_item: dict[str, Any], errors: list[str]) -> None:
    if packet.get("readiness_status") != "ready":
        errors.append(f"surface {surface} implementation_gate open requires readiness_status=ready")
    backlog_artifact_gate = backlog_item.get("artifact_gate", {}).get("status")
    if backlog_artifact_gate != "open":
        errors.append(
            f"surface {surface} cannot open implementation_gate while backlog artifact_gate.status={backlog_artifact_gate}"
        )
    if packet.get("approval_status") != "approved":
        errors.append(f"surface {surface} implementation_gate open requires approval_status=approved")
    if packet.get("security_signoff") not in {"approved", "not-required"}:
        errors.append(
            f"surface {surface} implementation_gate open requires security_signoff approved or not-required"
        )
    if packet.get("missing_evidence"):
        errors.append(f"surface {surface} implementation_gate open requires empty missing_evidence")

    for name, value, fields in (
        ("characterization_tests", packet.get("characterization_tests"), REQUIRED_CHARACTERIZATION_FIELDS),
        ("behavior_inventory", packet.get("behavior_inventory"), REQUIRED_BEHAVIOR_FIELDS),
        ("callback_governance", packet.get("callback_governance"), REQUIRED_CALLBACK_FIELDS),
        ("security_controls", packet.get("security_controls"), REQUIRED_SECURITY_FIELDS),
    ):
        if not isinstance(value, dict):
            errors.append(f"surface {surface} implementation_gate open requires {name} object")
            continue
        if value.get("status") != "complete":
            errors.append(f"surface {surface} implementation_gate open requires {name}.status=complete")
        if not value.get("evidence"):
            errors.append(f"surface {surface} implementation_gate open requires {name}.evidence")
        for field in sorted(fields - {"status", "evidence"}):
            if not is_complete_or_not_applicable(value.get(field)):
                errors.append(
                    f"surface {surface} implementation_gate open requires {name}.{field} complete or not-applicable"
                )

    secret_governance = packet.get("secret_governance")
    if not isinstance(secret_governance, dict):
        errors.append(f"surface {surface} implementation_gate open requires secret_governance object")
    else:
        if secret_governance.get("status") != "complete":
            errors.append(f"surface {surface} implementation_gate open requires secret_governance.status=complete")
        for field in (
            "telegram_bot_token_source_class",
            "wb_supplier_token_source_class",
            "chat_id_classification",
            "rotation_owner_classification",
        ):
            if secret_governance.get(field) == "unknown":
                errors.append(
                    f"surface {surface} implementation_gate open requires secret_governance.{field} classification"
                )


def validate_registry(
    data: dict[str, Any],
    backlog: dict[str, Any],
    role_catalog: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    if data.get("schema") != "bears-telegram-runtime-readiness.v1":
        errors.append("schema must be bears-telegram-runtime-readiness.v1")
    if not data.get("updated"):
        errors.append("updated date is required")

    policy = data.get("policy")
    if not isinstance(policy, dict):
        errors.append("policy must be an object")
    else:
        if policy.get("role_gate_status") != "ROLE_COVERAGE_BLOCKER":
            errors.append("policy.role_gate_status must be ROLE_COVERAGE_BLOCKER")
        require_non_empty_list(policy.get("packet_required_for"), "policy.packet_required_for", errors)
        require_non_empty_list(
            policy.get("implementation_open_requires"),
            "policy.implementation_open_requires",
            errors,
        )
        require_non_empty_string(policy.get("goal"), "policy.goal", errors)
        require_non_empty_string(policy.get("secret_policy"), "policy.secret_policy", errors)

    role_errors = validate_role_catalog(role_catalog)
    if role_errors:
        errors.append("role catalog is invalid: " + "; ".join(role_errors))
    backlog_errors = validate_backlog(backlog, role_catalog)
    if backlog_errors:
        errors.append("backlog is invalid: " + "; ".join(backlog_errors))

    packets = data.get("packets")
    if not isinstance(packets, dict) or not packets:
        errors.append("packets must be a non-empty object keyed by backlog surface")
        return errors

    backlog_items = {
        item.get("surface"): item for item in backlog.get("items", []) if isinstance(item, dict)
    }
    eligible_surfaces = {
        item.get("surface")
        for item in backlog.get("items", [])
        if isinstance(item, dict) and item.get("migration_status") in PACKET_REQUIRED_BACKLOG_STATUS
    }
    for surface in sorted(s for s in eligible_surfaces if isinstance(s, str) and s not in packets):
        errors.append(f"eligible backlog surface {surface} requires readiness packet")
    role_names = {role.get("name") for role in role_catalog.get("roles", []) if isinstance(role, dict)}

    for key, packet in packets.items():
        label = f"packets[{key}]"
        if not isinstance(packet, dict):
            errors.append(f"{label} must be an object")
            continue
        missing = REQUIRED_PACKET_FIELDS - packet.keys()
        if missing:
            errors.append(f"surface {packet.get('surface', key)} missing fields: {sorted(missing)}")
        surface = packet.get("surface", key)
        if key != surface:
            errors.append(f"packet key {key} must match surface {surface}")
        require_non_empty_string(packet.get("path"), f"surface {surface}.path", errors)
        require_non_empty_string(packet.get("role_route_target"), f"surface {surface}.role_route_target", errors)
        require_non_empty_string(packet.get("backlog_item"), f"surface {surface}.backlog_item", errors)
        require_non_empty_string(packet.get("last_verified"), f"surface {surface}.last_verified", errors)

        backlog_link = packet.get("backlog_link")
        if not isinstance(backlog_link, dict):
            errors.append(f"surface {surface}.backlog_link must be an object")
        else:
            if backlog_link.get("catalog") != BACKLOG_RELATIVE_PATH:
                errors.append(
                    f"surface {surface}.backlog_link.catalog must be {BACKLOG_RELATIVE_PATH}"
                )
            if backlog_link.get("surface") != surface:
                errors.append(f"surface {surface}.backlog_link.surface must equal packet surface")

        if packet.get("readiness_status") not in ALLOWED_READINESS_STATUS:
            errors.append(f"surface {surface} invalid readiness_status: {packet.get('readiness_status')}")
        if packet.get("implementation_gate") not in ALLOWED_IMPLEMENTATION_GATE:
            errors.append(
                f"surface {surface} invalid implementation_gate: {packet.get('implementation_gate')}"
            )
        if packet.get("approval_status") not in ALLOWED_APPROVAL_STATUS:
            errors.append(f"surface {surface} invalid approval_status: {packet.get('approval_status')}")
        if packet.get("security_signoff") not in ALLOWED_SECURITY_SIGNOFF:
            errors.append(f"surface {surface} invalid security_signoff: {packet.get('security_signoff')}")

        primary_role = packet.get("primary_role")
        if primary_role not in role_names:
            errors.append(f"surface {surface} primary_role is not registered: {primary_role}")
        supporting_roles = packet.get("supporting_roles")
        if not isinstance(supporting_roles, list):
            errors.append(f"surface {surface}.supporting_roles must be a list")
        else:
            for role in supporting_roles:
                if role not in role_names:
                    errors.append(f"surface {surface} supporting role is not registered: {role}")

        validate_detail_block(
            packet.get("characterization_tests"),
            label=f"surface {surface}.characterization_tests",
            fields=REQUIRED_CHARACTERIZATION_FIELDS,
            errors=errors,
        )
        validate_detail_block(
            packet.get("behavior_inventory"),
            label=f"surface {surface}.behavior_inventory",
            fields=REQUIRED_BEHAVIOR_FIELDS,
            errors=errors,
        )
        validate_detail_block(
            packet.get("callback_governance"),
            label=f"surface {surface}.callback_governance",
            fields=REQUIRED_CALLBACK_FIELDS,
            errors=errors,
        )
        validate_detail_block(
            packet.get("security_controls"),
            label=f"surface {surface}.security_controls",
            fields=REQUIRED_SECURITY_FIELDS,
            errors=errors,
        )
        validate_secret_governance(packet.get("secret_governance"), f"surface {surface}.secret_governance", errors)
        validate_text_list(
            packet.get("validation_plan"),
            f"surface {surface}.validation_plan",
            errors,
            require_non_empty=True,
        )
        validate_text_list(
            packet.get("rollback_plan"),
            f"surface {surface}.rollback_plan",
            errors,
            require_non_empty=True,
        )
        validate_text_list(
            packet.get("missing_evidence"),
            f"surface {surface}.missing_evidence",
            errors,
            require_non_empty=False,
        )

        backlog_item = backlog_items.get(surface)
        if backlog_item is None:
            errors.append(f"surface {surface} is missing from telegram-aiogram-migration backlog")
            continue

        if packet.get("backlog_item") != surface:
            errors.append(f"surface {surface}.backlog_item must equal packet surface")
        if packet.get("path") != backlog_item.get("path"):
            errors.append(f"surface {surface} path does not match backlog path")
        if packet.get("backlog_status") != backlog_item.get("migration_status"):
            errors.append(
                f"surface {surface} backlog_status {packet.get('backlog_status')} "
                f"does not match backlog migration_status {backlog_item.get('migration_status')}"
            )
        backlog_artifact_status = backlog_item.get("artifact_gate", {}).get("status")
        if packet.get("backlog_artifact_gate_status") != backlog_artifact_status:
            errors.append(
                f"surface {surface} backlog_artifact_gate_status {packet.get('backlog_artifact_gate_status')} "
                f"does not match backlog artifact_gate.status {backlog_artifact_status}"
            )
        if packet.get("role_route_target") != backlog_item.get("role_route_target"):
            errors.append(f"surface {surface} role_route_target does not match backlog role_route_target")
        if primary_role != backlog_item.get("primary_role"):
            errors.append(
                f"surface {surface} primary_role {primary_role} does not match backlog primary_role {backlog_item.get('primary_role')}"
            )
        if packet.get("supporting_roles") != backlog_item.get("supporting_roles"):
            errors.append(f"surface {surface} supporting_roles do not match backlog supporting_roles")

        route_packet = route_target(role_catalog, packet.get("role_route_target"))
        if route_packet.get("status") != "matched":
            errors.append(f"surface {surface} role_route_target produced blocker for {packet.get('role_route_target')}")
        else:
            routed_role = route_packet.get("primary_role") or route_packet.get("required_role")
            if primary_role != routed_role:
                errors.append(
                    f"surface {surface} primary_role {primary_role} does not match route role {routed_role}"
                )

        if packet.get("implementation_gate") == "open":
            require_open_gate_evidence(surface, packet, backlog_item, errors)
    return errors


def render_summary(data: dict[str, Any]) -> str:
    lines = [
        f"schema: {data.get('schema')}",
        f"updated: {data.get('updated')}",
        f"role_gate_status: {data.get('policy', {}).get('role_gate_status')}",
        "",
        "packets:",
    ]
    packets = data.get("packets", {})
    for surface in sorted(packets):
        packet = packets[surface]
        lines.append(
            "- {surface}: backlog={backlog_status}, readiness={readiness_status}, gate={implementation_gate}, role={primary_role}".format(
                **packet
            )
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["validate", "summary", "json"])
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--backlog", type=Path, default=DEFAULT_BACKLOG)
    parser.add_argument("--role-catalog", type=Path, default=DEFAULT_ROLE_CATALOG)
    args = parser.parse_args(argv)

    try:
        registry = load_registry(args.registry)
        backlog = load_backlog(args.backlog)
        role_catalog = load_role_catalog(args.role_catalog)
        errors = validate_registry(registry, backlog, role_catalog)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if args.command == "summary":
        print(render_summary(registry))
    elif args.command == "json":
        print(json.dumps(registry, indent=2, ensure_ascii=False))
    else:
        print(f"readiness registry ok: {args.registry}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
