import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN_ROOT / "scripts/capability_layout.py"
INVENTORY = PLUGIN_ROOT / "capabilities/inventory.v1.json"


class CapabilityRestrictedDataTests(unittest.TestCase):
    def run_layout(self, *args):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=PLUGIN_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:  # pragma: no cover - assertion aid
            self.fail(f"stdout is not JSON: {exc}: {result.stdout!r}; stderr={result.stderr!r}")
        return result, payload

    def write_mutated_inventory_without_fail_fixture(self):
        inventory = json.loads(INVENTORY.read_text())
        for row in inventory["capabilities"]:
            if row["id"] == "subagents-roles":
                row["fixtures"] = [item for item in row["fixtures"] if "/fail/" not in item]
        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        with handle:
            json.dump(inventory, handle)
        return Path(handle.name)

    def test_validate_parity_passes_for_pilot_capability(self):
        result, payload = self.run_layout("validate-parity", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["status"], "pass")
        self.assertGreaterEqual(payload["checked_capability_count"], 1)
        self.assertGreaterEqual(payload["pass_fixture_count"], 1)
        self.assertGreaterEqual(payload["fail_fixture_count"], 1)

    def test_validate_parity_rejects_missing_fail_fixture(self):
        mutated = self.write_mutated_inventory_without_fail_fixture()
        try:
            result, payload = self.run_layout("validate-parity", "--json", "--inventory", str(mutated))
        finally:
            mutated.unlink(missing_ok=True)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("PARITY_FAIL_FIXTURE_REQUIRED", {item["code"] for item in payload["errors"]})

    def test_validate_restricted_data_passes_checked_in_safe_sources(self):
        result, payload = self.run_layout("validate-restricted-data", "--json")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["restricted_data_status"], "clean")
        self.assertGreater(payload["scanned_file_count"], 0)

    def test_validate_restricted_data_rejects_extra_marker_file(self):
        marker = "__BEARS_" + "RESTRICTED_DATA_MARKER__"
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            handle.write(json.dumps({"synthetic_marker": marker}))
            temp_path = Path(handle.name)
        try:
            result, payload = self.run_layout("validate-restricted-data", "--json", "--extra-scan-path", str(temp_path))
        finally:
            temp_path.unlink(missing_ok=True)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("RESTRICTED_DATA_MARKER", {item["code"] for item in payload["errors"]})


if __name__ == "__main__":
    unittest.main()
