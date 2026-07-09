import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN_ROOT / "scripts/capability_layout.py"
FIXTURES = PLUGIN_ROOT / "tests/fixtures/capability_layout/environment_packets"
PASS_PACKET = FIXTURES / "pass/config_change_request.valid.json"


class CapabilityEnvironmentPacketTests(unittest.TestCase):
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

    def test_snapshot_environment_is_sanitized(self):
        result, payload = self.run_layout("snapshot-environment", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["content_read_status"], "no_content_read")
        self.assertEqual(payload["restricted_data_status"], "clean")
        text = json.dumps(payload, sort_keys=True).lower()
        for forbidden in ["authorization: bearer", "-----begin private key-----"]:
            self.assertNotIn(forbidden, text)

    def test_plan_environment_operation_is_dry_run_proposal(self):
        result, payload = self.run_layout("plan-environment-operation", "--operation", "config_change_request", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["operation_type"], "config_change_request")
        self.assertEqual(payload["default_mode"], "dry_run")
        self.assertTrue(payload["operator_authorization_required"])
        self.assertEqual(payload["mutation_status"], "not_mutated")

    def test_validate_environment_packet_pass_fixture(self):
        result, payload = self.run_layout("validate-environment-packet", "--packet", str(PASS_PACKET), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["proposal_status"], "proposal_only")

    def assert_packet_failure(self, name, expected_code):
        result, payload = self.run_layout("validate-environment-packet", "--packet", str(FIXTURES / "fail" / name), "--json")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual(payload["status"], "fail")
        self.assertIn(expected_code, {item["code"] for item in payload["errors"]})

    def test_default_apply_rejected(self):
        self.assert_packet_failure("default_apply.invalid.json", "ENV_DEFAULT_APPLY")

    def test_missing_rollback_rejected(self):
        self.assert_packet_failure("missing_rollback.invalid.json", "ENV_REQUIRED_COMMAND")

    def test_unknown_surface_rejected(self):
        self.assert_packet_failure("unknown_surface.invalid.json", "ENV_TARGET_SURFACE_UNLISTED")

    def test_missing_authorization_rejected(self):
        self.assert_packet_failure("missing_authorization.invalid.json", "ENV_OPERATOR_AUTH_REQUIRED")

    def test_restricted_marker_in_packet_rejected_from_temp_file(self):
        packet = json.loads(PASS_PACKET.read_text())
        packet["blocking_reasons"] = ["__BEARS_" + "RESTRICTED_DATA_MARKER__"]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(packet, handle)
            temp_path = Path(handle.name)
        try:
            result, payload = self.run_layout("validate-environment-packet", "--packet", str(temp_path), "--json")
        finally:
            temp_path.unlink(missing_ok=True)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("RESTRICTED_DATA_MARKER", {item["code"] for item in payload["errors"]})


if __name__ == "__main__":
    unittest.main()
