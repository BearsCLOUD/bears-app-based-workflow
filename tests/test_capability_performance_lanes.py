import json
import subprocess
import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN_ROOT / "scripts/capability_layout.py"
FIXTURES = PLUGIN_ROOT / "tests/fixtures/capability_layout/performance_lanes"
SNAPSHOT = PLUGIN_ROOT / "tests/fixtures/capability_layout/effective_config/pass/trusted_project_layer.valid.json"
PASS_PACKET = FIXTURES / "pass/all_surfaces.valid.json"


class CapabilityPerformanceLaneTests(unittest.TestCase):
    def run_layout(self, packet):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "validate-performance-claims", "--packet", str(packet), "--snapshot", str(SNAPSHOT), "--json"],
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

    def test_pass_fixture_validates_all_performance_surfaces(self):
        result, payload = self.run_layout(PASS_PACKET)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["claim_count"], 9)
        self.assertEqual(payload["surface_count"], 9)

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
