#!/usr/bin/env python3
"""Validate the Bears goal-orchestrator question bank."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CATALOG = PLUGIN_ROOT / "assets/catalog/goal-question-bank.v1.json"
SCHEMA = PLUGIN_ROOT / "assets/schemas/goal-question.v1.schema.json"
REQUIRED_CLASSES = {
    "what_is_source_of_truth",
    "what_is_smallest_verifiable_goal",
    "is_research_required",
    "is_planning_required",
    "which_executor_is_allowed",
    "which_role_is_required",
    "which_role_is_not_required_and_why",
    "which_model_tier_is_allowed",
    "which_mcp_tools_are_allowed",
    "which_files_can_be_read",
    "which_files_can_be_written",
    "what_is_validation_gate",
    "what_is_closeout_gate",
    "what_feedback_updates_roadmap",
}

if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))
from scripts.local_json_schema import validate_json_schema


def load(path: Path = CATALOG) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_all(path: Path = CATALOG) -> list[str]:
    packet = load(path)
    errors: list[str] = []
    if packet.get("schema") != "bears-goal-question-bank.v1":
        errors.append("catalog schema mismatch")
    for key in ["version", "updated", "owner_role", "questions"]:
        if key not in packet:
            errors.append(f"catalog missing {key}")
    if not isinstance(packet.get("questions"), list) or len(packet.get("questions", [])) < len(REQUIRED_CLASSES):
        errors.append("catalog must include at least the required question classes")
    seen: set[str] = set()
    classes: set[str] = set()
    for index, question in enumerate(packet.get("questions", [])):
        if not isinstance(question, dict):
            continue
        question_id = str(question.get("question_id", ""))
        if question_id in seen:
            errors.append(f"questions[{index}] duplicate question_id: {question_id}")
        seen.add(question_id)
        qclass = str(question.get("question_class") or question_id)
        classes.add(qclass)
        if question.get("answer_format") != "json_object":
            errors.append(f"questions[{index}] answer_format must be json_object")
        if question.get("blocks_when_missing") is True and not question.get("required_evidence"):
            errors.append(f"questions[{index}] blocking question requires required_evidence")
    missing = sorted(REQUIRED_CLASSES - classes)
    if missing:
        errors.append("missing required question classes: " + ", ".join(missing))
    return errors


def validate_catalog(path: Path = CATALOG) -> list[str]:
    """Validate the question-bank catalog."""
    return validate_all(path)


def print_packet(packet: dict[str, Any]) -> None:
    print(json.dumps(packet, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["validate"])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    errors = validate_all()
    packet = {"schema": "bears-goal-question-bank-validation.v1", "status": "pass" if not errors else "fail", "errors": errors}
    print_packet(packet) if args.json else print("goal_question_bank: " + packet["status"])
    return 0 if packet["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
