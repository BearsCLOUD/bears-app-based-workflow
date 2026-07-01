import json
import subprocess
import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = PLUGIN_ROOT / "capabilities/plugin_constitution/scripts/validate.py"
CAPABILITY = PLUGIN_ROOT / "capabilities/plugin_constitution/capability.json"
INVENTORY = PLUGIN_ROOT / "capabilities/inventory.v1.json"
PASS_FIXTURE = PLUGIN_ROOT / "capabilities/plugin_constitution/fixtures/pass/catalog.valid.json"
FAIL_FIXTURE = PLUGIN_ROOT / "capabilities/plugin_constitution/fixtures/fail/catalog.invalid.json"
PASS_RESTRICTED_FIXTURE = PLUGIN_ROOT / "capabilities/plugin_constitution/fixtures/pass/restricted-data.clean.json"
FAIL_RESTRICTED_FIXTURE = (
    PLUGIN_ROOT / "capabilities/plugin_constitution/fixtures/fail/restricted-data.synthetic-marker.json"
)
RESTRICTED_MARKER = "SYNTHETIC_RESTRICTED_DATA_MARKER_P1_09"


class PluginConstitutionCapabilityTests(unittest.TestCase):
    def run_wrapper(self, *args: str, cwd: str | Path = PLUGIN_ROOT):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--json", *args],
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:  # pragma: no cover
            self.fail(f"stdout is not JSON: {exc}: {result.stdout!r}; stderr={result.stderr!r}")
        return result, payload

    def test_wrapper_runs_from_repo_root(self):
        result, payload = self.run_wrapper(cwd=PLUGIN_ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["authority"], "legacy")
        self.assertEqual(payload["restricted_data_status"], "clean")
        self.assertTrue(
            any("restricted_data_marker" in item["rejection_codes"] for item in payload["fixture_results"])
        )

    def test_wrapper_runs_from_tmp(self):
        result, payload = self.run_wrapper(cwd="/tmp")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["plugin_root"], str(PLUGIN_ROOT))

    def test_pass_fixture_passes(self):
        result, payload = self.run_wrapper("--catalog", str(PASS_FIXTURE), "--no-check-files")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["status"], "pass")

    def test_restricted_data_pass_fixture_passes(self):
        result, payload = self.run_wrapper("--catalog", str(PASS_RESTRICTED_FIXTURE), "--no-check-files")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["restricted_data_status"], "clean")

    def test_fail_fixture_fails(self):
        result, payload = self.run_wrapper("--catalog", str(FAIL_FIXTURE), "--no-check-files")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(payload["status"], "fail")
        self.assertTrue(payload["errors"])

    def test_restricted_data_fail_fixture_is_sanitized(self):
        result, payload = self.run_wrapper("--catalog", str(FAIL_RESTRICTED_FIXTURE), "--no-check-files")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(payload["status"], "fail")
        self.assertEqual(payload["restricted_data_status"], "clean")
        self.assertTrue(any("restricted-data marker rejected" in error for error in payload["errors"]))
        self.assertNotIn(RESTRICTED_MARKER, result.stdout)
        self.assertNotIn(RESTRICTED_MARKER, result.stderr)

    def test_capability_json_aligns_with_inventory_row(self):
        capability = json.loads(CAPABILITY.read_text())
        inventory = json.loads(INVENTORY.read_text())
        rows = [row for row in inventory["capabilities"] if row["id"] == capability["id"]]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["lifecycle_state"], "dual")
        self.assertEqual(row["canonical_source_phase"], "legacy")
        for field in [
            "id",
            "python_package",
            "owner_role",
            "canonical_source_phase",
            "legacy_entrypoints",
            "compatibility_entrypoints",
            "schemas",
            "fixtures",
            "validators",
            "allowed_actions",
            "forbidden_actions",
            "forbidden_data",
            "sanitized_evidence_schema",
            "context_budget",
            "performance_claims",
            "offload_surface_claims",
            "programmatic_control_claims",
        ]:
            self.assertEqual(row[field], capability[field], field)
        self.assertIn("capabilities/plugin_constitution/tests/test_validate.py", row["tests"])


if __name__ == "__main__":
    unittest.main()
