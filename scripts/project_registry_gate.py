#!/usr/bin/env python3
"""Gate project-mandate usage through the Bears dev-core project registry."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = Path("/srv/bears/dev/registry/projects.v1.json")
DEFAULT_ROLE_CATALOG = PLUGIN_ROOT / "assets/catalog/platform-role-catalog.v1.json"
EXPECTED_SCHEMA = "bears-dev-project-registry.v1"
BLOCKER_STATUS = "PROJECT_REGISTRATION_BLOCKER"
ALLOWED_PROFILES = {
    "workspace_group",
    "repo_project",
    "module_service",
    "plugin_repo",
    "infra_repo",
    "transitional_container",
}
ALLOWED_MATCH_POLICIES = {"exact", "self_or_child"}
REQUIRED_ENTRY_FIELDS = {
    "id",
    "name",
    "kind",
    "artifact_profile",
    "status",
    "paths",
    "role_target",
    "match_policy",
    "project_mandate_allowed",
    "spec_required",
    "spec_path",
    "plan_path",
    "tasks_path",
}
FORBIDDEN_TEXT_MARKERS = (
    "token=",
    "secret=",
    "password=",
    "private_key=",
    "api_key=",
    "authorization:",
    "bearer ",
)
RESTRICTED_MUTATION_MARKERS = (
    "production mutation",
    "prod mutation",
    "secret mutation",
    "raw secret",
    "production data mutation",
)
APPROVAL_MARKERS = (
    "operator approval",
    "explicit approval",
    "approved by operator",
    "approval evidence",
    "approval required",
)
SPEC_KIT_ANALYZE_ARTIFACT = "speckit-analyze.json"
SPEC_KIT_ANALYZE_SCHEMA = "bears.speckit-analyze.v1"
SPEC_KIT_ANALYZE_FIELDS = ("spec_path", "plan_path", "tasks_path")


def normalize_path(value: str) -> str:
    return value.replace("\\", "/").rstrip("/") or "/"


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} root must be an object")
    return data


def load_platform_roles_module():
    script = PLUGIN_ROOT / "scripts/platform_roles.py"
    spec = importlib.util.spec_from_file_location("platform_roles", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[arg-type]
    return module


def load_role_catalog(path: Path, *, platform_roles_module: Any) -> dict[str, Any]:
    try:
        return platform_roles_module.load_json(path)
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


def _iter_text(value: Any, path: str = "root") -> list[tuple[str, str]]:
    if isinstance(value, str):
        return [(path, value)]
    if isinstance(value, list):
        found: list[tuple[str, str]] = []
        for index, item in enumerate(value):
            found.extend(_iter_text(item, f"{path}[{index}]"))
        return found
    if isinstance(value, dict):
        found = []
        for key, item in value.items():
            found.extend(_iter_text(item, f"{path}.{key}"))
        return found
    return []


def validate_registry(registry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if registry.get("schema") != EXPECTED_SCHEMA:
        errors.append(f"schema must be {EXPECTED_SCHEMA}")
    if registry.get("owner") != "bears-dev-core":
        errors.append("owner must be bears-dev-core")
    if registry.get("primary_markdown") != "/srv/bears/dev/PROJECTS.md":
        errors.append("primary_markdown must be /srv/bears/dev/PROJECTS.md")

    entries = registry.get("entries")
    if not isinstance(entries, list) or not entries:
        errors.append("entries must be a non-empty list")
        return errors

    seen_ids: set[str] = set()
    seen_paths: dict[str, str] = {}
    for index, entry in enumerate(entries):
        entry_path = f"entries[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{entry_path} must be an object")
            continue
        missing = REQUIRED_ENTRY_FIELDS - set(entry)
        if missing:
            errors.append(f"{entry_path} missing fields: {sorted(missing)}")
            continue

        entry_id = entry.get("id")
        if not isinstance(entry_id, str) or not entry_id.strip():
            errors.append(f"{entry_path}.id must be a non-empty string")
            continue
        if entry_id in seen_ids:
            errors.append(f"duplicate project id: {entry_id}")
        seen_ids.add(entry_id)

        profile = entry.get("artifact_profile")
        if profile not in ALLOWED_PROFILES:
            errors.append(f"{entry_path}.artifact_profile must be one of {sorted(ALLOWED_PROFILES)}")
        if entry.get("status") not in {"registered", "deprecated", "future"}:
            errors.append(f"{entry_path}.status must be registered, deprecated, or future")
        if entry.get("match_policy") not in ALLOWED_MATCH_POLICIES:
            errors.append(f"{entry_path}.match_policy must be exact or self_or_child")
        if not isinstance(entry.get("project_mandate_allowed"), bool):
            errors.append(f"{entry_path}.project_mandate_allowed must be boolean")
        if not isinstance(entry.get("spec_required"), bool):
            errors.append(f"{entry_path}.spec_required must be boolean")
        if not isinstance(entry.get("role_target"), str) or not entry["role_target"].strip():
            errors.append(f"{entry_path}.role_target must be a non-empty string")

        for field in ("spec_path", "plan_path", "tasks_path"):
            value = entry.get(field)
            if value is not None and not isinstance(value, str):
                errors.append(f"{entry_path}.{field} must be string or null")
                continue
            if isinstance(value, str) and value and not value.startswith("/srv/bears"):
                errors.append(f"{entry_path}.{field} must be an absolute /srv/bears path or null")

        if entry.get("spec_required") is True:
            for field in ("spec_path", "plan_path", "tasks_path"):
                value = entry.get(field)
                if not isinstance(value, str) or not value.strip():
                    errors.append(f"{entry_path}.{field} is required when spec_required is true")

        paths = entry.get("paths")
        if not isinstance(paths, list) or not paths:
            errors.append(f"{entry_path}.paths must be a non-empty list")
            continue

        if entry.get("status") == "registered" and entry.get("kind") == "product":
            for raw_path in paths:
                if isinstance(raw_path, str) and not normalize_path(raw_path).startswith("/srv/bears/dev/app/"):
                    errors.append(
                        f"{entry_path}.paths product entries must live under /srv/bears/dev/app/**: {raw_path}"
                    )
            role_target = entry.get("role_target")
            if isinstance(role_target, str) and not normalize_path(role_target).startswith("/srv/bears/dev/app/"):
                errors.append(
                    f"{entry_path}.role_target product entries must live under /srv/bears/dev/app/**: {role_target}"
                )

        for raw_path in paths:
            if not isinstance(raw_path, str) or not raw_path.startswith("/srv/bears"):
                errors.append(f"{entry_path}.paths entries must be absolute /srv/bears paths")
                continue
            norm = normalize_path(raw_path)
            previous = seen_paths.get(norm)
            if previous and previous != entry_id:
                errors.append(f"path {norm} is registered by both {previous} and {entry_id}")
            seen_paths[norm] = entry_id

    for path, text in _iter_text(registry):
        lower = text.casefold()
        if any(marker in lower for marker in FORBIDDEN_TEXT_MARKERS):
            errors.append(f"{path}: registry must not contain raw restricted data")

    return errors


def _entry_matches_path(entry: dict[str, Any], target: str) -> tuple[bool, int]:
    target_norm = normalize_path(target)
    best_score = -1
    for raw_path in entry.get("paths", []):
        if not isinstance(raw_path, str):
            continue
        path_norm = normalize_path(raw_path)
        if target_norm == path_norm:
            best_score = max(best_score, 100_000 + len(path_norm))
        elif entry.get("match_policy") == "self_or_child" and target_norm.startswith(path_norm + "/"):
            best_score = max(best_score, 80_000 + len(path_norm))
    return best_score >= 0, best_score


def find_registered_entry(registry: dict[str, Any], target: str) -> dict[str, Any] | None:
    matches: list[tuple[int, dict[str, Any]]] = []
    for entry in registry.get("entries", []):
        if not isinstance(entry, dict):
            continue
        matched, score = _entry_matches_path(entry, target)
        if matched:
            matches.append((score, entry))
    if not matches:
        return None
    matches.sort(key=lambda item: item[0], reverse=True)
    return matches[0][1]


def build_registration_blocker(target: str) -> dict[str, Any]:
    return {
        "status": BLOCKER_STATUS,
        "target": target,
        "why_blocked": "missing_project_registration",
        "required_registry": str(DEFAULT_REGISTRY),
        "required_markdown": "/srv/bears/dev/PROJECTS.md",
        "allowed_next_actions": [
            "add the project to /srv/bears/dev/PROJECTS.md",
            "add the machine entry to /srv/bears/dev/registry/projects.v1.json",
            "route the project through platform_roles.py",
            "rerun project_registry_gate.py validate-registry",
        ],
        "project_mandate_allowed": False,
    }


def _spec_packet_fields(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "spec_required": entry.get("spec_required"),
        "spec_path": entry.get("spec_path"),
        "plan_path": entry.get("plan_path"),
        "tasks_path": entry.get("tasks_path"),
    }


def _spec_kit_analyze_path(spec_path: str) -> Path:
    return Path(spec_path).parent / "governance" / SPEC_KIT_ANALYZE_ARTIFACT


def _validate_spec_kit_analyze_packet(artifact_paths: dict[str, Any]) -> list[str]:
    spec_path = artifact_paths.get("spec_path")
    if not isinstance(spec_path, str) or not spec_path.strip():
        return []

    analyze_path = _spec_kit_analyze_path(spec_path)
    if not analyze_path.is_file():
        return [f"missing Spec Kit analyze artifact: {analyze_path}"]

    try:
        payload = json.loads(analyze_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return [f"invalid Spec Kit analyze JSON in {analyze_path}: {exc}"]

    if not isinstance(payload, dict):
        return [f"Spec Kit analyze artifact must be an object: {analyze_path}"]

    errors: list[str] = []
    if payload.get("schema") != SPEC_KIT_ANALYZE_SCHEMA:
        errors.append(f"{SPEC_KIT_ANALYZE_ARTIFACT}.schema must be {SPEC_KIT_ANALYZE_SCHEMA}")
    status = payload.get("status")
    if not isinstance(status, str) or status.casefold() != "pass":
        errors.append(f"{SPEC_KIT_ANALYZE_ARTIFACT}.status must be PASS")

    for field in SPEC_KIT_ANALYZE_FIELDS:
        value = artifact_paths.get(field)
        expected = str(Path(value).resolve()) if isinstance(value, str) else value
        if payload.get(field) != expected:
            errors.append(f"{SPEC_KIT_ANALYZE_ARTIFACT}.{field} must match current file: {expected}")

    return errors


def _validate_spec_packet(entry: dict[str, Any], role_target: str, primary_role: str | None) -> list[str]:
    if entry.get("spec_required") is not True:
        return []

    errors: list[str] = []
    artifact_paths = {
        "spec_path": entry.get("spec_path"),
        "plan_path": entry.get("plan_path"),
        "tasks_path": entry.get("tasks_path"),
    }

    for field, value in artifact_paths.items():
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field} is required when spec_required is true")
            continue
        if not Path(value).is_file():
            errors.append(f"missing Spec Kit artifact: {value}")

    errors.extend(_validate_spec_kit_analyze_packet(artifact_paths))

    tasks_path = artifact_paths.get("tasks_path")
    if not isinstance(tasks_path, str) or not Path(tasks_path).is_file():
        return errors

    try:
        tasks_text = Path(tasks_path).read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"cannot read tasks_path {tasks_path}: {exc}")
        return errors

    tasks_lower = tasks_text.casefold()
    route_markers = [role_target]
    if primary_role:
        route_markers.append(primary_role)
    if not any(marker and marker.casefold() in tasks_lower for marker in route_markers):
        errors.append("tasks_path must mention the registered role_target or primary_role")

    has_restricted_mutation = any(marker in tasks_lower for marker in RESTRICTED_MUTATION_MARKERS)
    has_approval = any(marker in tasks_lower for marker in APPROVAL_MARKERS)
    if has_restricted_mutation and not has_approval:
        errors.append("tasks_path mentions restricted mutation without operator approval evidence")

    return errors


def gate_project_mandate(
    target: str,
    *,
    registry: dict[str, Any],
    role_catalog_path: Path = DEFAULT_ROLE_CATALOG,
    plugin_root: Path = PLUGIN_ROOT,
) -> dict[str, Any]:
    registry_errors = validate_registry(registry)
    if registry_errors:
        return {
            "status": BLOCKER_STATUS,
            "target": target,
            "why_blocked": "registry_invalid",
            "validation_errors": registry_errors,
            "project_mandate_allowed": False,
        }

    entry = find_registered_entry(registry, target)
    if entry is None:
        return build_registration_blocker(target)

    if entry.get("project_mandate_allowed") is not True:
        return {
            "status": BLOCKER_STATUS,
            "target": target,
            "why_blocked": "project_mandate_disabled",
            "project_id": entry.get("id"),
            "project_mandate_allowed": False,
            **_spec_packet_fields(entry),
        }

    platform_roles = load_platform_roles_module()
    catalog = load_role_catalog(role_catalog_path, platform_roles_module=platform_roles)
    role_target = entry.get("role_target") or target
    route_packet = platform_roles.route_target(catalog, str(role_target), plugin_root=plugin_root)
    if route_packet.get("status") != "matched":
        route_packet = dict(route_packet)
        route_packet["project_registration_status"] = "registered"
        route_packet["project_id"] = entry.get("id")
        route_packet["project_mandate_allowed"] = False
        route_packet.update(_spec_packet_fields(entry))
        return route_packet

    spec_errors = _validate_spec_packet(entry, str(role_target), route_packet.get("primary_role"))
    if spec_errors:
        return {
            "status": BLOCKER_STATUS,
            "target": target,
            "why_blocked": "spec_kit_gate_failed",
            "project_id": entry.get("id"),
            "role_target": role_target,
            "primary_role": route_packet.get("primary_role"),
            "project_mandate_allowed": False,
            "validation_errors": spec_errors,
            **_spec_packet_fields(entry),
        }

    return {
        "status": "matched",
        "target": target,
        "project_id": entry.get("id"),
        "project_name": entry.get("name"),
        "artifact_profile": entry.get("artifact_profile"),
        "role_target": role_target,
        "primary_role": route_packet.get("primary_role"),
        "concrete_part": route_packet.get("concrete_part"),
        "project_mandate_allowed": True,
        "next_action": "run project-mandate checklist for this registered target",
        **_spec_packet_fields(entry),
    }


def _render_value(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    return str(value)


def render_packet(packet: dict[str, Any]) -> str:
    if packet.get("status") == "matched":
        return "\n".join(
            [
                "status: matched",
                f"target: {packet.get('target')}",
                f"project_id: {packet.get('project_id')}",
                f"artifact_profile: {packet.get('artifact_profile')}",
                f"primary_role: {packet.get('primary_role')}",
                "project_mandate_allowed: true",
                f"spec_required: {_render_value(packet.get('spec_required'))}",
                f"spec_path: {_render_value(packet.get('spec_path'))}",
                f"plan_path: {_render_value(packet.get('plan_path'))}",
                f"tasks_path: {_render_value(packet.get('tasks_path'))}",
                f"next_action: {packet.get('next_action')}",
            ]
        )
    lines = [
        f"status: {packet.get('status')}",
        f"target: {packet.get('target')}",
        f"why_blocked: {packet.get('why_blocked')}",
        "project_mandate_allowed: false",
    ]
    for field in ("spec_required", "spec_path", "plan_path", "tasks_path"):
        if field in packet:
            lines.append(f"{field}: {_render_value(packet.get(field))}")
    if packet.get("allowed_next_actions"):
        lines.append("allowed_next_actions:")
        lines.extend(f"  - {item}" for item in packet["allowed_next_actions"])
    if packet.get("validation_errors"):
        lines.append("validation_errors:")
        lines.extend(f"  - {item}" for item in packet["validation_errors"])
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY), help="project registry path")
    parser.add_argument("--role-catalog", default=str(DEFAULT_ROLE_CATALOG), help="platform role catalog path")
    parser.add_argument("--json", action="store_true", help="print JSON packet")
    parser.add_argument(
        "--allow-missing-external-registry",
        action="store_true",
        help="allow validate-registry to skip only the missing default external /srv/bears dev registry",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate-registry", help="validate the machine project registry")
    gate = sub.add_parser("gate", help="check whether project-mandate may run for a target")
    gate.add_argument("target")
    return parser


def _missing_default_registry_allowed(args: argparse.Namespace, registry_path: Path) -> bool:
    return (
        args.allow_missing_external_registry
        and str(registry_path) == str(DEFAULT_REGISTRY)
        and not registry_path.exists()
    )


def _print_missing_external_registry_skip(registry_path: Path) -> None:
    print(f"project registry skipped: external registry missing: {registry_path}")
    print("skip_reason: external_registry_missing_in_clean_repo")
    print("local_semantics: validate-registry without --allow-missing-external-registry still fails")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate-registry":
        registry_path = Path(args.registry)
        if _missing_default_registry_allowed(args, registry_path):
            _print_missing_external_registry_skip(registry_path)
            return 0
        try:
            registry = load_json(registry_path)
        except FileNotFoundError:
            print(f"ERROR: project registry not found: {registry_path}", file=sys.stderr)
            return 1
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        errors = validate_registry(registry)
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print(f"project registry ok: {args.registry}")
        return 0

    try:
        platform_roles = load_platform_roles_module()
        load_role_catalog(Path(args.role_catalog), platform_roles_module=platform_roles)
        registry = load_json(Path(args.registry))
        packet = gate_project_mandate(
            args.target,
            registry=registry,
            role_catalog_path=Path(args.role_catalog),
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(packet, indent=2, ensure_ascii=False))
    else:
        print(render_packet(packet))
    return 0 if packet.get("status") == "matched" else 2


if __name__ == "__main__":
    sys.exit(main())
