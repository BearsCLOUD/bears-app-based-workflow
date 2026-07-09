from __future__ import annotations
import json, subprocess, sys, unittest
from pathlib import Path
from scripts import workflow_state_machine

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/workflow_state_machine"

class WorkflowStateMachineTest(unittest.TestCase):
    def test_catalog_validates(self) -> None:
        self.assertEqual([], workflow_state_machine.validate_all())

    def test_invalid_transition_fails(self) -> None:
        result = workflow_state_machine.can_transition(json.loads((FIXTURES / "bad/invalid-transition.json").read_text()))
        self.assertEqual("blocked", result["status"])
        self.assertTrue(any("not allowed" in item for item in result["errors"]))

    def test_missing_evidence_fails_transition(self) -> None:
        result = workflow_state_machine.can_transition(json.loads((FIXTURES / "bad/missing-evidence.json").read_text()))
        self.assertEqual("blocked", result["status"])
        self.assertTrue(any("missing" in item for item in result["errors"]))

    def test_invariant_violation_blocks_execution(self) -> None:
        packet = json.loads((FIXTURES / "bad/missing-evidence.json").read_text())
        result = workflow_state_machine.check_invariants("goal-438", packet)
        self.assertEqual("blocked", result["status"])
        self.assertTrue(result["errors"])

    def test_degradation_forces_manual_review(self) -> None:
        result = workflow_state_machine.can_transition(json.loads((FIXTURES / "good/degradation-manual-review.json").read_text()))
        self.assertEqual("pass", result["status"])
        bad = workflow_state_machine.can_transition(json.loads((FIXTURES / "bad/degradation-to-running.json").read_text()))
        self.assertEqual("blocked", bad["status"])

    def test_doctor_reports_state_machine_consistency(self) -> None:
        result = workflow_state_machine.doctor()
        self.assertEqual("pass", result["state_machine_consistency"])

    def test_cli_apply_json(self) -> None:
        completed = subprocess.run([sys.executable, "scripts/workflow_state_machine.py", "apply", "--packet", str(FIXTURES / "good/run-transition.json"), "--json"], cwd=ROOT, text=True, stdout=subprocess.PIPE, check=False)
        self.assertEqual(0, completed.returncode)
        self.assertEqual("running", json.loads(completed.stdout)["state"])

if __name__ == "__main__":
    unittest.main()
