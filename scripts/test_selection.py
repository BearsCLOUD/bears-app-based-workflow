#!/usr/bin/env python3
"""Select fast, slow, impacted, and manual emergency unittest commands."""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = PLUGIN_ROOT / "assets/catalog/test-selection.v1.json"
SCHEMA_PATH = PLUGIN_ROOT / "assets/schemas/test-selection.v1.schema.json"

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from scripts.local_json_schema import validate_json_schema


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def all_test_files() -> list[str]:
    return sorted(path.relative_to(PLUGIN_ROOT).as_posix() for path in (PLUGIN_ROOT / "tests").glob("test_*.py"))


def normalize_path(path: str) -> str:
    normalized = path.strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def matches(path: str, pattern: str) -> bool:
    return fnmatch.fnmatchcase(path, pattern) or fnmatch.fnmatchcase(path, pattern.rstrip("/**") + "/**")


def changed_files_from_git(range_spec: str) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", range_spec],
        cwd=PLUGIN_ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git diff failed for {range_spec}")
    return [normalize_path(line) for line in result.stdout.splitlines() if line.strip()]


def validate_catalog(catalog: dict[str, Any]) -> list[str]:
    errors = validate_json_schema(catalog, SCHEMA_PATH, "test-selection")
    tests = set(all_test_files())
    slow = set(catalog.get("slow_tests", []))
    always_fast = set(catalog.get("always_fast_tests", []))
    for rel_path in sorted(slow | always_fast):
        if rel_path not in tests:
            errors.append(f"test-selection.{rel_path} must reference an existing test file")
    if slow & always_fast:
        errors.append("test-selection.slow_tests and always_fast_tests must not overlap")
    seen_names: set[str] = set()
    for index, mapping in enumerate(catalog.get("mappings", [])):
        if not isinstance(mapping, dict):
            continue
        name = mapping.get("name")
        if isinstance(name, str):
            if name in seen_names:
                errors.append(f"test-selection.mappings[{index}].name must be unique")
            seen_names.add(name)
        for field_name in ("tests", "fast_required_tests"):
            for test_path in mapping.get(field_name, []):
                if test_path == "<changed-test-file>":
                    continue
                if test_path not in tests:
                    errors.append(f"test-selection.mappings[{index}].{field_name} references missing {test_path}")
    return errors


def impacted_tests(catalog: dict[str, Any], changed_files: list[str]) -> dict[str, Any]:
    tests: set[str] = set(catalog.get("always_fast_tests", []))
    fast_required_tests: set[str] = set(catalog.get("always_fast_tests", []))
    matched: list[str] = []
    unmatched: list[str] = []
    all_tests = set(all_test_files())
    for raw_path in changed_files:
        path = normalize_path(raw_path)
        path_matched = False
        for mapping in catalog.get("mappings", []):
            if any(matches(path, pattern) for pattern in mapping.get("patterns", [])):
                path_matched = True
                matched.append(f"{path}:{mapping.get('name')}")
                for test_path in mapping.get("tests", []):
                    tests.add(path if test_path == "<changed-test-file>" and path in all_tests else test_path)
                for test_path in mapping.get("fast_required_tests", []):
                    resolved = path if test_path == "<changed-test-file>" and path in all_tests else test_path
                    tests.add(resolved)
                    fast_required_tests.add(resolved)
        script_guess = path.replace("scripts/", "tests/test_") if path.startswith("scripts/") else ""
        if script_guess.endswith(".py") and script_guess in all_tests:
            path_matched = True
            matched.append(f"{path}:script-name-fallback")
            tests.add(script_guess)
        if not path_matched:
            unmatched.append(path)
    confidence = "high" if not unmatched else "low"
    if unmatched:
        tests = set(all_test_files())
    return {
        "selector_confidence": confidence,
        "changed_files": changed_files,
        "matched": sorted(set(matched)),
        "unmatched": sorted(set(unmatched)),
        "requires_full_suite": bool(unmatched),
        "fast_required_tests": sorted(fast_required_tests),
        "tests": sorted(tests),
    }


