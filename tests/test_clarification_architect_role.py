from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

from scripts.local_json_schema import validate_json_schema

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/clarification_architect"
QUESTION_SCHEMA = ROOT / "assets/schemas/clarification-question.v1.schema.json"
BATCH_SCHEMA = ROOT / "assets/schemas/clarification-question-batch.v1.schema.json"
ROLE_RESULT_SCHEMA = ROOT / "assets/schemas/clarification-role-result.v1.schema.json"
METHODOLOGY = ROOT / "assets/catalog/clarification-question-methodology.v1.json"
ROLE_PROFILE = ROOT / "assets/catalog/role-profiles/clarification-architect.v1.json"
PROMPT = ROOT / "prompts/roles/clarification-architect.md"
DOC = ROOT / "docs/reference/clarification-architect.md"

BANNED_KEYS = {
    "implementation_steps",
    "planning_steps",
    "next_steps",
    "tasks",
    "instructions",
    "patch_plan",
}
BANNED_PHRASES = (
    "implement the",
    "edit the file",
    "apply a patch",
    "run the tests",
    "create the file",
    "planning step",
)
PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def walk(value: Any) -> list[Any]:
    found = [value]
    if isinstance(value, dict):
        for item in value.values():
            found.extend(walk(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(walk(item))
    return found


def semantic_errors(packet: dict[str, Any], label: str) -> list[str]:
    errors: list[str] = []
    schema_name = packet.get("schema")
    if schema_name == "bears-clarification-role-result.v1":
        errors.extend(validate_json_schema(packet, ROLE_RESULT_SCHEMA, label))
        questions = packet.get("questions", [])
        if questions and packet.get("no_questions_reason") is not None:
            errors.append(f"{label}.no_questions_reason: must be null when questions are emitted")
        if not questions and not packet.get("no_questions_reason"):
            errors.append(f"{label}.no_questions_reason: is required when no questions are emitted")
    elif schema_name == "bears-clarification-question-batch.v1":
        errors.extend(validate_json_schema(packet, BATCH_SCHEMA, label))
        questions = packet.get("questions", [])
    elif schema_name == "bears-clarification-question.v1":
        questions = [packet]
    else:
        errors.append(f"{label}.schema: unsupported schema {schema_name!r}")
        questions = []

    fingerprints: set[str] = set()
    priorities: list[int] = []
    for index, question in enumerate(questions):
        qlabel = f"{label}.questions[{index}]"
        errors.extend(validate_json_schema(question, QUESTION_SCHEMA, qlabel))
        fingerprint = question.get("question_fingerprint")
        if fingerprint in fingerprints:
            errors.append(f"{qlabel}.question_fingerprint: duplicate active fingerprint")
        if isinstance(fingerprint, str):
            fingerprints.add(fingerprint)
        if question.get("answer_type") == "freeform_bounded":
            limit = question.get("answer_shape", {}).get("byte_limit")
            if not isinstance(limit, int) or limit > 1024:
                errors.append(f"{qlabel}.answer_shape.byte_limit: must be an integer <= 1024")
        text = str(question.get("question_text", "")).lower()
        if any(marker in text for marker in ("expand scope", "add another repo", "outside the goal")):
            if question.get("scope_change_request") is not True:
                errors.append(f"{qlabel}.scope_change_request: required for scope-changing question")
        priority = question.get("priority")
        if priority in PRIORITY_RANK:
            priorities.append(PRIORITY_RANK[priority])
    if priorities != sorted(priorities):
        errors.append(f"{label}.questions: priorities must be sorted P0, P1, P2")

    for node in walk(packet):
        if isinstance(node, dict):
            for key in node:
                if key in BANNED_KEYS:
                    errors.append(f"{label}.{key}: planning or implementation field is forbidden")
        elif isinstance(node, str):
            lowered = node.lower()
            for phrase in BANNED_PHRASES:
                if phrase in lowered:
                    errors.append(f"{label}: planning or implementation instruction is forbidden")
                    break
    return errors


class ClarificationArchitectRoleTests(unittest.TestCase):
    def test_schema_and_catalog_files_parse(self) -> None:
        for path in [QUESTION_SCHEMA, BATCH_SCHEMA, ROLE_RESULT_SCHEMA, METHODOLOGY, ROLE_PROFILE]:
            self.assertIsInstance(load_json(path), dict, path)

    def test_good_fixtures_validate(self) -> None:
        for path in sorted((FIXTURES / "good").glob("*.json")):
            with self.subTest(path=path.name):
                self.assertEqual([], semantic_errors(load_json(path), path.name))

    def test_bad_fixtures_fail_closed(self) -> None:
        for path in sorted((FIXTURES / "bad").glob("*.json")):
            with self.subTest(path=path.name):
                self.assertNotEqual([], semantic_errors(load_json(path), path.name))

    def test_prompt_requires_schema_and_forbids_implementation(self) -> None:
        prompt = PROMPT.read_text(encoding="utf-8")
        self.assertIn("assets/schemas/clarification-role-result.v1.schema.json", prompt)
        self.assertIn("Return one JSON object only", prompt)
        self.assertIn("Do not output", prompt)
        self.assertIn("implementation steps", prompt)

    def test_reference_documents_exec_boundary(self) -> None:
        doc = DOC.read_text(encoding="utf-8")
        self.assertIn("codex exec --sandbox read-only --output-schema assets/schemas/clarification-role-result.v1.schema.json -", doc)
        self.assertIn("before planning or implementation starts", doc)


if __name__ == "__main__":
    unittest.main()
