#!/usr/bin/env python3
"""Validate and capture a read-only dirty baseline for nested project repositories."""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY_CATALOG = PLUGIN_ROOT / "assets/catalog/project-dirty-baseline.v1.json"
DEFAULT_ROLE_CATALOG = PLUGIN_ROOT / "assets/catalog/platform-role-catalog.v1.json"
CANONICAL_PLUGIN_MOUNT = "/srv/bears/plugins/bears/"
REQUIRED_POLICY_FIELDS = {
    "schema",
    "owner_plugin",
    "concrete_part",
    "updated",
    "purpose",
    "route_target",
    "reference_doc",
    "validation",
    "status_contract",
    "scope_policy",
    "read_only_policy",
    "governance_scan",
    "output_contract",
}
REQUIRED_TOP_LEVEL_KEYS = {
    "schema",
    "root",
    "scope_mode",
    "container_inventory_only",
    "repo_count",
    "dirty_repo_count",
    "generated_at",
    "status",
    "operator_confirmation_required",
    "project_write_lane_allowed",
    "project_write_lane_blocked_by_dirty_baseline",
    "requires_exact_role_route",
    "write_handoff_allowed",
    "repositories",
}
REQUIRED_REPOSITORY_KEYS = {
    "repo_root",
    "branch",
    "head",
    "status_short_branch",
    "tracked_diff_summary",
    "untracked_files",
    "governance_files",
}
REQUIRED_GOVERNANCE_FILES = ("AGENTS.md", "SPEC.md", "requirements.md")
CANONICAL_FORBIDDEN_GIT_VERBS = {
    "add",
    "am",
    "apply",
    "checkout",
    "cherry-pick",
    "clean",
    "commit",
    "merge",
    "rebase",
    "reset",
    "restore",
    "revert",
    "rollback",
    "stash",
    "switch",
}
REQUIRED_FORBIDDEN_GIT_VERBS = CANONICAL_FORBIDDEN_GIT_VERBS
REQUIRED_GIT_FLAGS = {"--no-optional-locks"}
CAPTURE_SCHEMA = "bears-project-dirty-baseline-capture.v1"
PROJECT_WRITE_LANE_SCOPE = "project-write-lane"
CONTAINER_INVENTORY_SCOPE = "container-inventory"
SCOPE_MODE_CHOICES = (PROJECT_WRITE_LANE_SCOPE, CONTAINER_INVENTORY_SCOPE)


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON object from disk."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _resolve_plugin_owned_path(path_value: str) -> Path:
    """Resolve canonical workspace plugin paths inside a standalone plugin repo."""

    if path_value.startswith(CANONICAL_PLUGIN_MOUNT):
        return PLUGIN_ROOT / path_value.removeprefix(CANONICAL_PLUGIN_MOUNT)
    return Path(path_value)