def filter_tier(catalog: dict[str, Any], tests: list[str], tier: str, fast_required_tests: list[str] | None = None) -> list[str]:
    slow = set(catalog.get("slow_tests", []))
    required = set(fast_required_tests or [])
    if tier == "full":
        return sorted(tests)
    if tier == "slow":
        return sorted(test for test in tests if test in slow)
    return sorted(test for test in tests if test not in slow or test in required)


def shard_tests(tests: list[str], shard_index: int | None, shard_total: int | None) -> list[str]:
    if shard_index is None and shard_total is None:
        return tests
    if shard_index is None or shard_total is None or shard_total < 1 or shard_index < 0 or shard_index >= shard_total:
        raise ValueError("shard-index must be in [0, shard-total)")
    return [test for index, test in enumerate(tests) if index % shard_total == shard_index]


def selected_tests(args: argparse.Namespace, catalog: dict[str, Any]) -> dict[str, Any]:
    if args.suite:
        base_tests = all_test_files()
        selection = {
            "selector_confidence": "high",
            "changed_files": [],
            "matched": [],
            "unmatched": [],
            "requires_full_suite": False,
            "fast_required_tests": [],
            "tests": base_tests,
        }
    else:
        changed = [normalize_path(path) for path in args.changed_file]
        if args.from_git:
            changed.extend(changed_files_from_git(args.from_git))
        selection = impacted_tests(catalog, sorted(set(changed)))
        base_tests = selection["tests"]
    tier = args.tier or args.suite or "fast"
    selection["tier"] = tier
    selection["tests"] = shard_tests(
        filter_tier(catalog, base_tests, tier, selection.get("fast_required_tests", [])),
        args.shard_index,
        args.shard_total,
    )
    selection["slow_tests_deferred"] = sorted(set(base_tests) - set(selection["tests"])) if tier == "fast" else []
    selection["full_suite_advisory_only"] = bool(selection.get("requires_full_suite")) and tier != "full"
    return selection


def print_selection(selection: dict[str, Any], output_format: str) -> None:
    if output_format == "json":
        print(json.dumps(selection, indent=2, sort_keys=True))
    elif output_format == "shell":
        print(" ".join(selection["tests"]))
    else:
        for test_path in selection["tests"]:
            print(test_path)


def run_tests(selection: dict[str, Any], *, dry_run: bool, allow_low_confidence: bool = False) -> int:
    if selection.get("selector_confidence") == "low" and not allow_low_confidence:
        print(
            "test-selection refused low-confidence impacted run; update "
            "assets/catalog/test-selection.v1.json or rerun manually with --allow-low-confidence",
            file=sys.stderr,
        )
        if selection.get("unmatched"):
            print("unmatched paths: " + ", ".join(selection["unmatched"]), file=sys.stderr)
        return 2
    command = [sys.executable, "-m", "unittest", *selection["tests"]]
    print(" ".join(command))
    if dry_run:
        return 0
    if not selection["tests"]:
        return 0
    return subprocess.run(command, cwd=PLUGIN_ROOT, check=False).returncode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("--json", action="store_true")
    for name in ("list", "run"):
        item = subparsers.add_parser(name)
        item.add_argument("--changed-file", action="append", default=[])
        item.add_argument("--from-git")
        item.add_argument("--suite", choices=("fast", "slow", "full"))
        item.add_argument("--tier", choices=("fast", "slow", "full"))
        item.add_argument("--shard-index", type=int)
        item.add_argument("--shard-total", type=int)
        item.add_argument("--format", choices=("lines", "shell", "json"), default="lines")
        if name == "run":
            item.add_argument("--dry-run", action="store_true")
            item.add_argument("--allow-low-confidence", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    catalog = load_json(CATALOG_PATH)
    errors = validate_catalog(catalog)
    if args.command == "validate":
        packet = {"ok": not errors, "errors": errors}
        if args.json:
            print(json.dumps(packet, indent=2, sort_keys=True))
        elif errors:
            print("\n".join(errors), file=sys.stderr)
        else:
            print("test selection ok")
        return 0 if not errors else 1
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    try:
        selection = selected_tests(args, catalog)
    except (RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if args.command == "list":
        print_selection(selection, args.format)
        return 0
    if args.format != "lines":
        print_selection(selection, args.format)
    return run_tests(selection, dry_run=args.dry_run, allow_low_confidence=args.allow_low_confidence)


if __name__ == "__main__":
    raise SystemExit(main())
