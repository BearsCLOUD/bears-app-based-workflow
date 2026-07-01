#!/usr/bin/env python3
"""Phase 1 wrapper for the legacy Bears plugin constitution validator."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
LEGACY_SCRIPT = PLUGIN_ROOT / "scripts/plugin_constitution.py"
DEFAULT_CATALOG = PLUGIN_ROOT / "assets/catalog/plugin-constitution.v1.json"
LEGACY_AUTHORITY = "python3 scripts/plugin_constitution.py validate"
CAPABILITY_COMMAND = "python3 capabilities/plugin_constitution/scripts/validate.py --json"
RESULT_SCHEMA = "bears-plugin-constitution-capability-validation.v1"
RESTRICTED_DATA_STATUS = "clean"
RESTRICTED_DATA_MARKERS = (
    "SYNTHETIC_RESTRICTED_DATA_MARKER_P1_09",
)
FIXTURES_ROOT = PLUGIN_ROOT / "capabilities/plugin_constitution/fixtures"


def load_legacy_module() -> Any:
    spec = importlib.util.spec_from_file_location("bears_plugin_constitution_legacy", LEGACY_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("legacy plugin constitution validator is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[arg-type]
    return module


def result_packet(
    *,
    status: str,
    catalog: Path,
    errors: list[str],
    fixture_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "schema": RESULT_SCHEMA,
        "status": status,
        "phase": "phase_1_dual",
        "authority": "legacy",
        "legacy_authoritative_command": LEGACY_AUTHORITY,
        "capability_command": CAPABILITY_COMMAND,
        "plugin_root": str(PLUGIN_ROOT),
        "catalog_path": str(catalog.resolve()),
        "restricted_data_status": RESTRICTED_DATA_STATUS,
        "errors": errors,
        "fixture_results": fixture_results or [],
    }


def _iter_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        found: list[str] = []
        for item in value:
            found.extend(_iter_strings(item))
        return found
    if isinstance(value, dict):
        found = []
        for key, item in value.items():
            found.extend(_iter_strings(key))
            found.extend(_iter_strings(item))
        return found
    return []


def restricted_data_errors(data: dict[str, Any], source: Path) -> list[str]:
    marker_hits = 0
    for text in _iter_strings(data):
        if any(marker in text for marker in RESTRICTED_DATA_MARKERS):
            marker_hits += 1
    if marker_hits == 0:
        return []
    return [f"restricted-data marker rejected in {source.name}: synthetic marker count={marker_hits}"]


def _rejection_codes(errors: list[str]) -> list[str]:
    codes = []
    if any(error.startswith("restricted-data marker rejected") for error in errors):
        codes.append("restricted_data_marker")
    if any(not error.startswith("restricted-data marker rejected") for error in errors):
        codes.append("legacy_validation")
    return codes


def _validate_catalog(catalog: Path, *, check_files: bool) -> tuple[str, list[str], list[str]]:
    module = load_legacy_module()
    data = module.load_json(catalog)
    errors = module.validate_catalog(data, check_files=check_files)
    errors = list(errors) + restricted_data_errors(data, catalog)
    return "pass" if not errors else "fail", errors, _rejection_codes(errors)


def _fixture_result(path: Path, expected_status: str) -> dict[str, Any]:
    try:
        actual_status, errors, rejection_codes = _validate_catalog(path, check_files=False)
    except Exception:
        actual_status = "fail"
        errors = ["fixture validation failed before normalized inspection"]
        rejection_codes = ["validator_exception"]
    return {
        "fixture": str(path.relative_to(PLUGIN_ROOT)),
        "expected_status": expected_status,
        "actual_status": actual_status,
        "rejection_codes": rejection_codes,
        "restricted_data_status": RESTRICTED_DATA_STATUS,
        "sanitized": True,
        "error_count": len(errors),
    }


def validate_fixtures() -> tuple[list[dict[str, Any]], list[str]]:
    fixture_results: list[dict[str, Any]] = []
    unexpected: list[str] = []
    for expected_status, directory in (("pass", "pass"), ("fail", "fail")):
        for path in sorted((FIXTURES_ROOT / directory).glob("*.json")):
            result = _fixture_result(path, expected_status)
            fixture_results.append(result)
            if result["actual_status"] != expected_status:
                unexpected.append(f"{result['fixture']} expected {expected_status} got {result['actual_status']}")
    restricted_failures = [
        result
        for result in fixture_results
        if result["expected_status"] == "fail" and "restricted_data_marker" in result["rejection_codes"]
    ]
    if not restricted_failures:
        unexpected.append("fail fixtures must include one restricted-data marker rejection")
    return fixture_results, unexpected


def run_validation(catalog: Path, *, check_files: bool) -> dict[str, Any]:
    status, errors, _rejection_codes_for_catalog = _validate_catalog(catalog, check_files=check_files)
    fixture_results: list[dict[str, Any]] = []
    if catalog.resolve() == DEFAULT_CATALOG.resolve():
        fixture_results, fixture_errors = validate_fixtures()
        errors.extend(fixture_errors)
    return result_packet(
        status="pass" if status == "pass" and not errors else "fail",
        catalog=catalog,
        errors=errors,
        fixture_results=fixture_results,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate the plugin constitution capability wrapper")
    parser.add_argument("--json", action="store_true", help="emit deterministic JSON")
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG, help="constitution catalog path")
    parser.add_argument("--no-check-files", action="store_true", help="validate catalog content without repository file coverage")
    return parser


def emit(packet: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(packet, indent=2, sort_keys=True))
        return
    print(f"status: {packet['status']}")
    for item in packet["errors"]:
        print(f"error: {item}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    catalog = args.catalog
    try:
        packet = run_validation(catalog, check_files=not args.no_check_files)
    except Exception as exc:
        packet = result_packet(status="fail", catalog=catalog, errors=[str(exc)])
    emit(packet, json_output=args.json)
    return 0 if packet["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
