import json
import subprocess
import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN_ROOT / "scripts/capability_layout.py"
FIXTURES = PLUGIN_ROOT / "tests/fixtures/capability_layout/refactor_gate"
PASS_PACKET = FIXTURES / "pass/phase1_matrix.valid.json"


class CapabilityRefactorGateTests(unittest.TestCase):
    def run_layout(self, *args):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "validate-refactor-gate", *args, "--json"],
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

    def test_pass_fixtures_validate_refactor_gate(self):
        result, payload = self.run_layout()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["refactor_gate_status"], "pass")
        self.assertEqual(payload["checked_packet_count"], 1)
        self.assertEqual(payload["requirement_count"], 3)

    def test_explicit_pass_packet_validates(self):
        result, payload = self.run_layout("--packet", str(PASS_PACKET))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["restricted_data_status"], "clean")

    def test_fail_fixtures_reject_expected_codes(self):
        for path in sorted((FIXTURES / "fail").glob("*.json")):
            with self.subTest(path=path.name):
                expected = json.loads(path.read_text())["expected_code"]
                result, payload = self.run_layout("--packet", str(path))
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertEqual(payload["status"], "fail")
                self.assertIn(expected, {item["code"] for item in payload["errors"]})
                self.assertEqual(payload["restricted_data_status"], "clean")


if __name__ == "__main__":
    unittest.main()
