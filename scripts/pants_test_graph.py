#!/usr/bin/env python3
"""Validate and query the bounded Pants test graph pilot."""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = PLUGIN_ROOT / "assets/catalog/pants-test-graph.v1.json"
SCHEMA_PATH = PLUGIN_ROOT / "assets/schemas/pants-test-graph.v1.schema.json"
COMMANDS = (
    "pants test ::",
    "python3 scripts/pants_test_graph.py validate",
    "python3 scripts/pants_test_graph.py impacted --from-git <range> --json",
)

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from scripts.local_json_schema import validate_json_schema
from scripts import test_selection


def load_json(path: Path) -> Any:
    """Read a JSON file from disk."""
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def normalize_path(path: str) -> str:
    """Normalize a repository path for stable matching."""
    normalized = path.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def matches(path: str, pattern: str) -> bool:
    """Return true when a path matches a route pattern."""
    return fnmatch.fnmatchcase(path, pattern) or fnmatch.fnmatchcase(path, pattern.rstrip("/**") + "/**")


def changed_files_from_git(range_spec: str | None, *, staged: bool = False) -> list[str]:
    """Return changed files for a git range."""
    if staged:
        command = ["git", "diff", "--cached", "--name-only"]
    elif range_spec:
        command = ["git", "diff", "--name-only", range_spec]
    else:
        raise RuntimeError("--from-git, --staged, or --changed-file is required")
    result = subprocess.run(
        command,
        cwd=PLUGIN_ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git diff failed for {range_spec}")
    return [normalize_path(line) for line in result.stdout.splitlines() if line.strip()]


def _route_matches(route: dict[str, Any], path: str) -> bool:
    """Return true when a route should own the path."""
    return any(matches(path, pattern) for pattern in route.get("patterns", []))


def _route_tests(route: dict[str, Any]) -> list[str]:
    """Return stable unique tests for a route."""
    return sorted({normalize_path(test) for test in route.get("tests", [])})


def validate_catalog(catalog: dict[str, Any]) -> list[str]:
    """Validate the pilot catalog and required references."""
    errors = validate_json_schema(catalog, SCHEMA_PATH, "pants-test-graph")
    routes = [route for route in catalog.get("routes", []) if isinstance(route, dict)]
    route_names: set[str] = set()
    target_names: set[str] = set()
    tests = {path.relative_to(PLUGIN_ROOT).as_posix() for path in (PLUGIN_ROOT / "tests").glob("test_*.py")}
    required_commands = set(COMMANDS)

    for command in required_commands:
        if command not in catalog.get("commands", []):
            errors.append(f"pants-test-graph missing command: {command}")

    if catalog.get("owner_script") != "scripts/pants_test_graph.py":
        errors.append("pants-test-graph owner_script must be scripts/pants_test_graph.py")
    if catalog.get("authority_script") != "scripts/test_selection.py":
        errors.append("pants-test-graph authority_script must be scripts/test_selection.py")

    for path in (CATALOG_PATH, SCHEMA_PATH, PLUGIN_ROOT / "scripts/pants_test_graph.py", PLUGIN_ROOT / "scripts/test_selection.py", PLUGIN_ROOT / "docs/reference/pants-test-graph.md", PLUGIN_ROOT / "pants.toml", PLUGIN_ROOT / "BUILD"):
        if not path.exists():
            errors.append(f"missing required artifact: {path.relative_to(PLUGIN_ROOT)}")

    for index, route in enumerate(routes):
        name = str(route.get("name", ""))
        target = str(route.get("pants_target", ""))
        if not name:
            errors.append(f"pants-test-graph.routes[{index}].name is required")
            continue
        if name in route_names:
            errors.append(f"pants-test-graph route name must be unique: {name}")
        route_names.add(name)
        if target in target_names:
            errors.append(f"pants-test-graph pants_target must be unique: {target}")
        target_names.add(target)
        for test_path in _route_tests(route):
            if test_path not in tests:
                errors.append(f"pants-test-graph.route[{name}] references missing test {test_path}")

    route_map = {str(route.get("name", "")): route for route in routes}
    scripts_route = route_map.get("scripts-python")
    if not scripts_route or "scripts/*.py" not in scripts_route.get("patterns", []):
        errors.append("pants-test-graph must route scripts/*.py through scripts-python")
    if not scripts_route or "tests/test_pants_test_graph.py" not in scripts_route.get("tests", []):
        errors.append("pants-test-graph scripts-python must select tests/test_pants_test_graph.py")

    audit_route = route_map.get("external-review-audit-gate")
    if not audit_route or "docs/audits/external-review-2026-06-25/*" not in audit_route.get("patterns", []):
        errors.append("pants-test-graph must route external-review audit docs through external-review-audit-gate")
    if not audit_route or "tests/test_external_review_audit.py" not in audit_route.get("tests", []):
        errors.append("pants-test-graph external-review gate must select tests/test_external_review_audit.py")

    return errors


def route_selection(catalog: dict[str, Any], changed_files: list[str]) -> dict[str, Any]:
    """Select impacted tests and gates for a changed-file list."""
    selected_tests: set[str] = set()
    selected_targets: set[str] = set()
    matched: list[str] = []
    unmatched: list[str] = []
    gates: set[str] = set()

    for raw_path in sorted({normalize_path(path) for path in changed_files}):
        path_matched = False
        for route in catalog.get("routes", []):
            if not isinstance(route, dict) or not _route_matches(route, raw_path):
                continue
            path_matched = True
            matched.append(f"{raw_path}:{route.get('name')}")
            selected_tests.update(_route_tests(route))
            selected_targets.add(str(route.get("pants_target", "")))
            gate = str(route.get("gate") or "")
            if gate:
                gates.add(gate)
        if not path_matched:
            unmatched.append(raw_path)

    confidence = "high" if not unmatched else "low"
    return {
        "selector_confidence": confidence,
        "changed_files": sorted({normalize_path(path) for path in changed_files}),
        "matched": sorted(set(matched)),
        "unmatched": sorted(set(unmatched)),
        "requires_full_suite": bool(unmatched),
        "tests": sorted(selected_tests),
        "pants_targets": sorted(target for target in selected_targets if target),
        "gates": sorted(gates),
    }


def authority_selection(changed_files: list[str]) -> dict[str, Any]:
    """Return the comparison packet from test_selection.py."""
    catalog = test_selection.load_json(test_selection.CATALOG_PATH)
    selection = test_selection.impacted_tests(catalog, sorted({normalize_path(path) for path in changed_files}))
    return {
        "selector_confidence": selection["selector_confidence"],
        "changed_files": selection["changed_files"],
        "matched": selection["matched"],
        "unmatched": selection["unmatched"],
        "requires_full_suite": selection["requires_full_suite"],
        "tests": selection["tests"],
    }


def compare_selections(graph_tests: list[str], authority_tests: list[str]) -> dict[str, Any]:
    """Compare the pilot graph output against the authority selection."""
    graph_set = set(graph_tests)
    authority_set = set(authority_tests)
    return {
        "shared_tests": sorted(graph_set & authority_set),
        "graph_only_tests": sorted(graph_set - authority_set),
        "authority_only_tests": sorted(authority_set - graph_set),
    }


def validate_packet() -> dict[str, Any]:
    """Build the catalog validation packet."""
    errors: list[str] = []
    if not CATALOG_PATH.exists():
        errors.append("pants test graph catalog missing")
        catalog: dict[str, Any] = {}
    else:
        catalog = load_json(CATALOG_PATH)
    if not SCHEMA_PATH.exists():
        errors.append("pants test graph schema missing")
    if catalog:
        errors.extend(validate_catalog(catalog))
    return {
        "schema": "bears-pants-test-graph-validation.v1",
        "status": "pass" if not errors else "fail",
        "catalog_path": CATALOG_PATH.relative_to(PLUGIN_ROOT).as_posix(),
        "schema_path": SCHEMA_PATH.relative_to(PLUGIN_ROOT).as_posix(),
        "commands": list(COMMANDS),
        "route_count": len(catalog.get("routes", [])) if catalog else 0,
        "errors": errors,
    }


def impacted_packet(
    range_spec: str | None,
    *,
    changed_file: list[str] | None = None,
    staged: bool = False,
) -> dict[str, Any]:
    """Build the impacted-test packet for a git range."""
    errors: list[str] = []
    catalog = load_json(CATALOG_PATH)
    try:
        changed_files = [normalize_path(path) for path in changed_file or []]
        if staged or range_spec:
            changed_files.extend(changed_files_from_git(range_spec, staged=staged))
        changed_files = sorted(set(changed_files))
    except RuntimeError as exc:
        return {
            "schema": "bears-pants-test-graph-impact.v1",
            "status": "fail",
            "from_git": "<staged>" if staged else str(range_spec or "<explicit>"),
            "changed_files": [],
            "matched": [],
            "unmatched": [],
            "selector_confidence": "low",
            "requires_full_suite": True,
            "tests": [],
            "pants_targets": [],
            "gates": [],
            "authority": {
                "selector_confidence": "low",
                "requires_full_suite": True,
                "tests": [],
                "matched": [],
                "unmatched": [],
            },
            "comparison": {
                "shared_tests": [],
                "graph_only_tests": [],
                "authority_only_tests": [],
            },
            "errors": [str(exc)],
        }
    graph = route_selection(catalog, changed_files)
    authority = authority_selection(changed_files)
    comparison = compare_selections(graph["tests"], authority["tests"])
    errors.extend(validate_catalog(catalog))
    errors.extend([f"unmatched path: {path}" for path in graph["unmatched"]])
    return {
        "schema": "bears-pants-test-graph-impact.v1",
        "status": "pass" if not errors else "fail",
        "from_git": "<staged>" if staged else str(range_spec or "<explicit>"),
        "changed_files": graph["changed_files"],
        "matched": graph["matched"],
        "unmatched": graph["unmatched"],
        "selector_confidence": graph["selector_confidence"],
        "requires_full_suite": graph["requires_full_suite"],
        "tests": graph["tests"],
        "pants_targets": graph["pants_targets"],
        "gates": graph["gates"],
        "authority": authority,
        "comparison": comparison,
        "errors": errors,
    }


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    impacted = sub.add_parser("impacted")
    impacted.add_argument("--from-git")
    impacted.add_argument("--staged", action="store_true")
    impacted.add_argument("--changed-file", action="append", default=[])
    impacted.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command adapter."""
    args = build_parser().parse_args(argv)
    packet = (
        validate_packet()
        if args.command == "validate"
        else impacted_packet(args.from_git, changed_file=args.changed_file, staged=bool(args.staged))
    )
    print(json.dumps(packet, indent=2, sort_keys=True))
    return 0 if packet.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
