import unittest

from scripts import commit_closeout


class CommitCloseoutTests(unittest.TestCase):
    def test_current_contract_validates(self) -> None:
        self.assertEqual(commit_closeout.validate_all(), [])

    def test_message_requires_issue_and_changelog_link(self) -> None:
        message = """feat(closeout): add contract

Issue: #391
Delivery-Id: bears-governance-kernel-v1
Scope: machine-first-execution-kernel
Affected-Range: HEAD^..HEAD
Evidence: runtime/local-commit-validation/<commit_sha>.json
Evidence: runtime/bears-doctor/<commit_sha>.closeout.json
Changelog: release-note-gate:#384 delivery_id:bears-governance-kernel-v1
Blockers: none
"""
        metadata = commit_closeout.parse_metadata(message)
        self.assertEqual(metadata["Issue"], ["#391"])
        self.assertEqual(metadata["Delivery-Id"], ["bears-governance-kernel-v1"])
        self.assertIn("release-note-gate:#384 delivery_id:bears-governance-kernel-v1", metadata["Changelog"])

    def test_missing_runtime_proof_is_validation_debt(self) -> None:
        summary = commit_closeout.closeout_summary("0" * 40, "HEAD^..HEAD")
        self.assertEqual(summary["delivery_id"], "<missing>")
        self.assertEqual(summary["validation_result"], "fail")
        self.assertEqual(summary["debt_status"], "local_commit_validation_missing_or_failed")


if __name__ == "__main__":
    unittest.main()
