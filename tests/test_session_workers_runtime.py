from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PLUGIN_ROOT / "scripts" / "session_workers_runtime.py"
spec = importlib.util.spec_from_file_location("session_workers_runtime", SCRIPT_PATH)
runtime_module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(runtime_module)  # type: ignore[arg-type]


class SessionWorkersRuntimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = runtime_module.load_json(PLUGIN_ROOT / "assets" / "catalog" / "session-workers-runtime.v1.json")
        cls.role_catalog = runtime_module.load_json(PLUGIN_ROOT / "assets" / "catalog" / "platform-role-catalog.v1.json")

    def test_current_catalog_validates(self) -> None:
        self.assertEqual(runtime_module.validate_catalog(self.catalog, self.role_catalog), [])

    def test_cli_validate_success_has_clean_stderr(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "validate"],
            cwd=PLUGIN_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        self.assertIn("session worker runtime catalog ok", result.stdout)

    def test_cli_missing_catalog_has_stable_stderr(self) -> None:
        missing_catalog = PLUGIN_ROOT / "tmp-missing-session-workers-runtime.json"
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--catalog", str(missing_catalog), "validate"],
            cwd=PLUGIN_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr.strip(), f"ERROR: catalog not found: {missing_catalog}")
        self.assertNotIn("[Errno", result.stderr)

    def test_cli_missing_role_catalog_has_stable_stderr(self) -> None:
        missing_catalog = PLUGIN_ROOT / "tmp-missing-platform-role-catalog.json"
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--role-catalog", str(missing_catalog), "validate"],
            cwd=PLUGIN_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr.strip(), f"ERROR: catalog not found: {missing_catalog}")
        self.assertNotIn("[Errno", result.stderr)

    def test_rejects_missing_lane(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["worker_lanes"] = [lane for lane in catalog["worker_lanes"] if lane["lane"] != "review"]
        errors = runtime_module.validate_catalog(catalog, self.role_catalog)
        self.assertTrue(any("canonical lanes" in error for error in errors))

    def test_rejects_global_implement_rule(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["implementation_lane_policy"]["rule"] = "/speckit-implement is the global executor."
        errors = runtime_module.validate_catalog(catalog, self.role_catalog)
        self.assertTrue(any("not global" in error for error in errors))

    def test_records_fanout_thread_limit_runtime_preflight(self) -> None:
        concurrency = self.catalog["concurrency_policy"]
        self.assertIn("count active workers and open workers", concurrency["fanout_preflight_rule"])
        self.assertIn("close completed no-longer-needed workers", concurrency["fanout_preflight_rule"])
        self.assertIn("reserve critical-path wait slots", concurrency["fanout_preflight_rule"])
        self.assertIn("spawn bounded batches", concurrency["fanout_preflight_rule"])
        self.assertEqual(
            set(concurrency["fanout_counted_worker_states"]["active"]),
            {"claimed", "running", "waiting", "blocked", "stale"},
        )
        self.assertEqual(
            set(concurrency["fanout_counted_worker_states"]["open"]),
            {"claimed", "running", "waiting", "blocked", "stale", "completed"},
        )
        self.assertEqual(set(concurrency["fanout_counted_worker_states"]["closed"]), {"closed"})
        self.assertTrue(concurrency["critical_path_wait_slots_reserved"])
        self.assertEqual(concurrency["thread_limit_failure_classification"], "WORKFLOW_DRIFT")
        self.assertFalse(concurrency["thread_limit_failure_normal_recovery_allowed"])

    def test_records_capacity_fallback_partial_state_reconciliation(self) -> None:
        reconciliation = self.catalog["concurrency_policy"]["capacity_fallback_reconciliation"]
        self.assertTrue(reconciliation["required_before_capacity_fallback"])
        self.assertIn("Before capacity fallback", reconciliation["rule"])
        self.assertIn("unknown or completed-open agents are not free capacity", reconciliation["rule"])
        self.assertEqual(
            [bucket["bucket"] for bucket in reconciliation["buckets"]],
            runtime_module.PARTIAL_STATE_BUCKET_ORDER,
        )
        for bucket in reconciliation["buckets"]:
            self.assertEqual(
                set(bucket["source_states"]),
                runtime_module.PARTIAL_STATE_BUCKET_SOURCE_STATES[bucket["bucket"]],
            )
            self.assertFalse(bucket["counts_as_free_capacity"])
        self.assertEqual(
            set(reconciliation["fallback_blocking_buckets"]),
            runtime_module.CAPACITY_BLOCKING_PARTIAL_BUCKETS,
        )
        self.assertIn("Only closed workers are free capacity", reconciliation["free_capacity_rule"])
        self.assertIn("same task id", reconciliation["duplicate_launch_rule"])

    def test_rejects_fanout_thread_limit_runtime_drift_gap(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        concurrency = catalog["concurrency_policy"]
        concurrency["fanout_preflight_rule"] = "count active workers only"
        concurrency["fanout_counted_worker_states"]["open"].remove("completed")
        concurrency["critical_path_wait_slots_reserved"] = False
        concurrency["thread_limit_failure_classification"] = "NORMAL_RECOVERY"
        concurrency["thread_limit_failure_normal_recovery_allowed"] = True

        errors = runtime_module.validate_catalog(catalog, self.role_catalog)

        self.assertTrue(any("fanout_preflight_rule missing" in error for error in errors), errors)
        self.assertTrue(any("open must match fanout open states" in error for error in errors), errors)
        self.assertTrue(any("critical_path_wait_slots_reserved must be true" in error for error in errors), errors)
        self.assertTrue(any("thread_limit_failure_classification must be WORKFLOW_DRIFT" in error for error in errors), errors)
        self.assertTrue(any("thread_limit_failure_normal_recovery_allowed must be false" in error for error in errors), errors)

    def test_rejects_missing_capacity_fallback_reconciliation_rule(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        del catalog["concurrency_policy"]["capacity_fallback_reconciliation"]

        errors = runtime_module.validate_catalog(catalog, self.role_catalog)

        self.assertTrue(any("capacity_fallback_reconciliation must be an object" in error for error in errors), errors)

    def test_rejects_weakened_capacity_fallback_reconciliation(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        reconciliation = catalog["concurrency_policy"]["capacity_fallback_reconciliation"]
        reconciliation["rule"] = "Before capacity fallback, count active only."
        reconciliation["buckets"][1]["counts_as_free_capacity"] = True
        reconciliation["buckets"][3]["source_states"].remove("unknown")
        reconciliation["fallback_blocking_buckets"].remove("unknown-needs-refresh")
        reconciliation["free_capacity_rule"] = "Completed workers are free capacity."
        reconciliation["duplicate_launch_rule"] = "Launch another worker."
        reconciliation["required_evidence_checks"] = ["Inspect session tail."]

        errors = runtime_module.validate_catalog(catalog, self.role_catalog)

        self.assertTrue(any("rule missing session tail" in error for error in errors), errors)
        self.assertTrue(any("counts_as_free_capacity must be false" in error for error in errors), errors)
        self.assertTrue(any("source_states must match canonical source states" in error for error in errors), errors)
        self.assertTrue(any("fallback_blocking_buckets must block every partial-state bucket" in error for error in errors), errors)
        self.assertTrue(any("free_capacity_rule missing unknown" in error for error in errors), errors)
        self.assertTrue(any("duplicate_launch_rule must block duplicate launch" in error for error in errors), errors)
        self.assertTrue(any("required_evidence_checks missing task_complete" in error for error in errors), errors)

    def test_reconciles_completed_unknown_failed_and_active_partial_states(self) -> None:
        buckets = runtime_module.reconcile_partial_subagent_states(
            [
                {"worker_id": "worker-running", "status": "running"},
                {"worker_id": "worker-claimed", "state": "claimed"},
                {"worker_id": "worker-completed-open", "status": "completed"},
                {"worker_id": "worker-unknown", "status": "unknown"},
                {"worker_id": "worker-missing"},
                {"worker_id": "worker-failed", "status": "errored"},
                {"worker_id": "worker-capacity", "status": "capacity_error"},
                {"worker_id": "worker-blocked", "status": "blocked"},
            ]
        )

        self.assertEqual(buckets["active"], ["worker-running", "worker-claimed"])
        self.assertEqual(buckets["completed-needs-close"], ["worker-completed-open"])
        self.assertEqual(buckets["unknown-needs-refresh"], ["worker-unknown", "worker-missing"])
        self.assertEqual(buckets["failed-needs-review"], ["worker-failed", "worker-capacity"])
        self.assertEqual(buckets["blocked-needs-parent-action"], ["worker-blocked"])

    def test_completed_open_and_unknown_do_not_free_capacity(self) -> None:
        buckets = runtime_module.reconcile_partial_subagent_states(
            [
                {"worker_id": "worker-completed-open", "status": "completed"},
                {"worker_id": "worker-unknown", "status": "unknown"},
            ]
        )

        self.assertEqual(
            runtime_module.capacity_blocking_worker_ids(buckets),
            ["worker-completed-open", "worker-unknown"],
        )

    def test_runtime_accepts_fresh_worker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            self._write_runtime_fixture(runtime_dir)
            errors = runtime_module.validate_runtime(runtime_dir, self.catalog, self.role_catalog)
            self.assertEqual(errors, [])

    def test_runtime_rejects_lane_role_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            self._write_runtime_fixture(runtime_dir)
            session_workers = json.loads((runtime_dir / "session-workers.json").read_text())
            session_workers["workers"][0]["registered_role"] = "bears-auth-platform-engineer"
            (runtime_dir / "session-workers.json").write_text(json.dumps(session_workers))
            errors = runtime_module.validate_runtime(runtime_dir, self.catalog, self.role_catalog)
            self.assertTrue(any("not allowed for lane docs" in error for error in errors))

    def test_runtime_rejects_incompatible_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            self._write_runtime_fixture(runtime_dir)
            session_workers = json.loads((runtime_dir / "session-workers.json").read_text())
            session_workers["workers"][0]["resume_policy"] = {
                "requested_action": "resume",
                "reuse_key": session_workers["workers"][0]["reuse_key"],
                "compatibility": {
                    "goal_compatible": False,
                    "roadmap_compatible": False,
                    "lane_compatible": True,
                    "role_compatible": True,
                    "scope_compatible": False,
                    "repo_state_compatible": True,
                    "spec_kit_snapshot_compatible": True,
                    "roadmap_slice_compatible": True
                },
                "bounded_prior_evidence": ["previous closeout"],
                "reason": "scope changed"
            }
            (runtime_dir / "session-workers.json").write_text(json.dumps(session_workers))
            errors = runtime_module.validate_runtime(runtime_dir, self.catalog, self.role_catalog)
            self.assertTrue(any("requires all compatibility fields true" in error for error in errors))

    def test_runtime_rejects_spec_snapshot_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            self._write_runtime_fixture(runtime_dir)
            session_workers = json.loads((runtime_dir / "session-workers.json").read_text())
            session_workers["workers"][0]["spec_kit_snapshot"]["spec_id"] = "006-other-spec"
            (runtime_dir / "session-workers.json").write_text(json.dumps(session_workers))
            errors = runtime_module.validate_runtime(runtime_dir, self.catalog, self.role_catalog)
            self.assertTrue(any("spec_id must match worker spec_id" in error for error in errors))

    def test_runtime_rejects_stale_reuse_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            self._write_runtime_fixture(runtime_dir)
            session_workers = json.loads((runtime_dir / "session-workers.json").read_text())
            session_workers["workers"][0]["roadmap_slice"] = "changed-roadmap-slice"
            (runtime_dir / "session-workers.json").write_text(json.dumps(session_workers))
            errors = runtime_module.validate_runtime(runtime_dir, self.catalog, self.role_catalog)
            self.assertTrue(any("reuse_key must be deterministic" in error for error in errors))

    def test_runtime_rejects_missing_reuse_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            self._write_runtime_fixture(runtime_dir)
            (runtime_dir / "session-reuse-index.json").unlink()
            errors = runtime_module.validate_runtime(runtime_dir, self.catalog, self.role_catalog)
            self.assertTrue(any("missing runtime artifact" in error and "session-reuse-index.json" in error for error in errors))

    def test_runtime_accepts_concurrent_disjoint_specs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            self._write_runtime_fixture(runtime_dir)
            self._append_second_worker(runtime_dir)
            errors = runtime_module.validate_runtime(runtime_dir, self.catalog, self.role_catalog)
            self.assertEqual(errors, [])

    def test_runtime_rejects_concurrent_overlapping_scope_locks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            self._write_runtime_fixture(runtime_dir)
            self._append_second_worker(runtime_dir)
            scope_locks = json.loads((runtime_dir / "scope-locks.json").read_text())
            scope_locks["locks"][1]["target_path"] = "plugins/bears/docs/reference/session-workers-runtime.md"
            (runtime_dir / "scope-locks.json").write_text(json.dumps(scope_locks))
            errors = runtime_module.validate_runtime(runtime_dir, self.catalog, self.role_catalog)
            self.assertTrue(any("overlapping active scope lock" in error for error in errors))

    def test_runtime_rejects_audit_worker_with_parent_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            self._write_runtime_fixture(runtime_dir)
            self._append_audit_worker(runtime_dir, parent_context_allowed=True)
            errors = runtime_module.validate_runtime(runtime_dir, self.catalog, self.role_catalog)
            self.assertTrue(any("parent_context_allowed must be false for audit lane" in error for error in errors))

    def test_runtime_rejects_audit_resume_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            self._write_runtime_fixture(runtime_dir)
            self._append_audit_worker(runtime_dir, parent_context_allowed=False)
            session_workers = json.loads((runtime_dir / "session-workers.json").read_text())
            session_workers["workers"][1]["resume_policy"]["requested_action"] = "reuse"
            session_workers["workers"][1]["resume_policy"]["compatibility"] = {
                "goal_compatible": True,
                "roadmap_compatible": True,
                "lane_compatible": True,
                "role_compatible": True,
                "scope_compatible": True,
                "repo_state_compatible": True,
                "spec_kit_snapshot_compatible": True,
                "roadmap_slice_compatible": True
            }
            (runtime_dir / "session-workers.json").write_text(json.dumps(session_workers))
            errors = runtime_module.validate_runtime(runtime_dir, self.catalog, self.role_catalog)
            self.assertTrue(any("requested_action must be fresh for audit lane" in error for error in errors))

    def test_catalog_rejects_missing_goal_worker_requirement(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["worker_contract"]["required_fields"].remove("goal_id")
        errors = runtime_module.validate_catalog(catalog, self.role_catalog)
        self.assertTrue(any("canonical worker field set" in error for error in errors))

    def test_catalog_rejects_missing_goal_reuse_compatibility(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["resume_fork_rule"]["compatibility_fields"].remove("goal_compatible")
        errors = runtime_module.validate_catalog(catalog, self.role_catalog)
        self.assertTrue(any("canonical compatibility field set" in error for error in errors))

    def test_catalog_requires_validate_runtime_before_reuse_or_fork(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        del catalog["resume_fork_rule"]["required_pre_action_validation"]
        errors = runtime_module.validate_catalog(catalog, self.role_catalog)
        self.assertTrue(any("required_pre_action_validation" in error for error in errors), errors)

    def test_runtime_rejects_reuse_without_validate_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            self._write_runtime_fixture(runtime_dir)
            session_workers = json.loads((runtime_dir / "session-workers.json").read_text())
            worker = session_workers["workers"][0]
            worker["resume_policy"]["requested_action"] = "reuse"
            worker["resume_policy"]["compatibility"] = {
                "goal_compatible": True,
                "roadmap_compatible": True,
                "lane_compatible": True,
                "role_compatible": True,
                "scope_compatible": True,
                "repo_state_compatible": True,
                "spec_kit_snapshot_compatible": True,
                "roadmap_slice_compatible": True
            }
            worker["resume_policy"].pop("pre_action_validation", None)
            (runtime_dir / "session-workers.json").write_text(json.dumps(session_workers))
            errors = runtime_module.validate_runtime(runtime_dir, self.catalog, self.role_catalog)
            self.assertTrue(any("pre_action_validation" in error for error in errors), errors)

    def test_runtime_accepts_reuse_after_validate_runtime_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            self._write_runtime_fixture(runtime_dir)
            session_workers = json.loads((runtime_dir / "session-workers.json").read_text())
            worker = session_workers["workers"][0]
            worker["resume_policy"]["requested_action"] = "reuse"
            worker["resume_policy"]["compatibility"] = {
                "goal_compatible": True,
                "roadmap_compatible": True,
                "lane_compatible": True,
                "role_compatible": True,
                "scope_compatible": True,
                "repo_state_compatible": True,
                "spec_kit_snapshot_compatible": True,
                "roadmap_slice_compatible": True
            }
            worker["resume_policy"]["pre_action_validation"] = {
                "command": runtime_module.REQUIRED_RUNTIME_VALIDATION_COMMAND,
                "exit_code": 0,
                "compatibility_status": "compatible"
            }
            (runtime_dir / "session-workers.json").write_text(json.dumps(session_workers))
            errors = runtime_module.validate_runtime(runtime_dir, self.catalog, self.role_catalog)
            self.assertEqual(errors, [])

    def test_catalog_rejects_weakened_audit_policy(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["audit_lane_policy"]["reuse_allowed"] = True
        errors = runtime_module.validate_catalog(catalog, self.role_catalog)
        self.assertTrue(any("reuse_allowed must be false" in error for error in errors))

    def test_catalog_records_parallel_audit_and_wait_checkpoint_policy(self) -> None:
        audit = self.catalog["audit_lane_policy"]["parallel_monitoring"]
        self.assertEqual(audit["implementation_authority"], "forbidden")
        self.assertEqual(audit["blocks_main_workflow"], "hard_stop_only")
        wait_policy = self.catalog["wait_checkpoint_policy"]
        self.assertEqual(wait_policy["long_wait_call"], "wait_agent")
        self.assertEqual(set(wait_policy["required_before_wait_fields"]), runtime_module.WAIT_CHECKPOINT_REQUIRED_FIELDS)
        self.assertEqual(set(wait_policy["first_timeout_checkpoint_fields"]), runtime_module.WAIT_CHECKPOINT_FIRST_TIMEOUT_FIELDS)
        self.assertEqual(set(wait_policy["required_after_wait_result_fields"]), runtime_module.WAIT_RESULT_REQUIRED_FIELDS)
        self.assertEqual(wait_policy["target_mismatch_code"], runtime_module.WAIT_TARGET_MISMATCH_CODE)
        self.assertEqual(
            set(wait_policy["target_mismatch_next_safe_actions"]),
            runtime_module.WAIT_TARGET_MISMATCH_NEXT_SAFE_ACTIONS,
        )
        self.assertIn("After every wait_agent", wait_policy["target_mismatch_rule"])
        self.assertIn("out-of-band notifications", wait_policy["stage_advance_rule"])
        self.assertIn("plain waiting is not accepted", wait_policy["final_integration_rule"])

    def test_catalog_rejects_wait_policy_without_target_mismatch_guard(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["wait_checkpoint_policy"]["target_mismatch_code"] = ""
        catalog["wait_checkpoint_policy"]["target_mismatch_next_safe_actions"].remove("interrupt_original_agents")
        catalog["wait_checkpoint_policy"]["stage_advance_rule"] = "Parent may advance after any completion."
        errors = runtime_module.validate_catalog(catalog, self.role_catalog)
        self.assertTrue(any("target_mismatch_code must be WAIT_AGENT_TARGET_MISMATCH" in error for error in errors), errors)
        self.assertTrue(any("target_mismatch_next_safe_actions" in error for error in errors), errors)
        self.assertTrue(any("stage_advance_rule" in error for error in errors), errors)

    def test_catalog_rejects_wait_policy_without_delayed_integration(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["wait_checkpoint_policy"]["repeated_empty_timeout_actions"].remove("delayed_integration")
        errors = runtime_module.validate_catalog(catalog, self.role_catalog)
        self.assertTrue(any("canonical fallback actions" in error for error in errors), errors)

    def test_runtime_rejects_waiting_worker_without_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            self._write_runtime_fixture(runtime_dir)
            self._mark_worker_waiting(runtime_dir)
            errors = runtime_module.validate_runtime(runtime_dir, self.catalog, self.role_catalog)
            self.assertTrue(any("wait_checkpoint must be an object" in error for error in errors), errors)

    def test_runtime_accepts_waiting_worker_with_repeated_timeout_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            self._write_runtime_fixture(runtime_dir)
            self._mark_worker_waiting(runtime_dir, wait_checkpoint={
                "target_agent": "security-reviewer",
                "expected_artifact": "security review closeout packet",
                "owner_lane": "review",
                "timeout": "600s",
                "fallback_action": "emit checkpoint after first timeout",
                "timeout_count": 2,
                "waiting_for": "security-reviewer",
                "owner": "review lane",
                "needed_artifact": "security review closeout packet",
                "next_action_if_timeout_repeats": "run local read-only validation",
                "repeated_timeout_action": "local_read_only_check"
            })
            errors = runtime_module.validate_runtime(runtime_dir, self.catalog, self.role_catalog)
            self.assertEqual(errors, [])

    def test_runtime_rejects_blocker_escalation_without_blocker_definition_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            self._write_runtime_fixture(runtime_dir)
            self._mark_worker_waiting(runtime_dir, wait_checkpoint={
                "target_agent": "security-reviewer",
                "expected_artifact": "security review closeout packet",
                "owner_lane": "review",
                "timeout": "600s",
                "fallback_action": "emit checkpoint after first timeout",
                "timeout_count": 2,
                "waiting_for": "security-reviewer",
                "owner": "review lane",
                "needed_artifact": "security review closeout packet",
                "next_action_if_timeout_repeats": "escalate only a real blocker",
                "repeated_timeout_action": "blocker_escalation"
            })
            errors = runtime_module.validate_runtime(runtime_dir, self.catalog, self.role_catalog)
            self.assertTrue(any("blocker_definition_match must be true" in error for error in errors), errors)

    def test_runtime_rejects_wait_result_mismatch_that_advances_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            self._write_runtime_fixture(runtime_dir)
            self._mark_worker_waiting(runtime_dir, wait_checkpoint={
                "target_agent": "security-reviewer",
                "expected_artifact": "security review closeout packet",
                "owner_lane": "review",
                "timeout": "600s",
                "fallback_action": "emit checkpoint after first timeout",
                "wait_result_validation": {
                    "requested_target_ids": ["agent-requested"],
                    "returned_status_ids": ["agent-unrelated"],
                    "matching_target_ids": [],
                    "stage_advance_allowed": True,
                    "mismatch_code": "",
                    "next_safe_action": "launch_dependent_work"
                }
            })
            errors = runtime_module.validate_runtime(runtime_dir, self.catalog, self.role_catalog)
            self.assertTrue(any("stage_advance_allowed must be false" in error for error in errors), errors)
            self.assertTrue(any("mismatch_code must be WAIT_AGENT_TARGET_MISMATCH" in error for error in errors), errors)
            self.assertTrue(any("next_safe_action must keep waiting" in error for error in errors), errors)

    def test_runtime_accepts_wait_result_mismatch_when_parent_keeps_original_agents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            self._write_runtime_fixture(runtime_dir)
            self._mark_worker_waiting(runtime_dir, wait_checkpoint={
                "target_agent": "security-reviewer",
                "expected_artifact": "security review closeout packet",
                "owner_lane": "review",
                "timeout": "600s",
                "fallback_action": "emit checkpoint after first timeout",
                "wait_result_validation": {
                    "requested_target_ids": ["agent-requested"],
                    "returned_status_ids": ["agent-unrelated"],
                    "matching_target_ids": [],
                    "stage_advance_allowed": False,
                    "mismatch_code": runtime_module.WAIT_TARGET_MISMATCH_CODE,
                    "next_safe_action": "keep_waiting_original_agents"
                }
            })
            errors = runtime_module.validate_runtime(runtime_dir, self.catalog, self.role_catalog)
            self.assertEqual(errors, [])

    def test_runtime_rejects_wait_result_with_wrong_matching_target_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            self._write_runtime_fixture(runtime_dir)
            self._mark_worker_waiting(runtime_dir, wait_checkpoint={
                "target_agent": "security-reviewer",
                "expected_artifact": "security review closeout packet",
                "owner_lane": "review",
                "timeout": "600s",
                "fallback_action": "emit checkpoint after first timeout",
                "wait_result_validation": {
                    "requested_target_ids": ["agent-requested", "agent-other"],
                    "returned_status_ids": ["agent-requested", "agent-unrelated"],
                    "matching_target_ids": ["agent-other"],
                    "stage_advance_allowed": True,
                    "mismatch_code": "",
                    "next_safe_action": "accept_matching_wait_result"
                }
            })
            errors = runtime_module.validate_runtime(runtime_dir, self.catalog, self.role_catalog)
            self.assertTrue(any("matching_target_ids must equal" in error for error in errors), errors)


    def test_runtime_rejects_closeout_cyrillic_artifact_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            self._write_runtime_fixture(runtime_dir)
            closeout_path = runtime_dir / "workers" / "docs-001" / "worker-closeout.json"
            closeout = json.loads(closeout_path.read_text())
            closeout["summary"] = "\u0413\u043e\u0442\u043e\u0432\u043e"
            closeout_path.write_text(json.dumps(closeout))

            errors = runtime_module.validate_runtime(runtime_dir, self.catalog, self.role_catalog)

            self.assertTrue(any("English-only artifact text" in error for error in errors), errors)

    def test_runtime_rejects_passing_closeout_with_blocking_limitation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            self._write_runtime_fixture(runtime_dir)
            closeout_path = runtime_dir / "workers" / "docs-001" / "worker-closeout.json"
            closeout = json.loads(closeout_path.read_text())
            closeout["limitations"] = [
                {
                    "code": "TEST_NOT_RUN_DIRTY_CHECKOUT",
                    "severity": "blocking",
                    "details": "Shared checkout was dirty and no fresh checkout was available."
                }
            ]
            closeout_path.write_text(json.dumps(closeout))

            errors = runtime_module.validate_runtime(runtime_dir, self.catalog, self.role_catalog)

            self.assertTrue(any("blocking limitation" in error for error in errors), errors)

    def test_runtime_rejects_review_closeout_without_clean_checkout_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            self._write_runtime_fixture(runtime_dir)
            session_workers_path = runtime_dir / "session-workers.json"
            session_workers = json.loads(session_workers_path.read_text())
            worker = session_workers["workers"][0]
            worker["lane"] = "review"
            worker["registered_role"] = "bears-platform-security-reviewer"
            worker["reuse_key"] = runtime_module.reuse_key(worker)
            worker["resume_policy"]["reuse_key"] = worker["reuse_key"]
            session_workers_path.write_text(json.dumps(session_workers))

            orchestration_path = runtime_dir / "orchestration-state.json"
            orchestration = json.loads(orchestration_path.read_text())
            orchestration["workers_by_state"]["running"] = ["docs-001"]
            orchestration_path.write_text(json.dumps(orchestration))

            scope_locks_path = runtime_dir / "scope-locks.json"
            scope_locks = json.loads(scope_locks_path.read_text())
            scope_locks["locks"][0]["lane"] = "review"
            scope_locks_path.write_text(json.dumps(scope_locks))

            heartbeat_path = runtime_dir / "workers" / "docs-001" / "worker-heartbeat.json"
            heartbeat = json.loads(heartbeat_path.read_text())
            heartbeat["lane"] = "review"
            heartbeat["registered_role"] = "bears-platform-security-reviewer"
            heartbeat_path.write_text(json.dumps(heartbeat))

            closeout_path = runtime_dir / "workers" / "docs-001" / "worker-closeout.json"
            closeout = json.loads(closeout_path.read_text())
            closeout["lane"] = "review"
            closeout["registered_role"] = "bears-platform-security-reviewer"
            closeout_path.write_text(json.dumps(closeout))
            self._write_reuse_index(runtime_dir)

            errors = runtime_module.validate_runtime(runtime_dir, self.catalog, self.role_catalog)

            self.assertTrue(any("checkout is required for review and audit closeouts" in error for error in errors), errors)

    def test_runtime_rejects_plain_waiting_as_completed_closeout_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            self._write_runtime_fixture(runtime_dir)
            closeout_path = runtime_dir / "workers" / "docs-001" / "worker-closeout.json"
            closeout = json.loads(closeout_path.read_text())
            closeout["evidence"] = ["waiting"]
            closeout_path.write_text(json.dumps(closeout))
            errors = runtime_module.validate_runtime(runtime_dir, self.catalog, self.role_catalog)
            self.assertTrue(any("evidence artifacts, not plain waiting" in error for error in errors), errors)

    def test_runtime_rejects_missing_required_worker_goal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            self._write_runtime_fixture(runtime_dir)
            session_workers = json.loads((runtime_dir / "session-workers.json").read_text())
            del session_workers["workers"][0]["goal_id"]
            (runtime_dir / "session-workers.json").write_text(json.dumps(session_workers))
            errors = runtime_module.validate_runtime(runtime_dir, self.catalog, self.role_catalog)
            self.assertTrue(any("missing fields: goal_id" in error for error in errors))

    def test_runtime_rejects_missing_pre_task_authorization_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            self._write_runtime_fixture(runtime_dir)
            session_workers = json.loads((runtime_dir / "session-workers.json").read_text())
            actions = session_workers["workers"][0]["pre_task_hook"]["task_start_authorization"]["authorized_actions"]
            actions.remove("close")
            (runtime_dir / "session-workers.json").write_text(json.dumps(session_workers))
            errors = runtime_module.validate_runtime(runtime_dir, self.catalog, self.role_catalog)
            self.assertTrue(any("authorized_actions missing actions: close" in error for error in errors))


    def test_runtime_rejects_reuse_index_missing_continuation_ref(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            self._write_runtime_fixture(runtime_dir)
            reuse_index = json.loads((runtime_dir / "session-reuse-index.json").read_text())
            del reuse_index["entries"][0]["continuation_packet_ref"]
            (runtime_dir / "session-reuse-index.json").write_text(json.dumps(reuse_index))

            errors = runtime_module.validate_runtime(runtime_dir, self.catalog, self.role_catalog)

            self.assertTrue(any("continuation_packet_ref" in error for error in errors), errors)

    def test_runtime_rejects_reuse_decision_with_restricted_data_taint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            self._write_runtime_fixture(runtime_dir)
            reuse_index = json.loads((runtime_dir / "session-reuse-index.json").read_text())
            reuse_index["entries"][0]["selection_decision"] = "reuse"
            reuse_index["entries"][0]["restricted_data_taint"] = True
            (runtime_dir / "session-reuse-index.json").write_text(json.dumps(reuse_index))

            errors = runtime_module.validate_runtime(runtime_dir, self.catalog, self.role_catalog)

            self.assertTrue(any("restricted_data_taint must be false" in error for error in errors), errors)

    def test_runtime_rejects_missing_reuse_index_goal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            self._write_runtime_fixture(runtime_dir)
            reuse_index = json.loads((runtime_dir / "session-reuse-index.json").read_text())
            del reuse_index["entries"][0]["goal_id"]
            (runtime_dir / "session-reuse-index.json").write_text(json.dumps(reuse_index))
            errors = runtime_module.validate_runtime(runtime_dir, self.catalog, self.role_catalog)
            self.assertTrue(any("session-reuse-index.entries[0].goal_id" in error for error in errors))

    def test_runtime_rejects_audit_wrong_context_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            self._write_runtime_fixture(runtime_dir)
            self._append_audit_worker(runtime_dir, parent_context_allowed=False)
            session_workers = json.loads((runtime_dir / "session-workers.json").read_text())
            session_workers["workers"][1]["context_policy"] = "bounded_current_task"
            session_workers["workers"][1]["pre_task_hook"]["context_policy"] = "bounded_current_task"
            (runtime_dir / "session-workers.json").write_text(json.dumps(session_workers))
            errors = runtime_module.validate_runtime(runtime_dir, self.catalog, self.role_catalog)
            self.assertTrue(any("context_policy must be fresh_no_parent_context for audit lane" in error for error in errors))

    def test_runtime_rejects_audit_parent_worker_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runtime_dir = Path(tmp)
            self._write_runtime_fixture(runtime_dir)
            self._append_audit_worker(runtime_dir, parent_context_allowed=False)
            session_workers = json.loads((runtime_dir / "session-workers.json").read_text())
            session_workers["workers"][1]["parent_worker_id"] = "docs-001"
            session_workers["workers"][1]["pre_task_hook"]["parent_worker_id"] = "docs-001"
            (runtime_dir / "session-workers.json").write_text(json.dumps(session_workers))
            errors = runtime_module.validate_runtime(runtime_dir, self.catalog, self.role_catalog)
            self.assertTrue(any("parent_worker_id is forbidden for audit lane" in error for error in errors))

    def _mark_worker_waiting(self, runtime_dir: Path, *, wait_checkpoint: dict[str, object] | None = None) -> None:
        session_workers = json.loads((runtime_dir / "session-workers.json").read_text())
        session_workers["workers"][0]["status"] = "waiting"
        (runtime_dir / "session-workers.json").write_text(json.dumps(session_workers))
        heartbeat_path = runtime_dir / "workers" / "docs-001" / "worker-heartbeat.json"
        heartbeat = json.loads(heartbeat_path.read_text())
        heartbeat["status"] = "waiting"
        if wait_checkpoint is not None:
            heartbeat["wait_checkpoint"] = wait_checkpoint
        heartbeat_path.write_text(json.dumps(heartbeat))
        orchestration = json.loads((runtime_dir / "orchestration-state.json").read_text())
        orchestration["workers_by_state"]["running"] = []
        orchestration["workers_by_state"]["waiting"] = ["docs-001"]
        (runtime_dir / "orchestration-state.json").write_text(json.dumps(orchestration))
        scope_locks = json.loads((runtime_dir / "scope-locks.json").read_text())
        scope_locks["locks"][0]["status"] = "waiting"
        (runtime_dir / "scope-locks.json").write_text(json.dumps(scope_locks))
        self._write_reuse_index(runtime_dir)

    def _write_runtime_fixture(self, runtime_dir: Path) -> None:
        workers_dir = runtime_dir / "workers" / "docs-001"
        workers_dir.mkdir(parents=True, exist_ok=True)

        pre_task_hook = {
            "hook_id": "pre-task-docs-001",
            "task_id": "T-session-runtime-docs",
            "task_path": "specs/005-telegram-workflow-plugin/tasks.md",
            "goal_id": "goal-005",
            "roadmap_id": "roadmap-telegram-workflow",
            "questionnaire_ref": "questionnaire/session-runtime-005",
            "context_policy": "bounded_current_task",
            "spec_id": "005-telegram-workflow-plugin",
            "spec_path": "/srv/bears/specs/005-telegram-workflow-plugin",
            "roadmap_slice": "telegram-workflow-plugin-runtime",
            "repo_head": "abc1234",
            "missing_data_evidence": [
                "operator provided write scope and validation commands"
            ],
            "drift_answer_evidence": [
                "operator provided fresh task packet on 2026-06-06"
            ],
            "task_start_authorization": {
                "authorized": True,
                "authorized_by": "operator",
                "authorized_at": "2026-06-06T00:00:00Z",
                "authorized_actions": [
                    "spawn",
                    "reuse",
                    "manage",
                    "close"
                ]
            }
        }
        worker = {
            "worker_id": "docs-001",
            "status": "running",
            "lane": "docs",
            "registered_role": "bears-workflow-overlay-controller",
            "goal_id": "goal-005",
            "roadmap_id": "roadmap-telegram-workflow",
            "questionnaire_ref": "questionnaire/session-runtime-005",
            "context_policy": "bounded_current_task",
            "spec_id": "005-telegram-workflow-plugin",
            "spec_path": "/srv/bears/specs/005-telegram-workflow-plugin",
            "target_paths": [
                "plugins/bears/docs/reference/session-workers-runtime.md",
                "plugins/bears/assets/catalog/session-workers-runtime.v1.json"
            ],
            "allowed_write_scope": [
                "plugins/bears/docs",
                "plugins/bears/assets/catalog",
                "plugins/bears/scripts",
                "plugins/bears/tests"
            ],
            "forbidden_scope": [
                "projects/",
                "deploy/",
                "runtime/"
            ],
            "roadmap_slice": "telegram-workflow-plugin-runtime",
            "pre_task_hook": pre_task_hook,
            "spec_kit_snapshot": {
                "spec_id": "005-telegram-workflow-plugin",
                "spec_path": "/srv/bears/specs/005-telegram-workflow-plugin",
                "snapshot_id": "snap-005-abc1234",
                "captured_at": "2026-06-03T00:00:00Z",
                "repo_head": "abc1234",
                "artifacts": [
                    {
                        "name": "spec.md",
                        "path": "/srv/bears/specs/005-telegram-workflow-plugin/spec.md",
                        "status": "current"
                    },
                    {
                        "name": "plan.md",
                        "path": "/srv/bears/specs/005-telegram-workflow-plugin/plan.md",
                        "status": "missing"
                    }
                ]
            },
            "validation_target": "session worker runtime validator and unit tests",
            "evidence_target": "changed files and exact validation commands",
            "heartbeat_packet": {
                "path": "workers/docs-001/worker-heartbeat.json",
                "schema": "bears-worker-heartbeat.v1"
            },
            "closeout_packet": {
                "path": "workers/docs-001/worker-closeout.json",
                "schema": "bears-worker-closeout.v1"
            },
            "resume_policy": {
                "requested_action": "fresh",
                "compatibility": {
                    "goal_compatible": False,
                    "roadmap_compatible": False,
                    "lane_compatible": False,
                    "role_compatible": False,
                    "scope_compatible": False,
                    "repo_state_compatible": False,
                    "spec_kit_snapshot_compatible": False,
                    "roadmap_slice_compatible": False
                },
                "bounded_prior_evidence": [
                    "previous session summary"
                ],
                "reason": "fresh run on current Spec Kit truth"
            }
        }
        worker["reuse_key"] = runtime_module.reuse_key(worker)
        worker["resume_policy"]["reuse_key"] = worker["reuse_key"]
        session_workers = {
            "schema": "bears-session-workers.v1",
            "runtime_id": "runtime-001",
            "truth": "Spec Kit",
            "control": "bears",
            "work": "Codex sessions/session workers",
            "workers": [worker]
        }
        (runtime_dir / "session-workers.json").write_text(json.dumps(session_workers))

        orchestration_state = {
            "schema": "bears-session-orchestration-state.v1",
            "runtime_id": "runtime-001",
            "overall_status": "running",
            "workers_by_state": {
                "available": [],
                "claimed": [],
                "running": ["docs-001"],
                "waiting": [],
                "blocked": [],
                "stale": [],
                "completed": [],
                "closed": []
            },
            "scope_locks_file": "scope-locks.json"
        }
        (runtime_dir / "orchestration-state.json").write_text(json.dumps(orchestration_state))

        scope_locks = {
            "schema": "bears-scope-locks.v1",
            "runtime_id": "runtime-001",
            "locks": [
                {
                    "lock_id": "lock-docs-001",
                    "target_path": "plugins/bears/docs",
                    "owner_worker_id": "docs-001",
                    "lane": "docs",
                    "status": "running"
                }
            ]
        }
        (runtime_dir / "scope-locks.json").write_text(json.dumps(scope_locks))
        self._write_reuse_index(runtime_dir)

        heartbeat = {
            "schema": "bears-worker-heartbeat.v1",
            "runtime_id": "runtime-001",
            "worker_id": "docs-001",
            "status": "running",
            "lane": "docs",
            "registered_role": "bears-workflow-overlay-controller",
            "summary": "Updating plugin-owned session worker runtime docs and validator.",
            "validation_target": "session worker runtime validator and unit tests",
            "evidence_target": "changed files and exact validation commands",
            "pre_task_hook": pre_task_hook,
            "updated_at": "2026-06-03T00:10:00Z"
        }
        (workers_dir / "worker-heartbeat.json").write_text(json.dumps(heartbeat))

        closeout = {
            "schema": "bears-worker-closeout.v1",
            "runtime_id": "runtime-001",
            "worker_id": "docs-001",
            "final_status": "completed",
            "lane": "docs",
            "registered_role": "bears-workflow-overlay-controller",
            "summary": "Reserved closeout packet path for when the docs lane completes.",
            "changed_files": [
                "plugins/bears/docs/reference/session-workers-runtime.md"
            ],
            "validation_commands": [
                "python3 scripts/session_workers_runtime.py validate"
            ],
            "evidence": [
                "validator output"
            ],
            "pre_task_hook": pre_task_hook,
            "resume_recommendation": {
                "action": "fresh",
                "reuse_key": worker["reuse_key"],
                "compatibility": {
                    "goal_compatible": False,
                    "roadmap_compatible": False,
                    "lane_compatible": False,
                    "role_compatible": False,
                    "scope_compatible": False,
                    "repo_state_compatible": False,
                    "spec_kit_snapshot_compatible": False,
                    "roadmap_slice_compatible": False
                },
                "bounded_prior_evidence": [
                    "reserved closeout template"
                ],
                "reason": "spawn fresh unless the runtime is revalidated"
            }
        }
        (workers_dir / "worker-closeout.json").write_text(json.dumps(closeout))

    def _write_reuse_index(self, runtime_dir: Path) -> None:
        session_workers = json.loads((runtime_dir / "session-workers.json").read_text())
        entries = []
        for worker in session_workers["workers"]:
            entries.append({
                "worker_id": worker["worker_id"],
                "reuse_key": worker["reuse_key"],
                "goal_id": worker["goal_id"],
                "roadmap_id": worker["roadmap_id"],
                "lane": worker["lane"],
                "registered_role": worker["registered_role"],
                "scope_fingerprint": runtime_module.scope_fingerprint(worker),
                "repo_head": worker["spec_kit_snapshot"]["repo_head"],
                "spec_id": worker["spec_id"],
                "spec_path": worker["spec_path"],
                "spec_snapshot_id": worker["spec_kit_snapshot"]["snapshot_id"],
                "roadmap_slice": worker["roadmap_slice"],
                "status": worker["status"],
                "validation_target": worker["validation_target"],
                "continuation_packet_ref": worker["closeout_packet"]["path"],
                "restricted_data_taint": False,
                "last_validation_at": "2026-06-03T00:20:00Z",
                "selection_decision": "fresh",
                "reuse_allowed": worker["lane"] != "audit"
            })
        reuse_index = {
            "schema": "bears-session-reuse-index.v1",
            "runtime_id": session_workers["runtime_id"],
            "key_algorithm": "sha256-json-v1",
            "entries": entries
        }
        (runtime_dir / "session-reuse-index.json").write_text(json.dumps(reuse_index))

    def _append_second_worker(self, runtime_dir: Path) -> None:
        session_workers = json.loads((runtime_dir / "session-workers.json").read_text())
        worker = copy.deepcopy(session_workers["workers"][0])
        worker["worker_id"] = "docs-002"
        worker["goal_id"] = "goal-006"
        worker["roadmap_id"] = "roadmap-gateway-docs"
        worker["questionnaire_ref"] = "questionnaire/gateway-docs-006"
        worker["context_policy"] = "bounded_current_task"
        worker["spec_id"] = "006-gateway-docs"
        worker["spec_path"] = "/srv/bears/specs/006-gateway-docs"
        worker["target_paths"] = ["plugins/bears/assets/catalog/gateway-runtime.v1.json"]
        worker["allowed_write_scope"] = ["plugins/bears/assets/catalog/gateway-runtime.v1.json"]
        worker["roadmap_slice"] = "gateway-docs-runtime"
        worker["pre_task_hook"]["hook_id"] = "pre-task-docs-002"
        worker["pre_task_hook"]["task_id"] = "T-gateway-docs"
        worker["pre_task_hook"]["goal_id"] = worker["goal_id"]
        worker["pre_task_hook"]["roadmap_id"] = worker["roadmap_id"]
        worker["pre_task_hook"]["questionnaire_ref"] = worker["questionnaire_ref"]
        worker["pre_task_hook"]["context_policy"] = worker["context_policy"]
        worker["pre_task_hook"]["spec_id"] = worker["spec_id"]
        worker["pre_task_hook"]["spec_path"] = worker["spec_path"]
        worker["pre_task_hook"]["roadmap_slice"] = worker["roadmap_slice"]
        worker["spec_kit_snapshot"]["spec_id"] = worker["spec_id"]
        worker["spec_kit_snapshot"]["spec_path"] = worker["spec_path"]
        worker["spec_kit_snapshot"]["snapshot_id"] = "snap-006-abc1234"
        worker["spec_kit_snapshot"]["artifacts"][0]["path"] = "/srv/bears/specs/006-gateway-docs/spec.md"
        worker["heartbeat_packet"]["path"] = "workers/docs-002/worker-heartbeat.json"
        worker["closeout_packet"]["path"] = "workers/docs-002/worker-closeout.json"
        worker["reuse_key"] = runtime_module.reuse_key(worker)
        worker["resume_policy"]["reuse_key"] = worker["reuse_key"]
        session_workers["workers"].append(worker)
        (runtime_dir / "session-workers.json").write_text(json.dumps(session_workers))
        workers_dir = runtime_dir / "workers" / "docs-002"
        workers_dir.mkdir(parents=True, exist_ok=True)
        heartbeat = json.loads((runtime_dir / "workers" / "docs-001" / "worker-heartbeat.json").read_text())
        heartbeat.update({
            "worker_id": "docs-002",
            "lane": worker["lane"],
            "registered_role": worker["registered_role"],
            "pre_task_hook": worker["pre_task_hook"]
        })
        (workers_dir / "worker-heartbeat.json").write_text(json.dumps(heartbeat))
        closeout = json.loads((runtime_dir / "workers" / "docs-001" / "worker-closeout.json").read_text())
        closeout.update({
            "worker_id": "docs-002",
            "lane": worker["lane"],
            "registered_role": worker["registered_role"],
            "pre_task_hook": worker["pre_task_hook"]
        })
        closeout["resume_recommendation"]["reuse_key"] = worker["reuse_key"]
        (workers_dir / "worker-closeout.json").write_text(json.dumps(closeout))
        orchestration = json.loads((runtime_dir / "orchestration-state.json").read_text())
        orchestration["workers_by_state"]["running"].append("docs-002")
        (runtime_dir / "orchestration-state.json").write_text(json.dumps(orchestration))
        scope_locks = json.loads((runtime_dir / "scope-locks.json").read_text())
        scope_locks["locks"].append({
            "lock_id": "lock-docs-002",
            "target_path": "plugins/bears/assets/catalog/gateway-runtime.v1.json",
            "owner_worker_id": "docs-002",
            "lane": "docs",
            "status": "running"
        })
        (runtime_dir / "scope-locks.json").write_text(json.dumps(scope_locks))
        self._write_reuse_index(runtime_dir)

    def _append_audit_worker(self, runtime_dir: Path, *, parent_context_allowed: bool) -> None:
        self._append_second_worker(runtime_dir)
        session_workers = json.loads((runtime_dir / "session-workers.json").read_text())
        worker = session_workers["workers"][1]
        worker["worker_id"] = "audit-001"
        worker["lane"] = "audit"
        worker["registered_role"] = "bears-platform-security-reviewer"
        worker["context_policy"] = "fresh_no_parent_context"
        worker["pre_task_hook"]["context_policy"] = "fresh_no_parent_context"
        worker["heartbeat_packet"]["path"] = "workers/audit-001/worker-heartbeat.json"
        worker["closeout_packet"]["path"] = "workers/audit-001/worker-closeout.json"
        worker["pre_task_hook"]["hook_id"] = "pre-task-audit-001"
        worker["pre_task_hook"]["parent_context_allowed"] = parent_context_allowed
        worker["resume_policy"]["bounded_prior_evidence"] = []
        worker["reuse_key"] = runtime_module.reuse_key(worker)
        worker["resume_policy"]["reuse_key"] = worker["reuse_key"]
        session_workers["workers"][1] = worker
        (runtime_dir / "session-workers.json").write_text(json.dumps(session_workers))
        (runtime_dir / "workers" / "docs-002").rename(runtime_dir / "workers" / "audit-001")
        heartbeat = json.loads((runtime_dir / "workers" / "audit-001" / "worker-heartbeat.json").read_text())
        heartbeat.update({
            "worker_id": "audit-001",
            "lane": "audit",
            "registered_role": "bears-platform-security-reviewer",
            "pre_task_hook": worker["pre_task_hook"]
        })
        (runtime_dir / "workers" / "audit-001" / "worker-heartbeat.json").write_text(json.dumps(heartbeat))
        closeout = json.loads((runtime_dir / "workers" / "audit-001" / "worker-closeout.json").read_text())
        closeout.update({
            "worker_id": "audit-001",
            "lane": "audit",
            "registered_role": "bears-platform-security-reviewer",
            "pre_task_hook": worker["pre_task_hook"]
        })
        closeout["resume_recommendation"]["reuse_key"] = worker["reuse_key"]
        (runtime_dir / "workers" / "audit-001" / "worker-closeout.json").write_text(json.dumps(closeout))
        orchestration = json.loads((runtime_dir / "orchestration-state.json").read_text())
        orchestration["workers_by_state"]["running"][-1] = "audit-001"
        (runtime_dir / "orchestration-state.json").write_text(json.dumps(orchestration))
        scope_locks = json.loads((runtime_dir / "scope-locks.json").read_text())
        scope_locks["locks"][-1].update({
            "lock_id": "lock-audit-001",
            "owner_worker_id": "audit-001",
            "lane": "audit"
        })
        (runtime_dir / "scope-locks.json").write_text(json.dumps(scope_locks))
        self._write_reuse_index(runtime_dir)


if __name__ == "__main__":
    unittest.main()
