import json
import subprocess
import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN_ROOT / "scripts/capability_layout.py"
FIXTURES = PLUGIN_ROOT / "tests/fixtures/capability_layout/effective_config"
PASS_SNAPSHOT = FIXTURES / "pass/trusted_project_layer.valid.json"


class CapabilityEffectiveConfigTests(unittest.TestCase):
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

    def test_resolve_effective_environment_sanitized_shape(self):
        result, payload = self.run_layout("resolve-effective-environment", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["status"], "pass")
        for field in [
            "trusted_project_status",
            "config_precedence_order",
            "config_layers_checked",
            "managed_requirements_status",
            "project_layer_active",
            "effective_features",
            "effective_agents",
            "effective_service_tier",
            "effective_web_search_mode",
            "effective_permission_profile",
            "effective_approval_policy",
            "effective_hooks_enabled",
            "plugin_cache_status",
            "custom_agent_dirs_considered",
            "redacted_fields",
            "blocked_raw_sources",
            "effective_config_snapshot_id",
        ]:
            self.assertIn(field, payload)
        self.assertGreater(payload["redacted_fields"], 0)
        self.assertEqual(payload["restricted_data_status"], "clean")
        self.assertNotIn("raw_config_values", payload)
        self.assertNotIn("provider_base_urls", payload)

    def test_effective_config_pass_fixture_validates(self):
        result, payload = self.run_layout("validate-effective-config", "--snapshot", str(PASS_SNAPSHOT), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["runtime_claim_count"], 7)

    def test_managed_requirements_pass_fixture_validates(self):
        result, payload = self.run_layout("validate-managed-requirements", "--snapshot", str(PASS_SNAPSHOT), "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["managed_requirements_status"], "checked")

    def test_effective_config_fail_fixtures_reject_expected_codes(self):
        for path in sorted((FIXTURES / "fail").glob("*.json")):
            with self.subTest(path=path.name):
                expected = json.loads(path.read_text())["expected_code"]
                result, payload = self.run_layout("validate-effective-config", "--snapshot", str(path), "--json")
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertEqual(payload["status"], "fail")
                self.assertIn(expected, {item["code"] for item in payload["errors"]})


if __name__ == "__main__":
    unittest.main()
