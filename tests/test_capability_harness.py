from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import capability_harness

PLUGIN_ROOT = capability_harness.PLUGIN_ROOT
SCRIPT = PLUGIN_ROOT / "scripts/capability_harness.py"
STUB_CATALOG = PLUGIN_ROOT / "tests/fixtures/capability/catalogs/l0_l3_stub_matrix.valid.json"


class CapabilityHarnessContracts(unittest.TestCase):
    def cli(self, *args: str) -> tuple[int, dict]:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), *args, "--json"],
            cwd=PLUGIN_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:  # pragma: no cover
            self.fail(f"stdout is not JSON: {exc}; stdout={result.stdout!r}; stderr={result.stderr!r}")
        return result.returncode, payload

    def temp_catalog(self, mutate=None) -> Path:
        temp_dir = Path(tempfile.mkdtemp(prefix="capability-harness-test-"))
        path = temp_dir / "catalog.json"
        data = json.loads(capability_harness.DEFAULT_CATALOG.read_text(encoding="utf-8"))
        if mutate:
            mutate(data)
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.addCleanup(shutil.rmtree, temp_dir, ignore_errors=True)
        return path

    def test_catalog_declares_requested_ladder_modes_and_reports(self) -> None:
        code, payload = self.cli("validate-catalog")
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["task_levels"], {"L1": 1, "L2": 1, "L3": 1, "L4": 1, "L5": 1, "L6": 1, "L7": 1})
        self.assertEqual(payload["comparison_modes"], capability_harness.COMPARISON_MODES)
        catalog = json.loads(capability_harness.DEFAULT_CATALOG.read_text(encoding="utf-8"))
        self.assertIn("python3 scripts/capability_harness.py run --scenario <scenario_id> --executor stub --json", catalog["commands"])
        self.assertIn("python3 scripts/capability_harness.py run-matrix --levels L0,L1,L2,L3 --executor stub --json", catalog["commands"])

    def test_stub_catalog_validates_with_scenario_levels(self) -> None:
        code, payload = self.cli("validate-catalog", "--catalog", str(STUB_CATALOG))
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["scenario_levels"], {"L0": 3, "L1": 5, "L2": 3, "L3": 6})

    def test_schema_validation_failures_return_json_and_nonzero(self) -> None:
        def mutate(data: dict) -> None:
            data["tasks"][0].pop("schema", None)

        code, payload = self.cli("validate-catalog", "--catalog", str(self.temp_catalog(mutate)))
        self.assertNotEqual(code, 0)
        self.assertEqual(payload["status"], "fail")
        self.assertTrue(any(error["code"] == "TASK_SCHEMA_INVALID" for error in payload["errors"]), payload)

    def test_missing_fixture_files_return_json_and_nonzero(self) -> None:
        def mutate(data: dict) -> None:
            data["tasks"][3]["files_changed"] = ["tests/fixtures/capability/sandbox/missing_fixture.md"]

        code, payload = self.cli("validate-catalog", "--catalog", str(self.temp_catalog(mutate)))
        self.assertNotEqual(code, 0)
        self.assertEqual(payload["status"], "fail")
        self.assertTrue(any(error["code"] == "MISSING_FIXTURE_FILE" for error in payload["errors"]), payload)

    def test_invalid_level_task_combination_returns_json_and_nonzero(self) -> None:
        code, payload = self.cli("run-level", "--level", "L1", "--task", "l7_coordinate_subagents", "--mode", "bootstrap_plus_subagents", "--policy", "fixture")
        self.assertNotEqual(code, 0)
        self.assertEqual(payload["status"], "fail")
        self.assertIn("invalid level/task combination", payload["errors"][0])

    def test_bootstrap_packet_has_required_starting_knowledge(self) -> None:
        code, payload = self.cli("bootstrap", "--task", "l2_build_context")
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["schema"], "bears-knowledge-bootstrap-packet.v1")
        for field in ["repo_map", "instructions", "roadmap_node", "issue_facts", "related_files", "schemas", "catalogs", "prior_local_decisions_evidence", "allowed_tools_mcp_policy", "context_budget"]:
            self.assertIn(field, payload)
        self.assertTrue(payload["instructions"])
        self.assertIn("mcp_research", payload["allowed_tools_mcp_policy"])

    def test_external_facts_fixture_mode_is_sourced_timestamped_and_confidence_scored(self) -> None:
        code, payload = self.cli("collect-external", "--task", "l6_solve_issue_requiring_external_facts", "--policy", "fixture")
        self.assertEqual(code, 0, payload)
        self.assertGreaterEqual(len(payload["facts"]), 1)
        self.assertTrue(any(fact["source"] == "fixture" for fact in payload["facts"]))
        for fact in payload["facts"]:
            for field in ["source", "source_ref", "collected_at", "confidence"]:
                self.assertIn(field, fact)
                self.assertTrue(fact[field])

    def test_subagent_coordination_fixture_mode_passes_without_closeout_claim(self) -> None:
        code, payload = self.cli("run-level", "--level", "L7", "--task", "l7_coordinate_subagents", "--mode", "bootstrap_plus_subagents", "--policy", "fixture")
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["status"], "pass")
        self.assertIn("l7_governance_packet_builder", payload["usage_ledger"]["tools_called"])
        self.assertEqual(payload["usage_ledger"]["validation_status"], "pending_local_commit_validation")
        self.assertFalse(payload["usage_ledger"]["closeout_allowed"])

    def test_stub_run_compatibility_passes_and_updates_latest_report(self) -> None:
        code, payload = self.cli("run", "--scenario", "l2_doc_only_stub_patch_auto_close", "--executor", "stub")
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["scenario_id"], "l2_doc_only_stub_patch_auto_close")
        self.assertEqual(payload["result"]["closeout_decision"], "auto_close")
        report_code, report = self.cli("report", "--latest")
        self.assertEqual(report_code, 0, report)
        self.assertEqual(report["overall_result"], "pass")
        self.assertEqual(report["results"][0]["scenario_id"], "l2_doc_only_stub_patch_auto_close")

    def test_stub_run_failure_scenario_returns_nonzero(self) -> None:
        code, payload = self.cli("run", "--scenario", "l3_failing_validator_blocks_closeout", "--executor", "stub")
        self.assertNotEqual(code, 0)
        self.assertEqual(payload["status"], "fail")
        self.assertEqual(payload["result"]["expected_failed_gate"], "validator")
        self.assertEqual(payload["result"]["status"], "fail")

    def test_run_level_writes_reports_and_usage_ledger(self) -> None:
        code, payload = self.cli("run-level", "--level", "L6", "--task", "l6_solve_issue_requiring_external_facts", "--mode", "bootstrap_plus_external", "--policy", "fixture")
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["status"], "pass")
        run_dir = PLUGIN_ROOT / payload["run_dir"]
        for name in ["capability_progress.v1.json", "usage_ledger.v1.jsonl", "cost_quality_summary.v1.json"]:
            self.assertTrue((run_dir / name).exists(), name)
        ledger = json.loads((run_dir / "usage_ledger.v1.jsonl").read_text(encoding="utf-8").splitlines()[0])
        for field in capability_harness.REQUIRED_LEDGER_FIELDS:
            self.assertIn(field, ledger)
        self.assertGreater(ledger["external_facts_count"], 0)

    def test_full_matrix_generates_schema_valid_reports(self) -> None:
        code, payload = self.cli("run-matrix", "--mode", "bootstrap_plus_subagents", "--policy", "fixture")
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["status"], "pass")
        self.assertEqual([row["level"] for row in payload["results"]], list(capability_harness.TASK_LEVELS))
        self.assertEqual(payload["schema_validation"], "pass")
        run_dir = PLUGIN_ROOT / payload["run_dir"]
        self.assertFalse(capability_harness.validate_report_files(run_dir))
        ledger_rows = capability_harness.read_jsonl(run_dir / "usage_ledger.v1.jsonl")
        self.assertEqual(len(ledger_rows), 7)
        self.assertEqual([row["level"] for row in ledger_rows], list(capability_harness.TASK_LEVELS))

    def test_stub_matrix_levels_compatibility_uses_fixture_catalog(self) -> None:
        code, payload = self.cli("run-matrix", "--levels", "L0,L1,L2,L3", "--executor", "stub")
        self.assertNotEqual(code, 0, payload)
        self.assertEqual(payload["status"], "fail")
        self.assertEqual(payload["levels"], ["L0", "L1", "L2", "L3"])
        self.assertEqual(len(payload["results"]), 17)
        self.assertEqual({row["level"] for row in payload["results"]}, {"L0", "L1", "L2", "L3"})
        report_code, report = self.cli("report", "--latest")
        self.assertNotEqual(report_code, 0, report)
        self.assertEqual(report["overall_result"], "fail")
        self.assertEqual(len(report["results"]), 17)

    def test_matrix_json_output_is_stable_for_fixture_mode(self) -> None:
        first_code, first = self.cli("run-matrix", "--mode", "bootstrap_plus_subagents", "--policy", "fixture")
        second_code, second = self.cli("run-matrix", "--mode", "bootstrap_plus_subagents", "--policy", "fixture")
        self.assertEqual(first_code, 0, first)
        self.assertEqual(second_code, 0, second)
        self.assertEqual(first, second)

    def test_compare_runs_same_task_in_all_modes(self) -> None:
        code, payload = self.cli("compare", "--task", "l7_coordinate_subagents", "--policy", "fixture")
        self.assertEqual(code, 0, payload)
        self.assertEqual(payload["status"], "pass")
        self.assertEqual([row["mode"] for row in payload["results"]], capability_harness.COMPARISON_MODES)
        self.assertEqual(payload["best_mode"], "bootstrap_plus_subagents")


if __name__ == "__main__":
    unittest.main()
