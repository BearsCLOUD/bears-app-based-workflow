from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import roadmap_state_transition_authority as authority
from scripts import workflow_roadmap


class RoadmapStateTransitionAuthorityTest(unittest.TestCase):
    def resource_allow(self) -> dict[str, object]:
        return {
            "status": "allow",
            "mode": "exclusive",
            "checked_ref": "tests/test_roadmap_state_transition_authority.py",
            "gate_refs": ["resource-conflict:authority-test"],
            "active_elsewhere": False,
            "approval_refs": ["approval:test"],
            "evidence_refs": ["tests/test_roadmap_state_transition_authority.py"],
        }

    def roadmap_with_node(self, *, evidence_paths: list[str] | None = None, resource_conflict_status: dict[str, object] | None = None) -> dict[str, object]:
        roadmap = workflow_roadmap.load(workflow_roadmap.DEFAULT_ROADMAP)
        node = {
            "node_id": "issue-517-manual-review-check",
            "issue": "#517",
            "node_type": "validator",
            "state": "queued",
            "owner_role": "roadmap_reconciler",
            "source_of_truth": ["runtime_finding"],
            "inputs": [],
            "outputs": ["proof"],
            "depends_on": [],
            "decomposes_to": [],
            "blocked_by": [],
            "autostart_policy": "manual_review",
            "evidence_paths": evidence_paths or ["assets/catalog/workflow-roadmap.v1.json"],
        }
        if resource_conflict_status is not None:
            node["resource_conflict_status"] = resource_conflict_status
        roadmap["nodes"] = [node]
        return roadmap

    def test_catalog_validates(self) -> None:
        self.assertEqual(authority.validate_catalog(), [])

    def test_reconcile_check_reports_manual_review_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            roadmap_path = Path(tmp) / "roadmap.json"
            roadmap_path.write_text(json.dumps(self.roadmap_with_node(resource_conflict_status=self.resource_allow())), encoding="utf-8")
            packet = authority.reconcile_check(roadmap_path)
            self.assertEqual(packet["schema"], authority.RESULT_SCHEMA)
            self.assertEqual(packet["status"], "blocked")
            self.assertEqual(packet["blocked_transitions"][0]["reason"], "manual_review_preserved")
            self.assertEqual(packet["manual_review_promotions"][0]["node_id"], "issue-517-manual-review-check")

    def test_reconcile_check_reports_missing_resource_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            roadmap_path = Path(tmp) / "roadmap.json"
            roadmap_path.write_text(json.dumps(self.roadmap_with_node()), encoding="utf-8")
            packet = authority.reconcile_check(roadmap_path)
            self.assertEqual(packet["status"], "blocked")
            self.assertEqual(packet["blocked_transitions"][0]["reason"], "missing_resource_conflict_status")


    def test_doctor_reports_pass_with_default_roadmap_check(self) -> None:
        packet = authority.doctor()
        self.assertEqual(packet["schema"], "bears-roadmap-state-transition-authority-doctor.v1")
        self.assertEqual(packet["status"], "pass")
        self.assertEqual(packet["component_issue"], "#517")

    def test_cli_validate_json(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/roadmap_state_transition_authority.py", "validate", "--json"],
            cwd=authority.PLUGIN_ROOT,
            check=False,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        packet = json.loads(result.stdout)
        self.assertEqual(packet["status"], "pass")


if __name__ == "__main__":
    unittest.main()
