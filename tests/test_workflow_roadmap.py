from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts import workflow_roadmap


class WorkflowRoadmapTest(unittest.TestCase):
    def roadmap_node(
        self,
        *,
        node_id: str,
        state: str = "queued",
        autostart_policy: str = "eligible",
        evidence_paths: list[str] | None = None,
        outputs: list[str] | None = None,
        resource_conflict_status: dict[str, object] | None = None,
    ) -> dict[str, object]:
        node = {
            "node_id": node_id,
            "issue": "#517",
            "node_type": "validator",
            "state": state,
            "owner_role": "roadmap_reconciler",
            "source_of_truth": ["runtime_finding"],
            "inputs": [],
            "outputs": outputs or ["proof"],
            "depends_on": [],
            "decomposes_to": [],
            "blocked_by": [],
            "autostart_policy": autostart_policy,
            "evidence_paths": evidence_paths or ["assets/catalog/workflow-roadmap.v1.json"],
        }
        if resource_conflict_status is not None:
            node["resource_conflict_status"] = resource_conflict_status
        return node

    def resource_allow(self) -> dict[str, object]:
        return {
            "status": "allow",
            "mode": "exclusive",
            "checked_ref": "tests/test_workflow_roadmap.py",
            "gate_refs": ["resource-conflict:test-allow"],
            "active_elsewhere": False,
            "approval_refs": ["approval:test"],
            "evidence_refs": ["tests/test_workflow_roadmap.py"],
        }

    def resource_blocked(self, *, status: str = "blocked", active_elsewhere: bool = False) -> dict[str, object]:
        return {
            "status": status,
            "mode": "exclusive",
            "checked_ref": "tests/test_workflow_roadmap.py",
            "gate_refs": ["resource-conflict:test-block"],
            "active_elsewhere": active_elsewhere,
        }

    def write_transition_packet(self, node: dict[str, object], *, status: str = "pass") -> None:
        packet_path = workflow_roadmap.PLUGIN_ROOT / str(node["evidence_paths"][0])
        packet_path.parent.mkdir(parents=True, exist_ok=True)
        packet_path.write_text(
            json.dumps({
                "schema": workflow_roadmap.TRANSITION_PACKET_SCHEMA,
                "status": "pass",
                "node_id": node["node_id"],
                "issue_ref": node["issue"],
                "from_state": node["state"],
                "to_state": "validated",
                "source_hash": workflow_roadmap.node_source_hash(node),
                "validator_command_result": {"status": status},
                "required_gate_refs": ["tests/test_workflow_roadmap.py"],
            }),
            encoding="utf-8",
        )

    def test_catalog_validates(self) -> None:
        roadmap = workflow_roadmap.load(workflow_roadmap.DEFAULT_ROADMAP)
        self.assertEqual(workflow_roadmap.validate_roadmap(roadmap), [])

    def test_next_returns_only_eligible_leaf_nodes(self) -> None:
        roadmap = workflow_roadmap.load(workflow_roadmap.DEFAULT_ROADMAP)
        packet = workflow_roadmap.next_packet(roadmap)
        ids = [node["node_id"] for node in packet["nodes"]]
        self.assertNotIn("issue-413-implementation", ids)
        self.assertNotIn("issue-413-validation", ids)
        for node in packet["nodes"]:
            self.assertEqual(node["state"], "queued")
            self.assertEqual(node["autostart_policy"], "eligible")
            self.assertEqual(node["decomposes_to"], [])

    def test_add_node_uses_packet_and_rejects_duplicate(self) -> None:
        roadmap = workflow_roadmap.load(workflow_roadmap.DEFAULT_ROADMAP)
        node = dict(roadmap["nodes"][0])
        node["node_id"] = "issue-413-extra-validator"
        node["node_type"] = "validator"
        node["state"] = "manual_review"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            roadmap_path = root / "roadmap.json"
            packet_path = root / "packet.json"
            roadmap_path.write_text(json.dumps(roadmap), encoding="utf-8")
            packet_path.write_text(json.dumps({"node": node}), encoding="utf-8")
            updated = workflow_roadmap.add_node(roadmap_path, packet_path)
            self.assertIn("issue-413-extra-validator", workflow_roadmap.node_index(updated))
            with self.assertRaises(ValueError):
                workflow_roadmap.add_node(roadmap_path, packet_path)

    def test_decompose_creates_child_and_preserves_parent_link(self) -> None:
        roadmap = workflow_roadmap.load(workflow_roadmap.DEFAULT_ROADMAP)
        roadmap["nodes"].append({
            "node_id": "issue-413-large-node",
            "issue": "#413",
            "node_type": "implementation",
            "state": "queued",
            "owner_role": "roadmap_decomposer",
            "source_of_truth": ["catalog"],
            "inputs": [],
            "outputs": ["child work"],
            "depends_on": ["issue-413-contract"],
            "decomposes_to": [],
            "blocked_by": [],
            "autostart_policy": "eligible",
            "evidence_paths": ["assets/catalog/workflow-roadmap.v1.json"],
        })
        with tempfile.TemporaryDirectory() as tmp:
            roadmap_path = Path(tmp) / "roadmap.json"
            roadmap_path.write_text(json.dumps(roadmap), encoding="utf-8")
            packet = workflow_roadmap.decompose(roadmap_path, "issue-413-large-node")
            updated = workflow_roadmap.load(roadmap_path)
            parent = workflow_roadmap.node_index(updated)["issue-413-large-node"]
            child_id = packet["children"][0]
            child = workflow_roadmap.node_index(updated)[child_id]
            self.assertEqual(parent["decomposes_to"], [child_id])
            self.assertEqual(child["inputs"], ["parent:issue-413-large-node"])

    def test_reconcile_preserves_manual_review_from_local_evidence(self) -> None:
        roadmap = workflow_roadmap.load(workflow_roadmap.DEFAULT_ROADMAP)
        roadmap["nodes"].append(self.roadmap_node(
            node_id="issue-517-manual-review-proof",
            autostart_policy="manual_review",
            resource_conflict_status=self.resource_allow(),
        ))
        with tempfile.TemporaryDirectory() as tmp:
            roadmap_path = Path(tmp) / "roadmap.json"
            roadmap_path.write_text(json.dumps(roadmap), encoding="utf-8")
            packet = workflow_roadmap.reconcile(roadmap_path)
            self.assertEqual(packet["changed"], [])
            self.assertIn("manual_review_preserved", [item["reason"] for item in packet["blocked_transitions"]])
            node = workflow_roadmap.node_index(workflow_roadmap.load(roadmap_path))["issue-517-manual-review-proof"]
            self.assertEqual(node["state"], "queued")

    def test_reconcile_blocks_evidence_only_promotion(self) -> None:
        roadmap = workflow_roadmap.load(workflow_roadmap.DEFAULT_ROADMAP)
        roadmap["nodes"].append(self.roadmap_node(node_id="issue-517-evidence-only"))
        with tempfile.TemporaryDirectory() as tmp:
            roadmap_path = Path(tmp) / "roadmap.json"
            roadmap_path.write_text(json.dumps(roadmap), encoding="utf-8")
            packet = workflow_roadmap.reconcile(roadmap_path)
            self.assertIn("missing_resource_conflict_status", [item["reason"] for item in packet["blocked_transitions"]])
            node = workflow_roadmap.node_index(workflow_roadmap.load(roadmap_path))["issue-517-evidence-only"]
            self.assertEqual(node["state"], "queued")

    def test_reconcile_preserves_disabled_policy(self) -> None:
        roadmap = workflow_roadmap.load(workflow_roadmap.DEFAULT_ROADMAP)
        roadmap["nodes"].append(self.roadmap_node(
            node_id="issue-517-disabled-proof",
            autostart_policy="disabled",
        ))
        with tempfile.TemporaryDirectory() as tmp:
            roadmap_path = Path(tmp) / "roadmap.json"
            roadmap_path.write_text(json.dumps(roadmap), encoding="utf-8")
            packet = workflow_roadmap.reconcile(roadmap_path)
            self.assertIn("disabled_preserved", [item["reason"] for item in packet["blocked_transitions"]])
            node = workflow_roadmap.node_index(workflow_roadmap.load(roadmap_path))["issue-517-disabled-proof"]
            self.assertEqual(node["state"], "queued")

    def test_reconcile_blocks_hazard_marker(self) -> None:
        roadmap = workflow_roadmap.load(workflow_roadmap.DEFAULT_ROADMAP)
        roadmap["nodes"].append(self.roadmap_node(
            node_id="issue-517-hazard-proof",
            outputs=["seller migration cutover proof"],
            resource_conflict_status=self.resource_allow(),
        ))
        with tempfile.TemporaryDirectory() as tmp:
            roadmap_path = Path(tmp) / "roadmap.json"
            roadmap_path.write_text(json.dumps(roadmap), encoding="utf-8")
            packet = workflow_roadmap.reconcile(roadmap_path)
            self.assertIn("hazard_requires_manual_review", [item["reason"] for item in packet["blocked_transitions"]])
            node = workflow_roadmap.node_index(workflow_roadmap.load(roadmap_path))["issue-517-hazard-proof"]
            self.assertEqual(node["state"], "queued")

    def test_reconcile_accepts_transition_authority_packet(self) -> None:
        roadmap = workflow_roadmap.load(workflow_roadmap.DEFAULT_ROADMAP)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            node = self.roadmap_node(
                node_id="issue-517-authorized-proof",
                evidence_paths=["runtime/test-transition-authority/issue-517-authorized-proof.transition.json"],
                resource_conflict_status=self.resource_allow(),
            )
            self.write_transition_packet(node)
            roadmap["nodes"].append(node)
            roadmap_path = root / "roadmap.json"
            roadmap_path.write_text(json.dumps(roadmap), encoding="utf-8")
            packet = workflow_roadmap.reconcile(roadmap_path)
            self.assertIn({"node_id": "issue-517-authorized-proof", "from": "queued", "to": "validated"}, packet["changed"])
            blocked_ids = [item["node_id"] for item in packet["blocked_transitions"]]
            self.assertNotIn("issue-517-authorized-proof", blocked_ids)

    def test_reconcile_blocks_transition_packet_stale_hash(self) -> None:
        roadmap = workflow_roadmap.load(workflow_roadmap.DEFAULT_ROADMAP)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            node = self.roadmap_node(
                node_id="issue-517-stale-proof",
                evidence_paths=["runtime/test-transition-authority/issue-517-stale-proof.transition.json"],
                resource_conflict_status=self.resource_allow(),
            )
            self.write_transition_packet(node)
            node["outputs"] = ["proof changed after packet"]
            roadmap["nodes"].append(node)
            roadmap_path = root / "roadmap.json"
            roadmap_path.write_text(json.dumps(roadmap), encoding="utf-8")
            packet = workflow_roadmap.reconcile(roadmap_path)
            self.assertIn("stale_evidence_hash", [item["reason"] for item in packet["blocked_transitions"]])

    def test_reconcile_blocks_transition_packet_failed_validator(self) -> None:
        roadmap = workflow_roadmap.load(workflow_roadmap.DEFAULT_ROADMAP)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            node = self.roadmap_node(
                node_id="issue-517-failed-validator-proof",
                evidence_paths=["runtime/test-transition-authority/issue-517-failed-validator-proof.transition.json"],
                resource_conflict_status=self.resource_allow(),
            )
            self.write_transition_packet(node, status="fail")
            roadmap["nodes"].append(node)
            roadmap_path = root / "roadmap.json"
            roadmap_path.write_text(json.dumps(roadmap), encoding="utf-8")
            packet = workflow_roadmap.reconcile(roadmap_path)
            self.assertIn("missing_validator_packet", [item["reason"] for item in packet["blocked_transitions"]])

    def test_reconcile_blocks_transition_packet_mismatched_issue(self) -> None:
        roadmap = workflow_roadmap.load(workflow_roadmap.DEFAULT_ROADMAP)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            node = self.roadmap_node(
                node_id="issue-517-mismatched-issue-proof",
                evidence_paths=["runtime/test-transition-authority/issue-517-mismatched-issue-proof.transition.json"],
                resource_conflict_status=self.resource_allow(),
            )
            self.write_transition_packet(node)
            packet_path = workflow_roadmap.PLUGIN_ROOT / str(node["evidence_paths"][0])
            packet = json.loads(packet_path.read_text(encoding="utf-8"))
            packet["issue_ref"] = "#999"
            packet_path.write_text(json.dumps(packet), encoding="utf-8")
            roadmap["nodes"].append(node)
            roadmap_path = root / "roadmap.json"
            roadmap_path.write_text(json.dumps(roadmap), encoding="utf-8")
            packet = workflow_roadmap.reconcile(roadmap_path)
            self.assertIn("missing_validator_packet", [item["reason"] for item in packet["blocked_transitions"]])

    def test_reconcile_blocks_stale_resource_conflict_status(self) -> None:
        roadmap = workflow_roadmap.load(workflow_roadmap.DEFAULT_ROADMAP)
        roadmap["nodes"].append(self.roadmap_node(
            node_id="issue-517-stale-resource-proof",
            resource_conflict_status=self.resource_blocked(status="stale"),
        ))
        with tempfile.TemporaryDirectory() as tmp:
            roadmap_path = Path(tmp) / "roadmap.json"
            roadmap_path.write_text(json.dumps(roadmap), encoding="utf-8")
            packet = workflow_roadmap.reconcile(roadmap_path)
            self.assertIn("stale_resource_conflict_status", [item["reason"] for item in packet["blocked_transitions"]])

    def test_reconcile_blocks_exclusive_resource_active_elsewhere(self) -> None:
        roadmap = workflow_roadmap.load(workflow_roadmap.DEFAULT_ROADMAP)
        roadmap["nodes"].append(self.roadmap_node(
            node_id="issue-517-exclusive-resource-proof",
            resource_conflict_status={**self.resource_allow(), "active_elsewhere": True},
        ))
        with tempfile.TemporaryDirectory() as tmp:
            roadmap_path = Path(tmp) / "roadmap.json"
            roadmap_path.write_text(json.dumps(roadmap), encoding="utf-8")
            packet = workflow_roadmap.reconcile(roadmap_path)
            self.assertIn("exclusive_resource_active_elsewhere", [item["reason"] for item in packet["blocked_transitions"]])

    def test_next_excludes_evidence_node_without_resource_authority(self) -> None:
        roadmap = workflow_roadmap.load(workflow_roadmap.DEFAULT_ROADMAP)
        roadmap["nodes"] = [self.roadmap_node(node_id="issue-517-next-resource-missing")]
        packet = workflow_roadmap.next_packet(roadmap)
        self.assertEqual(packet["nodes"], [])

    def test_next_allows_evidence_node_with_resource_authority(self) -> None:
        roadmap = workflow_roadmap.load(workflow_roadmap.DEFAULT_ROADMAP)
        roadmap["nodes"] = [self.roadmap_node(
            node_id="issue-517-next-resource-allow",
            resource_conflict_status=self.resource_allow(),
        )]
        packet = workflow_roadmap.next_packet(roadmap)
        self.assertEqual([node["node_id"] for node in packet["nodes"]], ["issue-517-next-resource-allow"])


if __name__ == "__main__":
    unittest.main()
