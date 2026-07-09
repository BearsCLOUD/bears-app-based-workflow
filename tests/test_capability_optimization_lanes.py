import json
import subprocess
import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN_ROOT / "scripts/capability_layout.py"
FIXTURES = PLUGIN_ROOT / "tests/fixtures/capability_layout/optimization_lanes"
PASS_PACKET = FIXTURES / "pass/effective_config_resolution.valid.json"


class CapabilityOptimizationLaneTests(unittest.TestCase):
    def run_layout(self, packet):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "validate-optimization-plan", "--packet", str(packet), "--json"],
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

    def test_pass_fixture_validates(self):
        result, payload = self.run_layout(PASS_PACKET)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["lane"], "effective_config_resolution")
        self.assertEqual(payload["metric_field"], "validator_exit_code")

    def test_fail_fixtures_reject_expected_codes(self):
        for path in sorted((FIXTURES / "fail").glob("*.json")):
            with self.subTest(path=path.name):
                expected = json.loads(path.read_text())["expected_code"]
                result, payload = self.run_layout(path)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertEqual(payload["status"], "fail")
                self.assertIn(expected, {item["code"] for item in payload["errors"]})


if __name__ == "__main__":
    unittest.main()
