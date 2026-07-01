"""Tests for the Dagger delivery wrapper."""
from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PLUGIN_ROOT / "scripts" / "dagger_delivery.py"
spec = importlib.util.spec_from_file_location("dagger_delivery", SCRIPT_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)  # type: ignore[arg-type]


class DaggerDeliveryTests(unittest.TestCase):
    """Validate the delivery wrapper contract and CLI."""

    def setUp(self) -> None:
        self.catalog = module.load_json(module.CATALOG)

    def test_catalog_validates_and_commands_are_ordered(self) -> None:
        self.assertEqual(module.validate_catalog(self.catalog), [])

    def test_catalog_validation_rejects_wrong_gate_order(self) -> None:
        bad = copy.deepcopy(self.catalog)
        bad["gates"][1]["id"] = "policy_invariants"
        errors = module.validate_catalog(bad)
        self.assertTrue(any("gate order mismatch" in error for error in errors), errors)

    def test_validate_cli_emits_compact_packet(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "validate"],
            cwd=PLUGIN_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        packet = json.loads(result.stdout)
        self.assertEqual(packet["schema"], "bears-dagger-delivery-result.v1")
        self.assertEqual(packet["status"], "pass")
        self.assertEqual(packet["failed_gates"], [])
        self.assertEqual(packet["next_actions"], [])
        self.assertTrue(packet["artifacts"])

    def test_run_reports_tool_missing_without_dagger(self) -> None:
        with mock.patch.object(module, "dagger_binary_path", return_value=None):
            packet = module.run_packet("issue-461-demo")
        self.assertEqual(packet["status"], "tool_missing")
        self.assertEqual(packet["failed_gates"][0]["gate"], "dagger_binary")
        self.assertIn("manual_setup_required", packet["next_actions"][0])

    def test_run_passes_and_collects_artifacts(self) -> None:
        sha = "a" * 40
        with mock.patch.object(module, "dagger_binary_path", return_value="/usr/bin/dagger"), mock.patch.object(
            module, "current_commit_sha", return_value=sha
        ), mock.patch.object(
            module, "parent_range", return_value=f"{sha[:-1]}..{sha}"
        ), mock.patch.object(
            module,
            "run_json_command",
            side_effect=[
                (0, {"status": "pass", "summary_path": "docs/audits/external-review-2026-06-25/dagger-demo.json", "errors": []}, ""),
                (0, {"status": "pass", "summary": {"passed": 5, "failed": 0}, "errors": []}, ""),
                (0, {"status": "pass", "proof_path": f"runtime/local-commit-validation/{sha}.json", "commit_sha": sha, "tests": ["tests/test_dagger_delivery.py"]}, ""),
                (0, {"status": "pass", "closeout_summary": {"expected_evidence_paths": [f"runtime/local-commit-validation/{sha}.json"]}}, ""),
            ],
        ):
            packet = module.run_packet("issue-461-demo")
        self.assertEqual(packet["status"], "pass")
        self.assertEqual(packet["delivery_id"], "issue-461-demo")
        self.assertEqual(packet["failed_gates"], [])
        paths = [item["path"] for item in packet["artifacts"]]
        self.assertIn("assets/catalog/dagger-delivery-pipeline.v1.json", paths)
        self.assertIn("assets/schemas/dagger-delivery-result.v1.schema.json", paths)
        self.assertIn("docs/audits/external-review-2026-06-25/dagger-demo.json", paths)
        self.assertIn(f"runtime/local-commit-validation/{sha}.json", paths)
        self.assertEqual(packet["next_actions"], [])

    def test_run_fails_on_first_inner_gate(self) -> None:
        with mock.patch.object(module, "dagger_binary_path", return_value="/usr/bin/dagger"), mock.patch.object(
            module, "run_json_command", return_value=(1, {"status": "fail", "errors": ["review missing"]}, "review missing")
        ):
            packet = module.run_packet("issue-461-demo")
        self.assertEqual(packet["status"], "fail")
        self.assertEqual(packet["failed_gates"][0]["gate"], "external_review_audit")
        self.assertIn("fix external_review_audit", packet["next_actions"][0])


if __name__ == "__main__":
    unittest.main()
