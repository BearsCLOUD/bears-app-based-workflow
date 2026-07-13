"""Validate the DIRECT solo router against Graph Workflow v3 contracts."""

from __future__ import annotations

import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills/app-solo-route/SKILL.md"
WORKFLOW = ROOT / "contracts/app-workflow-definition.v2.json"
HANDOFF = ROOT / "contracts/app-stage-handoff.v3.schema.json"


class AppSoloRouteContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = SKILL.read_text(encoding="utf-8")
        cls.workflow = json.loads(WORKFLOW.read_text(encoding="utf-8"))
        cls.handoff = json.loads(HANDOFF.read_text(encoding="utf-8"))
        cls.routes = cls.workflow["routes"]

    def test_statuses_and_targets_share_one_registry(self) -> None:
        self.assertEqual(set(self.routes), set(self.handoff["properties"]["status"]["enum"]))
        self.assertFalse(set(self.routes.values()) - set(self.workflow["stages"]) - {"none"})
        self.assertIn("app-workflow-definition.v2", self.text)
        self.assertIn("app-stage-handoff.v3", self.text)

    def test_audited_is_only_success_terminal(self) -> None:
        self.assertEqual(self.routes["audited"], "none")
        self.assertEqual(self.routes["blocked"], "none")
        self.assertIn("`audited` is the only successful terminal status", self.text)
        self.assertIn("never product acceptance", self.text)

    def test_direct_and_journal_ownership_are_explicit(self) -> None:
        self.assertIn("Run only for a `DIRECT` workstream", self.text)
        self.assertIn("L3 workers never write the journal", self.text)
        self.assertNotIn("$subagents", self.text)

    def test_boundary_audits_and_compile_are_required(self) -> None:
        self.assertIn("Before each handoff, run the process audit", self.text)
        self.assertIn("compile with CAS", self.text)
        self.assertIn("convergence trace profile", self.text)


if __name__ == "__main__":
    unittest.main()
