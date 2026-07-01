"""Tests for the strict Telegram skill-bundle factory policy."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts import telegram_skill_factory_policy as policy


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = PLUGIN_ROOT / "assets/catalog/telegram-plugin-skill-factory-policy.v1.json"
CANONICAL_ROLE = "bears-telegram-platform-engineer"


class TelegramSkillFactoryPolicyTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(POLICY_PATH.read_text(encoding="utf-8"))

    def _write_policy(self, data: dict) -> Path:
        handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False)
        with handle:
            json.dump(data, handle)
        return Path(handle.name)

    def test_validate_default_policy(self):
        policy.validate_policy(POLICY_PATH)

    def test_canonical_gate_is_first_and_exact_role(self):
        gate_order = self.data["gate_order"]
        self.assertEqual(gate_order[0]["step"], "canonical_role_gate")
        self.assertIn("/srv/bears/plugins/bears/scripts/platform_roles.py", gate_order[0]["command"])
        self.assertEqual(gate_order[0]["required_primary_role"], CANONICAL_ROLE)
        self.assertEqual(gate_order[1]["step"], "telegram_skill_bundle_validation")

    def test_rejects_bundle_validation_before_canonical(self):
        data = dict(self.data)
        data["gate_order"] = list(reversed(self.data["gate_order"]))
        with self.assertRaises(policy.ValidationError):
            policy.validate_policy(self._write_policy(data))

    def test_skill_change_packet_requires_role_route_and_forward_evidence(self):
        fields = set(self.data["skill_change_packet"]["required_fields"])
        self.assertIn("canonical_role_route_status", fields)
        self.assertIn("selected_primary_role", fields)
        self.assertIn("forward_test_evidence", fields)
        self.assertIn("skill_bundle_boundary", fields)
        self.assertIn("standalone_plugin_impact", fields)
        self.assertEqual(self.data["skill_change_packet"]["required_route_status"], "matched")
        self.assertEqual(self.data["skill_change_packet"]["required_primary_role"], CANONICAL_ROLE)

    def test_rejects_missing_forward_test_evidence_field(self):
        data = json.loads(json.dumps(self.data))
        data["skill_change_packet"]["required_fields"].remove("forward_test_evidence")
        with self.assertRaises(policy.ValidationError):
            policy.validate_policy(self._write_policy(data))

    def test_subagent_handoff_forbids_generic_worker_without_role(self):
        handoff = self.data["subagent_handoff_packet"]
        self.assertTrue(handoff["role_must_match_canonical_primary"])
        self.assertEqual(handoff["generic_worker_without_role"], "forbidden")
        for field in ["heartbeat_status_packet", "closeout_packet", "current_spec_artifact_snapshot"]:
            self.assertIn(field, handoff["required_fields"])

    def test_skill_bundle_boundary_is_not_app_or_connector(self):
        boundary = self.data["skill_bundle_boundary"]
        self.assertEqual(boundary["root"], "/srv/bears/plugins/bears")
        self.assertEqual(boundary["mode"], "skills-catalogs-validators-only")
        self.assertEqual(boundary["central_skill"], "bears-telegram-workflow")
        self.assertIn("/srv/bears/plugins/bears-telegram-workflow", boundary["forbidden_standalone_surfaces"])
        self.assertIn(".app.json", boundary["forbidden_standalone_surfaces"])
        self.assertIn("live Telegram mutation behavior", boundary["forbidden_standalone_surfaces"])

    def test_required_validators_cover_factory_and_inventory(self):
        validators = self.data["required_validators"]
        self.assertIn("scripts/telegram_skill_factory_policy.py validate", validators)
        self.assertIn("scripts/telegram_surface_inventory.py validate --workspace-root /srv/bears", validators)
        self.assertIn("/srv/bears/plugins/bears/scripts/platform_roles.py validate", validators)
        self.assertIn("scripts/validate_overlay.py --json validate --strict-overlay-skills", validators)

    def test_forward_tests_cover_regression_cases(self):
        names = {item["name"] for item in self.data["forward_tests"]}
        self.assertIn("skill_creation_requires_canonical_gate_first", names)
        self.assertIn("subagent_handoff_requires_role_packet", names)
        self.assertIn("skill_bundle_boundary_is_not_live_connector", names)
        self.assertIn("duplicate_or_broad_skill_is_rejected", names)

    def test_cli_missing_policy_returns_stable_error_without_traceback(self):
        result = subprocess.run(
            [
                sys.executable,
                str(PLUGIN_ROOT / "scripts/telegram_skill_factory_policy.py"),
                "--policy",
                "/tmp/does-not-exist.json",
                "validate",
            ],
            check=False,
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "ERROR: policy not found: /tmp/does-not-exist.json\n")
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
