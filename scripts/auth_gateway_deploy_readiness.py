#!/usr/bin/env python3
"""Validate Bears auth_core -> bears_gateway -> cd_deploy_stage readiness gates."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACKET = PLUGIN_ROOT / "assets/catalog/auth-gateway-deploy-readiness.v1.json"
DEFAULT_CATALOG = PLUGIN_ROOT / "assets/catalog/platform-role-catalog.v1.json"
DEFAULT_PROJECT_REGISTRY = Path("/srv/bears/dev/registry/projects.v1.json")
LEGACY_PLATFORM_REPO_ROOT = "/srv/bears/dev/platform/bears-platform"
EXPECTED_REPO_ROOT = "/srv/bears/dev/platform"
EXPECTED_FILE_BACKED_VALIDATION = "python3 scripts/auth_gateway_deploy_readiness.py --check-files validate"
EXPECTED_SCHEMA = "bears-auth-gateway-deploy-readiness.v1"
EXPECTED_OWNER = "bears"
EXPECTED_WORKFLOW = "auth-gateway-deploy-core"
EXPECTED_SPINE = ["auth_core", "bears_gateway", "cd_deploy_stage"]
NEUTRAL_CORE_ROUTE_TARGETS = {
    "auth_core": "/srv/bears/dev/platform/src/bears_platform/auth",
    "bears_gateway": "/srv/bears/dev/platform/src/bears_platform/gateway",
    "cd_deploy_stage": "/srv/bears/dev/platform/src/bears_platform/deploy",
}
SELLER_LEGACY_ROOT = "/srv/bears/projects/seller/apps/"
REQUIRED_REPO_ARTIFACTS = ["AGENTS.md", "SPEC.md", "requirements.md"]
REQUIRED_SURFACE_FIELDS = {
    "surface",
    "canonical_path",
    "route_target",
    "primary_role",
    "supporting_roles",
    "readiness_status",
    "artifact_gate",
    "implementation_gate",
    "repo_artifacts",
    "blocking_evidence",
    "required_evidence_before_open",
    "safe_validation_commands",
    "rollback_plan",
    "deploy_impact",
    "last_verified",
}
OPEN_GATE = "open"
BLOCKED_GATE = "blocked"
SECRET_VALUE_PATTERNS = [
    re.compile(r"(?i)-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]{16,}"),
    re.compile(r"(?i)\b(?:token|secret|password|passwd|private_key|api_key)\s*[:=]\s*['\"]?[a-z0-9._~+/=-]{8,}"),
]


def _load_platform_roles() -> Any:
    module_path = PLUGIN_ROOT / "scripts/platform_roles.py"
    spec = importlib.util.spec_from_file_location("platform_roles", module_path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError(f"cannot load {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[arg-type]
    return module


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} root must be an object")
    if data.get("schema") == EXPECTED_SCHEMA:
        _normalize_platform_repo_paths(data)
    return data


def load_cli_json(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"{label} not found: {path}")
    return load_json(path)


def _normalize_platform_repo_paths(value: Any) -> Any:
    if isinstance(value, str):
        return value.replace(LEGACY_PLATFORM_REPO_ROOT, EXPECTED_REPO_ROOT)
    if isinstance(value, list):
        for index, item in enumerate(value):
            value[index] = _normalize_platform_repo_paths(item)
        return value
    if isinstance(value, dict):
        for key, item in value.items():
            value[key] = _normalize_platform_repo_paths(item)
        return value
    return value


def _append_type_error(errors: list[str], path: str, value: Any, expected: str) -> bool:
    if expected == "object" and not isinstance(value, dict):
        errors.append(f"{path} must be an object")
        return True
    if expected == "array" and not isinstance(value, list):
        errors.append(f"{path} must be an array")
        return True
    if expected == "string" and not isinstance(value, str):
        errors.append(f"{path} must be a string")
        return True
    if expected == "boolean" and not isinstance(value, bool):
        errors.append(f"{path} must be a boolean")
        return True
    return False


def _iter_strings(value: Any, path: str = "root") -> list[tuple[str, str]]:
    if isinstance(value, str):
        return [(path, value)]
    if isinstance(value, list):
        results: list[tuple[str, str]] = []
        for index, item in enumerate(value):
            results.extend(_iter_strings(item, f"{path}[{index}]"))
        return results
    if isinstance(value, dict):
        results = []
        for key, item in value.items():
            results.extend(_iter_strings(item, f"{path}.{key}"))
        return results
    return []


def _validate_no_secret_values(packet: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for path, text in _iter_strings(packet):
        for pattern in SECRET_VALUE_PATTERNS:
            if pattern.search(text):
                errors.append(f"{path}: looks like a raw secret value; keep only stable reference names")
                break
    return errors


def _validate_repo_artifacts(surface: dict[str, Any], errors: list[str], *, check_files: bool) -> None:
    surface_name = surface.get("surface", "<unknown>")
    artifacts = surface.get("repo_artifacts")
    if _append_type_error(errors, f"surface {surface_name}.repo_artifacts", artifacts, "object"):
        return

    repo_root = artifacts.get("repo_root")
    if _append_type_error(errors, f"surface {surface_name}.repo_artifacts.repo_root", repo_root, "string"):
        return
    if not Path(repo_root).is_absolute():
        errors.append(f"surface {surface_name}: repo_artifacts.repo_root must be an absolute path")

    required = artifacts.get("required")
    present = artifacts.get("present")
    missing = artifacts.get("missing")
    for field_name, value in (("required", required), ("present", present), ("missing", missing)):
        if _append_type_error(errors, f"surface {surface_name}.repo_artifacts.{field_name}", value, "array"):
            return
        if not all(isinstance(item, str) for item in value):
            errors.append(f"surface {surface_name}.repo_artifacts.{field_name} must contain only strings")
            return

    if required != REQUIRED_REPO_ARTIFACTS:
        errors.append(f"surface {surface_name}: required repo artifacts must be {REQUIRED_REPO_ARTIFACTS}")
    if sorted(present + missing) != sorted(required):
        errors.append(f"surface {surface_name}: present + missing must exactly cover required repo artifacts")

    if surface.get("artifact_gate") == OPEN_GATE and missing:
        errors.append(f"surface {surface_name}: artifact_gate cannot be open while repo artifacts are missing")

    canonical_path = surface.get("canonical_path")
    if not check_files or not isinstance(canonical_path, str):
        return
    root = Path(repo_root)
    if not root.is_dir():
        errors.append(f"surface {surface_name}: repo_artifacts.repo_root missing on disk: {repo_root}")
    if not Path(canonical_path).is_dir():
        errors.append(f"surface {surface_name}: canonical_path missing on disk: {canonical_path}")
    actual_present = sorted(item for item in required if (root / item).is_file())
    actual_missing = sorted(item for item in required if not (root / item).is_file())
    if sorted(present) != actual_present:
        errors.append(
            f"surface {surface_name}: repo_artifacts.present is stale; expected {actual_present}, got {sorted(present)}"
        )
    if sorted(missing) != actual_missing:
        errors.append(
            f"surface {surface_name}: repo_artifacts.missing is stale; expected {actual_missing}, got {sorted(missing)}"
        )


def _load_project_registry(path: Path = DEFAULT_PROJECT_REGISTRY) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    return data if isinstance(data, dict) else None


def _validate_registry_exact_entry(
    surface: dict[str, Any],
    errors: list[str],
    *,
    check_files: bool,
    registry: dict[str, Any] | None,
) -> None:
    if not check_files:
        return
    surface_name = surface.get("surface", "<unknown>")
    canonical_path = surface.get("canonical_path")
    if not isinstance(canonical_path, str):
        return
    if registry is None:
        errors.append(f"surface {surface_name}: root project registry unavailable: {DEFAULT_PROJECT_REGISTRY}")
        return
    entries = registry.get("entries")
    if not isinstance(entries, list):
        errors.append(f"surface {surface_name}: root project registry entries must be an array")
        return
    exact_entries = [
        entry
        for entry in entries
        if isinstance(entry, dict)
        and entry.get("status") == "registered"
        and canonical_path in entry.get("paths", [])
    ]
    if not exact_entries:
        errors.append(f"surface {surface_name}: root registry exact entry missing for canonical_path {canonical_path}")


def _validate_route(surface: dict[str, Any], catalog: dict[str, Any], errors: list[str]) -> None:
    platform_roles = _load_platform_roles()
    surface_name = surface.get("surface", "<unknown>")
    route_target = surface.get("route_target")
    if _append_type_error(errors, f"surface {surface_name}.route_target", route_target, "string"):
        return
    packet = platform_roles.route_target(catalog, route_target)
    if packet.get("status") != "matched":
        errors.append(f"surface {surface_name}: route_target does not match a registered role")
        return
    if packet.get("platform_part") != surface.get("surface"):
        errors.append(
            f"surface {surface_name}: route_target matched {packet.get('platform_part')}, expected {surface.get('surface')}"
        )
    if packet.get("required_role") != surface.get("primary_role"):
        errors.append(
            f"surface {surface_name}: primary_role {surface.get('primary_role')!r} does not match route role {packet.get('required_role')!r}"
        )


def _has_seller_legacy_path(value: str) -> bool:
    return SELLER_LEGACY_ROOT in value or "projects/seller/apps/" in value


def _validate_no_seller_bound_core_surface(surface: dict[str, Any], errors: list[str]) -> None:
    surface_name = surface.get("surface", "<unknown>")
    expected_path = NEUTRAL_CORE_ROUTE_TARGETS.get(surface_name)
    if expected_path is None:
        return
    for field in ("canonical_path", "route_target"):
        value = surface.get(field)
        if value != expected_path:
            errors.append(f"surface {surface_name}: {field} must be neutral core path {expected_path}")
        if isinstance(value, str) and _has_seller_legacy_path(value):
            errors.append(f"surface {surface_name}: {field} must not use a seller legacy path")
    for command in surface.get("safe_validation_commands", []):
        if isinstance(command, str) and _has_seller_legacy_path(command):
            errors.append(f"surface {surface_name}: safe_validation_commands must not require seller legacy paths")


def _validate_surface(
    surface: dict[str, Any],
    catalog: dict[str, Any],
    errors: list[str],
    *,
    check_files: bool,
    registry: dict[str, Any] | None,
) -> None:
    surface_name = surface.get("surface", "<unknown>")
    missing_fields = sorted(REQUIRED_SURFACE_FIELDS - surface.keys())
    if missing_fields:
        errors.append(f"surface {surface_name}: missing fields {missing_fields}")
        return

    for field in ("surface", "canonical_path", "route_target", "primary_role", "readiness_status", "artifact_gate", "implementation_gate", "last_verified"):
        _append_type_error(errors, f"surface {surface_name}.{field}", surface.get(field), "string")
    for field in ("supporting_roles", "blocking_evidence", "required_evidence_before_open", "safe_validation_commands"):
        _append_type_error(errors, f"surface {surface_name}.{field}", surface.get(field), "array")
    for field in ("rollback_plan", "deploy_impact"):
        _append_type_error(errors, f"surface {surface_name}.{field}", surface.get(field), "object")

    if not isinstance(surface.get("canonical_path"), str) or not surface["canonical_path"].startswith("/srv/bears/"):
        errors.append(f"surface {surface_name}: canonical_path must be an absolute /srv/bears path")
    if surface.get("artifact_gate") not in {OPEN_GATE, BLOCKED_GATE}:
        errors.append(f"surface {surface_name}: artifact_gate must be open or blocked")
    if surface.get("implementation_gate") not in {OPEN_GATE, BLOCKED_GATE}:
        errors.append(f"surface {surface_name}: implementation_gate must be open or blocked")
    if not surface.get("safe_validation_commands"):
        errors.append(f"surface {surface_name}: safe_validation_commands must be non-empty")
    if not surface.get("required_evidence_before_open"):
        errors.append(f"surface {surface_name}: required_evidence_before_open must be non-empty")

    _validate_repo_artifacts(surface, errors, check_files=check_files)
    artifacts = surface.get("repo_artifacts")
    if isinstance(artifacts, dict) and isinstance(artifacts.get("repo_root"), str):
        repo_root = artifacts["repo_root"]
        if not repo_root.startswith("/srv/bears/"):
            errors.append(f"surface {surface_name}: repo_artifacts.repo_root must be an absolute /srv/bears path")
    if isinstance(artifacts, dict) and artifacts.get("repo_root") != EXPECTED_REPO_ROOT:
        errors.append(f"surface {surface_name}: repo_artifacts.repo_root must be {EXPECTED_REPO_ROOT}")
    _validate_registry_exact_entry(surface, errors, check_files=check_files, registry=registry)
    _validate_no_seller_bound_core_surface(surface, errors)
    _validate_route(surface, catalog, errors)

    if surface.get("implementation_gate") == OPEN_GATE:
        if surface.get("readiness_status") != "ready":
            errors.append(f"surface {surface_name}: implementation_gate=open requires readiness_status=ready")
        if surface.get("blocking_evidence"):
            errors.append(f"surface {surface_name}: implementation_gate=open requires empty blocking_evidence")
        if surface.get("repo_artifacts", {}).get("missing"):
            errors.append(f"surface {surface_name}: implementation_gate=open requires no missing repo artifacts")
        rollback_status = surface.get("rollback_plan", {}).get("status")
        if rollback_status not in {"ready", "validated", "not-applicable"}:
            errors.append(f"surface {surface_name}: implementation_gate=open requires ready rollback_plan.status")


def validate_packet(
    packet: dict[str, Any],
    *,
    catalog: dict[str, Any] | None = None,
    check_files: bool = False,
    registry: dict[str, Any] | None = None,
) -> list[str]:
    errors: list[str] = []

    if packet.get("schema") != EXPECTED_SCHEMA:
        errors.append(f"schema must be {EXPECTED_SCHEMA}")
    if packet.get("owner_plugin") != EXPECTED_OWNER:
        errors.append(f"owner_plugin must be {EXPECTED_OWNER}")
    if packet.get("workflow_id") != EXPECTED_WORKFLOW:
        errors.append(f"workflow_id must be {EXPECTED_WORKFLOW}")
    if packet.get("strict_order") is not True:
        errors.append("strict_order must be true")
    if packet.get("ordered_spine") != EXPECTED_SPINE:
        errors.append("ordered_spine must be auth_core -> bears_gateway -> cd_deploy_stage")

    global_gate = packet.get("global_gate")
    if _append_type_error(errors, "global_gate", global_gate, "object") is False:
        if global_gate.get("status") not in {OPEN_GATE, BLOCKED_GATE}:
            errors.append("global_gate.status must be open or blocked")

    promotion_rules = packet.get("promotion_rules")
    if _append_type_error(errors, "promotion_rules", promotion_rules, "array") is False and not promotion_rules:
        errors.append("promotion_rules must be non-empty")

    surfaces = packet.get("surfaces")
    if _append_type_error(errors, "surfaces", surfaces, "array"):
        return errors
    surface_names = [surface.get("surface") for surface in surfaces if isinstance(surface, dict)]
    if surface_names != EXPECTED_SPINE:
        errors.append("surfaces must be ordered as auth_core -> bears_gateway -> cd_deploy_stage")

    if catalog is None:
        catalog = load_json(DEFAULT_CATALOG)
    if check_files and registry is None:
        registry = _load_project_registry()

    previous_open = True
    all_open = True
    for surface in surfaces:
        if not isinstance(surface, dict):
            errors.append("surfaces items must be objects")
            continue
        _validate_surface(surface, catalog, errors, check_files=check_files, registry=registry)
        surface_name = surface.get("surface", "<unknown>")
        gate_open = surface.get("implementation_gate") == OPEN_GATE
        if gate_open and not previous_open:
            errors.append(f"surface {surface_name}: implementation_gate cannot open before earlier spine surfaces")
        previous_open = previous_open and gate_open
        all_open = all_open and gate_open

    if isinstance(global_gate, dict):
        if global_gate.get("status") == OPEN_GATE and not all_open:
            errors.append("global_gate.status=open requires every surface implementation_gate to be open")
        if global_gate.get("status") == BLOCKED_GATE and all_open:
            errors.append("global_gate.status=blocked is stale because every implementation gate is open")

    errors.extend(_validate_no_secret_values(packet))
    return errors


def render_summary(packet: dict[str, Any]) -> str:
    lines = [
        f"workflow: {packet.get('workflow_id', '<unknown>')}",
        f"global_gate: {packet.get('global_gate', {}).get('status', '<unknown>')}",
        "surfaces:",
    ]
    for surface in packet.get("surfaces", []):
        if not isinstance(surface, dict):
            continue
        lines.append(
            "- {surface}: readiness={readiness} artifact_gate={artifact_gate} implementation_gate={implementation_gate} role={role}".format(
                surface=surface.get("surface", "<unknown>"),
                readiness=surface.get("readiness_status", "<unknown>"),
                artifact_gate=surface.get("artifact_gate", "<unknown>"),
                implementation_gate=surface.get("implementation_gate", "<unknown>"),
                role=surface.get("primary_role", "<unknown>"),
            )
        )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", default=str(DEFAULT_PACKET), help="readiness packet path")
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG), help="platform role catalog path")
    parser.add_argument(
        "--check-files",
        action="store_true",
        help="verify repo artifact file presence against the current local workspace checkout",
    )
    parser.add_argument(
        "--no-file-check",
        action="store_true",
        help="compatibility alias for repo-only validation; file presence checks stay disabled unless --check-files is set",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="validate readiness packet")
    sub.add_parser("summary", help="print compact readiness summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        packet = load_cli_json(Path(args.packet), label="packet")
        catalog = load_cli_json(Path(args.catalog), label="catalog")
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.command == "validate":
        errors = validate_packet(packet, catalog=catalog, check_files=args.check_files)
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print(f"auth/gateway/deploy readiness ok: {args.packet}")
        return 0

    if args.command == "summary":
        print(render_summary(packet))
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
