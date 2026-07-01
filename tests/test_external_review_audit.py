import copy
import json
import unittest

from scripts import external_review_audit


class ExternalReviewAuditTests(unittest.TestCase):
    def test_catalog_validates_with_repo_visible_summary(self) -> None:
        self.assertEqual(external_review_audit.validate_catalog(), [])

    def test_check_delivery_passes_for_issue_411_summary(self) -> None:
        packet = external_review_audit.check_delivery("issue-411-p0-reconcile-old-open-backlog-af")
        self.assertEqual(packet["status"], "pass")
        self.assertEqual(packet["issue"], 411)
        self.assertIn("validation_proof", packet["evidence_chain"])

    def test_unregistered_delivery_fails(self) -> None:
        packet = external_review_audit.check_delivery("issue-000-missing")
        self.assertEqual(packet["status"], "fail")
        self.assertIn("delivery not registered", "\n".join(packet["errors"]))

    def test_summary_forbidden_marker_fails(self) -> None:
        catalog = external_review_audit.load(external_review_audit.CATALOG)
        record = external_review_audit.delivery_record("issue-411-p0-reconcile-old-open-backlog-af", catalog)
        self.assertIsNotNone(record)
        summary = external_review_audit.load(external_review_audit.PLUGIN_ROOT / record["summary_path"])
        mutated = copy.deepcopy(summary)
        mutated["summary"] = "credential=value"
        errors = external_review_audit.validate_summary(mutated, mutated["delivery_id"], catalog)
        self.assertIn("summary contains forbidden", "\n".join(errors))

    def test_summary_missing_required_chain_fails(self) -> None:
        catalog = external_review_audit.load(external_review_audit.CATALOG)
        record = external_review_audit.delivery_record("issue-411-p0-reconcile-old-open-backlog-af", catalog)
        summary = external_review_audit.load(external_review_audit.PLUGIN_ROOT / record["summary_path"])
        mutated = json.loads(json.dumps(summary))
        mutated["evidence_chain"].pop("validation_proof")
        errors = external_review_audit.validate_summary(mutated, mutated["delivery_id"], catalog)
        self.assertIn("evidence_chain missing: validation_proof", errors)


if __name__ == "__main__":
    unittest.main()
