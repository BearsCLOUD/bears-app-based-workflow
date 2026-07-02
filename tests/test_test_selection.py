"""Validate fast/slow impacted test selection and manual full-suite policy."""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PLUGIN_ROOT / "scripts" / "test_selection.py"
spec = importlib.util.spec_from_file_location("test_selection", SCRIPT_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)  # type: ignore[arg-type]


class TestSelectionPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = module.load_json(PLUGIN_ROOT / "assets/catalog/test-selection.v1.json")

    def _args(self, **overrides: object) -> argparse.Namespace:
        data = {
            "suite": None,
            "tier": "fast",
            "changed_file": [],
            "from_git": None,
            "shard_index": None,
            "shard_total": None,
        }
        data.update(overrides)
        return argparse.Namespace(**data)

    def test_catalog_validates_against_schema_and_existing_files(self) -> None:
        self.assertEqual(module.validate_catalog(self.catalog), [])


    def test_normalize_path_preserves_dot_github_directory(self) -> None:
        self.assertEqual(module.normalize_path("./.github/workflows/validate.yml"), ".github/workflows/validate.yml")

    def test_function_test_loader_change_is_mapped(self) -> None:
        selection = module.selected_tests(
            self._args(changed_file=["tests/function_test_loader.py"], tier="fast"),
            self.catalog,
        )
        self.assertEqual(selection["selector_confidence"], "high")
        self.assertIn("tests/test_test_selection.py", selection["tests"])

    def test_platform_role_change_selects_fast_tests_without_slow_tests(self) -> None:
        selection = module.selected_tests(
            self._args(changed_file=["scripts/platform_roles.py"], tier="fast"),
            self.catalog,
        )
        self.assertEqual(selection["selector_confidence"], "high")
        self.assertIn("tests/test_plugin_validation_scripts.py", selection["tests"])
        self.assertNotIn("tests/test_platform_roles.py", selection["tests"])
        self.assertIn("tests/test_platform_roles.py", selection["slow_tests_deferred"])

    def test_agent_registration_sync_change_maps_to_platform_role_lane(self) -> None:
        selection = module.selected_tests(
            self._args(changed_file=["scripts/agent_registration_sync.py"], tier="fast"),
            self.catalog,
        )
        self.assertEqual(selection["selector_confidence"], "high")
        self.assertIn("tests/test_agent_registration_sync.py", selection["tests"])

    def test_workflow_reference_docs_map_to_subagent_lane(self) -> None:
        selection = module.selected_tests(
            self._args(
                changed_file=[
                    "docs/reference/roadmap-control.md",
                    "docs/reference/workflow-backlog-lane.md",
                ],
                tier="fast",
            ),
            self.catalog,
        )
        self.assertEqual(selection["selector_confidence"], "high")
        self.assertIn("tests/test_plugin_validation_scripts.py", selection["tests"])

    def test_orchestrator_delivery_audit_docs_are_not_plugin_lane(self) -> None:
        selection = module.selected_tests(
            self._args(
                changed_file=[
                    "docs/audits/orchestrator-deliveries/production/issue-550-delivery/delivery-manifest.v1.json",
                ],
                tier="fast",
            ),
            self.catalog,
        )
        self.assertEqual(selection["selector_confidence"], "low")
        self.assertTrue(selection["requires_full_suite"])
        self.assertNotIn("tests/test_orchestrator_issue_daemon.py", selection["tests"])
        self.assertNotIn("tests/test_goal_orchestrator.py", selection["tests"])

    def test_capability_harness_change_selects_capability_tests(self) -> None:
        selection = module.selected_tests(
            self._args(
                changed_file=[
                    "docs/reference/capability-harness.md",
                    "scripts/capability_harness.py",
                    "tests/fixtures/capability/catalogs/l0_l3_stub_matrix.valid.json",
                ],
                tier="fast",
            ),
            self.catalog,
        )
        self.assertEqual(selection["selector_confidence"], "high")
        self.assertIn("tests/test_capability_harness.py", selection["tests"])
        self.assertIn("tests/test_bears_doctor.py", selection["tests"])
        self.assertIn("tests/test_artifact_registry.py", selection["tests"])

    def test_unknown_path_uses_fast_suite_and_marks_full_suite_advisory(self) -> None:
        selection = module.selected_tests(
            self._args(changed_file=["docs/unmapped-policy.md"], tier="fast"),
            self.catalog,
        )
        slow = set(self.catalog["slow_tests"])
        self.assertEqual(selection["selector_confidence"], "low")
        self.assertTrue(selection["requires_full_suite"])
        self.assertTrue(selection["full_suite_advisory_only"])
        self.assertFalse(slow & set(selection["tests"]))

    def test_changed_test_file_maps_to_itself_when_fast(self) -> None:
        selection = module.selected_tests(
            self._args(changed_file=["tests/test_plugin_marketplace.py"], tier="fast"),
            self.catalog,
        )
        self.assertIn("tests/test_plugin_marketplace.py", selection["tests"])

    def test_shards_partition_the_fast_suite_without_overlap(self) -> None:
        all_fast = module.selected_tests(self._args(suite="fast", tier=None), self.catalog)["tests"]
        left = module.selected_tests(
            self._args(suite="fast", tier=None, shard_index=0, shard_total=2),
            self.catalog,
        )["tests"]
        right = module.selected_tests(
            self._args(suite="fast", tier=None, shard_index=1, shard_total=2),
            self.catalog,
        )["tests"]
        self.assertEqual(sorted(left + right), all_fast)
        self.assertFalse(set(left) & set(right))

    def test_cli_dry_run_does_not_execute_full_suite(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "scripts/test_selection.py",
                "run",
                "--changed-file",
                "scripts/test_selection.py",
                "--tier",
                "fast",
                "--dry-run",
            ],
            cwd=PLUGIN_ROOT,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("-m unittest", result.stdout)

    def test_cli_refuses_low_confidence_run_without_manual_override(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "scripts/test_selection.py",
                "run",
                "--changed-file",
                "docs/unmapped-policy.md",
                "--tier",
                "fast",
                "--dry-run",
            ],
            cwd=PLUGIN_ROOT,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("low-confidence", result.stderr)


    def test_unknown_path_falls_back_to_all_fast_tests(self) -> None:
        selection = module.selected_tests(
            self._args(changed_file=["docs/unmapped-policy.md"], tier="fast"),
            self.catalog,
        )
        all_fast = module.selected_tests(self._args(suite="fast", tier=None), self.catalog)["tests"]
        self.assertEqual(selection["tests"], all_fast)

    def test_loader_change_runs_lightweight_contract_tests(self) -> None:
        selection = module.selected_tests(
            self._args(changed_file=["tests/function_test_loader.py"], tier="fast"),
            self.catalog,
        )
        self.assertEqual(selection["selector_confidence"], "high")
        self.assertIn("tests/test_function_test_loader.py", selection["tests"])
        self.assertIn("tests/test_test_selection.py", selection["tests"])
        self.assertNotIn("tests/test_role_gate_methodology.py", selection["tests"])
        self.assertNotIn("tests/test_validate_overlay.py", selection["tests"])

    def test_unittest_loader_preserves_class_tests_in_mixed_modules(self) -> None:
        suite = unittest.defaultTestLoader.discover("tests", pattern="test_role_gate_methodology.py")
        self.assertEqual(suite.countTestCases(), 82)

    def test_every_function_loader_importer_is_mapped(self) -> None:
        importers = sorted(
            path.relative_to(PLUGIN_ROOT).as_posix()
            for path in (PLUGIN_ROOT / "tests").glob("test_*.py")
            if "load_function_tests" in path.read_text(encoding="utf-8")
            and path.name not in {"test_test_selection.py", "test_function_test_loader.py"}
        )
        loader_mapping = next(mapping for mapping in self.catalog["mappings"] if mapping["name"] == "function-test-loader")
        mapped_patterns = set(loader_mapping["patterns"])
        self.assertEqual(importers, sorted(mapped_patterns - {"tests/function_test_loader.py"}))

    def test_from_git_reads_changed_files_from_range(self) -> None:
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

    def test_from_git_invalid_range_returns_cli_error(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "scripts/test_selection.py",
                "list",
                "--from-git",
                "missing-ref...HEAD",
                "--tier",
                "fast",
            ],
            cwd=PLUGIN_ROOT,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("unknown revision", result.stderr)

    def test_low_confidence_manual_override_dry_run(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "scripts/test_selection.py",
                "run",
                "--changed-file",
                "docs/unmapped-policy.md",
                "--tier",
                "fast",
                "--dry-run",
                "--allow-low-confidence",
            ],
            cwd=PLUGIN_ROOT,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("-m unittest", result.stdout)

    def test_invalid_shard_bounds_raise_value_error(self) -> None:
        with self.assertRaises(ValueError):
            module.shard_tests(["tests/test_test_selection.py"], 1, 1)

    def test_slow_and_full_tiers_are_explicit(self) -> None:
        slow = module.selected_tests(self._args(suite="slow", tier=None), self.catalog)["tests"]
        full = module.selected_tests(self._args(suite="full", tier=None), self.catalog)["tests"]
        self.assertTrue(set(slow).issubset(full))
        self.assertIn("tests/test_platform_roles.py", slow)
        self.assertIn("tests/test_plugin_manifests.py", full)

    def test_github_workflow_keeps_operator_only_diagnostics(self) -> None:
        workflow = yaml.safe_load((PLUGIN_ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8"))
        workflow_run = json.dumps(workflow)
        workflow_on = workflow.get("on", workflow.get(True))
        self.assertEqual(set(workflow_on), {"workflow_dispatch"})
        self.assertIn("emergency_full_suite", workflow_on["workflow_dispatch"]["inputs"])
        self.assertNotIn("push", workflow_on)
        self.assertNotIn("pull_request", workflow_on)
        self.assertNotIn("merge_group", workflow_on)
        self.assertNotIn("unit-fast", workflow["jobs"])
        self.assertIn("python3 scripts/test_selection.py run --suite full --tier full", workflow_run)
        self.assertIn("python3 scripts/plugin_cache_sync.py validate-state", workflow_run)
        self.assertNotIn("--allow-low-confidence", workflow_run)
        self.assertNotIn("origin/main...HEAD", workflow_run)
        self.assertNotIn("refs/heads/dev", workflow_run)
        self.assertNotIn("python3 -m unittest discover -s tests", workflow_run)
        self.assertNotIn("python3 -m pytest -q tests", workflow_run)
        full_job = workflow["jobs"]["emergency-full-suite"]
        self.assertEqual(full_job["if"], "github.event_name == 'workflow_dispatch' && inputs.emergency_full_suite == true")
        self.assertIn("--suite full", json.dumps(full_job))


if __name__ == "__main__":
    unittest.main()
