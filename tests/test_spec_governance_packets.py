"""Regression tests for the Spec Kit governance packets bound to Telegram skill bundle."""
from __future__ import annotations

import json
from pathlib import Path
import unittest


def _find_workspace_root(start: Path) -> Path:
    """Return the nearest parent that contains the workspace Spec Kit packet."""
    for parent in [start, *start.parents]:
        if (parent / "specs" / "005-telegram-workflow-plugin").exists():
            return parent
    return Path("/srv/bears")


WORKSPACE_ROOT = _find_workspace_root(Path(__file__).resolve())
FEATURE_DIR = WORKSPACE_ROOT / "specs" / "005-telegram-workflow-plugin"
GOVERNANCE_DIR = FEATURE_DIR / "governance"
ROUTE_TARGET = "/srv/bears/plugins/bears/skills/bears-telegram-workflow"
CANONICAL_GATE_COMMAND = (
    "python3 /srv/bears/plugins/bears/scripts/platform_roles.py route "
    + ROUTE_TARGET
)
CANONICAL_ROLE = "bears-telegram-platform-engineer"
GOAL_ROLE = "bears-goal-prompt-generator"


@unittest.skipUnless(
    FEATURE_DIR.exists(),
    "workspace Spec Kit feature packet is outside this plugin checkout",
)
class SpecGovernancePacketTests(unittest.TestCase):
    def _load(self, name: str) -> dict:
        return json.loads((GOVERNANCE_DIR / name).read_text(encoding="utf-8"))

    def test_spec_status_is_ready_not_draft(self):
        text = (FEATURE_DIR / "spec.md").read_text(encoding="utf-8")
        self.assertIn("**Status**: Ready", text)
        self.assertNotIn("**Status**: Draft", text)

    def test_role_coverage_uses_canonical_gate_first(self):
        packet = self._load("role-coverage.json")
        self.assertEqual(packet["route_target"], ROUTE_TARGET)
        self.assertEqual(packet["coverage_status"], "complete")
        self.assertEqual(packet["route_evidence"]["command"], CANONICAL_GATE_COMMAND)
        self.assertEqual(packet["route_evidence"]["required_role"], CANONICAL_ROLE)
        role_names = {role["name"] for role in packet["roles"]}
        self.assertIn(CANONICAL_ROLE, role_names)
        self.assertIn(GOAL_ROLE, role_names)
        self.assertIn("auth_core -> bears_gateway -> cd_deploy_stage", packet["recommendation"])

    def test_policy_packet_owns_current_plugin_surfaces(self):
        packet = self._load("policy-packet.json")
        owning_paths = set(packet["scope"]["owning_paths"])
        self.assertIn("/srv/bears/plugins/bears", owning_paths)
        self.assertIn(ROUTE_TARGET, owning_paths)
        self.assertEqual(packet["canonical_role_gate"]["command"], CANONICAL_GATE_COMMAND)
        self.assertEqual(packet["canonical_role_gate"]["required_role"], CANONICAL_ROLE)
        bundle = packet["telegram_skill_bundle"]
        self.assertTrue(bundle["metadata_only"])
        self.assertFalse(bundle["standalone_plugin"])

    def test_deploy_and_blocker_packets_keep_runtime_closed(self):
        deploy = self._load("deploy-gate.json")
        blocker = self._load("blocker-review.json")
        self.assertEqual(deploy["impact"]["deploy"], "none")
        self.assertEqual(deploy["impact"]["runtime"], "none")
        self.assertFalse(deploy["live_telegram_actions"])
        self.assertIn("auth_core", deploy["ordered_platform_spine"])
        self.assertEqual(blocker["status"], "clean")
        self.assertEqual(blocker["blockers"], [])
        self.assertTrue(any("readiness" in item for item in blocker["blocked_follow_up"]))

    def test_governance_packets_have_no_stale_plugin_paths(self):
        combined = "\n".join(path.read_text(encoding="utf-8") for path in GOVERNANCE_DIR.glob("*.json"))
        stale_fragments = [
            "bears-workflow-overlay-platform-engineer",
            "bears-workflow-overlay-plugin",
            "/srv/bears/plugins/bears-telegram-workflow/scripts/platform_roles.py route",
            "/srv/bears/plugins/bears-telegram-workflow/.app.json",
            "/srv/bears/.specify/extensions.yml",
            "advisory_mode",
            "report-only",
        ]
        for fragment in stale_fragments:
            self.assertNotIn(fragment, combined)


if __name__ == "__main__":
    unittest.main()
