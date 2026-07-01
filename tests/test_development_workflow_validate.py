import json
import tempfile
import unittest
from pathlib import Path

from scripts import agent_workflow_map
from scripts import development_workflow_validate as workflow


class DevelopmentWorkflowValidateTests(unittest.TestCase):
    def test_validate_all_fixtures(self) -> None:
        self.assertEqual(workflow.validate_all(), [])

    def test_task_graph_rejects_cycle(self) -> None:
        packet = workflow.load_json(workflow.FIXTURE_DIR / "negative/task-graph--cycle.json")
        errors = workflow.validate_packet(packet, "task-graph")
        self.assertIn("task-graph dependencies must be acyclic", errors)

    def test_worker_closeout_requires_validation_results(self) -> None:
        packet = workflow.load_json(workflow.FIXTURE_DIR / "negative/worker-closeout--missing-validation.json")
        errors = workflow.validate_packet(packet, "worker-closeout")
        self.assertTrue(any("validation_results" in error for error in errors))

    def test_raw_sensitive_data_fails_validation(self) -> None:
        packet = workflow.load_json(workflow.FIXTURE_DIR / "negative/workspace-bootstrap--restricted-data.json")
        errors = workflow.validate_packet(packet, "workspace-bootstrap")
        self.assertIn("workspace-bootstrap packet contains restricted data marker", errors)

    def test_merge_allowed_requires_review_pass(self) -> None:
        packet = workflow.load_json(workflow.FIXTURE_DIR / "positive/merge-decision.json")
        packet["review_decision"] = "REVIEW_CHANGES_REQUESTED"
        errors = workflow.validate_packet(packet, "merge-decision")
        self.assertIn("merge-decision MERGE_ALLOWED requires review_decision REVIEW_PASS", errors)

    def test_validate_user_agreement_command_shape(self) -> None:
        packet = workflow.load_json(workflow.FIXTURE_DIR / "positive/user-agreement.json")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "packet.json"
            path.write_text(json.dumps(packet), encoding="utf-8")
            self.assertEqual(workflow.main(["validate-user-agreement", str(path)]), 0)

    def test_normalize_packet_schema_kind_supports_workflow_aliases(self) -> None:
        self.assertEqual(workflow.normalize_packet_schema_kind("global-review-result"), "review-result")
        self.assertEqual(workflow.normalize_packet_schema_kind("merge-ready-packet"), "merge-decision")
        self.assertIsNone(workflow.normalize_packet_schema_kind("route-decision"))

    def test_workflow_state_references_validate_applicable_packet_schemas(self) -> None:
        bindings = agent_workflow_map.load_json(agent_workflow_map.MAP_PATH)["state_bindings"]
        state_data = {
            "workflow_state": {
                "route": {"status": "ok"},
                "constitution": {"status": "ok"},
                "research": {"status": "ok"},
                "prototype": {"status": "ok"},
                "design": {"status": "ok"},
                "spec_kit": {"status": "ok"},
                "role_gate": {"status": "ok"},
                "execution": {"status": "ok"},
                "validation": {"status": "ok"},
                "review": {"packet_kind": "global-review-result", "packet_ref": "review-result.json"},
                "fix_wave": {"status": "ok"},
                "stage_boundary": {"packet_kind": "stage-boundary-audit", "packet_ref": "stage-boundary-audit.json"},
                "closeout": {"packet_kind": "closeout-packet", "packet_ref": "worker-closeout.json"},
                "merge_ready": {"packet_kind": "merge-ready-packet", "packet_ref": "merge-decision.json"},
                "cleanup": {"status": "ok"},
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for name in (
                "review-result.json",
                "stage-boundary-audit.json",
                "worker-closeout.json",
                "merge-decision.json",
            ):
                source = workflow.FIXTURE_DIR / "positive" / name
                (tmp_path / name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            self.assertEqual(
                workflow.validate_workflow_state_references(state_data, bindings, base_dir=tmp_path),
                [],
            )

    def test_workflow_state_reference_rejects_schema_mismatch(self) -> None:
        bindings = agent_workflow_map.load_json(agent_workflow_map.MAP_PATH)["state_bindings"]
        state_data = {
            "workflow_state": {
                "route": {"status": "ok"},
                "constitution": {"status": "ok"},
                "research": {"status": "ok"},
                "prototype": {"status": "ok"},
                "design": {"status": "ok"},
                "spec_kit": {"status": "ok"},
                "role_gate": {"status": "ok"},
                "execution": {"status": "ok"},
                "validation": {"status": "ok"},
                "review": {"packet_kind": "global-review-result", "packet_ref": "merge-decision.json"},
                "fix_wave": {"status": "ok"},
                "stage_boundary": {"packet_kind": "stage-boundary-audit", "packet_ref": "stage-boundary-audit.json"},
                "closeout": {"packet_kind": "closeout-packet", "packet_ref": "worker-closeout.json"},
                "merge_ready": {"packet_kind": "merge-ready-packet", "packet_ref": "merge-decision.json"},
                "cleanup": {"status": "ok"},
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for name in ("merge-decision.json", "stage-boundary-audit.json", "worker-closeout.json"):
                source = workflow.FIXTURE_DIR / "positive" / name
                (tmp_path / name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            errors = workflow.validate_workflow_state_references(state_data, bindings, base_dir=tmp_path)
        self.assertTrue(any("review-result.decision" in error for error in errors), errors)

    def test_local_workflow_metadata_refs_stay_local_without_schema_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "workflow-state.json").write_text("{}", encoding="utf-8")
            (tmp_path / "worker-state.json").write_text("{}", encoding="utf-8")
            packet = {
                "root_index": {
                    "kind": "workflow-state",
                    "path": "workflow-state.json",
                    "requires_network": False,
                },
                "worker_index": {
                    "kind": "workflow-worker-state",
                    "path": "worker-state.json",
                    "requires_network": False,
                },
            }
            self.assertEqual(
                workflow.validate_local_packet_ref_records(packet, base_dir=tmp_path, root_path="metadata"),
                [],
            )

    def test_local_workflow_metadata_refs_reject_network_paths(self) -> None:
        packet = {
            "worker_index": {
                "kind": "workflow-worker-state",
                "path": "https://example.invalid/worker-state.json",
                "requires_network": False,
            }
        }
        errors = workflow.validate_local_packet_ref_records(packet, root_path="metadata")
        self.assertIn("metadata.worker_index.path must be a local file path", errors)

    def test_local_workflow_metadata_refs_reject_absolute_paths(self) -> None:
        packet = {
            "worker_index": {
                "kind": "workflow-worker-state",
                "path": "/tmp/worker-state.json",
                "requires_network": False,
            }
        }
        errors = workflow.validate_local_packet_ref_records(packet, root_path="metadata")
        self.assertIn("metadata.worker_index.path must not be absolute", errors)

    def test_local_workflow_metadata_refs_reject_traversal_paths(self) -> None:
        packet = {
            "worker_index": {
                "kind": "workflow-worker-state",
                "path": "../outside/worker-state.json",
                "requires_network": False,
            }
        }
        errors = workflow.validate_local_packet_ref_records(packet, root_path="metadata")
        self.assertIn("metadata.worker_index.path must not contain path traversal", errors)


if __name__ == "__main__":
    unittest.main()