def _load_platform_roles_module() -> Any:
    spec = importlib.util.spec_from_file_location("platform_roles", PLUGIN_ROOT / "scripts/subagents_roles.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load subagents_roles.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[arg-type]
    return module


def validate_catalog(
    policy_catalog: dict[str, Any],
    *,
    role_catalog: dict[str, Any] | None = None,
    check_files: bool = True,
) -> list[str]:
    """Validate the dirty-baseline policy catalog and its read-only contract."""
    errors: list[str] = []
    missing = sorted(REQUIRED_POLICY_FIELDS - set(policy_catalog))
    for field in missing:
        errors.append(f"missing policy field: {field}")

    if policy_catalog.get("schema") != "bears-project-dirty-baseline.v1":
        errors.append("schema must be bears-project-dirty-baseline.v1")
    if policy_catalog.get("owner_plugin") != "bears":
        errors.append("owner_plugin must be bears")
    if policy_catalog.get("concrete_part") != "project_dirty_baseline":
        errors.append("concrete_part must be project_dirty_baseline")

    route_target = policy_catalog.get("route_target")
    if not isinstance(route_target, str) or not route_target.endswith("/scripts/project_dirty_baseline.py"):
        errors.append("route_target must point to scripts/project_dirty_baseline.py")
    reference_doc = policy_catalog.get("reference_doc")
    if not isinstance(reference_doc, str) or not reference_doc.endswith("/docs/reference/project-dirty-baseline.md"):
        errors.append("reference_doc must point to docs/reference/project-dirty-baseline.md")

    validation = policy_catalog.get("validation")
    if not isinstance(validation, dict):
        errors.append("validation must be an object")
    else:
        commands = validation.get("commands")
        if not isinstance(commands, list) or not commands:
            errors.append("validation.commands must be a non-empty list")
        if validation.get("requires_exact_role_route") is not True:
            errors.append("validation.requires_exact_role_route must be true")

    status_contract = policy_catalog.get("status_contract")
    if not isinstance(status_contract, dict):
        errors.append("status_contract must be an object")
    else:
        expected_statuses = {
            "clean": "CLEAN_READ_ONLY_BASELINE",
            "dirty_unconfirmed": "DIRTY_BASELINE_REQUIRES_OPERATOR_CONFIRMATION",
            "dirty_confirmed": "BASELINE_ACCEPTED_READ_ONLY",
            "container_inventory": "CONTAINER_INVENTORY_ONLY",
        }
        for name, expected_status in expected_statuses.items():
            packet = status_contract.get(name)
            if not isinstance(packet, dict):
                errors.append(f"status_contract.{name} must be an object")
                continue
            if packet.get("status") != expected_status:
                errors.append(f"status_contract.{name}.status must be {expected_status}")
            if packet.get("write_handoff_allowed") is not False:
                errors.append(f"status_contract.{name}.write_handoff_allowed must stay false")

    scope_policy = policy_catalog.get("scope_policy")
    if not isinstance(scope_policy, dict):
        errors.append("scope_policy must be an object")
    else:
        if scope_policy.get("projects_container_root") != "/srv/bears/projects":
            errors.append("scope_policy.projects_container_root must be /srv/bears/projects")
        if scope_policy.get("projects_root_is_baseline") is not False:
            errors.append("scope_policy.projects_root_is_baseline must be false")
        if scope_policy.get("plugin_core_closeout_blocked_by_projects_dirty_state") is not False:
            errors.append("scope_policy.plugin_core_closeout_blocked_by_projects_dirty_state must be false")
        if scope_policy.get("project_write_lane_requires_concrete_root") is not True:
            errors.append("scope_policy.project_write_lane_requires_concrete_root must be true")
        if scope_policy.get("container_inventory_scope_mode") != CONTAINER_INVENTORY_SCOPE:
            errors.append("scope_policy.container_inventory_scope_mode must be container-inventory")
        if scope_policy.get("project_write_lane_scope_mode") != PROJECT_WRITE_LANE_SCOPE:
            errors.append("scope_policy.project_write_lane_scope_mode must be project-write-lane")
        rules = scope_policy.get("rules")
        if not isinstance(rules, list) or not any("not the baseline" in str(rule) for rule in rules):
            errors.append("scope_policy.rules must state that /srv/bears/projects is not the baseline")

    read_only_policy = policy_catalog.get("read_only_policy")
    if not isinstance(read_only_policy, dict):
        errors.append("read_only_policy must be an object")
    else:
        flags = read_only_policy.get("git_global_flags")
        if not isinstance(flags, list) or not REQUIRED_GIT_FLAGS.issubset(set(flags)):
            errors.append("read_only_policy.git_global_flags must include --no-optional-locks")
        forbidden_verbs = read_only_policy.get("forbidden_git_verbs")
        if not isinstance(forbidden_verbs, list):
            errors.append("read_only_policy.forbidden_git_verbs must be a list")
        elif set(forbidden_verbs) != REQUIRED_FORBIDDEN_GIT_VERBS:
            missing = sorted(REQUIRED_FORBIDDEN_GIT_VERBS - set(forbidden_verbs))
            extra = sorted(set(forbidden_verbs) - REQUIRED_FORBIDDEN_GIT_VERBS)
            detail = []
            if missing:
                detail.append("missing " + ", ".join(missing))
            if extra:
                detail.append("unexpected " + ", ".join(extra))
            errors.append(
                "read_only_policy.forbidden_git_verbs must exactly match canonical mutating git verbs"
                + (": " + "; ".join(detail) if detail else "")
            )
        forbidden_patterns = read_only_policy.get("forbidden_shell_patterns")
        if not isinstance(forbidden_patterns, list) or "git commit" not in forbidden_patterns:
            errors.append("read_only_policy.forbidden_shell_patterns must include git commit")
        if read_only_policy.get("diff_content_allowed") is not False:
            errors.append("read_only_policy.diff_content_allowed must be false")
        if read_only_policy.get("untracked_file_contents_allowed") is not False:
            errors.append("read_only_policy.untracked_file_contents_allowed must be false")
        if read_only_policy.get("write_handoff_allowed") is not False:
            errors.append("read_only_policy.write_handoff_allowed must stay false")
        if read_only_policy.get("operator_confirmation_only_changes_status") is not True:
            errors.append("read_only_policy.operator_confirmation_only_changes_status must be true")

    governance_scan = policy_catalog.get("governance_scan")
    if not isinstance(governance_scan, dict):
        errors.append("governance_scan must be an object")
    else:
        if "root_default" in governance_scan:
            errors.append("governance_scan.root_default is forbidden; /srv/bears/projects is not a baseline")
        if governance_scan.get("container_inventory_root") != "/srv/bears/projects":
            errors.append("governance_scan.container_inventory_root must be /srv/bears/projects")
        if governance_scan.get("project_write_lane_root") != "<concrete-repo-root>":
            errors.append("governance_scan.project_write_lane_root must be <concrete-repo-root>")
        nearest_files = governance_scan.get("nearest_files")
        if nearest_files != list(REQUIRED_GOVERNANCE_FILES):
            errors.append("governance_scan.nearest_files must equal [AGENTS.md, SPEC.md, requirements.md]")

    output_contract = policy_catalog.get("output_contract")
    if not isinstance(output_contract, dict):
        errors.append("output_contract must be an object")
    else:
        top_level_required = output_contract.get("top_level_required")
        if not isinstance(top_level_required, list) or not REQUIRED_TOP_LEVEL_KEYS.issubset(set(top_level_required)):
            errors.append("output_contract.top_level_required must cover the capture top-level keys")
        repository_required = output_contract.get("repository_required")
        if not isinstance(repository_required, list) or not REQUIRED_REPOSITORY_KEYS.issubset(
            set(repository_required)
        ):
            errors.append("output_contract.repository_required must cover repository keys")
        tracked_fields = output_contract.get("tracked_diff_summary_fields")
        if tracked_fields != ["status", "path"]:
            errors.append("output_contract.tracked_diff_summary_fields must equal [status, path]")

    if check_files:
        for path_value in (route_target, reference_doc):
            if isinstance(path_value, str) and not _resolve_plugin_owned_path(path_value).is_file():
                errors.append(f"referenced file missing: {path_value}")

    if role_catalog is None:
        role_catalog = load_json(DEFAULT_ROLE_CATALOG)
    try:
        platform_roles = _load_platform_roles_module()
        routed = platform_roles.route_target(
            role_catalog,
            route_target,
            plugin_root=PLUGIN_ROOT,
        )
    except Exception as exc:  # noqa: BLE001
        errors.append(f"platform role route check failed: {exc}")
    else:
        if routed.get("status") != "matched":
            errors.append(f"platform role route must match, got {routed.get('status')}")
        if routed.get("concrete_part") != policy_catalog.get("concrete_part"):
            errors.append("platform role route concrete_part drifted away from project_dirty_baseline")
        if routed.get("primary_role") != "bears-subagents-roles-governor":
            errors.append("platform role route primary_role must stay bears-subagents-roles-governor")

    return errors


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _git_command(repo_root: Path, *args: str) -> str:
    command = ["git", "--no-optional-locks", *args]
    result = subprocess.run(
        command,
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _git_command_allow_failure(repo_root: Path, *args: str) -> str | None:
    command = ["git", "--no-optional-locks", *args]
    result = subprocess.run(
        command,
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def discover_git_repositories(root: Path) -> list[Path]:
    """Discover nested git repositories under the bounded root."""
    repos: set[Path] = set()
    for current_root, dirnames, filenames in __import__("os").walk(root, topdown=True):
        current_path = Path(current_root)
        if ".git" in dirnames or ".git" in filenames:
            repos.add(current_path.resolve())
        if ".git" in dirnames:
            dirnames.remove(".git")
    return sorted(repos)


def _nearest_governance_files(repo_root: Path, scan_root: Path) -> dict[str, dict[str, Any]]:
    governance: dict[str, dict[str, Any]] = {}
    current = repo_root.resolve()
    scan_root = scan_root.resolve()
    for filename in REQUIRED_GOVERNANCE_FILES:
        found_path: Path | None = None
        probe = current
        while True:
            candidate = probe / filename
            if candidate.is_file():
                found_path = candidate
                break
            if probe == scan_root or probe.parent == probe:
                break
            probe = probe.parent
        governance[filename] = {
            "present": found_path is not None,
            "nearest_path": str(found_path) if found_path else None,
        }
    return governance


def _status_metadata(repo_root: Path) -> tuple[str, list[dict[str, str]], list[str]]:
    status_output = _git_command(repo_root, "status", "--short", "--branch", "--untracked-files=all")
    lines = status_output.splitlines()
    branch_line = ""
    tracked_diff_summary: list[dict[str, str]] = []
    untracked_files: list[str] = []
    for line in lines:
        if line.startswith("## "):
            branch_line = line[3:]
            continue
        if line.startswith("?? "):
            untracked_files.append(line[3:])
            continue
        if not line:
            continue
        tracked_diff_summary.append({"status": line[:2].strip() or line[:2], "path": line[3:]})
    return branch_line, tracked_diff_summary, untracked_files


def collect_repository_packet(repo_root: Path, scan_root: Path) -> dict[str, Any]:
    """Collect read-only provenance metadata for a single repository."""
    branch = _git_command_allow_failure(repo_root, "branch", "--show-current") or "(detached)"
    head = _git_command(repo_root, "rev-parse", "HEAD")
    upstream = _git_command_allow_failure(repo_root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    status_short_branch, tracked_diff_summary, untracked_files = _status_metadata(repo_root)
    return {
        "repo_root": str(repo_root.resolve()),
        "branch": branch,
        "head": head,
        "upstream": upstream,
        "status_short_branch": status_short_branch,
        "tracked_diff_summary": tracked_diff_summary,
        "untracked_files": sorted(untracked_files),
        "governance_files": _nearest_governance_files(repo_root, scan_root),
        "repository_dirty": bool(tracked_diff_summary or untracked_files),
    }


def capture_baseline(
    root: Path,
    *,
    operator_confirmed_baseline: bool = False,
    scope_mode: str = PROJECT_WRITE_LANE_SCOPE,
) -> dict[str, Any]:
    """Capture a read-only dirty baseline for nested repositories under root."""
    if scope_mode not in SCOPE_MODE_CHOICES:
        raise ValueError(f"scope_mode must be one of: {', '.join(SCOPE_MODE_CHOICES)}")
    bounded_root = root.resolve()
    if not bounded_root.is_dir():
        raise FileNotFoundError(f"root not found: {bounded_root}")

    repositories = [collect_repository_packet(repo_root, bounded_root) for repo_root in discover_git_repositories(bounded_root)]
    dirty_repo_count = sum(1 for repo in repositories if repo["repository_dirty"])
    container_inventory_only = scope_mode == CONTAINER_INVENTORY_SCOPE
    if container_inventory_only:
        status = "CONTAINER_INVENTORY_ONLY"
        operator_confirmation_required = False
        project_write_lane_blocked_by_dirty_baseline = False
    elif dirty_repo_count and not operator_confirmed_baseline:
        status = "DIRTY_BASELINE_REQUIRES_OPERATOR_CONFIRMATION"
        operator_confirmation_required = True
        project_write_lane_blocked_by_dirty_baseline = True
    elif dirty_repo_count:
        status = "BASELINE_ACCEPTED_READ_ONLY"
        operator_confirmation_required = False
        project_write_lane_blocked_by_dirty_baseline = False
    else:
        status = "CLEAN_READ_ONLY_BASELINE"
        operator_confirmation_required = False
        project_write_lane_blocked_by_dirty_baseline = False

    if container_inventory_only:
        notes = [
            "Read-only container inventory only.",
            "This packet is not a baseline for Bears plugin-core stabilization.",
            "Dirty repositories under the container do not block plugin-governance-only closeout.",
            "Select a concrete repo root and use project-write-lane mode before any repo write handoff.",
            "Run subagents_roles.py route <target> separately before any scoped implementation handoff.",
        ]
    else:
        notes = [
            "Read-only provenance gate only.",
            "This packet never authorizes product/runtime/deploy/integration writes.",
            "Run subagents_roles.py route <target> separately before any scoped implementation handoff.",
        ]

    return {
        "schema": CAPTURE_SCHEMA,
        "root": str(bounded_root),
        "scope_mode": scope_mode,
        "container_inventory_only": container_inventory_only,
        "repo_count": len(repositories),
        "dirty_repo_count": dirty_repo_count,
        "generated_at": _utc_now(),
        "status": status,
        "operator_confirmed_baseline": operator_confirmed_baseline,
        "operator_confirmation_required": operator_confirmation_required,
        "project_write_lane_allowed": False,
        "project_write_lane_blocked_by_dirty_baseline": project_write_lane_blocked_by_dirty_baseline,
        "requires_exact_role_route": True,
        "write_handoff_allowed": False,
        "repositories": repositories,
        "notes": notes,
    }


def render_summary(packet: dict[str, Any]) -> str:
    """Render a compact non-JSON summary."""
    return (
        f"status={packet['status']} root={packet['root']} repo_count={packet['repo_count']} "
        f"dirty_repo_count={packet['dirty_repo_count']} scope_mode={packet['scope_mode']} "
        f"write_handoff_allowed={str(packet['write_handoff_allowed']).lower()}"
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy-catalog", default=str(DEFAULT_POLICY_CATALOG), help="dirty baseline policy catalog path")
    parser.add_argument("--role-catalog", default=str(DEFAULT_ROLE_CATALOG), help="subagents roles catalog path")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="validate the dirty-baseline catalog and read-only policy")
    capture = sub.add_parser("capture", help="capture read-only dirty-baseline provenance under a root")
    capture.add_argument("--root", required=True, help="bounded root that contains nested repositories")
    capture.add_argument(
        "--scope-mode",
        choices=SCOPE_MODE_CHOICES,
        default=PROJECT_WRITE_LANE_SCOPE,
        help="repo write-lane gate by default; use container-inventory for read-only /srv/bears/projects inventory",
    )
    capture.add_argument("--json", action="store_true", help="emit JSON packet")
    capture.add_argument(
        "--operator-confirmed-baseline",
        action="store_true",
        help="acknowledge dirty baseline as operator-confirmed provenance only",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI."""
    args = build_parser().parse_args(argv)
    try:
        policy_catalog = load_json(Path(args.policy_catalog))
        role_catalog = load_json(Path(args.role_catalog))
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.command == "validate":
        errors = validate_catalog(policy_catalog, role_catalog=role_catalog)
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print(f"project dirty baseline policy ok: {args.policy_catalog}")
        return 0

    if args.command == "capture":
        try:
            packet = capture_baseline(
                Path(args.root),
                operator_confirmed_baseline=args.operator_confirmed_baseline,
                scope_mode=args.scope_mode,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(packet, indent=2, sort_keys=True))
        else:
            print(render_summary(packet))
        return 0 if packet["status"] != "DIRTY_BASELINE_REQUIRES_OPERATOR_CONFIRMATION" else 2

    print(f"ERROR: unsupported command: {args.command}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
