"""Validate the bounded Pants test graph pilot."""

from __future__ import annotations

import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts import pants_test_graph as module
from scripts import test_selection

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


class PantsTestGraphTests(unittest.TestCase):
    """Exercise the pilot graph and its command adapter."""

    def setUp(self) -> None:
        self.catalog = module.load_json(module.CATALOG_PATH)

    def test_catalog_validates_against_schema_and_existing_files(self) -> None:
        self.assertEqual(module.validate_catalog(self.catalog), [])

    def test_build_has_expected_pants_targets(self) -> None:
        build = (PLUGIN_ROOT / "BUILD").read_text(encoding="utf-8")
        self.assertIn('python_sources(\n    name="pants_scripts"', build)
        self.assertIn('python_tests(\n    name="pants_tests"', build)
        self.assertIn('files(\n    name="pants_catalog_files"', build)
        self.assertIn('files(\n    name="pants_schema_files"', build)
        self.assertIn('files(\n    name="pants_graph_files"', build)
        self.assertIn('files(\n    name="external_review_audit_files"', build)

    def test_pants_toml_pins_python_backend(self) -> None:
        pants_toml = (PLUGIN_ROOT / "pants.toml").read_text(encoding="utf-8")
        self.assertIn('pants_version = "2.32.0"', pants_toml)
        self.assertIn('backend_packages = ["pants.backend.python"]', pants_toml)
        self.assertIn('build_file_name = "BUILD"', pants_toml)

    def test_script_change_maps_to_graph_self_check(self) -> None:
        packet = module.route_selection(self.catalog, ["scripts/pants_test_graph.py"])
        self.assertEqual(packet["selector_confidence"], "high")
        self.assertIn("tests/test_pants_test_graph.py", packet["tests"])
        authority = module.authority_selection(["scripts/pants_test_graph.py"])
        self.assertIn("tests/test_pants_test_graph.py", authority["tests"])
        comparison = module.compare_selections(packet["tests"], authority["tests"])
        self.assertIn("tests/test_pants_test_graph.py", comparison["shared_tests"])

    def test_external_review_audit_artifacts_map_to_gate_tests(self) -> None:
        packet = module.route_selection(
            self.catalog,
            [
                "docs/audits/external-review-2026-06-25/README.md",
                "assets/catalog/external-review-audit.v1.json",
            ],
        )
        self.assertEqual(packet["selector_confidence"], "high")
        self.assertIn("tests/test_external_review_audit.py", packet["tests"])
        self.assertIn("tests/test_artifact_registry.py", packet["tests"])
        self.assertIn("tests/test_test_selection.py", packet["tests"])
        self.assertIn("tests/test_bears_doctor.py", packet["tests"])
        self.assertIn("external-review-audit", packet["gates"])

    def test_orchestrator_delivery_audit_artifacts_are_not_plugin_lane(self) -> None:
        packet = module.route_selection(
            self.catalog,
            [
                "docs/audits/orchestrator-deliveries/production/issue-550-delivery/delivery-manifest.v1.json",
            ],
        )
        self.assertEqual(packet["selector_confidence"], "low")
        self.assertTrue(packet["requires_full_suite"])
        self.assertNotIn("tests/test_orchestrator_issue_daemon.py", packet["tests"])
        self.assertNotIn("tests/test_goal_orchestrator.py", packet["tests"])
        self.assertNotIn("orchestrator-delivery-audit", packet["gates"])

    def test_unknown_path_requires_full_suite(self) -> None:
        packet = module.route_selection(self.catalog, ["docs/unmapped-policy.md"])
        self.assertEqual(packet["selector_confidence"], "low")
        self.assertTrue(packet["requires_full_suite"])
        self.assertIn("docs/unmapped-policy.md", packet["unmatched"])

    def test_validate_command_emits_json(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = module.main(["validate"])
        packet = json.loads(buffer.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(packet["status"], "pass")
        self.assertEqual(packet["schema"], "bears-pants-test-graph-validation.v1")

    def test_impacted_command_emits_json_for_graph_change(self) -> None:
        with patch.object(module, "changed_files_from_git", return_value=["scripts/pants_test_graph.py"]):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = module.main(["impacted", "--from-git", "HEAD~1...HEAD", "--json"])
        packet = json.loads(buffer.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(packet["status"], "pass")
        self.assertIn("tests/test_pants_test_graph.py", packet["tests"])
        self.assertEqual(packet["authority"]["selector_confidence"], "high")

    def test_impacted_command_reports_git_errors_as_json_failure(self) -> None:
        with patch.object(module, "changed_files_from_git", side_effect=RuntimeError("fatal: bad revision")):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                exit_code = module.main(["impacted", "--from-git", "missing-ref...HEAD", "--json"])
        packet = json.loads(buffer.getvalue())
        self.assertNotEqual(exit_code, 0)
        self.assertEqual(packet["status"], "fail")
        self.assertIn("fatal: bad revision", packet["errors"][0])

    def test_changed_files_from_git_reads_range(self) -> None:
        old_root = module.PLUGIN_ROOT
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
            (repo / "tracked.txt").write_text("one\n", encoding="utf-8")
            subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "one"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            (repo / "tracked.txt").write_text("two\n", encoding="utf-8")
            subprocess.run(["git", "commit", "-am", "two"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                module.PLUGIN_ROOT = repo
                self.assertEqual(module.changed_files_from_git("HEAD~1...HEAD"), ["tracked.txt"])
            finally:
                module.PLUGIN_ROOT = old_root


if __name__ == "__main__":
    unittest.main()
