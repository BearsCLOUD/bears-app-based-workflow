from __future__ import annotations
import json, subprocess, sys, unittest
from pathlib import Path
from scripts import workflow_inference

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/workflow_inference"

class WorkflowInferenceTest(unittest.TestCase):
    def test_catalog_validates(self) -> None:
        self.assertEqual([], workflow_inference.validate_all())

    def test_accepted_facts_derive_can_write(self) -> None:
        packet = workflow_inference.materialize(FIXTURES / "good/accepted-can-write.json")
        self.assertEqual("pass", packet["status"])
        self.assertTrue(any(f["predicate"] == "can_write" and f["arguments"] == ["fixture-role", "fixture-file.py"] for f in packet["facts"]))

    def test_candidate_facts_cannot_derive_can_write(self) -> None:
        packet = workflow_inference.materialize(FIXTURES / "bad/candidate-can-write.json")
        self.assertFalse(any(f["predicate"] == "can_write" and f["arguments"] == ["candidate-role", "candidate-file.py"] for f in packet["facts"]))
        self.assertTrue(any(f["predicate"] in {"research_required", "planning_required", "manual_review_required"} for f in packet["facts"]))

    def test_explanation_returns_proof_trace(self) -> None:
        result = workflow_inference.explain("derived-can_write-bears-machine-first-execution-kernel-engineer-scripts_workflow_inference.py")
        self.assertEqual("pass", result["status"])
        self.assertIn("fact-438-role-owns-file", result["proof_trace"])

    def test_closed_world_negation_requires_declaration(self) -> None:
        bad = json.loads((FIXTURES / "bad/undeclared-negation.json").read_text())
        errors = workflow_inference.validate_catalog_packet({"rules": bad["rules"], "closed_world_predicates": []})
        self.assertTrue(any("closed-world predicate is not declared" in item for item in errors))

    def test_doctor_reports_inference_freshness(self) -> None:
        result = workflow_inference.doctor()
        self.assertEqual("pass", result["inference_freshness"])
        self.assertEqual([], result["rule_errors"])

    def test_cli_query_json(self) -> None:
        completed = subprocess.run([
            sys.executable, "scripts/workflow_inference.py", "query", "--predicate", "can_write", "--args", '["bears-machine-first-execution-kernel-engineer","scripts/workflow_inference.py"]', "--json"
        ], cwd=ROOT, text=True, stdout=subprocess.PIPE, check=False)
        self.assertEqual(0, completed.returncode)
        self.assertEqual("pass", json.loads(completed.stdout)["status"])

if __name__ == "__main__":
    unittest.main()
