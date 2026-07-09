#!/usr/bin/env python3
"""Validate and report the Bears Temporal evaluation packet."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = PLUGIN_ROOT / "assets" / "catalog" / "temporal-evaluation.v1.json"
DOC_PATH = PLUGIN_ROOT / "docs" / "research" / "temporal-evaluation.md"
EXPECTED_SCHEMA = "bears-temporal-evaluation.v1"
EXPECTED_COMMANDS = [
    "python3 scripts/temporal_evaluation.py validate",
    "python3 scripts/temporal_evaluation.py report --json",
]
EXPECTED_DECISIONS = {"not_adopted", "candidate", "adopt"}
EXPECTED_OPTIONS = {
    "local_worker_state_file_model",
    "dagger_wrapper",
    "simple_queue_lease",
    "temporal",
}
EXPECTED_PRECONDITION_IDS = {
    "closeout_and_policy_gates_executable",
    "durable_gap_proven",
    "operational_owner_assigned",
    "worker_recovery_requirements_defined",
}


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON object from `path`."""

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} root must be an object")
    return data


def validate_doc(path: Path = DOC_PATH) -> list[str]:
    """Validate the research note content."""

    if not path.is_file():
        return [f"doc not found: {path}"]
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    for phrase in (
        "Temporal is not needed",
        "local worker/state-file model",
        "Dagger wrapper",
        "simple queue/lease",
    ):
        if phrase not in text:
            errors.append(f"doc missing phrase: {phrase}")
    for command in EXPECTED_COMMANDS:
        if command not in text:
            errors.append(f"doc missing command: {command}")
    for heading in ("## Comparison", "## Adoption preconditions"):
        if heading not in text:
            errors.append(f"doc missing heading: {heading}")
    return errors


def validate_catalog(catalog: dict[str, Any]) -> list[str]:
    """Validate the canonical Temporal evaluation packet."""

    errors: list[str] = []
    if catalog.get("schema") != EXPECTED_SCHEMA:
        errors.append(f"schema must be {EXPECTED_SCHEMA}")
    if str(catalog.get("version")) != "1":
        errors.append("version must be 1")
    if catalog.get("owner_plugin") != "bears":
        errors.append("owner_plugin must be bears")
    if catalog.get("decision") not in EXPECTED_DECISIONS:
        errors.append("decision must be not_adopted, candidate, or adopt")
    if catalog.get("need_for_worker_runtime") != "not_required_now":
        errors.append("need_for_worker_runtime must be not_required_now")
    commands = catalog.get("commands", [])
    if commands != EXPECTED_COMMANDS:
        errors.append("commands must match the required command surface")

    closeout_policy = catalog.get("closeout_policy", {})
    if not isinstance(closeout_policy, dict):
        errors.append("closeout_policy must be an object")
    else:
        for field in (
            "temporal_dependency_allowed",
            "service_execution_allowed",
            "worker_process_execution_allowed",
            "production_execution_allowed",
        ):
            if closeout_policy.get(field) is not False:
                errors.append(f"closeout_policy.{field} must be false")

    comparison = catalog.get("comparison", [])
    if not isinstance(comparison, list):
        errors.append("comparison must be a list")
    else:
        options = {item.get("option") for item in comparison if isinstance(item, dict)}
        if options != EXPECTED_OPTIONS:
            errors.append(
                "comparison must cover local_worker_state_file_model, "
                "dagger_wrapper, simple_queue_lease, and temporal"
            )

    preconditions = catalog.get("adoption_preconditions", [])
    if not isinstance(preconditions, list) or not preconditions:
        errors.append("adoption_preconditions must be a non-empty list")
    else:
        seen_ids = {item.get("id") for item in preconditions if isinstance(item, dict)}
        if seen_ids != EXPECTED_PRECONDITION_IDS:
            errors.append("adoption_preconditions must cover the required adoption gates")
        for index, item in enumerate(preconditions):
            if not isinstance(item, dict):
                errors.append(f"adoption_preconditions[{index}] must be an object")
                continue
            if not str(item.get("description") or "").strip():
                errors.append(f"adoption_preconditions[{index}].description must be non-empty")

    adoption_gate = catalog.get("adoption_gate", {})
    if not isinstance(adoption_gate, dict):
        errors.append("adoption_gate must be an object")
    else:
        if adoption_gate.get("adopt_requires_preconditions") is not True:
            errors.append("adoption_gate.adopt_requires_preconditions must be true")
        if catalog.get("decision") == "adopt":
            if adoption_gate.get("adopt_allowed") is not True:
                errors.append("adoption_gate.adopt_allowed must be true for adopt")
            if adoption_gate.get("preconditions_met") is not True:
                errors.append("adopt requires preconditions to pass")
        else:
            if adoption_gate.get("adopt_allowed") is not False:
                errors.append("adoption_gate.adopt_allowed must be false until adoption")
            if adoption_gate.get("preconditions_met") is not False:
                errors.append("adoption_gate.preconditions_met must be false")

    return errors


def validate_all() -> list[str]:
    """Validate the catalog and the research note together."""

    errors = validate_catalog(load_json(CATALOG_PATH))
    errors.extend(validate_doc())
    return errors


def report_packet() -> dict[str, Any]:
    """Build the JSON report packet."""

    catalog = load_json(CATALOG_PATH)
    errors = validate_all()
    return {
        "schema": "bears-temporal-evaluation-report.v1",
        "status": "pass" if not errors else "fail",
        "decision": catalog["decision"],
        "need_for_worker_runtime": catalog["need_for_worker_runtime"],
        "comparison": catalog["comparison"],
        "adoption_preconditions": catalog["adoption_preconditions"],
        "adoption_gate": catalog["adoption_gate"],
        "closeout_policy": catalog["closeout_policy"],
        "commands": catalog["commands"],
        "errors": errors,
    }


def command_validate(_args: argparse.Namespace) -> int:
    """Run validation and print a compact result packet."""

    errors = validate_all()
    print(
        json.dumps(
            {
                "schema": "bears-temporal-evaluation-validation.v1",
                "status": "pass" if not errors else "fail",
                "decision": load_json(CATALOG_PATH)["decision"],
                "errors": errors,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if not errors else 1


def command_report(_args: argparse.Namespace) -> int:
    """Print the evaluation report packet."""

    packet = report_packet()
    print(json.dumps(packet, indent=2, sort_keys=True))
    return 0 if packet["status"] == "pass" else 1


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.set_defaults(func=command_validate)
    report = sub.add_parser("report")
    report.add_argument("--json", action="store_true")
    report.set_defaults(func=command_report)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the selected CLI command."""

    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
