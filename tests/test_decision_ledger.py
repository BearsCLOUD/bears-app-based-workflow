import json
import unittest

from scripts import decision_ledger


class DecisionLedgerTests(unittest.TestCase):
    def test_validate_ledger_accepts_good_and_rejects_bad_fixture(self) -> None:
        self.assertEqual(decision_ledger.validate_ledger(decision_ledger.GOOD), [])
        self.assertTrue(decision_ledger.validate_ledger(decision_ledger.BAD))

    def test_current_ledger_validates(self) -> None:
        self.assertEqual(decision_ledger.validate_ledger(decision_ledger.LEDGER), [])

    def test_changed_schema_requires_accepted_decision(self) -> None:
        ledger = decision_ledger.load(decision_ledger.LEDGER)
        self.assertEqual(decision_ledger.missing_required_decisions(["assets/schemas/decision-ledger.v1.schema.json"], ledger), [])
        errors = decision_ledger.missing_required_decisions(["assets/schemas/uncovered.v1.schema.json"], ledger)
        self.assertIn("missing accepted decision", "\n".join(errors))

    def test_accepted_record_blocks_unresolved_inputs_and_contradictions(self) -> None:
        record = decision_ledger.records(decision_ledger.load(decision_ledger.BAD))[0]
        errors = decision_ledger.record_errors(record, 0)
        self.assertIn("unresolved_inputs", "\n".join(errors))

    def test_decision_required_scope_is_bounded(self) -> None:
        self.assertTrue(decision_ledger.decision_required("scripts/new_validator.py"))
        self.assertTrue(decision_ledger.decision_required("hooks/pre_task_guard.py"))
        self.assertFalse(decision_ledger.decision_required("docs/reference/new.md"))
        self.assertFalse(decision_ledger.decision_required("assets/catalog/decision-ledger.v1.json"))

    def test_report_shape_is_compact_and_safe(self) -> None:
        ledger = decision_ledger.load(decision_ledger.LEDGER)
        rendered = json.dumps(ledger).lower()
        self.assertNotIn("private key", rendered)
        self.assertNotIn("credential=", rendered)
        self.assertLessEqual(
            len(decision_ledger.report_records(ledger)),
            decision_ledger.REPORT_RECORD_LIMIT,
        )


if __name__ == "__main__":
    unittest.main()
