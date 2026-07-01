from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import bears_goals, bears_principles


class BearsGoalsPrinciplesTest(unittest.TestCase):
    def test_catalogs_validate(self) -> None:
        self.assertEqual(bears_goals.validate_catalog(), [])
        self.assertEqual(bears_principles.validate_catalog(), [])

    def test_required_active_principles_are_present(self) -> None:
        active = bears_principles.active_principle_ids()
        self.assertLessEqual(bears_principles.REQUIRED_ACTIVE, active)

    def test_decision_requires_active_principle_and_goal(self) -> None:
        packet = {
            "schema": "bears-principle-decision.v1",
            "decision_id": "issue-415-contract",
            "issue": "#415",
            "decision": "Add validatable Bears goals and principles catalogs.",
            "principles_applied": ["machine_contracts_over_prose", "no_silent_role_omission"],
            "goals_supported": ["kernel_decisions_are_explicit"],
            "alternatives_rejected": ["Implicit chat preference without machine-checkable references."],
            "reason_code": "issue-415-machine-contract",
            "evidence_paths": ["assets/catalog/bears-principles.v1.json"],
        }
        self.assertEqual(bears_principles.decision_errors(packet), [])

    def test_decision_missing_principle_fails(self) -> None:
        packet = {
            "schema": "bears-principle-decision.v1",
            "decision_id": "issue-415-missing-principle",
            "issue": "#415",
            "decision": "Material workflow decision without a principle reference.",
            "principles_applied": [],
            "goals_supported": ["kernel_decisions_are_explicit"],
            "alternatives_rejected": [],
            "reason_code": "missing-principle",
            "evidence_paths": ["assets/catalog/bears-goals.v1.json"],
        }
        errors = bears_principles.decision_errors(packet)
        self.assertTrue(any("principles_applied" in error for error in errors))

    def test_principle_exception_requires_reason(self) -> None:
        catalog = bears_principles.load()
        catalog["principles"] = [dict(catalog["principles"][0])]
        catalog["principles"][0]["exceptions"] = [{"reason_code": "", "rationale": "", "evidence_paths": []}]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "principles.json"
            path.write_text(json.dumps(catalog), encoding="utf-8")
            errors = bears_principles.validate_catalog(path)
        self.assertTrue(any("explicit reason required" in error for error in errors))

    def test_doctor_reports_counts(self) -> None:
        packet = bears_principles.doctor_packet()
        self.assertEqual(packet["status"], "pass")
        self.assertGreaterEqual(packet["active_goal_count"], 1)
        self.assertEqual(packet["active_principle_count"], len(bears_principles.REQUIRED_ACTIVE))


if __name__ == "__main__":
    unittest.main()
