import ast
import copy
import inspect
import json
import tempfile
import unittest
from pathlib import Path

from scripts import agent_workflow_map as workflow_map


class AgentWorkflowMapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = workflow_map.load_json(workflow_map.MAP_PATH)

    def test_validate_all(self) -> None:
        self.assertEqual(workflow_map.validate_all(), [])

    def test_render_mermaid_uses_process_graph_edges(self) -> None:
        rendered = workflow_map.render_mermaid(self.data["process_graph"])
        self.assertEqual(rendered, self.data["generated_mermaid"])
        self.assertIn("global_review --> fix_wave", rendered)

    def test_missing_fix_loop_fails(self) -> None:
        data = copy.deepcopy(self.data)
        data["process_graph"]["edges"] = [
            edge
            for edge in data["process_graph"]["edges"]
            if (edge["from"], edge["to"]) != ("fix_wave", "validation")
        ]
        data["process_graph"]["loop_edges"] = []
        errors = workflow_map.validate_map(data)
        self.assertIn("process_graph.edges missing edge fix_wave -> validation", errors)
        self.assertIn("process_graph.loop_edges must include global_review -> fix_wave -> validation", errors)

    def test_review_policy_requires_global_review_before_closeout_and_merge_ready(self) -> None:
        data = copy.deepcopy(self.data)
        data["review_policy"]["intermediate_review_blockers"] = True
        data["review_policy"]["global_review_required_before"] = ["closeout"]
        errors = workflow_map.validate_map(data)
        self.assertIn("review_policy.intermediate_review_blockers must be false", errors)
        self.assertIn("review_policy.global_review_required_before must require closeout and merge_ready", errors)

    def test_state_bindings_require_fix_wave_mapping(self) -> None:
        data = copy.deepcopy(self.data)
        del data["state_bindings"]["fix_wave"]
        errors = workflow_map.validate_map(data)
        self.assertIn("state_bindings missing required stages: fix_wave", errors)

    def test_dirty_triage_policy_validates_state_names_and_actions(self) -> None:
        data = copy.deepcopy(self.data)
        data["dirty_triage_policy"]["states"]["unsafe_dirty_blocker"]["actions"] = ["wait"]
        del data["dirty_triage_policy"]["states"]["obsolete_cleanup_candidate"]
        errors = workflow_map.validate_map(data)
        self.assertIn("dirty_triage_policy.states must match the required state machine names", errors)
        self.assertIn(
            "dirty_triage_policy.states.unsafe_dirty_blocker.actions must match the planned actions",
            errors,
        )

    def test_worker_state_policy_enforces_per_worker_model(self) -> None:
        data = copy.deepcopy(self.data)
        data["worker_state_policy"]["global_workflow_state_role"] = "worker_writable"
        data["worker_state_policy"]["blocking_gates"] = ["validation"]
        errors = workflow_map.validate_map(data)
        self.assertIn(
            "worker_state_policy.global_workflow_state_role must match the canonical worker-state policy",
            errors,
        )
        self.assertIn(
            "worker_state_policy.blocking_gates must match the canonical worker-state policy",
            errors,
        )

    def test_hook_automation_policy_allows_only_aggregate_refresh_to_touch_index(self) -> None:
        data = copy.deepcopy(self.data)
        data["hook_automation_policy"]["hooks"]["heartbeat"]["writes"] = ["workflow_state_aggregate"]
        del data["hook_automation_policy"]["hooks"]["aggregator_index_refresh"]
        errors = workflow_map.validate_map(data)
        self.assertIn("hook_automation_policy.hooks must match the canonical hook set", errors)
        self.assertIn(
            "hook_automation_policy.hooks.heartbeat.writes must match the canonical hook policy",
            errors,
        )

    def test_validate_state_uses_local_packet_refs_only(self) -> None:
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
                "review": {
                    "packet_kind": "global-review-result",
                    "packet_ref": "review-result.json",
                },
                "fix_wave": {"status": "ok"},
                "stage_boundary": {
                    "packet_kind": "stage-boundary-audit",
                    "packet_ref": "stage-boundary-audit.json",
                },
                "closeout": {
                    "packet_kind": "closeout-packet",
                    "packet_ref": "worker-closeout.json",
                },
                "merge_ready": {
                    "packet_kind": "merge-ready-packet",
                    "packet_ref": "merge-decision.json",
                },
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
                source = workflow_map.PLUGIN_ROOT / "tests/fixtures/development_workflow/positive" / name
                (tmp_path / name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            state_path = tmp_path / "workflow-state.json"
            state_path.write_text(json.dumps(state_data), encoding="utf-8")
            self.assertEqual(
                workflow_map.validate_state_file(self.data, state_data, state_file=state_path),
                [],
            )

    def test_validate_state_rejects_non_local_ref(self) -> None:
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
                "review": {
                    "packet_kind": "global-review-result",
                    "packet_ref": "https://example.invalid/review-result.json",
                },
                "fix_wave": {"status": "ok"},
                "stage_boundary": {
                    "packet_kind": "stage-boundary-audit",
                    "packet_ref": "stage-boundary-audit.json",
                },
                "closeout": {
                    "packet_kind": "closeout-packet",
                    "packet_ref": "worker-closeout.json",
                },
                "merge_ready": {
                    "packet_kind": "merge-ready-packet",
                    "packet_ref": "merge-decision.json",
                },
                "cleanup": {"status": "ok"},
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for name in ("stage-boundary-audit.json", "worker-closeout.json", "merge-decision.json"):
                source = workflow_map.PLUGIN_ROOT / "tests/fixtures/development_workflow/positive" / name
                (tmp_path / name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
            state_path = tmp_path / "workflow-state.json"
            state_path.write_text(json.dumps(state_data), encoding="utf-8")
            errors = workflow_map.validate_state_file(self.data, state_data, state_file=state_path)
        self.assertIn("workflow_state.review.path must be a local file path", errors)

    def test_validate_state_rejects_absolute_worker_state_ref(self) -> None:
        state_data = workflow_map.load_json(
            workflow_map.PLUGIN_ROOT / "tests/fixtures/development_workflow/positive/workflow-state.json"
        )
        state_data["worker_state_refs"][0]["path"] = "/tmp/worker-state.v1.json"
        state_path = workflow_map.PLUGIN_ROOT / "tests/fixtures/development_workflow/positive/workflow-state.json"
        errors = workflow_map.validate_state_file(self.data, state_data, state_file=state_path)
        self.assertIn(
            "workflow-state.worker_state_refs[0].path must not be absolute",
            errors,
        )

    def test_validate_state_rejects_worker_state_ref_traversal(self) -> None:
        state_data = workflow_map.load_json(
            workflow_map.PLUGIN_ROOT / "tests/fixtures/development_workflow/positive/workflow-state.json"
        )
        state_data["worker_state_refs"][0]["path"] = "../outside/worker-state.v1.json"
        state_path = workflow_map.PLUGIN_ROOT / "tests/fixtures/development_workflow/positive/workflow-state.json"
        errors = workflow_map.validate_state_file(self.data, state_data, state_file=state_path)
        self.assertIn(
            "workflow-state.worker_state_refs[0].path must not contain path traversal",
            errors,
        )

    def test_validate_state_accepts_aggregate_index_and_validates_worker_fixture(self) -> None:
        state_path = workflow_map.PLUGIN_ROOT / "tests/fixtures/development_workflow/positive/workflow-state.json"
        state_data = workflow_map.load_json(state_path)
        self.assertEqual(
            workflow_map.validate_state_file(self.data, state_data, state_file=state_path),
            [],
        )


    def test_validate_state_rejects_bad_format_values(self) -> None:
        state_path = workflow_map.PLUGIN_ROOT / "tests/fixtures/development_workflow/positive/workflow-state.json"
        state_data = workflow_map.load_json(state_path)
        state_data["generated_at"] = "not-a-datetime"
        state_data["active_prs"][0]["url"] = "not a uri"
        errors = workflow_map.validate_state_file(self.data, state_data, state_file=state_path)
        self.assertTrue(any("workflow-state.generated_at" in error for error in errors), errors)
        self.assertTrue(any("workflow-state.active_prs[0].url" in error for error in errors), errors)

    def test_validate_worker_state_rejects_bad_date_time_format(self) -> None:
        worker_path = workflow_map.PLUGIN_ROOT / "tests/fixtures/development_workflow/positive/worker-state.json"
        worker_data = workflow_map.load_json(worker_path)
        worker_data["heartbeat"]["last_seen"] = "not-a-datetime"
        errors = workflow_map.validate_worker_state_file(self.data, worker_data, state_file=worker_path)
        self.assertTrue(any("worker-state.heartbeat.last_seen" in error for error in errors), errors)

    def test_validate_worker_state_enforces_hundreds_safe_hook_writes(self) -> None:
        worker_path = workflow_map.PLUGIN_ROOT / "tests/fixtures/development_workflow/positive/worker-state.json"
        worker_data = workflow_map.load_json(worker_path)
        self.assertEqual(
            workflow_map.validate_worker_state_file(self.data, worker_data, state_file=worker_path),
            [],
        )
        broken = copy.deepcopy(worker_data)
        broken["hook_events"][0]["write_scope"] = "aggregate_index"
        errors = workflow_map.validate_worker_state_file(self.data, broken, state_file=worker_path)
        self.assertIn(
            "worker-state.hook_events[0].write_scope must be own_worker_state for worker-local hooks",
            errors,
        )

    def test_validate_code_avoids_forbidden_runtime_imports(self) -> None:
        source = inspect.getsource(workflow_map)
        tree = ast.parse(source)
        forbidden_imports = {"subprocess", "socket", "urllib", "requests", "http", "http.client"}
        seen_imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                seen_imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                seen_imports.add(node.module)
        self.assertTrue(forbidden_imports.isdisjoint(seen_imports), seen_imports)
        for forbidden_token in ("git ", " gh ", "curl ", "ssh "):
            self.assertNotIn(forbidden_token, source)


if __name__ == "__main__":
    unittest.main()
