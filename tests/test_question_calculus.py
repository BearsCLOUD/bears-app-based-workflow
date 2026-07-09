from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import decision_graph, question_calculus

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/question_calculus"


class QuestionCalculusTest(unittest.TestCase):
    def test_catalog_validates(self) -> None:
        self.assertEqual([], question_calculus.validate_all())

    def test_invalid_answer_type_fails(self) -> None:
        packet = json.loads((FIXTURES / "bad/invalid-answer.json").read_text())
        result = question_calculus.prove_answer(packet)
        self.assertEqual("blocked", result["status"])
        self.assertTrue(any("answer" in item for item in result["errors"]))

    def test_gate_cannot_unlock_without_accepted_proof(self) -> None:
        packet = json.loads((FIXTURES / "bad/candidate-unlocks.json").read_text())
        result = question_calculus.prove_answer(packet)
        self.assertEqual("blocked", result["status"])
        self.assertEqual([], result["unlocked_gates"])

    def test_ambiguous_executor_answer_routes_manual_review(self) -> None:
        result = question_calculus.ask("select_executor", {"executor_candidates": ["codex", "opencode"]})
        self.assertEqual("manual_review", result["answer"])
        self.assertEqual("manual_review", result["answer_type"])
        self.assertIn("execution_allowed", result["blocked_gates"])

    def test_missing_decision_graph_blocks_goal_execution(self) -> None:
        result = decision_graph.check_gate("missing", "execution_allowed", graph_path=None)
        self.assertEqual("blocked", result["status"])
        self.assertFalse(result["unlocked"])

    def test_decision_graph_references_accepted_formal_semantic_fact(self) -> None:
        graph = decision_graph.build_graph("goal-437")
        self.assertIn("fact-435-implements-formal-semantics-kernel", graph["semantic_fact_refs"])
        self.assertEqual([], decision_graph.validate_graph(graph))

    def test_doctor_reports_decision_graph_coverage(self) -> None:
        result = decision_graph.doctor()
        self.assertEqual("pass", result["decision_graph_coverage"])

    def test_cli_build_and_check_gate_json(self) -> None:
        build = subprocess.run(
            [sys.executable, "scripts/decision_graph.py", "build", "--goal-id", "goal-437", "--json"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(0, build.returncode)
        graph = json.loads(build.stdout)
        self.assertEqual("pass", graph["status"])
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(graph, handle)
            graph_path = handle.name
        gate = subprocess.run(
            [sys.executable, "scripts/decision_graph.py", "check-gate", "--goal-id", "goal-437", "--gate", "source_of_truth_resolved", "--graph", graph_path, "--json"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(0, gate.returncode)
        self.assertEqual("pass", json.loads(gate.stdout)["status"])


if __name__ == "__main__":
    unittest.main()
