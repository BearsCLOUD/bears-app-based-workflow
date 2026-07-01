import json
import subprocess
import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN_ROOT / "scripts/capability_layout.py"
FIXTURES = PLUGIN_ROOT / "tests/fixtures/capability_layout/rule_coverage"
PASS_LEDGER = FIXTURES / "pass/rule_coverage_matrix.valid.json"


class CapabilityRuleCoverageTests(unittest.TestCase):
    def run_layout(self, *args):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "validate-rule-coverage", *args, "--json"],
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

    def test_inventory_rule_coverage_passes(self):
        result, payload = self.run_layout()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["rule_coverage_status"], "pass")
        self.assertEqual(payload["instruction_only_rule_count"], 0)
        self.assertIn("checked_rule_count", payload)

    def test_pass_fixture_validates_p1_16_and_p1_17_rows(self):
        result, payload = self.run_layout("--ledger", str(PASS_LEDGER))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["checked_rule_count"], 2)

    def test_fail_fixtures_reject_expected_codes(self):
        for path in sorted((FIXTURES / "fail").glob("*.json")):
            with self.subTest(path=path.name):
                expected = json.loads(path.read_text())["expected_code"]
                result, payload = self.run_layout("--ledger", str(path))
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertEqual(payload["status"], "fail")
                self.assertIn(expected, {item["code"] for item in payload["errors"]})
                self.assertEqual(payload["restricted_data_status"], "clean")


if __name__ == "__main__":
    unittest.main()
