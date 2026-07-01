import tempfile
import unittest
from pathlib import Path

from scripts import workspace_hygiene


class WorkspaceHygieneTests(unittest.TestCase):
    def test_validate_accepts_good_and_rejects_bad_fixture(self) -> None:
        self.assertEqual(workspace_hygiene.validate_policy(workspace_hygiene.GOOD), [])
        self.assertTrue(workspace_hygiene.validate_policy(workspace_hygiene.BAD))

    def test_current_policy_validates(self) -> None:
        self.assertEqual(workspace_hygiene.validate_all(), [])

    def test_classifies_local_validation_proof(self) -> None:
        policy = workspace_hygiene.load(workspace_hygiene.POLICY)
        klass = workspace_hygiene.match_class("runtime/local-commit-validation/abc.json", policy)
        self.assertIsNotNone(klass)
        self.assertEqual(klass["lifecycle_class"], "local_validation_proof")

    def test_cleanup_refuses_tracked_durable_file(self) -> None:
        packet = workspace_hygiene.cleanup_path("scripts/workspace_hygiene.py", apply=False)
        self.assertEqual(packet["status"], "fail")
        self.assertIn("refuses tracked file", "\n".join(packet["errors"]))

    def test_cleanup_refuses_secret_path(self) -> None:
        packet = workspace_hygiene.cleanup_path("runtime/secret.env", apply=False)
        self.assertEqual(packet["status"], "fail")
        self.assertIn("unsafe cleanup path", "\n".join(packet["errors"]))

    def test_cleanup_dry_run_requires_allowed_class(self) -> None:
        runtime_root = workspace_hygiene.PLUGIN_ROOT / "runtime/plans"
        runtime_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=runtime_root) as tmpdir:
            rel = Path(tmpdir).relative_to(workspace_hygiene.PLUGIN_ROOT).as_posix()
            packet = workspace_hygiene.cleanup_path(rel, apply=False)
            self.assertEqual(packet["status"], "pass")
            self.assertFalse(packet["applied"])
            self.assertTrue(Path(tmpdir).exists())

    def test_cleanup_plan_is_dry_run_by_default(self) -> None:
        plan = workspace_hygiene.cleanup_plan()
        self.assertTrue(plan["dry_run_default"])
        self.assertEqual(plan["status"], "pass")


if __name__ == "__main__":
    unittest.main()
