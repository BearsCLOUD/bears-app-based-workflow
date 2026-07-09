import copy
import json
import unittest

from scripts import enterprise_issue_release


class EnterpriseIssueReleaseTests(unittest.TestCase):
    def test_release_manifest_uses_canonical_delivery_identity(self) -> None:
        self.assertEqual(enterprise_issue_release.validate_manifest(), [])
        packet = json.loads(enterprise_issue_release.MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(packet["release_id"], enterprise_issue_release.canonical_delivery_id())
        self.assertEqual(packet["delivery_id"], enterprise_issue_release.canonical_delivery_id())
        self.assertEqual(packet["dependency_policy"]["max_active"], 1)
        self.assertFalse(packet["service_policy"]["auto_install"])

    def test_mismatched_release_id_fails(self) -> None:
        packet = json.loads(enterprise_issue_release.MANIFEST.read_text(encoding="utf-8"))
        bad = copy.deepcopy(packet)
        bad["release_id"] = "issue-394-local-name"
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "release.json"
            path.write_text(json.dumps(bad), encoding="utf-8")
            errors = enterprise_issue_release.validate_manifest(path)
        self.assertIn("release_id must equal canonical", "\n".join(errors))


if __name__ == "__main__":
    unittest.main()
