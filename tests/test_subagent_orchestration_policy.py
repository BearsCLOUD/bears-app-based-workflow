from __future__ import annotations

import copy
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import tomllib

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PLUGIN_ROOT / "scripts" / "subagent_orchestration_policy.py"
spec = importlib.util.spec_from_file_location("subagent_orchestration_policy", SCRIPT_PATH)
policy_module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(policy_module)  # type: ignore[arg-type]


class SubagentOrchestrationPolicyTest(unittest.TestCase):
    EXPECTED_MAIN_AGENT_ALLOWED_ACTIONS = [
        "route",
        "split",
        "assign",
        "wait",
        "integrate_evidence",
        "run_validators",
        "close",
        "report",
        "pre_task_hook",
    ]
    EXPECTED_MAIN_AGENT_FORBIDDEN_ACTIONS = [
        "file_read_as_content_collector",
        "file_write",
        "git_add",
        "git_commit",
        "git_push",
        "pull_request_mutation",
        "implementation_tool_use",
    ]
    EXPECTED_PARENT_CONTROL_ALLOWED_ACTIONS = [
        "route_target_and_role_selection",
        "split_assignment_packets",
        "request_named_validation_hook",
            "run_validators",
        "run_status_checks",
        "read_command_exit_codes",
        "read_bounded_summaries",
        "inspect_git_status_short",
        "inspect_changed_file_names",
        "create_github_planning_issue_when_operator_requested",
        "update_github_planning_issue_when_operator_requested",
        "integrate_subagent_evidence",
        "close_stale_or_completed_subagents",
    ]
    EXPECTED_PARENT_CONTROL_FORBIDDEN_ACTIONS = [
        "file_write",
        "implementation_command",
        "git_add",
        "git_commit",
        "git_push",
        "pull_request_mutation_without_explicit_operator_request",
        "broad_file_content_collection",
        "raw_secret_read",
        "raw_log_read",
        "raw_chat_read",
        "raw_vpn_config_read",
        "production_data_read",
        "secret_read",
        "env_file_read",
    ]
    EXPECTED_NO_SUBAGENT_CASES = {
        "side-conversation-answer",
        "question-only-explanation",
        "single-command-read-only-status-check",
        "bounded-repo-inspection-no-mutation",
        "small-exact-file-bugfix-policy-exception",
        "repo-boundary-change",
        "plugin-policy-change",
        "runtime-deployment-migration-secret-change",
        "multi-file-implementation",
        "explicit-subagent-request",
    }
    EXPECTED_VALIDATION_HOOKS = {
        "platform_roles_validate",
        "role_route",
        "role_audit",
        "project_registry_gate",
        "project_registry_validate",
        "subagent_policy_validate",
        "overlay_validate",
        "roadmap_validate",
        "git_discipline_validate",
        "plugin_constitution_validate",
        "role_gate_methodology_validate",
        "session_workers_runtime_validate",
        "agent_github_dev_cd_validate",
        "skill_catalog_generate_check",
        "secret_factory_validate",
        "full_tests_discover",
    }
    EXPECTED_HOOK_RESULT_FIELDS = {
        "hook_id",
        "cwd",
        "command_id",
        "exit_code",
        "sanitized_summary",
        "validation_target",
    }
    EVIDENCE_GATHERING_AGENT_FILES = {
        "blocker-taxonomy-evaluator.toml",
        "deploy-impact-gate.toml",
        "governance-project-router.toml",
        "role-coverage-gate.toml",
        "workflow-artifact-validator.toml",
    }
    HELPER_AGENT_RUNTIME = {
        "bears-git-workflow-helper.toml": {"model": "gpt-5.4-mini", "reasoning_effort": "medium"},
        "bears-review-fix-helper.toml": {"model": "gpt-5.4-mini", "reasoning_effort": "medium"},
        "bears-token-budget-helper.toml": {"model": "gpt-5.4-mini", "reasoning_effort": "medium"},
    }
    EXPECTED_MAIN_AGENT = {"model": "gpt-5.5", "reasoning_effort": "medium"}
    EXPECTED_DELEGATED_SUBAGENTS = {
        "model": "gpt-5.4-mini",
        "reasoning_effort": "medium",
        "applies_to": [
            "audit agents",
            "complex-task agents",
            "agents that can spawn subagents",
        ],
    }
    EXPECTED_EVIDENCE_GATHERING_ROLES = {
        "blocker-taxonomy-evaluator",
        "deploy-impact-gate",
        "governance-project-router",
        "role-coverage-gate",
        "workflow-artifact-validator",
    }
    EXPECTED_EVIDENCE_GATHERING_APPLIES_TO = {
        "file reading agents",
        "log reading agents",
        "information/evidence gathering agents",
    }
    EXPECTED_COMMIT_LOCAL_VALIDATION_TEST_CLOSEOUT_RESPONSIBILITIES = {
        "commit",
        "local_commit_validation_status",
        "test_artifact_create_or_fix",
        "closeout",
    }
    EXPECTED_COMMIT_LOCAL_VALIDATION_TEST_CLOSEOUT_ALLOWED_CHECKS = {
        "platform_roles_route_for_changed_targets",
        "platform_roles_audit_for_changed_targets",
        "json_toml_python_syntax",
        "git_diff_check",
        "git_status_log",
        "local_commit_validation_proof_metadata",
    }
    EXPECTED_COMMIT_LOCAL_VALIDATION_TEST_CLOSEOUT_FORBIDDEN_CHECKS = {
        "pytest",
        "unittest",
        "repo_validator_suites",
        "raw_ci_log_read",
    }
    EXPECTED_COMMIT_LOCAL_VALIDATION_TEST_CLOSEOUT_CLOSEOUT_FIELDS = {
        "start_sha",
        "final_sha",
        "changed_files",
        "commit_sha",
        "push_status",
        "local_commit_validation_status",
        "local_commit_validation_proof_path",
        "test_artifact_changes",
        "local_test_policy_evidence",
        "closeout_status",
    }
    EXPECTED_CONCURRENT_GIT_SAFETY_POLICY = {
        "one_file_one_owner_per_wave": True,
        "git_fetch_before_commit": True,
        "git_fetch_before_push": True,
        "verify_head_origin_main_start_sha": True,
        "fast_forward_only_push": True,
        "force_push_forbidden": True,
        "stale_file_change_policy": "stop_or_explicit_rebase_diff_review",
        "changed_files_required": True,
        "parent_closeout_head_status_check_required": True,
    }
    EXPECTED_WORKER_POOL_STATES = {
        "active",
        "idle",
        "reusable",
        "fresh-required",
        "stale",
    }
    EXPECTED_GOAL_PREFLIGHT_TOP_FIELDS = {
        "enabled",
        "preflight_id",
        "applies_to",
        "fixed_assignment_packet",
        "batch_role_gate",
        "spawn_agent_argument_shape",
        "wait_agent_target_validation",
        "wait_any_loop",
        "worker_pool_ledger",
        "backend_only_scope_lock",
        "handoff_guards",
        "fanout_thread_limit_preflight",
        "new_wave_gate",
        "final_join_gate",
        "result_policy",
        "issue_mapping",
        "parent_plan_status_gate",
    }

    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = policy_module.load_json(PLUGIN_ROOT / "assets/catalog/subagent-orchestration-policy.v1.json")

    def _valid_speckit_assignment(self, *, lane: str = "worker") -> dict[str, object]:
        packet: dict[str, object] = {
            "assignment_packet_id": "assign-p1-19-worker",
            "agent_lane": lane,
            "spec_kit_binding": {
                "spec_md_path": "specs/subagent-speckit-executable-logic/spec.md",
                "plan_md_path": "specs/subagent-speckit-executable-logic/plan.md",
                "tasks_md_path": "specs/subagent-speckit-executable-logic/tasks.md",
            },
            "speckit_analyze": {
                "status": "PASS",
                "artifact_ref": "specs/subagent-speckit-executable-logic/governance/speckit-analyze.json",
            },
            "source_task_ids": ["P1-19"],
            "rule_coverage_ids": ["subagent-speckit-executable-logic"],
            "validator_subcommands": [
                "validate-speckit-assignment",
                "validate-speckit-closeout",
            ],
            "expected_executable_proof": {
                "proof_type": "validator",
                "proof_command": "python3 scripts/subagent_orchestration_policy.py validate-speckit-closeout --packet <packet>",
            },
            "restricted_data_status": "clean",
        }
        if lane == "reviewer":
            packet.update(
                {
                    "assignment_packet_id": "assign-p1-19-reviewer",
                    "lane_mode": "advisory_async",
                    "wait_budget_seconds": 0,
                    "hard_stop_reason": "none",
                }
            )
        return packet

    def _valid_speckit_closeout(self, *, lane_mode: str = "worker") -> dict[str, object]:
        packet: dict[str, object] = {
            "closeout_packet_id": "closeout-p1-19-worker",
            "assignment_packet_id": "assign-p1-19-worker",
            "lane_mode": lane_mode,
            "rule_coverage_ids": ["subagent-speckit-executable-logic"],
            "executable_proof_refs": ["unit:test_subagent_speckit_worker_assignment_passes"],
            "validator_exit_codes": {
                "python3 scripts/subagent_orchestration_policy.py validate-speckit-closeout --packet <packet>": 0
            },
            "schema_packet_refs": ["schema:bears-subagent-closeout-executable-v1"],
            "restricted_data_status": "clean",
            "stale_result_rejection": {
                "status": "checked",
                "stale_result": False,
                "checked_at": "2026-06-19T00:00:00Z",
                "freshness_source": "assignment_packet_id+validator_exit_codes",
                "assignment_packet_id": "assign-p1-19-worker",
            },
            "acceptance_evidence_refs": ["validator_exit_codes", "schema_packet_refs"],
        }
        if lane_mode == "advisory_async":
            packet.update(
                {
                    "closeout_packet_id": "closeout-p1-19-reviewer",
                    "assignment_packet_id": "assign-p1-19-reviewer",
                    "hard_stop_reason": "none",
                    "wait_budget_seconds": 0,
                }
            )
            stale = packet["stale_result_rejection"]
            assert isinstance(stale, dict)
            stale["assignment_packet_id"] = "assign-p1-19-reviewer"
        return packet

    def test_current_policy_validates(self) -> None:
        self.assertEqual(policy_module.validate_policy(self.policy), [])

    def test_subagent_speckit_worker_assignment_passes(self) -> None:
        errors = policy_module.validate_subagent_speckit_assignment_packet(
            self._valid_speckit_assignment()
        )
        self.assertEqual(errors, [])

    def test_subagent_speckit_reviewer_advisory_assignment_passes(self) -> None:
        errors = policy_module.validate_subagent_speckit_assignment_packet(
            self._valid_speckit_assignment(lane="reviewer")
        )
        self.assertEqual(errors, [])

    def test_subagent_speckit_blocking_gate_assignment_passes(self) -> None:
        packet = self._valid_speckit_assignment(lane="reviewer")
        packet.update(
            {
                "lane_mode": "blocking_gate",
                "hard_stop_reason": "security",
                "timeout_seconds": 900,
                "expected_closeout_artifact": "docs/audits/security-review.json",
                "fallback_action": "block parent integration until security closeout exists",
                "blocking_condition": "security review rejects restricted-data handling",
            }
        )
        errors = policy_module.validate_subagent_speckit_assignment_packet(packet)
        self.assertEqual(errors, [])

    def test_subagent_speckit_assignment_rejects_missing_spec_kit_binding(self) -> None:
        packet = self._valid_speckit_assignment()
        packet.pop("spec_kit_binding")
        errors = policy_module.validate_subagent_speckit_assignment_packet(packet)
        self.assertTrue(any("spec_kit_binding" in error for error in errors), errors)

    def test_subagent_speckit_assignment_rejects_missing_executable_proof(self) -> None:
        packet = self._valid_speckit_assignment()
        packet.pop("expected_executable_proof")
        errors = policy_module.validate_subagent_speckit_assignment_packet(packet)
        self.assertTrue(any("expected_executable_proof" in error for error in errors), errors)

    def test_subagent_speckit_assignment_rejects_non_pass_analyze(self) -> None:
        packet = self._valid_speckit_assignment()
        packet["speckit_analyze"] = {"status": "FAIL", "artifact_ref": "governance/speckit-analyze.json"}
        errors = policy_module.validate_subagent_speckit_assignment_packet(packet)
        self.assertTrue(any("speckit_analyze.status" in error for error in errors), errors)

    def test_advisory_async_assignment_requires_zero_wait_budget(self) -> None:
        packet = self._valid_speckit_assignment(lane="reviewer")
        packet["wait_budget_seconds"] = 5
        errors = policy_module.validate_subagent_speckit_assignment_packet(packet)
        self.assertTrue(any("wait_budget_seconds" in error for error in errors), errors)

    def test_blocking_gate_assignment_requires_valid_hard_stop_fields(self) -> None:
        packet = self._valid_speckit_assignment(lane="reviewer")
        packet.update(
            {
                "lane_mode": "blocking_gate",
                "hard_stop_reason": "nice_to_have_review",
                "timeout_seconds": 0,
            }
        )
        errors = policy_module.validate_subagent_speckit_assignment_packet(packet)
        self.assertTrue(any("hard_stop_reason" in error for error in errors), errors)
        self.assertTrue(any("timeout_seconds" in error for error in errors), errors)
        self.assertTrue(any("expected_closeout_artifact" in error for error in errors), errors)
        self.assertTrue(any("fallback_action" in error for error in errors), errors)
        self.assertTrue(any("blocking_condition" in error for error in errors), errors)

    def test_subagent_executable_worker_closeout_passes(self) -> None:
        errors = policy_module.validate_subagent_speckit_closeout_packet(
            self._valid_speckit_closeout()
        )
        self.assertEqual(errors, [])

    def test_subagent_executable_reviewer_closeout_passes(self) -> None:
        errors = policy_module.validate_subagent_speckit_closeout_packet(
            self._valid_speckit_closeout(lane_mode="advisory_async")
        )
        self.assertEqual(errors, [])

    def test_subagent_closeout_rejects_parent_context_acceptance(self) -> None:
        packet = self._valid_speckit_closeout()
        packet["acceptance_evidence_refs"] = ["parent_thread_summary"]
        errors = policy_module.validate_subagent_speckit_closeout_packet(packet)
        self.assertTrue(any("forbidden acceptance evidence" in error for error in errors), errors)

    def test_subagent_closeout_rejects_parent_context_in_validation_summary(self) -> None:
        packet = self._valid_speckit_closeout()
        packet["validation_summary"] = "accepted from parent-thread-summary"
        errors = policy_module.validate_subagent_speckit_closeout_packet(packet)
        self.assertTrue(any("validation_summary" in error for error in errors), errors)
        self.assertTrue(any("parent-thread-summary" in error for error in errors), errors)

    def test_subagent_closeout_rejects_chat_excerpt_text(self) -> None:
        packet = self._valid_speckit_closeout()
        packet["chat_excerpt"] = "chat text says done"
        errors = policy_module.validate_subagent_speckit_closeout_packet(packet)
        self.assertTrue(any("chat_excerpt" in error for error in errors), errors)
        self.assertTrue(any("chat text" in error for error in errors), errors)

    def test_subagent_closeout_rejects_reviewer_opinion_notes(self) -> None:
        packet = self._valid_speckit_closeout()
        packet["review_notes"] = "reviewer opinion says ok"
        errors = policy_module.validate_subagent_speckit_closeout_packet(packet)
        self.assertTrue(any("review_notes" in error for error in errors), errors)
        self.assertTrue(any("reviewer opinion" in error for error in errors), errors)

    def test_forbidden_closeout_text_scan_includes_nested_fields(self) -> None:
        packet = {
            "result": {
                "notes": [
                    "validator exit code passed",
                    "unchecked issue text says accepted",
                ]
            }
        }
        errors = policy_module._validate_no_forbidden_acceptance_evidence(packet, "packet")
        self.assertTrue(any("packet.result.notes[1]" in error for error in errors), errors)
        self.assertTrue(any("unchecked issue text" in error for error in errors), errors)

    def test_forbidden_closeout_text_scan_allows_clean_text_fields(self) -> None:
        packet = {
            "validation_summary": "validator exit code 0",
            "review_notes": "schema packet and status packet reviewed",
        }
        errors = policy_module._validate_no_forbidden_acceptance_evidence(packet, "packet")
        self.assertEqual(errors, [])

    def test_subagent_closeout_rejects_stale_result(self) -> None:
        packet = self._valid_speckit_closeout(lane_mode="advisory_async")
        stale = packet["stale_result_rejection"]
        assert isinstance(stale, dict)
        stale["stale_result"] = True
        errors = policy_module.validate_subagent_speckit_closeout_packet(packet)
        self.assertTrue(any("stale_result must be false" in error for error in errors), errors)

    def test_subagent_closeout_rejects_missing_restricted_data_status(self) -> None:
        packet = self._valid_speckit_closeout()
        packet.pop("restricted_data_status")
        errors = policy_module.validate_subagent_speckit_closeout_packet(packet)
        self.assertTrue(any("restricted_data_status" in error for error in errors), errors)

    def test_subagent_closeout_rejects_missing_executable_proof(self) -> None:
        packet = self._valid_speckit_closeout()
        packet.pop("executable_proof_refs")
        errors = policy_module.validate_subagent_speckit_closeout_packet(packet)
        self.assertTrue(any("executable_proof_refs" in error for error in errors), errors)

    def test_validate_speckit_assignment_cli_passes_and_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pass_packet = Path(tmpdir) / "assignment-pass.json"
            fail_packet = Path(tmpdir) / "assignment-fail.json"
            pass_packet.write_text(json.dumps(self._valid_speckit_assignment()), encoding="utf-8")
            fail_data = self._valid_speckit_assignment()
            fail_data.pop("source_task_ids")
            fail_packet.write_text(json.dumps(fail_data), encoding="utf-8")
            passed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "validate-speckit-assignment",
                    "--packet",
                    str(pass_packet),
                ],
                cwd=PLUGIN_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            failed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "validate-speckit-assignment",
                    "--packet",
                    str(fail_packet),
                ],
                cwd=PLUGIN_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(passed.returncode, 0, passed.stderr)
        self.assertNotEqual(failed.returncode, 0, failed.stdout)
        self.assertIn("source_task_ids", failed.stderr)

    def test_validate_speckit_closeout_cli_passes_and_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            pass_packet = Path(tmpdir) / "closeout-pass.json"
            fail_packet = Path(tmpdir) / "closeout-fail.json"
            pass_packet.write_text(json.dumps(self._valid_speckit_closeout()), encoding="utf-8")
            fail_data = self._valid_speckit_closeout()
            fail_data["acceptance_evidence_refs"] = ["reviewer_opinion"]
            fail_packet.write_text(json.dumps(fail_data), encoding="utf-8")
            passed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "validate-speckit-closeout",
                    "--packet",
                    str(pass_packet),
                ],
                cwd=PLUGIN_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            failed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "validate-speckit-closeout",
                    "--packet",
                    str(fail_packet),
                ],
                cwd=PLUGIN_ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertEqual(passed.returncode, 0, passed.stderr)
        self.assertNotEqual(failed.returncode, 0, failed.stdout)
        self.assertIn("forbidden acceptance evidence", failed.stderr)

    def test_records_reusable_worker_pool_policy(self) -> None:
        self.assertIn("reusable-worker-pool-policy", self.policy["required_rule_ids"])
        limits = self.policy["limits"]
        self.assertEqual(limits["hard_max_active_subagents"], 100)
        self.assertLess(limits["default_active_executing_subagents"], 100)
        self.assertIn("absolute safety cap", limits["hard_max_rule"])
        pool = self.policy["orchestration_model"]["worker_pool_policy"]
        self.assertEqual(pool["hard_max_active_subagents"], 100)
        self.assertLess(pool["default_active_executing_subagents"], 100)
        self.assertEqual(pool["default_cap_applies_to"], "actively_executing_workers_only")
        self.assertFalse(pool["warm_reusable_workers_count_against_default_active_cap"])
        self.assertEqual(
            {item["state"] for item in pool["worker_states"]},
            self.EXPECTED_WORKER_POOL_STATES,
        )
        self.assertEqual(
            set(pool["reuse_required_all"]),
            {
                "same_role",
                "same_repo_boundary",
                "compatible_write_scope",
                "no_restricted_data_taint",
                "compact_continuation_packet",
            },
        )
        self.assertEqual(
            pool["reuse_or_fork_session_runtime_precondition"]["command"],
            policy_module.REQUIRED_SESSION_RUNTIME_VALIDATION_COMMAND,
        )

    def test_rejects_hard_max_as_normal_active_target(self) -> None:
        packet = copy.deepcopy(self.policy)
        packet["limits"]["default_active_executing_subagents"] = 100
        packet["orchestration_model"]["worker_pool_policy"]["default_active_executing_subagents"] = 100
        errors = policy_module.validate_policy(packet)
        self.assertTrue(
            any("default_active_executing_subagents" in error for error in errors),
            errors,
        )

    def test_worker_reuse_allowed_with_matching_scope_packet(self) -> None:
        request = {
            "reuse_requested": True,
            "worker_state": "reusable",
            "worker_role": "bears-subagent-orchestration-engineer",
            "requested_role": "bears-subagent-orchestration-engineer",
            "worker_repo_boundary": "/srv/bears/plugins/bears",
            "requested_repo_boundary": "/srv/bears/plugins/bears",
            "worker_write_scope": "assets/catalog/subagent-orchestration-policy.v1.json",
            "requested_write_scope": "assets/catalog/subagent-orchestration-policy.v1.json",
            "write_scope_compatible": True,
            "restricted_data_taint": False,
            "lane_inherit_parent_context": True,
            "session_runtime_validation": {
                "command": policy_module.REQUIRED_SESSION_RUNTIME_VALIDATION_COMMAND,
                "runtime_dir": "/tmp/bears-runtime",
                "exit_code": 0,
                "compatibility_status": "compatible",
            },
            "compact_continuation_packet": {
                "worker_id": "worker-issue-15",
                "role": "bears-subagent-orchestration-engineer",
                "repo_boundary": "/srv/bears/plugins/bears",
                "write_scope": "assets/catalog/subagent-orchestration-policy.v1.json",
                "last_assignment_packet_id": "assign-issue-15",
                "status_summary": "policy edit ready for continuation",
                "validation_target": "assets/catalog/subagent-orchestration-policy.v1.json",
                "restricted_data_taint": False,
                "changed_files": ["assets/catalog/subagent-orchestration-policy.v1.json"],
            },
        }
        self.assertEqual(
            policy_module.validate_worker_reuse_request(request, self.policy),
            [],
        )

    def test_worker_reuse_denied_when_role_or_scope_mismatch(self) -> None:
        request = {
            "reuse_requested": True,
            "worker_state": "reusable",
            "worker_role": "bears-platform-role-governor",
            "requested_role": "bears-subagent-orchestration-engineer",
            "worker_repo_boundary": "/srv/bears/plugins/bears",
            "requested_repo_boundary": "/srv/bears/plugins/bears",
            "worker_write_scope": "README.md",
            "requested_write_scope": "scripts/subagent_orchestration_policy.py",
            "write_scope_compatible": False,
            "restricted_data_taint": False,
            "lane_inherit_parent_context": True,
            "compact_continuation_packet": {
                "worker_id": "worker-issue-15",
                "role": "bears-platform-role-governor",
                "repo_boundary": "/srv/bears/plugins/bears",
                "write_scope": "README.md",
                "last_assignment_packet_id": "assign-issue-15",
                "status_summary": "different scope",
                "validation_target": "README.md",
                "restricted_data_taint": False,
                "changed_files": ["README.md"],
            },
        }
        errors = policy_module.validate_worker_reuse_request(request, self.policy)
        self.assertTrue(any("same_role" in error for error in errors), errors)
        self.assertTrue(any("compatible_write_scope" in error for error in errors), errors)

    def test_worker_reuse_denied_when_restricted_data_taint_is_present(self) -> None:
        request = {
            "reuse_requested": True,
            "worker_state": "reusable",
            "worker_role": "bears-subagent-orchestration-engineer",
            "requested_role": "bears-subagent-orchestration-engineer",
            "worker_repo_boundary": "/srv/bears/plugins/bears",
            "requested_repo_boundary": "/srv/bears/plugins/bears",
            "write_scope_compatible": True,
            "restricted_data_taint": True,
            "lane_inherit_parent_context": True,
            "compact_continuation_packet": {
                "worker_id": "worker-issue-15",
                "role": "bears-subagent-orchestration-engineer",
                "repo_boundary": "/srv/bears/plugins/bears",
                "write_scope": "assets/catalog/subagent-orchestration-policy.v1.json",
                "last_assignment_packet_id": "assign-issue-15",
                "status_summary": "restricted data taint present",
                "validation_target": "assets/catalog/subagent-orchestration-policy.v1.json",
                "restricted_data_taint": True,
                "changed_files": ["assets/catalog/subagent-orchestration-policy.v1.json"],
            },
        }
        errors = policy_module.validate_worker_reuse_request(request, self.policy)
        self.assertTrue(any("no_restricted_data_taint" in error for error in errors), errors)
        self.assertTrue(
            any("compact_continuation_packet.restricted_data_taint" in error for error in errors),
            errors,
        )

    def test_worker_reuse_denied_when_continuation_packet_has_forbidden_fields(self) -> None:
        for field in ("raw_secret", "raw_log", "raw_chat", "raw_vpn_config", "production_data"):
            with self.subTest(field=field):
                request = {
                    "reuse_requested": True,
                    "worker_state": "reusable",
                    "worker_role": "bears-subagent-orchestration-engineer",
                    "requested_role": "bears-subagent-orchestration-engineer",
                    "worker_repo_boundary": "/srv/bears/plugins/bears",
                    "requested_repo_boundary": "/srv/bears/plugins/bears",
                    "write_scope_compatible": True,
                    "restricted_data_taint": False,
                    "lane_inherit_parent_context": True,
                    "session_runtime_validation": {
                        "command": policy_module.REQUIRED_SESSION_RUNTIME_VALIDATION_COMMAND,
                        "runtime_dir": "/tmp/bears-runtime",
                        "exit_code": 0,
                        "compatibility_status": "compatible",
                    },
                    "compact_continuation_packet": {
                        "worker_id": "worker-issue-15",
                        "role": "bears-subagent-orchestration-engineer",
                        "repo_boundary": "/srv/bears/plugins/bears",
                        "write_scope": "assets/catalog/subagent-orchestration-policy.v1.json",
                        "last_assignment_packet_id": "assign-issue-15",
                        "status_summary": "forbidden packet field present",
                        "validation_target": "assets/catalog/subagent-orchestration-policy.v1.json",
                        "restricted_data_taint": False,
                        "changed_files": ["assets/catalog/subagent-orchestration-policy.v1.json"],
                        field: "redacted",
                    },
                }
                errors = policy_module.validate_worker_reuse_request(request, self.policy)
                self.assertTrue(any("contains forbidden fields" in error and field in error for error in errors), errors)

    def test_worker_reuse_requires_session_runtime_validation(self) -> None:
        request = {
            "reuse_requested": True,
            "worker_state": "reusable",
            "worker_role": "bears-subagent-orchestration-engineer",
            "requested_role": "bears-subagent-orchestration-engineer",
            "worker_repo_boundary": "/srv/bears/plugins/bears",
            "requested_repo_boundary": "/srv/bears/plugins/bears",
            "write_scope_compatible": True,
            "restricted_data_taint": False,
            "lane_inherit_parent_context": True,
            "compact_continuation_packet": {
                "worker_id": "worker-issue-15",
                "role": "bears-subagent-orchestration-engineer",
                "repo_boundary": "/srv/bears/plugins/bears",
                "write_scope": "assets/catalog/subagent-orchestration-policy.v1.json",
                "last_assignment_packet_id": "assign-issue-15",
                "status_summary": "missing session runtime validation",
                "validation_target": "assets/catalog/subagent-orchestration-policy.v1.json",
                "restricted_data_taint": False,
                "changed_files": ["assets/catalog/subagent-orchestration-policy.v1.json"],
            },
        }
        errors = policy_module.validate_worker_reuse_request(request, self.policy)
        self.assertTrue(any("session_runtime_validation" in error for error in errors), errors)

    def test_fresh_audit_required_when_parent_context_not_inherited(self) -> None:
        request = {
            "reuse_requested": True,
            "requested_worker_state": "reusable",
            "lane_inherit_parent_context": False,
            "parent_context_attached": True,
        }
        errors = policy_module.validate_worker_reuse_request(request, self.policy)
        self.assertTrue(any("fresh-required" in error for error in errors), errors)
        self.assertTrue(any("reuse_requested" in error for error in errors), errors)
        self.assertTrue(any("parent_context_attached" in error for error in errors), errors)

    def test_missing_policy_cli_uses_stable_error(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bears-missing-policy-") as tmpdir:
            missing_policy = Path(tmpdir) / "missing-policy.json"
            env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--policy",
                    str(missing_policy),
                    "validate",
                ],
                cwd=PLUGIN_ROOT,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )

        combined_output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 1)
        self.assertIn(f"ERROR: policy not found: {missing_policy}", combined_output)
        self.assertNotIn("Errno", combined_output)
        self.assertNotIn("Traceback", combined_output)

    def test_requires_each_non_product_post_task_audit(self) -> None:
        for audit_id in policy_module.REQUIRED_POST_TASK_AUDITS:
            with self.subTest(audit_id=audit_id):
                packet = copy.deepcopy(self.policy)
                packet["non_product_post_task_audit"]["required_subagents"] = [
                    audit
                    for audit in packet["non_product_post_task_audit"]["required_subagents"]
                    if audit["id"] != audit_id
                ]
                errors = policy_module.validate_policy(packet)
                self.assertTrue(any(audit_id in error for error in errors))

    def test_rejects_wrong_post_task_audit_role(self) -> None:
        packet = copy.deepcopy(self.policy)
        packet["non_product_post_task_audit"]["required_subagents"][0]["role"] = "bears-platform-role-governor"
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("plugin-fit-audit role" in error for error in errors))

    def test_records_project_mandate_bears_ownership_rule(self) -> None:
        self.assertIn("project-mandate-owned-by-bears", self.policy["required_rule_ids"])
        rules = {rule["id"]: rule["rule"] for rule in self.policy["rules"]}
        self.assertIn("project-mandate", rules["project-mandate-owned-by-bears"])
        self.assertIn("project registry gate", rules["project-mandate-owned-by-bears"])

    def test_records_main_agent_orchestration_only_rule(self) -> None:
        self.assertIn("main-agent-orchestration-only", self.policy["required_rule_ids"])
        parent_policy = self.policy["orchestration_model"]["main_agent_action_policy"]
        self.assertEqual(parent_policy["mode"], "orchestration_only_for_subagent_enabled_tasks")
        self.assertEqual(
            parent_policy["allowed_actions"],
            self.EXPECTED_MAIN_AGENT_ALLOWED_ACTIONS,
        )
        self.assertEqual(
            parent_policy["forbidden_actions"],
            self.EXPECTED_MAIN_AGENT_FORBIDDEN_ACTIONS,
        )

    def test_records_parent_control_lane(self) -> None:
        self.assertIn("parent-control-lane-actions", self.policy["required_rule_ids"])
        lane = self.policy["orchestration_model"]["parent_control_lane"]
        self.assertTrue(lane["enabled"])
        self.assertEqual(lane["lane_id"], "parent_control_lane")
        self.assertEqual(lane["mode"], "orchestration_control_only")
        self.assertEqual(lane["action_policy_reference"], "main_agent_action_policy")
        self.assertEqual(lane["implementation_authority"], "forbidden")
        self.assertEqual(
            lane["allowed_control_actions"],
            self.EXPECTED_PARENT_CONTROL_ALLOWED_ACTIONS,
        )
        self.assertEqual(
            lane["forbidden_control_actions"],
            self.EXPECTED_PARENT_CONTROL_FORBIDDEN_ACTIONS,
        )
        self.assertTrue(lane["status_output_policy"]["exit_codes_allowed"])
        self.assertTrue(lane["status_output_policy"]["bounded_summaries_allowed"])
        self.assertTrue(lane["status_output_policy"]["changed_file_names_allowed"])
        self.assertEqual(
            lane["status_output_policy"]["file_content_collection"],
            "forbidden",
        )
        self.assertEqual(
            lane["github_policy"]["planning_issue_mutation"],
            "operator_requested_only",
        )
        self.assertEqual(
            lane["github_policy"]["pull_request_mutation"],
            "forbidden_without_explicit_operator_request",
        )
        self.assertEqual(
            set(lane["restricted_data_policy"]["blocked_reads"]),
            {"raw_secret", "secret", "env_file", "raw_log", "raw_chat", "raw_vpn_config", "production_data"},
        )

    def test_rejects_parent_control_lane_implementation_authority(self) -> None:
        packet = copy.deepcopy(self.policy)
        packet["orchestration_model"]["parent_control_lane"]["implementation_authority"] = "allowed"
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("implementation_authority" in error for error in errors), errors)

    def test_rejects_missing_parent_control_allowed_action(self) -> None:
        packet = copy.deepcopy(self.policy)
        actions = packet["orchestration_model"]["parent_control_lane"]["allowed_control_actions"]
        actions.remove("inspect_git_status_short")
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("inspect_git_status_short" in error for error in errors), errors)

    def test_rejects_missing_parent_control_forbidden_action(self) -> None:
        packet = copy.deepcopy(self.policy)
        actions = packet["orchestration_model"]["parent_control_lane"]["forbidden_control_actions"]
        actions.remove("raw_vpn_config_read")
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("raw_vpn_config_read" in error for error in errors), errors)

    def test_rejects_parent_control_restricted_data_read_gap(self) -> None:
        packet = copy.deepcopy(self.policy)
        reads = packet["orchestration_model"]["parent_control_lane"]["restricted_data_policy"]["blocked_reads"]
        reads.remove("production_data")
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("production_data" in error for error in errors), errors)

    def test_records_no_subagent_mode_decision_table(self) -> None:
        self.assertIn("no-subagent-mode-decision-table", self.policy["required_rule_ids"])
        no_subagent_mode = self.policy["orchestration_model"]["no_subagent_mode"]
        self.assertTrue(no_subagent_mode["enabled"])
        self.assertEqual(
            no_subagent_mode["parent_instruction_rule"],
            "nearest_role_instructions_still_apply",
        )
        self.assertEqual(
            no_subagent_mode["role_gate_rule"],
            "required_role_gate_still_applies",
        )
        self.assertEqual(
            no_subagent_mode["mutation_upgrade_rule"],
            "upgrade_to_normal_gated_mode_before_write",
        )
        self.assertEqual(
            no_subagent_mode["read_only_audit_rule"],
            "do_not_run_non_product_audit_subagents",
        )
        self.assertEqual(
            {entry["id"] for entry in no_subagent_mode["decision_table"]},
            self.EXPECTED_NO_SUBAGENT_CASES,
        )

    def test_rejects_missing_no_subagent_mode_case(self) -> None:
        for case_id in self.EXPECTED_NO_SUBAGENT_CASES:
            with self.subTest(case_id=case_id):
                packet = copy.deepcopy(self.policy)
                packet["orchestration_model"]["no_subagent_mode"]["decision_table"] = [
                    entry
                    for entry in packet["orchestration_model"]["no_subagent_mode"]["decision_table"]
                    if entry["id"] != case_id
                ]
                errors = policy_module.validate_policy(packet)
                self.assertTrue(any(case_id in error for error in errors), errors)

    def test_no_subagent_side_conversation_skips_audits(self) -> None:
        no_subagent_mode = self.policy["orchestration_model"]["no_subagent_mode"]
        entry = {
            item["id"]: item
            for item in no_subagent_mode["decision_table"]
        }["side-conversation-answer"]
        self.assertEqual(entry["decision"], "allowed_no_subagent_mode")
        self.assertEqual(entry["scope"], "answer_only")
        self.assertEqual(entry["mutation_handling"], "forbidden")
        self.assertEqual(entry["stage_boundary_audits"], "not_run")
        self.assertEqual(entry["role_gate"], "apply_when_required")

    def test_no_subagent_bounded_repo_inspection_is_read_only(self) -> None:
        no_subagent_mode = self.policy["orchestration_model"]["no_subagent_mode"]
        entry = {
            item["id"]: item
            for item in no_subagent_mode["decision_table"]
        }["bounded-repo-inspection-no-mutation"]
        self.assertEqual(entry["decision"], "allowed_no_subagent_mode")
        self.assertEqual(entry["scope"], "bounded_read_only_repo_inspection")
        self.assertEqual(entry["mutation_handling"], "forbidden")
        self.assertEqual(entry["stage_boundary_audits"], "not_run")

    def test_no_subagent_mutation_upgrades_for_small_bugfix(self) -> None:
        no_subagent_mode = self.policy["orchestration_model"]["no_subagent_mode"]
        entry = {
            item["id"]: item
            for item in no_subagent_mode["decision_table"]
        }["small-exact-file-bugfix-policy-exception"]
        self.assertEqual(entry["decision"], "allowed_no_subagent_mode")
        self.assertEqual(
            entry["required_existing_policy"],
            "small exact-file bugfix exception",
        )
        self.assertEqual(
            entry["mutation_handling"],
            "upgrade_to_normal_gated_mode_before_write",
        )
        self.assertEqual(entry["role_gate"], "apply_when_required")

    def test_no_subagent_explicit_subagent_request_is_blocked(self) -> None:
        no_subagent_mode = self.policy["orchestration_model"]["no_subagent_mode"]
        entry = {
            item["id"]: item
            for item in no_subagent_mode["decision_table"]
        }["explicit-subagent-request"]
        self.assertEqual(entry["decision"], "blocked_no_subagent_mode")
        self.assertEqual(entry["required_result"], "subagent_mode_required")
        self.assertEqual(entry["role_gate"], "apply_when_required")

    def test_rejects_no_subagent_mode_role_gate_bypass(self) -> None:
        packet = copy.deepcopy(self.policy)
        packet["orchestration_model"]["no_subagent_mode"]["role_gate_rule"] = "skip_role_gate"
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("role_gate_rule" in error for error in errors), errors)

    def test_rejects_no_subagent_mutation_without_upgrade(self) -> None:
        packet = copy.deepcopy(self.policy)
        table = packet["orchestration_model"]["no_subagent_mode"]["decision_table"]
        for entry in table:
            if entry["id"] == "small-exact-file-bugfix-policy-exception":
                entry["mutation_handling"] = "write_in_no_subagent_mode"
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("mutation_handling" in error for error in errors), errors)

    def test_records_governed_validation_hook_runner(self) -> None:
        self.assertIn("governed-validation-hook-runner", self.policy["required_rule_ids"])
        runner = self.policy["orchestration_model"]["validation_hook_runner"]
        self.assertTrue(runner["required"])
        self.assertEqual(runner["request_model"], "named_hook_only")
        self.assertEqual(runner["cwd_policy"], "plugin_root_only")
        self.assertEqual(set(runner["controls"]), {"run_validators", "close"})
        self.assertEqual(
            set(runner["allowed_output_modes"]),
            {"bounded_json", "concise_text"},
        )
        self.assertIn("arbitrary_shell", runner["forbidden_request_kinds"])
        self.assertIn("inline_command", runner["forbidden_request_kinds"])
        self.assertEqual(
            {hook["hook_id"] for hook in runner["allowed_hooks"]},
            self.EXPECTED_VALIDATION_HOOKS,
        )
        self.assertTrue(
            self.EXPECTED_HOOK_RESULT_FIELDS.issubset(
                set(runner["result_schema"]["required_fields"])
            )
        )
        self.assertIn("raw_stdout", runner["result_schema"]["forbidden_fields"])
        self.assertIn("secret", runner["result_schema"]["forbidden_fields"])
        self.assertIn("raw_chat_read", runner["forbidden_request_kinds"])
        self.assertIn("raw_vpn_config_read", runner["forbidden_request_kinds"])
        self.assertIn("raw_log", runner["result_schema"]["forbidden_fields"])
        self.assertIn("raw_chat", runner["result_schema"]["forbidden_fields"])
        self.assertIn("raw_vpn_config", runner["result_schema"]["forbidden_fields"])
        self.assertIn("production_data", runner["result_schema"]["forbidden_fields"])

    def test_rejects_unknown_validation_hook(self) -> None:
        packet = copy.deepcopy(self.policy)
        packet["orchestration_model"]["validation_hook_runner"]["allowed_hooks"].append({
            "hook_id": "unknown_hook",
            "command_id": "unknown_hook",
            "script": "scripts/platform_roles.py",
            "args": ["validate"],
            "target_required": False,
        })
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("unexpected" in error and "unknown_hook" in error for error in errors), errors)

    def test_rejects_arbitrary_shell_validation_hook(self) -> None:
        packet = copy.deepcopy(self.policy)
        hook = packet["orchestration_model"]["validation_hook_runner"]["allowed_hooks"][0]
        hook["script"] = "scripts/run_anything.py"
        hook["args"] = ["bash", "-c", "{validation_target}"]
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("role_route.script" in error for error in errors), errors)
        self.assertTrue(any("forbidden shell token" in error for error in errors), errors)

    def test_rejects_missing_hook_result_schema_field(self) -> None:
        for field in self.EXPECTED_HOOK_RESULT_FIELDS:
            with self.subTest(field=field):
                packet = copy.deepcopy(self.policy)
                fields = packet["orchestration_model"]["validation_hook_runner"]["result_schema"]["required_fields"]
                fields.remove(field)
                errors = policy_module.validate_policy(packet)
                self.assertTrue(any(field in error for error in errors), errors)

    def test_rejects_raw_output_or_secret_result_fields(self) -> None:
        packet = copy.deepcopy(self.policy)
        forbidden = packet["orchestration_model"]["validation_hook_runner"]["result_schema"]["forbidden_fields"]
        forbidden.remove("raw_stdout")
        forbidden.remove("secret")
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("raw_stdout" in error for error in errors), errors)
        self.assertTrue(any("secret" in error for error in errors), errors)

    def test_rejects_missing_any_main_agent_allowed_action_token(self) -> None:
        for token in self.EXPECTED_MAIN_AGENT_ALLOWED_ACTIONS:
            with self.subTest(token=token):
                packet = copy.deepcopy(self.policy)
                packet["orchestration_model"]["main_agent_action_policy"]["allowed_actions"] = [
                    action
                    for action in packet["orchestration_model"]["main_agent_action_policy"]["allowed_actions"]
                    if action != token
                ]
                errors = policy_module.validate_policy(packet)
                self.assertTrue(
                    any(
                        "orchestration_model.main_agent_action_policy.allowed_actions missing required tokens"
                        in error
                        and token in error
                        for error in errors
                    ),
                    errors,
                )

    def test_rejects_missing_any_main_agent_forbidden_action_token(self) -> None:
        for token in self.EXPECTED_MAIN_AGENT_FORBIDDEN_ACTIONS:
            with self.subTest(token=token):
                packet = copy.deepcopy(self.policy)
                packet["orchestration_model"]["main_agent_action_policy"]["forbidden_actions"] = [
                    action
                    for action in packet["orchestration_model"]["main_agent_action_policy"]["forbidden_actions"]
                    if action != token
                ]
                errors = policy_module.validate_policy(packet)
                self.assertTrue(
                    any(
                        "orchestration_model.main_agent_action_policy.forbidden_actions missing required tokens"
                        in error
                        and token in error
                        for error in errors
                    ),
                    errors,
                )

    def test_records_pre_task_hook_controls(self) -> None:
        hook = self.policy["orchestration_model"]["pre_task_hook"]
        self.assertTrue(hook["required"])
        self.assertTrue(hook["runs_before_task_start"])
        self.assertEqual(hook["roadmap_entrypoint"], "/goal")
        self.assertEqual(set(hook["controls"]), {"spawn", "manage", "close"})
        self.assertEqual(
            set(hook["must_request_operator_inputs"]),
            {"missing data", "drift answers"},
        )
        for field in (
            "assignment packet id",
            "pre-task hook evidence",
            "operator missing data answers",
            "operator drift answers",
            "task-start authorization",
        ):
            with self.subTest(field=field):
                self.assertIn(field, hook["evidence_fields"])

    def test_rejects_missing_pre_task_hook_operator_input(self) -> None:
        packet = copy.deepcopy(self.policy)
        packet["orchestration_model"]["pre_task_hook"]["must_request_operator_inputs"] = [
            "missing data"
        ]
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("drift answers" in error for error in errors))

    def test_rejects_roadmap_not_routed_through_goal(self) -> None:
        packet = copy.deepcopy(self.policy)
        packet["orchestration_model"]["pre_task_hook"]["roadmap_entrypoint"] = "plans.md"
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("roadmap_entrypoint must be /goal" in error for error in errors))

    def test_records_spec_kit_gate_for_complex_mutation(self) -> None:
        self.assertIn("spec-kit-packet-before-broad-work", self.policy["required_rule_ids"])
        spec_gate = self.policy["lifecycle"]["spec_kit_gate"]
        self.assertEqual(spec_gate["required_artifacts"], ["spec.md", "plan.md", "tasks.md"])
        self.assertTrue(spec_gate["analyze_required"])
        for marker in ("plugin", "repo-boundary", "infra", "kubernetes", "migration"):
            with self.subTest(marker=marker):
                self.assertIn(marker, spec_gate["mandatory_for"])
        self.assertIn("small bugfix", " ".join(spec_gate["exemptions"]))

    def test_rejects_missing_lifecycle(self) -> None:
        packet = copy.deepcopy(self.policy)
        packet.pop("lifecycle")
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("lifecycle" in error for error in errors))

    def test_stage_boundary_audit_not_per_file(self) -> None:
        audit = self.policy["lifecycle"]["audit_policy"]
        self.assertEqual(audit["cadence"], "stage_boundary_only")
        self.assertIn("speckit-analyze PASS", audit["speckit_analyze_stage"])
        self.assertEqual(
            self.policy["lifecycle"]["stages"],
            [
                "route_gate",
                "constitution_gate",
                "research_gate",
                "prototype_gate",
                "design_gate",
                "spec_kit_gate",
                "role_gate",
                "subagent_execution",
                "validation",
                "stage_boundary_audit",
            ],
        )
        required_ids = set(self.policy["required_rule_ids"])
        self.assertIn("constitution-gate-before-research", required_ids)
        self.assertIn("plugin-fit-stage-boundary-audit", required_ids)
        self.assertNotIn("plugin-fit-post-task-audit", required_ids)
        self.assertEqual(
            self.policy["legacy_aliases"]["rule_ids"]["plugin-fit-post-task-audit"],
            "plugin-fit-stage-boundary-audit",
        )

    def test_rejects_lifecycle_without_constitution_gate(self) -> None:
        packet = copy.deepcopy(self.policy)
        packet["lifecycle"]["stages"].remove("constitution_gate")
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("constitution_gate" in error for error in errors), errors)

    def test_parallel_rule_requires_parallel_delegation_for_disjoint_p_tasks(self) -> None:
        rules = {rule["id"]: rule["rule"] for rule in self.policy["rules"]}
        text = rules["parallel-tasks-use-parallel-subagents"]
        self.assertIn("[P]", text)
        self.assertIn("MUST", text)
        self.assertIn("maximize parallelism", text)
        self.assertIn("parallel delegation", text)
        self.assertIn("disjoint", text)

    def test_rejects_weakened_parallel_rule(self) -> None:
        packet = copy.deepcopy(self.policy)
        for rule in packet["rules"]:
            if rule["id"] == "parallel-tasks-use-parallel-subagents":
                rule["rule"] = "Parallel tasks can be considered when convenient."
        errors = policy_module.validate_policy(packet)
        self.assertTrue(
            any("parallel-tasks-use-parallel-subagents text missing" in error for error in errors)
        )

    def test_records_non_blocking_parallel_audit_lane(self) -> None:
        self.assertIn("parallel-audit-lane-non-blocking", self.policy["required_rule_ids"])
        lane = self.policy["orchestration_model"]["parallel_audit_lane"]
        self.assertEqual(lane["implementation_authority"], "forbidden")
        self.assertEqual(lane["blocks_main_workflow"], "hard_stop_only")
        self.assertIn("wait_agent_checkpoint", lane["auditable_events"])
        severities = {item["level"]: item for item in lane["severity_levels"]}
        self.assertFalse(severities["warning"]["blocks_main_workflow"])
        self.assertFalse(severities["material"]["blocks_main_workflow"])
        self.assertTrue(severities["hard_stop"]["blocks_main_workflow"])
        self.assertIn("deduplication_key", lane["github_issue_policy"]["update_rule"])
        self.assertIn("raw_log", lane["github_issue_policy"]["issue_body_forbidden_fields"])
        self.assertEqual(
            set(lane["github_issue_policy"]["required_report_linkage_fields"]),
            {"created_issue", "updated_issue", "existing_issue"},
        )
        self.assertTrue(lane["github_issue_policy"]["report_only_blockers_rejected"])

    def test_records_parallel_commit_local_validation_test_closeout_lane(self) -> None:
        self.assertIn(
            "parallel-commit-local-validation-test-closeout-lane",
            self.policy["required_rule_ids"],
        )
        lane = self.policy["orchestration_model"]["commit_local_validation_test_closeout_lane"]
        self.assertTrue(lane["enabled"])
        self.assertEqual(lane["lane_id"], "parallel-commit-local-validation-test-closeout-lane")
        self.assertEqual(lane["start_condition"], "immediately_after_governed_workflow_start")
        self.assertEqual(lane["required_subagent_count"], 1)
        self.assertTrue(lane["parallel_with_parent_orchestrator"])
        self.assertEqual(lane["parent_wait_policy"], "do_not_wait")
        self.assertEqual(lane["model"], "gpt-5.4-mini")
        self.assertEqual(lane["reasoning_effort"], "medium")
        self.assertEqual(lane["prompt_prefix"], "/goal")
        self.assertEqual(lane["required_prompt_token"], "/goal")
        self.assertEqual(lane["required_role_profile"], "bears-git-workflow-helper")
        self.assertEqual(
            set(lane["responsibilities"]),
            self.EXPECTED_COMMIT_LOCAL_VALIDATION_TEST_CLOSEOUT_RESPONSIBILITIES,
        )
        local_test_policy = lane["local_test_policy"]
        self.assertEqual(
            local_test_policy["pytest_unittest_repo_validators"],
            "local_commit_validation_owned_only",
        )
        self.assertEqual(
            local_test_policy["manual_local_execution"],
            "forbidden_without_explicit_operator_lift",
        )
        self.assertEqual(
            set(local_test_policy["allowed_local_checks"]),
            self.EXPECTED_COMMIT_LOCAL_VALIDATION_TEST_CLOSEOUT_ALLOWED_CHECKS,
        )
        self.assertEqual(
            set(local_test_policy["forbidden_manual_checks"]),
            self.EXPECTED_COMMIT_LOCAL_VALIDATION_TEST_CLOSEOUT_FORBIDDEN_CHECKS,
        )
        hook_safety = lane["hook_safety_policy"]
        self.assertTrue(hook_safety["fast_hooks_only"])
        self.assertEqual(hook_safety["impacted_fast_tests_in_hooks"], "required")
        self.assertEqual(hook_safety["broad_tests_in_hooks"], "forbidden")
        self.assertEqual(hook_safety["network_calls_in_hooks"], "forbidden")
        self.assertEqual(hook_safety["raw_logs_in_hooks"], "forbidden")
        self.assertEqual(
            set(lane["closeout_required_fields"]),
            self.EXPECTED_COMMIT_LOCAL_VALIDATION_TEST_CLOSEOUT_CLOSEOUT_FIELDS,
        )
        self.assertEqual(
            lane["concurrent_git_safety_policy"],
            self.EXPECTED_CONCURRENT_GIT_SAFETY_POLICY,
        )

    def test_rejects_commit_local_validation_closeout_lane_without_helper_role(self) -> None:
        packet = copy.deepcopy(self.policy)
        packet["orchestration_model"]["commit_local_validation_test_closeout_lane"][
            "required_role_profile"
        ] = "bears-subagent-orchestration-engineer"
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("bears-git-workflow-helper" in error for error in errors), errors)

    def test_rejects_commit_local_validation_closeout_lane_when_force_push_not_forbidden(self) -> None:
        packet = copy.deepcopy(self.policy)
        packet["orchestration_model"]["commit_local_validation_test_closeout_lane"][
            "concurrent_git_safety_policy"
        ]["force_push_forbidden"] = False
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("force_push_forbidden" in error for error in errors), errors)

    def test_rejects_commit_local_validation_closeout_lane_without_fast_forward_only(self) -> None:
        packet = copy.deepcopy(self.policy)
        del packet["orchestration_model"]["commit_local_validation_test_closeout_lane"][
            "concurrent_git_safety_policy"
        ]["fast_forward_only_push"]
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("fast_forward_only_push" in error for error in errors), errors)

    def test_rejects_commit_local_validation_closeout_lane_without_one_file_one_owner(self) -> None:
        packet = copy.deepcopy(self.policy)
        del packet["orchestration_model"]["commit_local_validation_test_closeout_lane"][
            "concurrent_git_safety_policy"
        ]["one_file_one_owner_per_wave"]
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("one_file_one_owner_per_wave" in error for error in errors), errors)

    def test_rejects_commit_local_validation_closeout_lane_without_sha_and_files_fields(self) -> None:
        packet = copy.deepcopy(self.policy)
        closeout_fields = packet["orchestration_model"]["commit_local_validation_test_closeout_lane"][
            "closeout_required_fields"
        ]
        for field in ("start_sha", "final_sha", "changed_files"):
            closeout_fields.remove(field)
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("start_sha" in error for error in errors), errors)
        self.assertTrue(any("final_sha" in error for error in errors), errors)
        self.assertTrue(any("changed_files" in error for error in errors), errors)

    def test_rejects_commit_local_validation_closeout_lane_that_waits_for_parent(self) -> None:
        packet = copy.deepcopy(self.policy)
        packet["orchestration_model"]["commit_local_validation_test_closeout_lane"][
            "parent_wait_policy"
        ] = "wait"
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("parent_wait_policy must be do_not_wait" in error for error in errors), errors)

    def test_rejects_commit_local_validation_closeout_lane_without_goal_prompt_token(self) -> None:
        packet = copy.deepcopy(self.policy)
        lane = packet["orchestration_model"]["commit_local_validation_test_closeout_lane"]
        lane["prompt_prefix"] = "closeout"
        lane["required_prompt_token"] = "closeout"
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("/goal" in error for error in errors), errors)

    def test_rejects_commit_local_validation_closeout_lane_without_local_commit_validation_owned_tests_policy(self) -> None:
        packet = copy.deepcopy(self.policy)
        packet["orchestration_model"]["commit_local_validation_test_closeout_lane"][
            "local_test_policy"
        ]["pytest_unittest_repo_validators"] = "manual"
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("local_commit_validation_owned_only" in error for error in errors), errors)

    def test_hard_stop_packet_without_issue_linkage_fails_closed(self) -> None:
        packet = {
            "severity": "hard_stop",
            "issue_body": {
                "finding_summary": "Role coverage missing.",
                "severity": "hard_stop",
                "deduplication_key": "role:missing",
                "bounded_evidence_refs": ["docs/evidence/role.md"],
                "affected_target": "scripts/example.py",
                "required_next_action": "Create exact role mapping.",
                "hard_stop_condition": "ROLE_COVERAGE_BLOCKER",
            },
        }
        errors = policy_module.validate_parallel_audit_finding_packet(packet)
        self.assertIn("warning, material, and hard_stop findings require exactly one of created_issue, updated_issue, or existing_issue", errors)
        self.assertIn("report-only hard_stop finding is rejected without remediation issue linkage", errors)

    def test_warning_finding_with_issue_linkage_allows_monitoring_continue(self) -> None:
        packet = {
            "severity": "warning",
            "updated_issue": "https://github.com/BearsCLOUD/bears-codex-workflow-plugin/issues/91",
            "issue_body": {
                "finding_summary": "Doc drift warning.",
                "severity": "warning",
                "deduplication_key": "docs:drift",
                "bounded_evidence_refs": ["docs/evidence/drift.md"],
                "affected_target": "README.md",
                "required_next_action": "Align doc reference.",
                "hard_stop_condition": "not_applicable",
            },
        }
        self.assertEqual(policy_module.validate_parallel_audit_finding_packet(packet), [])

    def test_issue_body_rejects_restricted_data_fields(self) -> None:
        packet = {
            "severity": "material",
            "created_issue": "https://github.com/BearsCLOUD/bears-codex-workflow-plugin/issues/191",
            "issue_body": {
                "finding_summary": "Unsafe evidence.",
                "severity": "material",
                "deduplication_key": "unsafe:evidence",
                "bounded_evidence_refs": ["docs/evidence/redacted.md"],
                "affected_target": "policy",
                "required_next_action": "Remove unsafe field.",
                "hard_stop_condition": "not_applicable",
                "raw_log": "forbidden",
            },
        }
        errors = policy_module.validate_parallel_audit_finding_packet(packet)
        self.assertTrue(any("forbidden fields" in error for error in errors), errors)

    def test_rejects_parallel_audit_lane_that_blocks_non_hard_stop(self) -> None:
        packet = copy.deepcopy(self.policy)
        packet["orchestration_model"]["parallel_audit_lane"]["severity_levels"][1]["blocks_main_workflow"] = True
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("warning blocks_main_workflow must be False" in error for error in errors), errors)

    def test_rejects_parallel_audit_lane_with_implementation_authority(self) -> None:
        packet = copy.deepcopy(self.policy)
        packet["orchestration_model"]["parallel_audit_lane"]["implementation_authority"] = "allowed"
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("implementation_authority must be forbidden" in error for error in errors), errors)

    def test_rejects_parallel_audit_lane_without_deduplication_key(self) -> None:
        packet = copy.deepcopy(self.policy)
        packet["orchestration_model"]["parallel_audit_lane"]["github_issue_policy"]["deduplication_key_fields"].remove("target_path")
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("deduplication_key_fields missing" in error for error in errors), errors)

    def test_records_goal_parallelization_preflight(self) -> None:
        self.assertIn("goal-parallelization-preflight", self.policy["required_rule_ids"])
        preflight = self.policy["orchestration_model"]["goal_parallelization_preflight"]
        self.assertEqual(set(preflight), self.EXPECTED_GOAL_PREFLIGHT_TOP_FIELDS)
        self.assertTrue(preflight["enabled"])
        self.assertEqual(preflight["preflight_id"], "goal_parallelization_preflight")
        self.assertEqual(preflight["fixed_assignment_packet"]["packet_shape"], "fixed")
        self.assertIn("assignment_packet_id", preflight["fixed_assignment_packet"]["required_fields"])
        self.assertTrue(preflight["spawn_agent_argument_shape"]["strict_args_only"])
        self.assertIn("assignment_packet_id", preflight["spawn_agent_argument_shape"]["required_args"])
        self.assertEqual(
            preflight["spawn_agent_argument_shape"]["content_path_policy"]["exactly_one_of"],
            ["message", "items"],
        )
        self.assertTrue(
            preflight["spawn_agent_argument_shape"]["content_path_policy"][
                "reject_when_both_present"
            ]
        )
        self.assertEqual(
            preflight["spawn_agent_argument_shape"]["plugin_mention_canonical_form"][
                "content_path"
            ],
            "items",
        )
        self.assertEqual(
            preflight["spawn_agent_argument_shape"]["plugin_mention_canonical_form"][
                "items_length"
            ],
            1,
        )
        self.assertIn(
            "PRE_TASK_HOOK",
            preflight["spawn_agent_argument_shape"]["retry_path_preservation"][
                "preserve_sections_byte_for_byte"
            ],
        )
        self.assertTrue(preflight["wait_agent_target_validation"]["reject_unknown_target_id"])
        self.assertEqual(preflight["wait_any_loop"]["mode"], "wait_any")
        self.assertEqual(
            preflight["wait_any_loop"]["target_set_source"],
            "worker_pool_ledger.active_agent_ids",
        )
        self.assertTrue(
            preflight["worker_pool_ledger"]["completed_close_evidence_required_before_new_wave"]
        )
        self.assertTrue(
            preflight["worker_pool_ledger"]["partial_state_reconciliation_required_before_capacity_fallback"]
        )
        self.assertTrue(preflight["worker_pool_ledger"]["same_ledger_for_nested_subagents"])
        self.assertIn("parent_agent_id", preflight["worker_pool_ledger"]["required_fields"])
        self.assertIn("depth", preflight["worker_pool_ledger"]["required_fields"])
        self.assertIn("parent_authorization_id", preflight["worker_pool_ledger"]["required_fields"])
        self.assertIn("reuse_reason", preflight["worker_pool_ledger"]["required_fields"])
        self.assertEqual(preflight["backend_only_scope_lock"]["scope"], "backend_only")
        self.assertTrue(preflight["final_join_gate"]["blocks_parent_completion"])
        self.assertEqual(
            preflight["final_join_gate"]["gate_id"],
            "final_subagent_join_gate_before_parent_completion",
        )
        self.assertIn("queued", preflight["final_join_gate"]["fail_closed_states"])
        self.assertIn(
            "any_failed_subagent_without_disposition",
            preflight["final_join_gate"]["fail_closed_conditions"],
        )
        self.assertIn(
            "all_spawned_subagent_outcomes_integrated",
            preflight["final_join_gate"]["pass_conditions"],
        )
        self.assertEqual(
            preflight["result_policy"]["no_eligible_task_status"],
            "non_blocker",
        )
        self.assertIn("no_eligible_task", preflight["result_policy"]["non_blocking_results"])
        self.assertIn("no_write", preflight["result_policy"]["allowed_results"])
        self.assertIn("needs_parent_split", preflight["result_policy"]["allowed_results"])
        self.assertIn("no_write", preflight["result_policy"]["non_blocking_results"])
        self.assertIn("needs_parent_split", preflight["result_policy"]["non_blocking_results"])
        fanout = preflight["fanout_thread_limit_preflight"]
        self.assertTrue(fanout["active_open_count_required"])
        self.assertIn("worker_pool_ledger.active_agent_ids", fanout["active_open_count_sources"])
        self.assertIn("worker_pool_ledger.open_agent_ids", fanout["active_open_count_sources"])
        self.assertEqual(set(fanout["active_states_counted"]), {"spawned", "active"})
        self.assertEqual(
            set(fanout["open_states_counted"]),
            {"spawned", "active", "completed", "stale", "partial"},
        )
        self.assertTrue(fanout["completed_no_longer_needed_close_before_spawn"])
        self.assertEqual(
            fanout["close_completed_source"],
            "worker_pool_ledger.closeout_evidence",
        )
        self.assertEqual(
            fanout["critical_path_wait_slot_reservation"]["reserved_slots_min"],
            1,
        )
        self.assertTrue(fanout["bounded_batch_spawn_when_requested_exceeds_available"])
        self.assertEqual(fanout["thread_limit_failure_classification"], "WORKFLOW_DRIFT")
        self.assertFalse(fanout["thread_limit_failure_normal_recovery_allowed"])
        self.assertTrue(fanout["drift_evidence_required"])
        new_wave = preflight["new_wave_gate"]
        self.assertTrue(new_wave["block_completed_not_closed_without_reuse_reason"])
        self.assertEqual(new_wave["reuse_reason_source"], "worker_pool_ledger.reuse_reason")
        self.assertEqual(
            set(new_wave["checkpoint_count_fields"]),
            {"active_workers", "active_reviewers", "completed_not_closed_agents"},
        )
        plan_gate = preflight["parent_plan_status_gate"]
        self.assertTrue(plan_gate["required"])
        self.assertEqual(
            set(plan_gate["applies_to_steps"]),
            {"pull_request", "merge", "review"},
        )
        self.assertIn("merge_sha", plan_gate["merge_completed_extra_required_fields"])
        self.assertTrue(plan_gate["blocked_requires_bears_blocker_artifact"])
        self.assertIn("WORKFLOW_DRIFT", preflight["result_policy"]["blocked_results"])
        self.assertEqual(
            preflight["issue_mapping"],
            policy_module.EXPECTED_GOAL_PREFLIGHT_ISSUE_MAPPING,
        )

    def test_rejects_goal_parallelization_preflight_missing_fixed_assignment_packet(self) -> None:
        packet = copy.deepcopy(self.policy)
        packet["orchestration_model"]["goal_parallelization_preflight"].pop("fixed_assignment_packet")
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("fixed_assignment_packet" in error for error in errors), errors)

    def test_rejects_goal_parallelization_preflight_spawn_arg_gap(self) -> None:
        packet = copy.deepcopy(self.policy)
        args = packet["orchestration_model"]["goal_parallelization_preflight"]["spawn_agent_argument_shape"]["required_args"]
        args.remove("assignment_packet_id")
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("spawn_agent_argument_shape.required_args missing" in error and "assignment_packet_id" in error for error in errors), errors)

    def test_rejects_goal_parallelization_preflight_spawn_content_path_gap(self) -> None:
        packet = copy.deepcopy(self.policy)
        content = packet["orchestration_model"]["goal_parallelization_preflight"]["spawn_agent_argument_shape"]["content_path_policy"]
        content["reject_when_both_present"] = False
        content["exactly_one_of"] = ["items"]
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("exactly_one_of" in error and "message, items" in error for error in errors), errors)
        self.assertTrue(any("reject_when_both_present must be true" in error for error in errors), errors)

    def test_spawn_preflight_rejects_both_message_and_items_fixture(self) -> None:
        packet = policy_module.load_json(
            PLUGIN_ROOT / "tests/fixtures/spawn_agent_invalid_both_fields.json"
        )
        errors = policy_module.validate_spawn_agent_preflight_packet(packet, self.policy)
        self.assertTrue(
            any("invalid_spawn_agent_arguments" in error and "not both" in error for error in errors),
            errors,
        )

    def test_spawn_preflight_accepts_items_plugin_mention_fixture(self) -> None:
        packet = policy_module.load_json(
            PLUGIN_ROOT / "tests/fixtures/spawn_agent_valid_items_plugin_mention.json"
        )
        self.assertEqual(
            policy_module.validate_spawn_agent_preflight_packet(packet, self.policy),
            [],
        )

    def test_spawn_preflight_rejects_plugin_mention_in_message_path(self) -> None:
        packet = {
            "spawn_agent_arguments": {
                "assignment_packet_id": "issue-142:T002",
                "message": (
                    "@bears\n"
                    "PRE_TASK_HOOK\n"
                    "packet_id=issue-142:T002\n"
                    "ASSIGNMENT_PACKET\n"
                    "role=bears-subagent-orchestration-engineer"
                ),
            },
            "retry_path_preservation": {
                "schema_error_retry_logged_as_workflow_drift": True,
                "wrapper_only_change": True,
                "preserved_sections_byte_for_byte": [
                    "PRE_TASK_HOOK",
                    "ASSIGNMENT_PACKET",
                ],
            },
        }
        errors = policy_module.validate_spawn_agent_preflight_packet(packet, self.policy)
        self.assertTrue(any("message is forbidden for @bears plugin mention" in error for error in errors), errors)

    def test_goal_preflight_records_batch_role_gate_and_issue_handoff_guards(self) -> None:
        preflight = self.policy["orchestration_model"]["goal_parallelization_preflight"]
        self.assertTrue(preflight["batch_role_gate"]["required"])
        self.assertEqual(preflight["batch_role_gate"]["blocker_result"], "ROLE_COVERAGE_BLOCKER")
        self.assertEqual(
            preflight["batch_role_gate"]["command"],
            "python3 scripts/subagent_orchestration_policy.py batch-role-gate --paths-json <paths-json> --json",
        )
        guards = {guard["guard_id"]: guard for guard in preflight["handoff_guards"]}
        for guard_id in policy_module.REQUIRED_HANDOFF_GUARDS:
            self.assertIn(guard_id, guards)
            self.assertTrue(guards[guard_id]["required"])
            self.assertTrue(guards[guard_id]["issue"].startswith("BearsCLOUD/bears-codex-workflow-plugin#"))
        self.assertIn("frontend", preflight["backend_only_scope_lock"]["forbidden_task_surfaces"])
        self.assertIn("web client", preflight["backend_only_scope_lock"]["forbidden_task_surfaces"])

    def test_batch_role_gate_matches_known_subagent_policy_paths(self) -> None:
        result = policy_module.batch_role_gate(
            [
                "assets/catalog/subagent-orchestration-policy.v1.json",
                "scripts/subagent_orchestration_policy.py",
            ],
            self.policy,
        )
        self.assertEqual(result["status"], "matched")
        self.assertEqual(result["blockers"], [])
        self.assertEqual(
            {item["primary_role"] for item in result["matched"]},
            {"bears-subagent-orchestration-engineer"},
        )

    def test_spawn_preflight_rejects_fork_context_with_role_or_model_override(self) -> None:
        packet = {
            "spawn_agent_arguments": {
                "assignment_packet_id": "issue-84:T001",
                "fork_context": True,
                "agent_type": "bears-platform-security-reviewer",
                "model": "gpt-5.5",
                "items": [
                    {
                        "type": "text",
                        "text": "@bears\nPRE_TASK_HOOK\nASSIGNMENT_PACKET\nrole=bears-platform-security-reviewer",
                    }
                ],
            }
        }
        errors = policy_module.validate_spawn_agent_preflight_packet(packet, self.policy)
        self.assertTrue(any("fork_context_inheritance_violation" in error for error in errors), errors)

    def test_spawn_preflight_rejects_orchestrator_for_leaf_pr_delivery(self) -> None:
        packet = {
            "spawn_agent_arguments": {
                "assignment_packet_id": "issue-112:T001",
                "agent_type": "bears-orchestrator",
                "leaf_delivery": True,
                "actions": ["pr_merge"],
                "items": [
                    {
                        "type": "text",
                        "text": "@bears\nPRE_TASK_HOOK\nASSIGNMENT_PACKET\nleaf PR delivery only",
                    }
                ],
            }
        }
        errors = policy_module.validate_spawn_agent_preflight_packet(packet, self.policy)
        self.assertTrue(any("leaf_pr_delivery_role_guard" in error for error in errors), errors)

    def test_spawn_preflight_rejects_model_unsupported_reasoning_summary(self) -> None:
        packet = {
            "spawn_agent_arguments": {
                "assignment_packet_id": "issue-83:T001",
                "profile_path": "agents/agent-installer.toml",
                "model": "gpt-5.3-codex-spark",
                "reasoning": {"summary": "auto"},
                "items": [
                    {
                        "type": "text",
                        "text": "@bears\nPRE_TASK_HOOK\nASSIGNMENT_PACKET\nmodel capability preflight",
                    }
                ],
            }
        }
        errors = policy_module.validate_spawn_agent_preflight_packet(packet, self.policy)
        self.assertTrue(any("unsupported_model_parameter" in error for error in errors), errors)
        self.assertTrue(any("agents/agent-installer.toml" in error for error in errors), errors)

    def test_spawn_preflight_rejects_credential_surface_output_and_scout_implement_mix(self) -> None:
        packet = {
            "spawn_agent_arguments": {
                "assignment_packet_id": "issue-129:T001",
                "agent_type": "bears-subagent-orchestration-engineer",
                "items": [
                    {
                        "type": "text",
                        "text": (
                            "@bears\nPRE_TASK_HOOK\nASSIGNMENT_PACKET\n"
                            "Run gh auth status, then inspect and implement if found."
                        ),
                    }
                ],
            }
        }
        errors = policy_module.validate_spawn_agent_preflight_packet(packet, self.policy)
        self.assertTrue(any("credential_surface_output_guard" in error for error in errors), errors)
        self.assertTrue(any("discovery_implementation_split_guard" in error for error in errors), errors)

    def test_parent_control_rejects_patch_content_command(self) -> None:
        errors = policy_module.validate_parent_control_packet(
            {"command": "git diff -- /srv/bears/kubernetes | sed -n '1,260p'"}
        )
        self.assertTrue(any("parent_control_patch_content_forbidden" in error for error in errors), errors)
        self.assertEqual(
            policy_module.validate_parent_control_packet({"command": "git diff --stat"}),
            [],
        )
        self.assertEqual(
            policy_module.validate_parent_control_packet({"command": "git diff --name-status"}),
            [],
        )

    def test_pr_publication_closeout_requires_no_checks_and_merge_not_authorized(self) -> None:
        packet = {
            "isDraft": False,
            "reviewDecision": "",
            "statusCheckRollup": [],
            "closeout_markers": [],
        }
        errors = policy_module.validate_pr_publication_closeout_packet(packet)
        self.assertTrue(any("MERGE_NOT_AUTHORIZED" in error for error in errors), errors)
        self.assertTrue(any("NO_CHECKS_REPORTED" in error for error in errors), errors)
        valid = dict(packet)
        valid["closeout_markers"] = ["NO_CHECKS_REPORTED", "MERGE_NOT_AUTHORIZED"]
        self.assertEqual(policy_module.validate_pr_publication_closeout_packet(valid), [])

    def test_subagent_closeout_rejects_non_english_and_unscoped_fail(self) -> None:
        non_english = {"status": "PASS", "summary": "Файлы изменены, проверки пройдены"}
        self.assertTrue(
            any(
                "English-only" in error
                for error in policy_module.validate_subagent_closeout_quality_packet(non_english)
            )
        )
        unscoped = {
            "verdict": "FAIL",
            "assigned_slice_passed": True,
            "remaining_work": ["T085"],
        }
        errors = policy_module.validate_subagent_closeout_quality_packet(unscoped)
        self.assertTrue(any("PASS_WITH_REMAINING_WORK" in error for error in errors), errors)

    def test_rejects_goal_parallelization_preflight_wait_target_gap(self) -> None:
        packet = copy.deepcopy(self.policy)
        target = packet["orchestration_model"]["goal_parallelization_preflight"]["wait_agent_target_validation"]
        target["reject_unknown_target_id"] = False
        target["target_id_sources"].remove("worker_pool_ledger.agent_id")
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("reject_unknown_target_id must be true" in error for error in errors), errors)
        self.assertTrue(any("target_id_sources missing" in error and "worker_pool_ledger.agent_id" in error for error in errors), errors)

    def test_rejects_goal_parallelization_preflight_fanout_thread_limit_gap(self) -> None:
        packet = copy.deepcopy(self.policy)
        fanout = packet["orchestration_model"]["goal_parallelization_preflight"]["fanout_thread_limit_preflight"]
        fanout["active_open_count_required"] = False
        fanout["active_open_count_sources"].remove("worker_pool_ledger.open_agent_ids")
        fanout["critical_path_wait_slot_reservation"]["reserved_slots_min"] = 0
        fanout["bounded_batch_spawn_when_requested_exceeds_available"] = False
        fanout["thread_limit_failure_classification"] = "NORMAL_RECOVERY"
        fanout["thread_limit_failure_normal_recovery_allowed"] = True

        errors = policy_module.validate_policy(packet)

        self.assertTrue(any("active_open_count_required must be true" in error for error in errors), errors)
        self.assertTrue(any("active_open_count_sources missing" in error for error in errors), errors)
        self.assertTrue(any("reserved_slots_min must be 1" in error for error in errors), errors)
        self.assertTrue(any("bounded_batch_spawn_when_requested_exceeds_available must be true" in error for error in errors), errors)
        self.assertTrue(any("thread_limit_failure_classification must be WORKFLOW_DRIFT" in error for error in errors), errors)
        self.assertTrue(any("thread_limit_failure_normal_recovery_allowed must be false" in error for error in errors), errors)

    def test_rejects_goal_parallelization_preflight_worker_ledger_reconciliation_gap(self) -> None:
        packet = copy.deepcopy(self.policy)
        ledger = packet["orchestration_model"]["goal_parallelization_preflight"]["worker_pool_ledger"]
        ledger["partial_state_reconciliation_required_before_capacity_fallback"] = False
        ledger["same_ledger_for_nested_subagents"] = False
        ledger["nested_tracking_fields"].remove("parent_agent_id")
        errors = policy_module.validate_policy(packet)
        self.assertTrue(
            any("worker_pool_ledger.partial_state_reconciliation_required_before_capacity_fallback must be true" in error for error in errors),
            errors,
        )
        self.assertTrue(any("same_ledger_for_nested_subagents must be true" in error for error in errors), errors)
        self.assertTrue(any("nested_tracking_fields missing" in error and "parent_agent_id" in error for error in errors), errors)

    def test_rejects_goal_parallelization_preflight_new_wave_gate_gap(self) -> None:
        packet = copy.deepcopy(self.policy)
        new_wave = packet["orchestration_model"]["goal_parallelization_preflight"]["new_wave_gate"]
        new_wave["block_completed_not_closed_without_reuse_reason"] = False
        new_wave["checkpoint_count_fields"].remove("active_reviewers")
        errors = policy_module.validate_policy(packet)
        self.assertTrue(
            any("block_completed_not_closed_without_reuse_reason must be true" in error for error in errors),
            errors,
        )
        self.assertTrue(any("checkpoint_count_fields missing" in error and "active_reviewers" in error for error in errors), errors)

    def test_rejects_parent_plan_status_gate_gap(self) -> None:
        packet = copy.deepcopy(self.policy)
        gate = packet["orchestration_model"]["goal_parallelization_preflight"]["parent_plan_status_gate"]
        gate["completed_required_evidence_fields"].remove("worker_closeout_evidence")
        gate["blocked_requires_bears_blocker_artifact"] = False
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("worker_closeout_evidence" in error for error in errors), errors)
        self.assertTrue(any("blocked_requires_bears_blocker_artifact must be true" in error for error in errors), errors)

    def test_rejects_goal_parallelization_preflight_backend_scope_gap(self) -> None:
        packet = copy.deepcopy(self.policy)
        lock = packet["orchestration_model"]["goal_parallelization_preflight"]["backend_only_scope_lock"]
        lock["scope"] = "full_stack"
        lock["forbidden_task_surfaces"].remove("github_pr_issue_state")
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("backend_only_scope_lock.scope must be backend_only" in error for error in errors), errors)
        self.assertTrue(any("forbidden_task_surfaces missing" in error and "github_pr_issue_state" in error for error in errors), errors)

    def test_rejects_goal_parallelization_preflight_no_eligible_task_blocker(self) -> None:
        packet = copy.deepcopy(self.policy)
        result_policy = packet["orchestration_model"]["goal_parallelization_preflight"]["result_policy"]
        result_policy["non_blocking_results"] = []
        result_policy["no_eligible_task_status"] = "blocked"
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("non_blocking_results missing" in error and "no_eligible_task" in error for error in errors), errors)
        self.assertTrue(any("no_eligible_task_status must be non_blocker" in error for error in errors), errors)

    def test_rejects_goal_parallelization_preflight_final_join_gap(self) -> None:
        packet = copy.deepcopy(self.policy)
        join = packet["orchestration_model"]["goal_parallelization_preflight"]["final_join_gate"]
        join["blocks_parent_completion"] = False
        join["fail_closed_states"].remove("queued")
        join["fail_closed_conditions"].remove("any_completed_subagent_without_close_decision")
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("final_join_gate.blocks_parent_completion must be true" in error for error in errors), errors)
        self.assertTrue(any("final_join_gate.fail_closed_states missing" in error and "queued" in error for error in errors), errors)
        self.assertTrue(
            any(
                "final_join_gate.fail_closed_conditions missing" in error
                and "any_completed_subagent_without_close_decision" in error
                for error in errors
            ),
            errors,
        )

    def test_rejects_goal_parallelization_preflight_missing_final_join_rule(self) -> None:
        packet = copy.deepcopy(self.policy)
        packet["orchestration_model"]["goal_parallelization_preflight"].pop("final_join_gate")
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("final_join_gate" in error for error in errors), errors)

    def test_final_subagent_join_gate_passes_integrated_closed_outcomes(self) -> None:
        request = {
            "worker_pool_ledger": [
                {
                    "agent_id": "agent-1",
                    "state": "closed",
                    "outcome_integrated": True,
                    "integrated_evidence": "validator exit 0",
                    "close_decision": "accepted",
                },
                {
                    "agent_id": "agent-2",
                    "state": "failed",
                    "outcome_integrated": True,
                    "integrated_evidence": "failure reviewed",
                    "close_decision": "rejected",
                    "failure_disposition": "superseded by parent fix",
                },
            ],
            "dependent_waits": [
                {"wait_id": "wait-1", "status": "resolved"},
            ],
        }

        gate = policy_module.evaluate_final_subagent_join_gate(request, self.policy)

        self.assertEqual(gate["status"], "passed")
        self.assertFalse(gate["blocks_parent_completion"])
        self.assertEqual(gate["block_reasons"], [])
        self.assertEqual(gate["joined_agent_ids"], ["agent-1", "agent-2"])
        self.assertTrue(gate["no_dependent_wait_remaining"])

    def test_final_subagent_join_gate_supports_ledger_object_scope(self) -> None:
        request = {
            "worker_pool_ledger": {
                "all_spawned_agent_ids": ["agent-1"],
                "agents": [
                    {
                        "agent_id": "agent-1",
                        "state": "closed",
                        "outcome_integrated": True,
                        "integrated_evidence": "validator exit 0",
                        "close_decision": "accepted",
                    }
                ],
            },
            "dependent_waits": [
                {"wait_id": "wait-1", "status": "resolved"},
            ],
        }

        gate = policy_module.evaluate_final_subagent_join_gate(request, self.policy)

        self.assertEqual(gate["status"], "passed")
        self.assertEqual(gate["joined_agent_ids"], ["agent-1"])

    def test_final_subagent_join_gate_fails_closed_for_missing_spawned_id_in_ledger_object(
        self,
    ) -> None:
        request = {
            "worker_pool_ledger": {
                "all_spawned_agent_ids": ["missing-agent"],
                "entries": [],
            },
            "dependent_waits": [
                {"wait_id": "wait-1", "status": "resolved"},
            ],
        }

        gate = policy_module.evaluate_final_subagent_join_gate(request, self.policy)

        self.assertEqual(gate["status"], "blocked")
        self.assertTrue(gate["blocks_parent_completion"])
        self.assertEqual(gate["joined_agent_ids"], [])
        self.assertEqual(gate["pending_agent_ids"], ["missing-agent"])
        self.assertIn(
            "any_spawned_subagent_missing_terminal_evidence",
            gate["block_reasons"],
        )

    def test_final_subagent_join_gate_fails_closed_for_open_or_unintegrated_outcomes(self) -> None:
        request = {
            "worker_pool_ledger": [
                {"agent_id": "agent-active", "state": "active"},
                {"agent_id": "agent-queued", "state": "queued"},
                {"agent_id": "agent-unknown", "state": "mystery"},
                {
                    "agent_id": "agent-failed",
                    "state": "failed",
                    "outcome_integrated": True,
                    "integrated_evidence": "failure observed",
                    "close_decision": "rejected",
                },
                {
                    "agent_id": "agent-completed-no-evidence",
                    "state": "completed",
                    "close_decision": "accepted",
                },
                {
                    "agent_id": "agent-completed-no-decision",
                    "state": "completed",
                    "outcome_integrated": True,
                    "integrated_evidence": "validator exit 0",
                },
            ],
            "dependent_waits": [
                {"wait_id": "wait-1", "status": "active"},
            ],
        }

        gate = policy_module.evaluate_final_subagent_join_gate(request, self.policy)

        self.assertEqual(gate["status"], "blocked")
        self.assertTrue(gate["blocks_parent_completion"])
        self.assertIn("any_spawned_subagent_active", gate["block_reasons"])
        self.assertIn("any_spawned_subagent_queued", gate["block_reasons"])
        self.assertIn("any_spawned_subagent_unknown", gate["block_reasons"])
        self.assertIn("any_failed_subagent_without_disposition", gate["block_reasons"])
        self.assertIn("any_completed_subagent_without_integrated_evidence", gate["block_reasons"])
        self.assertIn("any_completed_subagent_without_close_decision", gate["block_reasons"])
        self.assertIn("any_dependent_wait_remaining", gate["block_reasons"])
        self.assertEqual(
            gate["pending_agent_ids"],
            [
                "agent-active",
                "agent-queued",
                "agent-unknown",
                "agent-failed",
                "agent-completed-no-evidence",
                "agent-completed-no-decision",
            ],
        )

    def test_goal_parallelization_ready_two_lane_plan(self) -> None:
        request = {
            "goal_id": "issue-173",
            "tasks": [
                {
                    "id": "T001",
                    "target_path": "scripts/subagent_orchestration_policy.py",
                    "task_surface": "validator_script",
                    "write_scope": ["scripts/subagent_orchestration_policy.py"],
                },
                {
                    "id": "T002",
                    "target_path": "tests/test_subagent_orchestration_policy.py",
                    "task_surface": "unit_tests",
                    "write_scope": ["tests/test_subagent_orchestration_policy.py"],
                },
            ],
        }

        plan = policy_module.plan_goal_parallelization(request, self.policy)

        self.assertEqual(plan["schema"], policy_module.PARALLELIZATION_PLAN_SCHEMA)
        self.assertTrue(plan["read_only"])
        self.assertEqual(plan["status"], "ready")
        self.assertEqual(plan["default_active_worker_count"], 2)
        self.assertEqual(plan["block_reasons"], [])
        self.assertEqual(len(plan["assignment_packets"]), 2)
        self.assertEqual(len(plan["worker_pool_ledger"]), 2)
        self.assertEqual(plan["fanout_thread_limit_preflight"]["active_open_count"], 0)
        self.assertEqual(plan["fanout_thread_limit_preflight"]["open_count"], 0)
        self.assertEqual(plan["fanout_thread_limit_preflight"]["available_slots"], 15)
        self.assertFalse(plan["fanout_thread_limit_preflight"]["bounded_batches_required"])
        self.assertEqual(
            plan["fanout_thread_limit_preflight"]["spawn_batches"],
            [{"wave": 1, "max_spawn_count": 2, "wait_before_next_wave": False}],
        )
        self.assertEqual(
            {lane["role"] for lane in plan["lanes"]},
            {"bears-subagent-orchestration-engineer"},
        )
        self.assertTrue(all(lane["eligible_for_parallel_wave"] for lane in plan["lanes"]))

    def test_goal_parallelization_counts_open_agents_and_batches_fanout(self) -> None:
        request = {
            "goal_id": "issue-154",
            "worker_pool_ledger": [
                *[
                    {"agent_id": f"agent-{index}", "state": "active"}
                    for index in range(1, 15)
                ],
                {
                    "agent_id": "agent-completed",
                    "state": "completed",
                    "no_longer_needed": True,
                    "closeout_evidence": "closeout-packet",
                    "reuse_reason": "reuse for follow-up review",
                },
            ],
            "tasks": [
                {
                    "id": "T001",
                    "target_path": "scripts/subagent_orchestration_policy.py",
                    "task_surface": "validator_script",
                    "write_scope": ["scripts/subagent_orchestration_policy.py"],
                },
                {
                    "id": "T002",
                    "target_path": "tests/test_subagent_orchestration_policy.py",
                    "task_surface": "unit_tests",
                    "write_scope": ["tests/test_subagent_orchestration_policy.py"],
                },
            ],
        }

        plan = policy_module.plan_goal_parallelization(request, self.policy)

        fanout = plan["fanout_thread_limit_preflight"]
        self.assertEqual(plan["status"], "ready")
        self.assertEqual(plan["default_active_worker_count"], 1)
        self.assertEqual(fanout["active_open_count"], 14)
        self.assertEqual(fanout["open_count"], 15)
        self.assertEqual(fanout["completed_no_longer_needed_agent_ids"], ["agent-completed"])
        self.assertTrue(fanout["close_before_spawn_required"])
        self.assertEqual(fanout["reserved_critical_wait_slots"], 1)
        self.assertEqual(fanout["available_slots"], 1)
        self.assertTrue(fanout["bounded_batches_required"])
        self.assertEqual(
            fanout["spawn_batches"],
            [
                {"wave": 1, "max_spawn_count": 1, "wait_before_next_wave": True},
                {"wave": 2, "max_spawn_count": 1, "wait_before_next_wave": False},
            ],
        )

    def test_new_wave_blocks_completed_not_closed_without_reuse_reason(self) -> None:
        request = {
            "goal_id": "issue-138",
            "worker_pool_ledger": [
                {"agent_id": "worker-active", "role": "bears-subagent-orchestration-engineer", "state": "active"},
                {"agent_id": "reviewer-active", "role": "bears-platform-security-reviewer", "state": "active"},
                {"agent_id": "worker-done", "role": "bears-subagent-orchestration-engineer", "state": "completed"},
            ],
            "tasks": [
                {
                    "id": "T001",
                    "target_path": "scripts/subagent_orchestration_policy.py",
                    "task_surface": "validator_script",
                    "write_scope": ["scripts/subagent_orchestration_policy.py"],
                },
            ],
        }

        plan = policy_module.plan_goal_parallelization(request, self.policy)

        self.assertEqual(plan["status"], "blocked")
        self.assertEqual(plan["assignment_packets"], [])
        self.assertIn(
            "completed_not_closed_subagent_without_reuse_reason:worker-done",
            plan["block_reasons"],
        )
        checkpoint = plan["new_wave_closeout_checkpoint"]
        self.assertEqual(
            checkpoint["counts"],
            {
                "active_workers": 1,
                "active_reviewers": 1,
                "completed_not_closed_agents": 1,
            },
        )
        self.assertFalse(checkpoint["new_wave_allowed"])

    def test_new_wave_blocks_object_form_completed_id_without_reuse_reason(self) -> None:
        request = {
            "goal_id": "issue-138",
            "worker_pool_ledger": {
                "active_agent_ids": ["worker-active"],
                "open_agent_ids": ["worker-active", "worker-done"],
                "completed_agent_ids": ["worker-done"],
            },
            "tasks": [
                {
                    "id": "T001",
                    "target_path": "scripts/subagent_orchestration_policy.py",
                    "task_surface": "validator_script",
                    "write_scope": ["scripts/subagent_orchestration_policy.py"],
                },
            ],
        }

        plan = policy_module.plan_goal_parallelization(request, self.policy)

        self.assertEqual(plan["status"], "blocked")
        self.assertEqual(plan["assignment_packets"], [])
        self.assertIn(
            "completed_not_closed_subagent_without_reuse_reason:worker-done",
            plan["block_reasons"],
        )
        checkpoint = plan["new_wave_closeout_checkpoint"]
        self.assertEqual(
            checkpoint["counts"],
            {
                "active_workers": 1,
                "active_reviewers": 0,
                "completed_not_closed_agents": 1,
            },
        )
        self.assertEqual(checkpoint["active_worker_agent_ids"], ["worker-active"])
        self.assertEqual(checkpoint["completed_not_closed_agent_ids"], ["worker-done"])
        self.assertFalse(checkpoint["new_wave_allowed"])
        fanout = plan["fanout_thread_limit_preflight"]
        self.assertEqual(fanout["active_agent_ids"], ["worker-active"])
        self.assertEqual(fanout["open_agent_ids"], ["worker-active", "worker-done"])
        self.assertEqual(fanout["active_open_count"], 1)
        self.assertEqual(fanout["open_count"], 2)

    def test_new_wave_allows_completed_not_closed_with_reuse_reason(self) -> None:
        request = {
            "goal_id": "issue-138",
            "worker_pool_ledger": [
                {
                    "agent_id": "worker-done",
                    "role": "bears-subagent-orchestration-engineer",
                    "state": "completed",
                    "reuse_reason": "same role and scope follow-up wave",
                },
            ],
            "tasks": [
                {
                    "id": "T001",
                    "target_path": "scripts/subagent_orchestration_policy.py",
                    "task_surface": "validator_script",
                    "write_scope": ["scripts/subagent_orchestration_policy.py"],
                },
            ],
        }

        plan = policy_module.plan_goal_parallelization(request, self.policy)

        self.assertEqual(plan["status"], "ready")
        self.assertEqual(len(plan["assignment_packets"]), 1)
        self.assertTrue(plan["new_wave_closeout_checkpoint"]["new_wave_allowed"])

    def test_parent_plan_completed_merge_requires_exact_closeout_evidence(self) -> None:
        packet = {
            "step_type": "merge",
            "status": "completed",
            "evidence": {
                "pr_url": "https://github.com/BearsCLOUD/bears-codex-workflow-plugin/pull/999",
                "merge_sha": "abc1234",
                "check_status": "PASS",
                "reviewer_pass_evidence": "reviewer PASS in closeout",
                "worker_closeout_evidence": "worker closed with validators exit 0",
            },
            "worker_pool_ledger": [
                {"agent_id": "worker-1", "state": "closed"},
            ],
        }

        self.assertEqual(
            policy_module.validate_parent_plan_status_update(packet, self.policy),
            [],
        )

    def test_parent_plan_completed_pr_rejects_missing_closeout_evidence(self) -> None:
        packet = {
            "step_type": "pull_request",
            "status": "completed",
            "evidence": {
                "pr_url": "https://github.com/BearsCLOUD/bears-codex-workflow-plugin/pull/999",
                "check_status": "pending",
                "reviewer_pass_evidence": "review pending",
            },
        }

        errors = policy_module.validate_parent_plan_status_update(packet, self.policy)

        self.assertTrue(any("worker_closeout_evidence" in error for error in errors), errors)
        self.assertTrue(any("check_status" in error for error in errors), errors)
        self.assertTrue(any("reviewer_pass_evidence must include PASS" in error for error in errors), errors)

    def test_parent_plan_remains_in_progress_while_prerequisite_worker_active(self) -> None:
        packet = {
            "step_type": "review",
            "status": "completed",
            "prerequisite_worker_id": "worker-1",
            "evidence": {
                "pr_url": "https://github.com/BearsCLOUD/bears-codex-workflow-plugin/pull/999",
                "check_status": "PASS",
                "reviewer_pass_evidence": "reviewer PASS",
                "worker_closeout_evidence": "worker closeout",
            },
            "worker_pool_ledger": [
                {"agent_id": "worker-1", "state": "active"},
            ],
        }

        errors = policy_module.validate_parent_plan_status_update(packet, self.policy)

        self.assertTrue(any("must remain in_progress" in error for error in errors), errors)

    def test_parent_plan_blocked_requires_named_bears_blocker_artifact(self) -> None:
        missing = {
            "step_type": "review",
            "status": "blocked",
        }
        self.assertTrue(
            any("bears_blocker_artifact required" in error for error in policy_module.validate_parent_plan_status_update(missing, self.policy))
        )
        valid = {
            "step_type": "review",
            "status": "blocked",
            "bears_blocker_artifact": {
                "artifact_id": "blocker-145",
                "artifact_type": "bears-blocker-review",
                "status": "blocked",
                "owner": "bears-subagent-orchestration-engineer",
                "path_or_url": "issues/145",
            },
        }

        self.assertEqual(policy_module.validate_parent_plan_status_update(valid, self.policy), [])

    def test_goal_parallelization_classifies_thread_limit_failure_as_drift(self) -> None:
        request = {
            "goal_id": "issue-154",
            "last_spawn_failure": {
                "code": "thread_limit",
                "message": "thread limit reached",
            },
            "tasks": [
                {
                    "id": "T001",
                    "target_path": "scripts/subagent_orchestration_policy.py",
                    "task_surface": "validator_script",
                    "write_scope": ["scripts/subagent_orchestration_policy.py"],
                },
            ],
        }

        plan = policy_module.plan_goal_parallelization(request, self.policy)

        fanout = plan["fanout_thread_limit_preflight"]
        self.assertEqual(plan["status"], "blocked")
        self.assertEqual(plan["assignment_packets"], [])
        self.assertIn("WORKFLOW_DRIFT:thread_limit_spawn_failure", plan["block_reasons"])
        self.assertEqual(fanout["thread_limit_failure_classification"], "WORKFLOW_DRIFT")
        self.assertFalse(fanout["normal_recovery_allowed"])
        self.assertTrue(fanout["drift_evidence_required"])

    def test_goal_parallelization_reports_role_coverage_blocker(self) -> None:
        request = {
            "goal_id": "issue-173",
            "tasks": [
                {
                    "id": "T001",
                    "target_path": "unknown/not-mapped.file",
                    "task_surface": "validator_script",
                },
            ],
        }

        plan = policy_module.plan_goal_parallelization(request, self.policy)

        self.assertEqual(plan["status"], "blocked")
        self.assertEqual(plan["assignment_packets"], [])
        self.assertEqual(plan["role_gaps"][0]["status"], "ROLE_COVERAGE_BLOCKER")
        self.assertIn("role_coverage_gaps", plan["block_reasons"])
        self.assertIn("ROLE_COVERAGE_BLOCKER:unknown/not-mapped.file", plan["lanes"][0]["block_reasons"])

    def test_goal_parallelization_blocks_write_scope_and_repo_boundary_mismatch(self) -> None:
        request = {
            "goal_id": "issue-173",
            "tasks": [
                {
                    "id": "T001",
                    "target_path": "scripts/subagent_orchestration_policy.py",
                    "task_surface": "validator_script",
                    "write_scope": ["README.md", "/srv/bears/kubernetes"],
                    "repo_boundary": "BearsCLOUD/other-repo",
                },
            ],
        }

        plan = policy_module.plan_goal_parallelization(request, self.policy)

        self.assertEqual(plan["status"], "blocked")
        self.assertEqual(plan["assignment_packets"], [])
        blockers = plan["lanes"][0]["block_reasons"]
        self.assertIn("repo_boundary_mismatch:BearsCLOUD/other-repo", blockers)
        self.assertIn("write_scope_route_mismatch:README.md", blockers)
        self.assertIn("write_scope_route_mismatch:/srv/bears/kubernetes", blockers)

    def test_goal_parallelization_blocks_external_target_with_plugin_repo_boundary(self) -> None:
        request = {
            "goal_id": "issue-173",
            "tasks": [
                {
                    "id": "T001",
                    "target_path": "/srv/bears/kubernetes",
                    "task_surface": "kubernetes",
                    "repo_boundary": policy_module.PARALLELIZATION_REPO_BOUNDARY,
                },
            ],
        }

        plan = policy_module.plan_goal_parallelization(request, self.policy)

        self.assertEqual(plan["status"], "blocked")
        self.assertEqual(plan["assignment_packets"], [])
        blockers = plan["lanes"][0]["block_reasons"]
        self.assertIn("target_path_outside_plugin_root:/srv/bears/kubernetes", blockers)
        self.assertIn("write_scope_outside_plugin_root:/srv/bears/kubernetes", blockers)
        self.assertIn("target_path_outside_plugin_root:/srv/bears/kubernetes", plan["block_reasons"])

    def test_goal_parallelization_blocks_path_traversal_in_write_scope(self) -> None:
        request = {
            "goal_id": "issue-173",
            "tasks": [
                {
                    "id": "T001",
                    "target_path": "scripts/subagent_orchestration_policy.py",
                    "task_surface": "validator_script",
                    "write_scope": ["scripts/subagent_orchestration_policy.py", "../kubernetes"],
                },
            ],
        }

        plan = policy_module.plan_goal_parallelization(request, self.policy)

        self.assertEqual(plan["status"], "blocked")
        self.assertEqual(plan["assignment_packets"], [])
        self.assertIn("write_scope_outside_plugin_root:../kubernetes", plan["block_reasons"])
        self.assertIn("write_scope_outside_plugin_root:../kubernetes", plan["lanes"][0]["block_reasons"])

    def test_goal_parallelization_blocks_backend_only_forbidden_surface_in_write_scope(self) -> None:
        request = {
            "goal_id": "issue-173",
            "tasks": [
                {
                    "id": "T001",
                    "target_path": "scripts/subagent_orchestration_policy.py",
                    "task_surface": "validator_script",
                    "write_scope": ["README.md"],
                },
            ],
        }

        plan = policy_module.plan_goal_parallelization(request, self.policy)

        self.assertEqual(plan["status"], "blocked")
        self.assertEqual(plan["assignment_packets"], [])
        self.assertIn("backend_only_forbidden_surface:README", plan["block_reasons"])
        self.assertIn("backend_only_forbidden_surface:README", plan["lanes"][0]["block_reasons"])

    def test_goal_parallelization_blocks_request_backend_only_scope_lock_disabled(self) -> None:
        request = {
            "goal_id": "issue-173",
            "backend_only_scope_lock": False,
            "tasks": [
                {
                    "id": "T001",
                    "target_path": "README.md",
                    "task_surface": "validator_script",
                    "write_scope": ["README.md"],
                },
            ],
        }

        plan = policy_module.plan_goal_parallelization(request, self.policy)

        self.assertEqual(plan["status"], "blocked")
        self.assertTrue(plan["backend_only_scope_lock"])
        self.assertEqual(plan["assignment_packets"], [])
        self.assertIn("backend_only_scope_lock_disabled", plan["block_reasons"])
        self.assertIn("backend_only_forbidden_surface:README", plan["block_reasons"])
        self.assertIn("backend_only_scope_lock_disabled", plan["lanes"][0]["block_reasons"])
        self.assertIn("backend_only_forbidden_surface:README", plan["lanes"][0]["block_reasons"])

    def test_goal_parallelization_blocks_overlapping_write_scope(self) -> None:
        request = {
            "goal_id": "issue-173",
            "tasks": [
                {
                    "id": "T001",
                    "target_path": "scripts/subagent_orchestration_policy.py",
                    "task_surface": "validator_script",
                    "write_scope": ["scripts/subagent_orchestration_policy.py"],
                },
                {
                    "id": "T002",
                    "target_path": "scripts/subagent_orchestration_policy.py",
                    "task_surface": "validator_script",
                    "write_scope": ["scripts/subagent_orchestration_policy.py"],
                },
            ],
        }

        plan = policy_module.plan_goal_parallelization(request, self.policy)

        blocker = "overlapping_write_scope:scripts/subagent_orchestration_policy.py"
        self.assertEqual(plan["status"], "blocked")
        self.assertEqual(plan["classification"], "blocked")
        self.assertEqual(plan["assignment_packets"], [])
        self.assertIn(blocker, plan["block_reasons"])
        self.assertTrue(all(blocker in lane["block_reasons"] for lane in plan["lanes"]))
        self.assertTrue(all(lane["classification"] == "blocked" for lane in plan["lanes"]))
        self.assertTrue(all(blocker in lane["classification_reasons"] for lane in plan["lanes"]))
        self.assertTrue(all(not lane["eligible_for_parallel_wave"] for lane in plan["lanes"]))

    def test_goal_parallelization_classifies_no_eligible_task(self) -> None:
        request = {
            "goal_id": "issue-173",
            "tasks": [
                {
                    "id": "T002",
                    "target_path": "tests/test_subagent_orchestration_policy.py",
                    "task_surface": "unit_tests",
                    "depends_on": ["T001"],
                },
            ],
        }

        plan = policy_module.plan_goal_parallelization(request, self.policy)

        self.assertEqual(plan["status"], "no_eligible_task")
        self.assertEqual(plan["assignment_packets"], [])
        self.assertEqual(plan["worker_pool_ledger"], [])
        self.assertEqual(plan["lanes"][0]["status"], "waiting")
        self.assertEqual(plan["lanes"][0]["classification"], "waiting")
        self.assertFalse(plan["lanes"][0]["eligible_for_parallel_wave"])
        self.assertIn("waiting_for_dependencies", plan["lanes"][0]["classification_reasons"])
        self.assertIn("no_eligible_task", plan["classification_reasons"])

    def test_goal_parallelization_classifies_empty_tasks_as_no_eligible_task(self) -> None:
        request = {
            "goal_id": "issue-103",
            "tasks": [],
        }

        plan = policy_module.plan_goal_parallelization(request, self.policy)

        self.assertEqual(plan["status"], "no_eligible_task")
        self.assertEqual(plan["classification"], "no_eligible_task")
        self.assertEqual(plan["block_reasons"], [])
        self.assertIn("no_tasks", plan["classification_reasons"])
        self.assertEqual(plan["assignment_packets"], [])

    def test_goal_parallelization_classifies_no_write_without_assignment(self) -> None:
        request = {
            "goal_id": "issue-103",
            "tasks": [
                {
                    "id": "T001",
                    "target_path": "tests/test_subagent_orchestration_policy.py",
                    "task_surface": "unit_tests",
                    "read_only": True,
                    "write_scope": [],
                },
            ],
        }

        plan = policy_module.plan_goal_parallelization(request, self.policy)

        self.assertEqual(plan["status"], "no_write")
        self.assertEqual(plan["classification"], "no_write")
        self.assertEqual(plan["assignment_packets"], [])
        self.assertEqual(plan["worker_pool_ledger"], [])
        self.assertEqual(plan["lanes"][0]["status"], "no_write")
        self.assertEqual(plan["lanes"][0]["classification"], "no_write")
        self.assertIn("no_write_capable_work", plan["lanes"][0]["classification_reasons"])
        self.assertIn("no_write_capable_work", plan["classification_reasons"])
        self.assertEqual(plan["block_reasons"], [])

    def test_goal_parallelization_classifies_parent_scope_as_needs_parent_split(self) -> None:
        request = {
            "goal_id": "issue-103",
            "tasks": [
                {
                    "id": "T001",
                    "target_path": "plugins/bears",
                    "task_surface": "policy_catalog",
                },
            ],
        }

        plan = policy_module.plan_goal_parallelization(request, self.policy)

        self.assertEqual(plan["status"], "needs_parent_split")
        self.assertEqual(plan["classification"], "needs_parent_split")
        self.assertEqual(plan["role_gaps"], [])
        self.assertEqual(plan["assignment_packets"], [])
        self.assertEqual(plan["worker_pool_ledger"], [])
        self.assertEqual(plan["lanes"][0]["status"], "needs_parent_split")
        self.assertEqual(plan["lanes"][0]["classification"], "needs_parent_split")
        self.assertIn("parent_scope_requires_split", plan["lanes"][0]["classification_reasons"])
        self.assertIn("parent_scope_requires_split", plan["classification_reasons"])
        self.assertNotIn("role_coverage_gaps", plan["block_reasons"])

    def test_goal_parallelization_blocks_backend_only_forbidden_surface(self) -> None:
        request = {
            "goal_id": "issue-173",
            "tasks": [
                {
                    "id": "T001",
                    "target_path": "README.md",
                    "task_surface": "README",
                },
            ],
        }

        plan = policy_module.plan_goal_parallelization(request, self.policy)

        self.assertEqual(plan["status"], "blocked")
        self.assertEqual(plan["assignment_packets"], [])
        self.assertIn("backend_only_forbidden_surface:README", plan["block_reasons"])
        self.assertIn("backend_only_forbidden_surface:README", plan["lanes"][0]["block_reasons"])

    def test_plan_parallelization_cli_outputs_json(self) -> None:
        request = {
            "goal_id": "issue-173",
            "tasks": [
                {
                    "id": "T001",
                    "target_path": "scripts/subagent_orchestration_policy.py",
                    "task_surface": "validator_script",
                },
            ],
        }
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
            json.dump(request, handle)
            request_path = handle.name
        self.addCleanup(lambda: Path(request_path).unlink(missing_ok=True))

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "plan-parallelization",
                "--request",
                request_path,
                "--json",
            ],
            cwd=PLUGIN_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        plan = json.loads(result.stdout)
        self.assertEqual(plan["schema"], policy_module.PARALLELIZATION_PLAN_SCHEMA)
        self.assertEqual(plan["status"], "ready")
        self.assertEqual(plan["classification"], "ready")
        self.assertIn("classification_reasons", plan)
        self.assertEqual(plan["lanes"][0]["classification"], "ready")
        self.assertTrue(plan["read_only"])

    def test_records_cache_sync_and_transitional_superseded_rules(self) -> None:
        rules = {rule["id"]: rule["rule"] for rule in self.policy["rules"]}
        self.assertIn(".codex-plugin/plugin.json", rules["cache-sync-with-plugin-metadata"])
        self.assertIn("Superseded checks must name the active replacement validation command", rules["transitional-tests-superseded-by-dev-core"])

    def test_records_exact_agent_runtime_policy(self) -> None:
        runtime_policy = self.policy["agent_runtime_policy"]
        self.assertEqual(runtime_policy["main_agent"], self.EXPECTED_MAIN_AGENT)
        self.assertEqual(runtime_policy["delegated_subagents"], self.EXPECTED_DELEGATED_SUBAGENTS)
        self.assertEqual(
            set(runtime_policy["evidence_gathering_agents"]["roles"]),
            self.EXPECTED_EVIDENCE_GATHERING_ROLES,
        )
        self.assertEqual(
            set(runtime_policy["evidence_gathering_agents"]["applies_to"]),
            self.EXPECTED_EVIDENCE_GATHERING_APPLIES_TO,
        )
        self.assertEqual(runtime_policy["evidence_gathering_agents"]["model"], "gpt-5.4-mini")
        self.assertEqual(runtime_policy["evidence_gathering_agents"]["reasoning_effort"], "medium")
        self.assertEqual(
            runtime_policy["codex_schema_value_aliases"]["operator_wording_middle"],
            "medium",
        )
        self.assertEqual(runtime_policy["commit_local_validation_test_closeout_lane"]["model"], "gpt-5.4-mini")
        self.assertEqual(runtime_policy["commit_local_validation_test_closeout_lane"]["reasoning_effort"], "medium")
        self.assertEqual(
            runtime_policy["commit_local_validation_test_closeout_lane"]["required_role_profile"],
            "bears-git-workflow-helper",
        )
        self.assertEqual(
            runtime_policy["commit_local_validation_test_closeout_lane"]["applies_to"],
            ["parallel commit/local-validation/test-closeout subagent"],
        )

    def test_rejects_wrong_subagent_limit(self) -> None:
        packet = copy.deepcopy(self.policy)
        packet["limits"]["max_concurrent_subagents"] = 10
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("max_concurrent_subagents" in error for error in errors))

    def test_rejects_forbidden_reasoning_effort_value(self) -> None:
        packet = copy.deepcopy(self.policy)
        packet["agent_runtime_policy"]["evidence_gathering_agents"]["reasoning_effort"] = "l" + "ow"
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("forbidden reasoning effort value" in error for error in errors))

    def test_rejects_weakened_agent_runtime_reasoning(self) -> None:
        packet = copy.deepcopy(self.policy)
        packet["agent_runtime_policy"]["main_agent"]["reasoning_effort"] = "l" + "ow"
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("main_agent.reasoning_effort" in error for error in errors))

    def test_rejects_missing_required_rule(self) -> None:
        packet = copy.deepcopy(self.policy)
        packet["rules"] = [rule for rule in packet["rules"] if rule["id"] != "role-gate-first"]
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("rules missing required ids" in error for error in errors))

    def test_rejects_nested_subagents_disabled(self) -> None:
        packet = copy.deepcopy(self.policy)
        packet["orchestration_model"]["nested_subagents"]["allowed"] = False
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("nested_subagents.allowed" in error for error in errors))

    def test_rejects_nested_subagent_authorization_policy_gap(self) -> None:
        packet = copy.deepcopy(self.policy)
        nested = packet["orchestration_model"]["nested_subagents"]
        nested["worker_nested_delegation_default"] = "allowed"
        nested["parent_authorization_required_fields"].remove("scope")
        nested["unauthorized_spawn_classification"] = "warning"
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("worker_nested_delegation_default" in error for error in errors), errors)
        self.assertTrue(any("parent_authorization_required_fields missing" in error and "scope" in error for error in errors), errors)
        self.assertTrue(any("unauthorized_spawn_classification must be WORKFLOW_DRIFT" in error for error in errors), errors)

    def test_nested_worker_delegation_blocks_without_parent_authorization(self) -> None:
        classification = policy_module.validate_nested_delegation_request(
            {
                "requested_role": "bears-platform-security-reviewer",
                "write_scope": "assets/catalog/subagent-orchestration-policy.v1.json",
                "worker_pool_ledger_id": "goal_parallelization_worker_pool_ledger",
            },
            self.policy,
        )

        self.assertEqual(classification["status"], "blocked")
        self.assertEqual(classification["classification"], "WORKFLOW_DRIFT")
        self.assertIn("parent_authorization_required", classification["block_reasons"])

    def test_nested_worker_delegation_allows_authorized_same_ledger_request(self) -> None:
        classification = policy_module.validate_nested_delegation_request(
            {
                "requested_role": "bears-platform-security-reviewer",
                "write_scope": "assets/catalog/subagent-orchestration-policy.v1.json",
                "current_nested_count": 0,
                "requested_nested_count": 1,
                "worker_pool_ledger_id": "goal_parallelization_worker_pool_ledger",
                "tracked_in_worker_pool_ledger": True,
                "parent_authorization": {
                    "authorization_id": "auth-155",
                    "allowed_role": "bears-platform-security-reviewer",
                    "scope": "assets/catalog/subagent-orchestration-policy.v1.json",
                    "max_nested_count": 1,
                },
            },
            self.policy,
        )

        self.assertTrue(classification["allowed"], classification)
        self.assertEqual(classification["status"], "allowed")

    def test_nested_worker_delegation_blocks_scope_and_count_drift(self) -> None:
        classification = policy_module.validate_nested_delegation_request(
            {
                "requested_role": "bears-platform-security-reviewer",
                "write_scope": "tests/test_subagent_orchestration_policy.py",
                "current_nested_count": 1,
                "requested_nested_count": 1,
                "worker_pool_ledger_id": "other-ledger",
                "parent_authorization": {
                    "authorization_id": "auth-155",
                    "allowed_role": "bears-platform-security-reviewer",
                    "scope": "assets/catalog/subagent-orchestration-policy.v1.json",
                    "max_nested_count": 1,
                },
            },
            self.policy,
        )

        self.assertEqual(classification["status"], "blocked")
        self.assertEqual(classification["classification"], "WORKFLOW_DRIFT")
        self.assertIn("parent_authorization_scope_mismatch", classification["block_reasons"])
        self.assertIn("parent_authorization_max_nested_count_exceeded", classification["block_reasons"])
        self.assertIn("authorized_nested_subagent_not_tracked_in_worker_pool_ledger", classification["block_reasons"])

    def test_requires_explicit_delegation_controller_roles(self) -> None:
        packet = copy.deepcopy(self.policy)
        packet["orchestration_model"]["delegation_controller_roles"] = [
            controller
            for controller in packet["orchestration_model"]["delegation_controller_roles"]
            if controller["id"] != "devops-delegation-controller"
        ]
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("devops-delegation-controller" in error for error in errors))

    def test_allows_multiple_orchestrators_but_requires_controller_spawn_authority(self) -> None:
        self.assertTrue(self.policy["orchestration_model"]["multiple_orchestrators_allowed"])
        rule_map = {rule["id"]: rule["rule"] for rule in self.policy["rules"]}
        self.assertIn(
            "Multiple orchestrators may exist",
            rule_map["multi-orchestrator-controller-only-spawn"],
        )
        self.assertIn(
            "delegation-controller roles",
            rule_map["multi-orchestrator-controller-only-spawn"],
        )

    def test_rejects_multiple_orchestrators_flag_disabled(self) -> None:
        packet = copy.deepcopy(self.policy)
        packet["orchestration_model"]["multiple_orchestrators_allowed"] = False
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("multiple_orchestrators_allowed" in error for error in errors))

    def test_each_audit_requires_fresh_spawn_without_parent_context(self) -> None:
        for audit in self.policy["non_product_post_task_audit"]["required_subagents"]:
            with self.subTest(audit=audit["id"]):
                self.assertTrue(audit["spawn_fresh"])
                self.assertFalse(audit["inherit_parent_context"])

    def test_rejects_audit_reuse_or_parent_context_inheritance(self) -> None:
        packet = copy.deepcopy(self.policy)
        packet["non_product_post_task_audit"]["required_subagents"][0]["spawn_fresh"] = False
        packet["non_product_post_task_audit"]["required_subagents"][0]["inherit_parent_context"] = True
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("spawn_fresh must be true" in error for error in errors))
        self.assertTrue(any("inherit_parent_context must be false" in error for error in errors))

    def test_devops_controller_can_spawn_required_lanes(self) -> None:
        controllers = {
            item["id"]: item
            for item in self.policy["orchestration_model"]["delegation_controller_roles"]
        }
        controller = controllers["devops-delegation-controller"]
        self.assertEqual(controller["role"], "bears-deploy-platform-engineer")
        self.assertIn("kubernetes-specialist", controller["may_spawn_roles"])
        for lane in policy_module.REQUIRED_DELEGATION_CONTROLLERS["devops-delegation-controller"]["must_lanes"]:
            with self.subTest(lane=lane):
                self.assertIn(lane, controller["lanes"])

    def test_l2_domain_controllers_spawn_goal_helpers_without_parent_context(self) -> None:
        controllers = {
            item["id"]: item
            for item in self.policy["orchestration_model"]["delegation_controller_roles"]
        }
        nested = self.policy["orchestration_model"]["nested_subagents"]
        expected = {
            "l2-platform-domain-delegation-controller": "l2-platform-domain-orchestrator",
            "l2-gitops-domain-delegation-controller": "l2-gitops-domain-orchestrator",
            "l2-infra-domain-delegation-controller": "l2-infra-domain-orchestrator",
            "l2-product-infra-domain-delegation-controller": "l2-product-infra-domain-orchestrator",
        }
        helper_roles = {
            "bears-token-budget-helper",
            "bears-git-workflow-helper",
            "bears-review-fix-helper",
        }
        helper_lanes = {
            "token economy support",
            "git local-validation cache closeout support",
            "review fix support",
        }
        for controller_id, role in expected.items():
            with self.subTest(controller_id=controller_id):
                controller = controllers[controller_id]
                self.assertEqual(controller["role"], role)
                self.assertTrue(helper_roles.issubset(set(controller["may_spawn_roles"])))
                self.assertTrue(helper_lanes.issubset(set(controller["lanes"])))
                self.assertIn("parent context inheritance", controller["forbidden"])
                self.assertIn(role, nested["who_may_spawn"])
        self.assertIn(
            "L2 helper subagent parent context inheritance",
            nested["forbidden_conditions"],
        )

    def test_rejects_l2_domain_controller_without_goal_helper_role(self) -> None:
        packet = copy.deepcopy(self.policy)
        controllers = packet["orchestration_model"]["delegation_controller_roles"]
        for controller in controllers:
            if controller["id"] == "l2-platform-domain-delegation-controller":
                controller["may_spawn_roles"] = [
                    role for role in controller["may_spawn_roles"] if role != "bears-git-workflow-helper"
                ]
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("bears-git-workflow-helper" in error for error in errors))

    def test_rejects_missing_runtime_verification_lane(self) -> None:
        packet = copy.deepcopy(self.policy)
        controllers = packet["orchestration_model"]["delegation_controller_roles"]
        for controller in controllers:
            if controller["id"] == "devops-delegation-controller":
                controller["lanes"] = [
                    lane for lane in controller["lanes"] if lane != "runtime verification"
                ]
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("runtime verification" in error for error in errors))

    def test_validates_synthetic_delegation_closeout_packet(self) -> None:
        packet = {
            "controller_id": "workflow-delegation-controller",
            "parent role route": "bears-subagent-orchestration-engineer",
            "child role": "bears-platform-role-governor",
            "child lane": "plugin policy review",
            "write scope or read-only scope": "read-only policy review",
            "validation command": "python3 scripts/subagent_orchestration_policy.py validate",
            "assignment packet id": "assign-001",
            "pre-task hook evidence": "pre-task hook completed before task start",
            "operator missing data answers": "none missing",
            "operator drift answers": "drift answers recorded",
            "task-start authorization": "task start approved from pre-task hook",
            "spawn evidence": "assignment packet accepted",
            "closeout evidence": "closeout packet collected",
            "validation hook result": {
                "hook_id": "subagent_policy_validate",
                "cwd": str(PLUGIN_ROOT),
                "command_id": "subagent_policy_validate",
                "exit_code": 0,
                "sanitized_summary": "subagent policy validation passed",
                "validation_target": "assets/catalog/subagent-orchestration-policy.v1.json",
            },
        }
        self.assertEqual(policy_module.validate_delegation_closeout_packet(packet, self.policy), [])

    def test_rejects_delegation_closeout_without_validation_hook_result(self) -> None:
        packet = {
            "controller_id": "workflow-delegation-controller",
            "parent role route": "bears-subagent-orchestration-engineer",
            "child role": "bears-platform-role-governor",
            "child lane": "plugin policy review",
            "write scope or read-only scope": "read-only policy review",
            "validation command": "python3 scripts/subagent_orchestration_policy.py validate",
            "assignment packet id": "assign-001",
            "pre-task hook evidence": "pre-task hook completed before task start",
            "operator missing data answers": "none missing",
            "operator drift answers": "drift answers recorded",
            "task-start authorization": "task start approved from pre-task hook",
            "spawn evidence": "assignment packet accepted",
            "closeout evidence": "closeout packet collected",
        }
        errors = policy_module.validate_delegation_closeout_packet(packet, self.policy)
        self.assertTrue(any("validation hook result" in error for error in errors), errors)

    def test_rejects_delegation_closeout_with_raw_hook_output(self) -> None:
        packet = {
            "controller_id": "workflow-delegation-controller",
            "parent role route": "bears-subagent-orchestration-engineer",
            "child role": "bears-platform-role-governor",
            "child lane": "plugin policy review",
            "write scope or read-only scope": "read-only policy review",
            "validation command": "python3 scripts/subagent_orchestration_policy.py validate",
            "assignment packet id": "assign-001",
            "pre-task hook evidence": "pre-task hook completed before task start",
            "operator missing data answers": "none missing",
            "operator drift answers": "drift answers recorded",
            "task-start authorization": "task start approved from pre-task hook",
            "spawn evidence": "assignment packet accepted",
            "closeout evidence": "closeout packet collected",
            "validation hook result": {
                "hook_id": "subagent_policy_validate",
                "cwd": str(PLUGIN_ROOT),
                "command_id": "subagent_policy_validate",
                "exit_code": 0,
                "sanitized_summary": "subagent policy validation passed",
                "validation_target": "assets/catalog/subagent-orchestration-policy.v1.json",
                "raw_stdout": "full output",
            },
        }
        errors = policy_module.validate_delegation_closeout_packet(packet, self.policy)
        self.assertTrue(any("raw_stdout" in error for error in errors), errors)

    def test_rejects_delegation_closeout_with_restricted_hook_fields(self) -> None:
        packet = {
            "controller_id": "workflow-delegation-controller",
            "parent role route": "bears-subagent-orchestration-engineer",
            "child role": "bears-platform-role-governor",
            "child lane": "plugin policy review",
            "write scope or read-only scope": "read-only policy review",
            "validation command": "python3 scripts/subagent_orchestration_policy.py validate",
            "assignment packet id": "assign-001",
            "pre-task hook evidence": "pre-task hook completed before task start",
            "operator missing data answers": "none missing",
            "operator drift answers": "drift answers recorded",
            "task-start authorization": "task start approved from pre-task hook",
            "spawn evidence": "assignment packet accepted",
            "closeout evidence": "closeout packet collected",
            "validation hook result": {
                "hook_id": "subagent_policy_validate",
                "cwd": str(PLUGIN_ROOT),
                "command_id": "subagent_policy_validate",
                "exit_code": 0,
                "sanitized_summary": "subagent policy validation passed",
                "validation_target": "assets/catalog/subagent-orchestration-policy.v1.json",
                "raw_log": "raw log body",
                "raw_chat": "raw chat body",
                "raw_vpn_config": "raw vpn config body",
                "production_data": "production data body",
            },
        }
        errors = policy_module.validate_delegation_closeout_packet(packet, self.policy)
        self.assertTrue(any("raw_log" in error for error in errors), errors)
        self.assertTrue(any("raw_chat" in error for error in errors), errors)
        self.assertTrue(any("raw_vpn_config" in error for error in errors), errors)
        self.assertTrue(any("production_data" in error for error in errors), errors)

    def test_rejects_delegation_closeout_read_only_child_with_write_scope(self) -> None:
        packet = {
            "controller_id": "workflow-delegation-controller",
            "parent role route": "bears-subagent-orchestration-engineer",
            "child role": "bears-platform-security-reviewer",
            "child lane": "plugin policy review",
            "write scope or read-only scope": "docs/generated/README.skill-inventory.md",
            "validation command": "python3 scripts/subagent_orchestration_policy.py validate",
            "assignment packet id": "assign-001",
            "pre-task hook evidence": "pre-task hook completed before task start",
            "operator missing data answers": "none missing",
            "operator drift answers": "drift answers recorded",
            "task-start authorization": "task start approved from pre-task hook",
            "spawn evidence": "assignment packet accepted",
            "closeout evidence": "closeout packet collected",
            "validation hook result": {
                "hook_id": "subagent_policy_validate",
                "cwd": str(PLUGIN_ROOT),
                "command_id": "subagent_policy_validate",
                "exit_code": 0,
                "sanitized_summary": "subagent policy validation passed",
                "validation_target": "assets/catalog/subagent-orchestration-policy.v1.json",
            },
        }
        errors = policy_module.validate_delegation_closeout_packet(packet, self.policy)
        self.assertTrue(any("write_scope" in error for error in errors), errors)

    def test_rejects_delegation_closeout_read_only_child_with_path_containing_read_only(self) -> None:
        packet = {
            "controller_id": "workflow-delegation-controller",
            "parent role route": "bears-subagent-orchestration-engineer",
            "child role": "bears-platform-security-reviewer",
            "child lane": "plugin policy review",
            "write scope or read-only scope": "docs/read-only-note.md",
            "validation command": "python3 scripts/subagent_orchestration_policy.py validate",
            "assignment packet id": "assign-001",
            "pre-task hook evidence": "pre-task hook completed before task start",
            "operator missing data answers": "none missing",
            "operator drift answers": "drift answers recorded",
            "task-start authorization": "task start approved from pre-task hook",
            "spawn evidence": "assignment packet accepted",
            "closeout evidence": "closeout packet collected",
            "validation hook result": {
                "hook_id": "subagent_policy_validate",
                "cwd": str(PLUGIN_ROOT),
                "command_id": "subagent_policy_validate",
                "exit_code": 0,
                "sanitized_summary": "subagent policy validation passed",
                "validation_target": "assets/catalog/subagent-orchestration-policy.v1.json",
            },
        }
        errors = policy_module.validate_delegation_closeout_packet(packet, self.policy)
        self.assertTrue(any("write_scope" in error for error in errors), errors)

    def test_rejects_delegation_closeout_read_only_child_with_write_authority(self) -> None:
        packet = {
            "controller_id": "workflow-delegation-controller",
            "parent role route": "bears-subagent-orchestration-engineer",
            "child role": "bears-platform-security-reviewer",
            "child lane": "plugin policy review",
            "write scope or read-only scope": "read-only policy review",
            "assignment_authority": [
                "file_write",
                "git_push",
                "runtime_mutation",
                "deployment_mutation",
                "credential_access",
            ],
            "validation command": "python3 scripts/subagent_orchestration_policy.py validate",
            "assignment packet id": "assign-001",
            "pre-task hook evidence": "pre-task hook completed before task start",
            "operator missing data answers": "none missing",
            "operator drift answers": "drift answers recorded",
            "task-start authorization": "task start approved from pre-task hook",
            "spawn evidence": "assignment packet accepted",
            "closeout evidence": "closeout packet collected",
            "validation hook result": {
                "hook_id": "subagent_policy_validate",
                "cwd": str(PLUGIN_ROOT),
                "command_id": "subagent_policy_validate",
                "exit_code": 0,
                "sanitized_summary": "subagent policy validation passed",
                "validation_target": "assets/catalog/subagent-orchestration-policy.v1.json",
            },
        }
        errors = policy_module.validate_delegation_closeout_packet(packet, self.policy)
        self.assertTrue(any("file_write" in error for error in errors), errors)
        self.assertTrue(any("git_push" in error for error in errors), errors)
        self.assertTrue(any("runtime_mutation" in error for error in errors), errors)
        self.assertTrue(any("deployment_mutation" in error for error in errors), errors)
        self.assertTrue(any("credential_access" in error for error in errors), errors)

    def test_validate_assignment_cli_rejects_read_only_write_scope(self) -> None:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json") as handle:
            handle.write(
                '{"agent_name":"bears-platform-security-reviewer",'
                '"sandbox_mode":"read-only","write_scope":"docs/out.md"}'
            )
            handle.flush()
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "validate-assignment",
                    "--packet",
                    handle.name,
                ],
                cwd=PLUGIN_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        self.assertEqual(result.returncode, 1)
        self.assertIn("write_scope", result.stderr)

    def test_rejects_synthetic_delegation_packet_without_pre_task_hook_or_closeout_evidence(self) -> None:
        packet = {
            "controller_id": "workflow-delegation-controller",
            "parent role route": "bears-subagent-orchestration-engineer",
            "child role": "bears-platform-role-governor",
            "child lane": "plugin policy review",
            "write scope or read-only scope": "read-only policy review",
            "validation command": "python3 scripts/subagent_orchestration_policy.py validate",
            "assignment packet id": "assign-001",
            "spawn evidence": "assignment packet accepted",
        }
        errors = policy_module.validate_delegation_closeout_packet(packet, self.policy)
        self.assertTrue(any("pre-task hook evidence" in error for error in errors))
        self.assertTrue(any("operator drift answers" in error for error in errors))
        self.assertTrue(any("task-start authorization" in error for error in errors))
        self.assertTrue(any("closeout evidence" in error for error in errors))

    def test_rejects_config_drift(self) -> None:
        config = {
            "agents": {"max_threads": 8, "max_depth": 3},
            "mcp_servers": {"workspace-map": {"enabled": False}},
        }
        errors = policy_module.validate_codex_config(config, self.policy)
        self.assertTrue(any("agents.max_threads" in error for error in errors))

    def test_accepts_expected_config_knobs(self) -> None:
        config = {
            "agents": {"max_threads": 100, "max_depth": 3},
            "mcp_servers": {"workspace-map": {"enabled": False}},
        }
        self.assertEqual(policy_module.validate_codex_config(config, self.policy), [])

    def test_agent_tomls_match_runtime_policy(self) -> None:
        for path in sorted((PLUGIN_ROOT / "agents").glob("*.toml")):
            with self.subTest(agent=path.name):
                data = tomllib.loads(path.read_text())
                if path.name in self.HELPER_AGENT_RUNTIME:
                    runtime = self.HELPER_AGENT_RUNTIME[path.name]
                    expected_model = runtime["model"]
                    expected_effort = runtime["reasoning_effort"]
                else:
                    expected_model = "gpt-5.4-mini" if path.name in self.EVIDENCE_GATHERING_AGENT_FILES else "gpt-5.5"
                    expected_effort = "medium" if path.name in self.EVIDENCE_GATHERING_AGENT_FILES else "high"
                self.assertEqual(data["model"], expected_model)
                self.assertEqual(data["model_reasoning_effort"], expected_effort)



    def test_issue20_research_contract_validates(self) -> None:
        self.assertEqual([], policy_module.validate_research_artifact_contract(self.policy["research_artifact_contract"]))

    def test_issue20_lifecycle_research_gate_records_required_conditions(self) -> None:
        gate = self.policy["lifecycle"]["research_gate"]
        for marker in ("broad", "runtime", "integration", "ui/ux flow", "automation", "plugin", "infra", "kubernetes", "migration", "boundary-sensitive"):
            with self.subTest(marker=marker):
                self.assertIn(marker, gate["required_for"])
        self.assertEqual(gate["artifact_basenames"]["research"], "research.md")
        self.assertIn("explicit operator skip", gate["skip_policy"])
        self.assertIn("automation pattern", gate["narrow_skip_required_no_change_fields"])

    def test_issue20_operator_research_skip_validates(self) -> None:
        packet = self._issue22_design_packet()
        packet["research_artifacts"] = None
        packet["research_skip"] = {"type": "operator_skip", "approved_by": "operator", "approval_reference": "issue-20", "reason": "bounded override"}
        self.assertEqual([], policy_module.validate_implementation_packet(packet, self.policy["design_artifact_contract"]))

    def test_issue20_narrow_exact_file_research_skip_validates(self) -> None:
        packet = self._issue22_design_packet()
        packet["research_artifacts"] = None
        packet["research_skip"] = {
            "type": "narrow_exact_file_skip",
            "exact_file_scope": "scripts/subagent_orchestration_policy.py",
            "no_boundary_change": True,
            "no_runtime_change": True,
            "no_deploy_change": True,
            "no_restricted_data_change": True,
            "no_public_behavior_change": True,
            "no_workflow_change": True,
            "no_ui_change": True,
            "no_ux_change": True,
            "no_automation_pattern_change": True,
        }
        self.assertEqual([], policy_module.validate_implementation_packet(packet, self.policy["design_artifact_contract"]))

    def test_issue20_rejects_broad_workflow_packet_without_research(self) -> None:
        packet = self._issue22_design_packet()
        packet["research_artifacts"] = None
        errors = policy_module.validate_implementation_packet(packet, self.policy["design_artifact_contract"])
        self.assertTrue(any("research_artifacts missing required artifacts" in error for error in errors))

    def test_issue20_rejects_missing_ux_research_for_cli_status_error_recovery(self) -> None:
        packet = self._issue22_design_packet()
        packet["cli_change"] = True
        packet["status_behavior_change"] = True
        packet["error_behavior_change"] = True
        packet["recovery_behavior_change"] = True
        packet["research_artifacts"].pop("ux_research")
        errors = policy_module.validate_implementation_packet(packet, self.policy["design_artifact_contract"])
        self.assertTrue(any("ux_research missing required artifact" in error for error in errors))

    def test_issue20_rejects_unbounded_or_proprietary_research_claim(self) -> None:
        packet = self._issue22_design_packet()
        packet["research_artifacts"]["research"]["bounded_summary"] = False
        packet["research_artifacts"]["research"]["no_large_source_copy"] = False
        errors = policy_module.validate_implementation_packet(packet, self.policy["design_artifact_contract"])
        self.assertTrue(any("bounded_summary" in error for error in errors))
        self.assertTrue(any("no_large_source_copy" in error for error in errors))

    def test_issue20_requires_sources_when_repository_research_used(self) -> None:
        packet = self._issue22_design_packet()
        packet["research_artifacts"]["prior_art"]["sources"] = []
        errors = policy_module.validate_implementation_packet(packet, self.policy["design_artifact_contract"])
        self.assertTrue(any("sources are required" in error for error in errors))

    def test_issue22_design_contract_validates(self) -> None:
        self.assertEqual([], policy_module.validate_design_artifact_contract(self.policy["design_artifact_contract"]))
        self.assertEqual("README.md#issue-22-design-artifact-contract", self.policy["design_artifact_contract"]["artifact_path"])

    def test_issue22_required_design_packet_validates(self) -> None:
        packet = self._issue22_design_packet()
        self.assertEqual([], policy_module.validate_implementation_packet(packet, self.policy["design_artifact_contract"]))

    def test_issue22_approved_skip_validates(self) -> None:
        packet = self._issue22_design_packet()
        packet["design_artifact"] = None
        packet["design_skip"] = {"type": "approved_skip", "approved_by": "operator", "approval_reference": "issue-22", "reason": "bounded override"}
        self.assertEqual([], policy_module.validate_implementation_packet(packet, self.policy["design_artifact_contract"]))

    def test_issue22_narrow_bugfix_skip_validates(self) -> None:
        packet = self._issue22_design_packet()
        packet["design_artifact"] = None
        packet["design_skip"] = {
            "type": "narrow_bugfix_skip",
            "exact_file_scope": "scripts/subagent_orchestration_policy.py",
            "no_boundary_change": True,
            "no_runtime_change": True,
            "no_deploy_change": True,
            "no_restricted_data_change": True,
            "no_public_behavior_change": True,
        }
        self.assertEqual([], policy_module.validate_implementation_packet(packet, self.policy["design_artifact_contract"]))

    def test_issue22_rejects_missing_decision_table_for_branch_behavior(self) -> None:
        packet = self._issue22_design_packet()
        packet["design_artifact"]["sections"].remove("decision table or policy matrix")
        errors = policy_module.validate_implementation_packet(packet, self.policy["design_artifact_contract"])
        self.assertTrue(any("decision table" in error for error in errors))

    def test_issue22_rejects_missing_validator_impact(self) -> None:
        packet = self._issue22_design_packet()
        packet["validator_impact"] = []
        errors = policy_module.validate_implementation_packet(packet, self.policy["design_artifact_contract"])
        self.assertTrue(any("validator_impact" in error for error in errors))

    def test_issue22_rejects_missing_design(self) -> None:
        packet = self._issue22_design_packet()
        packet["design_artifact"] = None
        errors = policy_module.validate_implementation_packet(packet, self.policy["design_artifact_contract"])
        self.assertTrue(any("missing required design" in error for error in errors))

    def _issue20_research_artifacts(self) -> dict[str, object]:
        def artifact(path: str) -> dict[str, object]:
            return {
                "path": path,
                "sections": list(policy_module.REQUIRED_RESEARCH_SECTIONS),
                "decision_or_recommendation": "Require bounded research before gated implementation.",
                "used_web_or_repository_research": True,
                "sources": ["issue #20", "repository policy files"],
                "bounded_summary": True,
                "no_large_source_copy": True,
                "no_proprietary_copy": True,
            }

        return {
            "research": artifact("features/issue-20/research.md"),
            "prior_art": artifact("features/issue-20/prior-art.md"),
            "ux_research": artifact("features/issue-20/ux-research.md"),
        }

    def _issue22_design_packet(self) -> dict[str, object]:
        return {
            "change_type": "orchestration policy",
            "research_required": True,
            "research_artifacts": self._issue20_research_artifacts(),
            "research_skip": None,
            "prototype_required": False,
            "prototype_artifact": None,
            "prototype_skip": None,
            "prototype_review": None,
            "design_required": True,
            "design_artifact": {
                "path": "README.md#issue-22-design-artifact-contract",
                "sections": list(policy_module.REQUIRED_DESIGN_SECTIONS),
            },
            "design_skip": None,
            "affected_artifacts": ["assets/catalog/subagent-orchestration-policy.v1.json"],
            "validator_impact": ["validate_design_artifact_contract"],
            "documentation_impact": ["README.md"],
            "test_plan": ["issue #22 tests"],
            "safety_boundaries": ["repo-only governance files"],
            "behavior_branches": ["required design", "approved skip"],
        }

    def test_issue22_records_research_prototype_design_before_spec_kit(self) -> None:
        stages = self.policy["lifecycle"]["stages"]
        self.assertLess(stages.index("research_gate"), stages.index("design_gate"))
        self.assertLess(stages.index("prototype_gate"), stages.index("design_gate"))
        self.assertLess(stages.index("design_gate"), stages.index("spec_kit_gate"))

    def test_issue21_prototype_contract_validates(self) -> None:
        self.assertEqual([], policy_module.validate_prototype_artifact_contract(self.policy["prototype_artifact_contract"]))

    def test_issue21_required_prototype_packet_validates(self) -> None:
        packet = self._issue21_prototype_packet()
        self.assertEqual([], policy_module.validate_implementation_packet(packet, self.policy["design_artifact_contract"]))

    def test_issue21_narrow_bugfix_prototype_skip_validates(self) -> None:
        packet = self._issue21_prototype_packet()
        packet["prototype_artifact"] = None
        packet["prototype_skip"] = {
            "type": "narrow_bugfix_skip",
            "exact_file_scope": "scripts/subagent_orchestration_policy.py",
            "no_boundary_change": True,
            "no_runtime_change": True,
            "no_deploy_change": True,
            "no_restricted_data_change": True,
            "no_public_behavior_change": True,
        }
        self.assertEqual([], policy_module.validate_implementation_packet(packet, self.policy["design_artifact_contract"]))

    def test_issue21_already_proven_pattern_prototype_skip_validates(self) -> None:
        packet = self._issue21_prototype_packet()
        packet["prototype_artifact"] = None
        packet["prototype_skip"] = {
            "type": "already_proven_pattern_skip",
            "pattern_reference": "issue-22 design gate validator shape",
            "evidence": "validated catalog and unit tests",
        }
        self.assertEqual([], policy_module.validate_implementation_packet(packet, self.policy["design_artifact_contract"]))

    def test_issue21_rejects_production_mutation_prototype_claim(self) -> None:
        packet = self._issue21_prototype_packet()
        packet["prototype_artifact"]["production_mutation"] = True
        errors = policy_module.validate_implementation_packet(packet, self.policy["design_artifact_contract"])
        self.assertTrue(any("production_mutation" in error for error in errors))

    def test_issue21_rejects_restricted_data_read_prototype_claim(self) -> None:
        packet = self._issue21_prototype_packet()
        packet["prototype_artifact"]["restricted_data_reads"] = True
        errors = policy_module.validate_implementation_packet(packet, self.policy["design_artifact_contract"])
        self.assertTrue(any("restricted_data_reads" in error for error in errors))

    def test_issue21_rejects_broad_implementation_prototype_claim(self) -> None:
        packet = self._issue21_prototype_packet()
        packet["prototype_artifact"]["broad_implementation"] = True
        errors = policy_module.validate_implementation_packet(packet, self.policy["design_artifact_contract"])
        self.assertTrue(any("broad_implementation" in error for error in errors))

    def test_issue21_rejects_missing_decision_outcome(self) -> None:
        packet = self._issue21_prototype_packet()
        packet["prototype_artifact"].pop("decision")
        errors = policy_module.validate_implementation_packet(packet, self.policy["design_artifact_contract"])
        self.assertTrue(any("decision" in error for error in errors))

    def test_issue21_rejects_missing_prototype_artifact_when_required(self) -> None:
        packet = self._issue21_prototype_packet()
        packet["prototype_artifact"] = None
        errors = policy_module.validate_implementation_packet(packet, self.policy["design_artifact_contract"])
        self.assertTrue(any("prototype_artifact missing required artifact" in error for error in errors))

    def test_issue21_requires_operator_approval_for_remaining_material_change(self) -> None:
        packet = self._issue21_prototype_packet()
        packet["runtime_change"] = True
        packet["prototype_review"] = None
        errors = policy_module.validate_implementation_packet(packet, self.policy["design_artifact_contract"])
        self.assertTrue(any("operator approval" in error for error in errors))

    def _issue21_prototype_packet(self) -> dict[str, object]:
        packet = self._issue22_design_packet()
        packet.update({
            "prototype_required": True,
            "research_or_design_unresolved_high_risk_uncertainty": True,
            "cheaply_testable_before_implementation": True,
            "prototype_artifact": {
                "path": "features/issue-21/spike.md",
                "sections": list(policy_module.PROTOTYPE_REQUIRED_SECTIONS),
                "decision": "proceed",
                "production_mutation": False,
                "restricted_data_reads": False,
                "broad_implementation": False,
                "durable_implementation": False,
                "cleanup_or_discard_requirements": ["discard prototype output before durable implementation"],
            },
            "prototype_skip": None,
            "prototype_review": {
                "operator_approved_to_implement": True,
                "approved_by": "operator",
                "approval_reference": "issue-21",
            },
            "material_behavior_change": False,
            "runtime_change": False,
            "boundary_change": False,
            "ui_ux_change": False,
            "architecture_change": False,
        })
        return packet

    def test_records_read_only_agent_safety_guard(self) -> None:
        self.assertIn("read-only-agent-safety-guard", self.policy["required_rule_ids"])
        guard = self.policy["orchestration_model"]["read_only_agent_safety_guard"]
        self.assertTrue(guard["required"])
        self.assertTrue(guard["sandbox_mode_is_not_authority_proof"])
        self.assertEqual(
            guard["validator_command"],
            "python3 scripts/subagent_orchestration_policy.py validate",
        )
        self.assertEqual(guard["read_only_sandbox_modes"], ["read-only"])
        self.assertTrue(
            set(policy_module.REQUIRED_READ_ONLY_FORBIDDEN_AUTHORITY).issubset(
                set(guard["forbidden_authority_tokens"])
            )
        )
        self.assertIn(
            "sandbox_mode is not sufficient proof by itself",
            guard["stage_boundary_audit_wording"],
        )
        self.assertEqual(
            guard["documentation"]["active_validation_command"],
            "python3 scripts/subagent_orchestration_policy.py validate",
        )

    def test_rejects_missing_read_only_forbidden_authority_token(self) -> None:
        packet = copy.deepcopy(self.policy)
        guard = packet["orchestration_model"]["read_only_agent_safety_guard"]
        guard["forbidden_authority_tokens"].remove("git_push")
        errors = policy_module.validate_policy(packet)
        self.assertTrue(any("git_push" in error for error in errors), errors)

    def test_records_pr_task_role_action_guard(self) -> None:
        self.assertIn("pr-task-role-action-guard", self.policy["required_rule_ids"])
        guard = self.policy["orchestration_model"]["pr_task_role_action_guard"]
        self.assertTrue(guard["required"])
        self.assertTrue(guard["fail_closed_by_default"])
        self.assertIn("bears-platform-security-reviewer", guard["read_only_reviewer_roles"])
        self.assertIn("bears-platform-role-governor", guard["governor_roles"])
        self.assertTrue(
            set(policy_module.REQUIRED_PR_MUTATION_ACTIONS).issubset(
                set(guard["writable_pr_actions"])
            )
        )
        self.assertTrue(
            set(policy_module.REQUIRED_PR_READ_ONLY_ACTIONS).issubset(
                set(guard["read_only_pr_actions"])
            )
        )
        self.assertIn(
            {
                "status": policy_module.PR_REVIEWER_MUTATION_STATUS,
                "reason": policy_module.PR_REVIEWER_MUTATION_REASON,
            },
            guard["status_reasons"],
        )
        self.assertIn(
            {
                "status": policy_module.PR_GOVERNOR_MUTATION_STATUS,
                "reason": policy_module.PR_GOVERNOR_MUTATION_REASON,
            },
            guard["status_reasons"],
        )

    def test_records_role_profile_fallback_guard(self) -> None:
        self.assertIn("role-profile-fallback-parity-guard", self.policy["required_rule_ids"])
        guard = self.policy["orchestration_model"]["role_profile_fallback_guard"]
        self.assertTrue(guard["required"])
        self.assertTrue(guard["fail_closed_by_default"])
        self.assertIn("backend-developer", guard["generic_agent_types"])
        self.assertIn("domain_owner", guard["domain_owner_fields"])
        self.assertEqual(guard["required_downgrade_record"], "ROLE_PROFILE_DOWNGRADE")
        self.assertIn("explicit_operator_approval", guard["approval_paths"])
        self.assertIn("validated_role_parity_packet", guard["approval_paths"])
        self.assertEqual(
            guard["parent_preference_order"],
            [
                "retry_same_bears_role",
                "reduce_scope",
                "split_task",
                "request_role_profile_downgrade",
            ],
        )
        self.assertIn(
            "Bears role profile stays attached",
            guard["model_fallback_definition"],
        )
        self.assertIn("generic role", guard["role_profile_fallback_definition"])
        self.assertIn("pr_publish", guard["generic_fallback_forbidden_without_mutation_authority"])
        self.assertIn("mutation_authority_lane", guard["final_report_required_fields"])
        self.assertIn("parity_enforcement", guard["final_report_required_fields"])
        self.assertIn("profile_downgrade_status", guard["final_report_required_fields"])
        self.assertIn("safety_rationale", guard["final_report_required_fields"])
        status_reasons = {
            (item["status"], item["reason"])
            for item in guard["status_reasons"]
        }
        self.assertNotIn(("allowed", "model_fallback_only"), status_reasons)

    def test_rejects_missing_role_profile_fallback_guard(self) -> None:
        packet = copy.deepcopy(self.policy)
        packet["orchestration_model"].pop("role_profile_fallback_guard")
        packet["required_rule_ids"].remove("role-profile-fallback-parity-guard")
        packet["rules"] = [
            rule for rule in packet["rules"] if rule["id"] != "role-profile-fallback-parity-guard"
        ]

        errors = policy_module.validate_policy(packet)

        self.assertTrue(any("role-profile-fallback-parity-guard" in error for error in errors), errors)
        self.assertTrue(any("role_profile_fallback_guard" in error for error in errors), errors)

    def test_rejects_missing_pr_task_role_action_guard(self) -> None:
        packet = copy.deepcopy(self.policy)
        packet["orchestration_model"].pop("pr_task_role_action_guard")
        packet["required_rule_ids"].remove("pr-task-role-action-guard")
        packet["rules"] = [
            rule for rule in packet["rules"] if rule["id"] != "pr-task-role-action-guard"
        ]

        errors = policy_module.validate_policy(packet)

        self.assertTrue(any("pr-task-role-action-guard" in error for error in errors), errors)
        self.assertTrue(any("pr_task_role_action_guard" in error for error in errors), errors)

    def test_allows_read_only_pr_review_assignment(self) -> None:
        assignment = {
            "role": "bears-platform-security-reviewer",
            "sandbox_mode": "read-only",
            "pr_task": True,
            "pr_actions": ["read-only review", "inspect"],
        }

        classification = policy_module.classify_pr_task_assignment(assignment, self.policy)
        errors = policy_module.validate_read_only_assignment_packet(assignment, self.policy)

        self.assertEqual(classification["status"], policy_module.PR_ALLOWED_STATUS)
        self.assertEqual(classification["reason"], policy_module.PR_ALLOWED_READ_ONLY_REASON)
        self.assertFalse(classification["blocked"])
        self.assertEqual(errors, [])

    def test_blocks_read_only_reviewer_pr_mutation_assignment(self) -> None:
        assignment = {
            "role": "bears-platform-security-reviewer",
            "sandbox_mode": "read-only",
            "pr_task": True,
            "pr_actions": ["label", "comment", "ready-for-review"],
        }

        classification = policy_module.classify_pr_task_assignment(assignment, self.policy)
        errors = policy_module.validate_read_only_assignment_packet(assignment, self.policy)

        self.assertEqual(classification["status"], policy_module.PR_REVIEWER_MUTATION_STATUS)
        self.assertEqual(classification["reason"], policy_module.PR_REVIEWER_MUTATION_REASON)
        self.assertTrue(classification["blocked"])
        self.assertEqual(
            classification["actions"],
            ["pr_comment", "pr_label", "pr_ready_for_review"],
        )
        self.assertTrue(any(policy_module.PR_REVIEWER_MUTATION_STATUS in error for error in errors), errors)
        self.assertTrue(any(policy_module.PR_REVIEWER_MUTATION_REASON in error for error in errors), errors)

    def test_blocks_governor_writable_pr_task_without_writer_lane(self) -> None:
        assignment = {
            "role": "bears-platform-role-governor",
            "pr_task": True,
            "pr_actions": ["merge", "rebase", "delete branch", "push", "title edit", "body edit"],
        }

        classification = policy_module.classify_pr_task_assignment(assignment, self.policy)

        self.assertEqual(classification["status"], policy_module.PR_GOVERNOR_MUTATION_STATUS)
        self.assertEqual(classification["reason"], policy_module.PR_GOVERNOR_MUTATION_REASON)
        self.assertTrue(classification["blocked"])
        self.assertEqual(
            classification["actions"],
            [
                "git_push",
                "pr_body_edit",
                "pr_branch_delete",
                "pr_merge",
                "pr_rebase",
                "pr_title_edit",
            ],
        )

    def test_allows_governor_writable_pr_task_with_explicit_writer_lane(self) -> None:
        packet = copy.deepcopy(self.policy)
        packet["orchestration_model"]["pr_task_role_action_guard"]["governor_writer_lanes"] = [
            {
                "id": "governor-pr-writer-lane",
                "writable_pr_tasks": True,
                "roles": ["bears-platform-role-governor"],
                "allowed_actions": ["pr_label"],
                "policy_reference": "operator-approved-writer-lane",
            }
        ]
        self.assertEqual(policy_module.validate_policy(packet), [])
        assignment = {
            "role": "bears-platform-role-governor",
            "pr_task": True,
            "pr_writer_lane_id": "governor-pr-writer-lane",
            "pr_actions": ["label"],
        }

        classification = policy_module.classify_pr_task_assignment(assignment, packet)

        self.assertEqual(classification["status"], policy_module.PR_ALLOWED_STATUS)
        self.assertEqual(
            classification["reason"],
            policy_module.PR_ALLOWED_GOVERNOR_WRITER_REASON,
        )
        self.assertFalse(classification["blocked"])

    def test_issue159_rejects_generic_backend_fallback_for_bears_gateway_handoff(self) -> None:
        assignment = {
            "agent_type": "backend-developer",
            "domain_owner": "bears-gateway-platform-engineer",
            "implementation_handoff": True,
            "task_summary": "Bears platform gateway implementation",
            "allowed_actions": ["publish", "ready", "merge", "push"],
        }

        classification = policy_module.classify_role_profile_fallback_assignment(
            assignment,
            self.policy,
        )
        errors = policy_module.validate_read_only_assignment_packet(assignment, self.policy)

        self.assertEqual(classification["status"], policy_module.ROLE_PROFILE_DOWNGRADE_STATUS)
        self.assertEqual(classification["reason"], policy_module.ROLE_PROFILE_DOWNGRADE_REASON)
        self.assertTrue(classification["blocked"])
        self.assertTrue(classification["mutation_blocked"])
        self.assertEqual(classification["fallback_role"], "backend-developer")
        self.assertEqual(classification["domain_owner"], "bears-gateway-platform-engineer")
        self.assertEqual(
            classification["actions"],
            ["git_push", "pr_merge", "pr_publish", "pr_ready_for_review"],
        )
        self.assertTrue(any(policy_module.ROLE_PROFILE_DOWNGRADE_STATUS in error for error in errors), errors)
        self.assertTrue(
            any(policy_module.GENERIC_FALLBACK_PR_MUTATION_STATUS in error for error in errors),
            errors,
        )

    def test_issue159_rejects_mixed_bears_agent_type_and_generic_fallback_agent_type(self) -> None:
        assignment = {
            "agent_type": "bears-gateway-platform-engineer",
            "fallback_agent_type": "backend-developer",
            "implementation_handoff": True,
            "task_summary": "Bears gateway implementation handoff",
        }

        classification = policy_module.classify_role_profile_fallback_assignment(
            assignment,
            self.policy,
        )
        errors = policy_module.validate_read_only_assignment_packet(assignment, self.policy)

        self.assertEqual(classification["status"], policy_module.ROLE_PROFILE_DOWNGRADE_STATUS)
        self.assertEqual(classification["reason"], policy_module.ROLE_PROFILE_DOWNGRADE_REASON)
        self.assertTrue(classification["blocked"])
        self.assertEqual(classification["fallback_role"], "backend-developer")
        self.assertEqual(classification["domain_owner"], "bears-gateway-platform-engineer")
        self.assertTrue(any(policy_module.ROLE_PROFILE_DOWNGRADE_STATUS in error for error in errors), errors)

    def test_issue159_rejects_generic_fallback_with_target_write_paths_list(self) -> None:
        assignment = {
            "agent_type": "bears-gateway-platform-engineer",
            "fallback_agent_type": "backend-developer",
            "target_write_paths": ["scripts/gateway_policy.py"],
            "task_summary": "Bears gateway implementation handoff",
        }

        classification = policy_module.classify_role_profile_fallback_assignment(
            assignment,
            self.policy,
        )
        errors = policy_module.validate_read_only_assignment_packet(assignment, self.policy)

        self.assertEqual(classification["status"], policy_module.ROLE_PROFILE_DOWNGRADE_STATUS)
        self.assertTrue(classification["blocked"])
        self.assertTrue(any(policy_module.ROLE_PROFILE_DOWNGRADE_STATUS in error for error in errors), errors)

    def test_issue159_spawn_preflight_blocks_mixed_generic_fallback_packet_shape(self) -> None:
        packet = {
            "spawn_agent_arguments": {
                "assignment_packet_id": "issue-159:T001",
                "items": [
                    {
                        "type": "text",
                        "text": (
                            "@bears\n"
                            "PRE_TASK_HOOK\n"
                            "ASSIGNMENT_PACKET\n"
                            "role=bears-gateway-platform-engineer"
                        ),
                    }
                ],
                "agent_type": "bears-gateway-platform-engineer",
                "fallback_agent_type": "backend-developer",
                "target_write_paths": ["scripts/gateway_policy.py"],
            },
        }

        errors = policy_module.validate_spawn_agent_preflight_packet(packet, self.policy)

        self.assertTrue(any(policy_module.ROLE_PROFILE_DOWNGRADE_STATUS in error for error in errors), errors)

    def test_issue159_role_profile_fallback_final_report_rejects_each_missing_required_field(
        self,
    ) -> None:
        report = {
            "fallback_role": "backend-developer",
            "domain_owner": "bears-gateway-platform-engineer",
            "profile_downgrade_status": "ROLE_PROFILE_DOWNGRADE",
            "parity_enforcement": "validated_role_parity_packet",
            "mutation_authority_lane": "not_requested",
            "safety_rationale": "No raw secrets, raw logs, production data, or runtime surface touched.",
        }

        self.assertEqual(
            policy_module.validate_role_profile_fallback_final_report_packet(report, self.policy),
            [],
        )
        for field in sorted(report):
            with self.subTest(field=field):
                broken = dict(report)
                broken.pop(field)
                errors = policy_module.validate_role_profile_fallback_final_report_packet(
                    broken,
                    self.policy,
                )
                self.assertTrue(
                    any(f"missing required final report field: {field}" in error for error in errors),
                    errors,
                )

    def test_issue159_delegation_closeout_enforces_role_profile_final_report_fields(self) -> None:
        packet = {
            "controller_id": "workflow-delegation-controller",
            "parent role route": "bears-subagent-orchestration-engineer",
            "child role": "bears-platform-role-governor",
            "child lane": "plugin policy review",
            "write scope or read-only scope": "read-only policy review",
            "validation command": "python3 scripts/subagent_orchestration_policy.py validate",
            "assignment packet id": "assign-issue-159",
            "pre-task hook evidence": "pre-task hook completed before task start",
            "operator missing data answers": "none missing",
            "operator drift answers": "drift answers recorded",
            "task-start authorization": "task start approved from pre-task hook",
            "spawn evidence": "assignment packet accepted",
            "closeout evidence": "closeout packet collected",
            "validation hook result": {
                "hook_id": "subagent_policy_validate",
                "cwd": str(PLUGIN_ROOT),
                "command_id": "subagent_policy_validate",
                "exit_code": 0,
                "sanitized_summary": "subagent policy validation passed",
                "validation_target": "assets/catalog/subagent-orchestration-policy.v1.json",
            },
            "final_report": {
                "fallback_role": "backend-developer",
                "domain_owner": "bears-gateway-platform-engineer",
                "profile_downgrade_status": "ROLE_PROFILE_DOWNGRADE",
                "parity_enforcement": "validated_role_parity_packet",
                "mutation_authority_lane": "not_requested",
            },
        }

        errors = policy_module.validate_delegation_closeout_packet(packet, self.policy)

        self.assertTrue(any("missing required final report field: safety_rationale" in error for error in errors), errors)

    def test_role_profile_fallback_requires_separate_mutation_authority_lane(self) -> None:
        assignment = {
            "agent_type": "backend-developer",
            "domain_owner": "bears-gateway-platform-engineer",
            "implementation_handoff": True,
            "allowed_actions": ["publish", "ready", "merge"],
            "role_profile_downgrade": "ROLE_PROFILE_DOWNGRADE",
            "role_parity_packet": {
                "validated": True,
                "domain_owner": "bears-gateway-platform-engineer",
                "fallback_agent_type": "backend-developer",
                "developer_instructions_packet_attached": True,
                "exact_role_profile_attached": True,
                "role_gate_result_attached": True,
            },
        }

        classification = policy_module.classify_role_profile_fallback_assignment(
            assignment,
            self.policy,
        )
        errors = policy_module.validate_read_only_assignment_packet(assignment, self.policy)

        self.assertEqual(
            classification["status"],
            policy_module.GENERIC_FALLBACK_PR_MUTATION_STATUS,
        )
        self.assertEqual(
            classification["reason"],
            policy_module.GENERIC_FALLBACK_PR_MUTATION_REASON,
        )
        self.assertTrue(classification["blocked"])
        self.assertTrue(any(policy_module.GENERIC_FALLBACK_PR_MUTATION_STATUS in error for error in errors), errors)

    def test_allows_generic_fallback_with_parity_and_mutation_lane(self) -> None:
        assignment = {
            "agent_type": "backend-developer",
            "domain_owner": "bears-gateway-platform-engineer",
            "implementation_handoff": True,
            "allowed_actions": ["publish", "ready"],
            "role_profile_downgrade": "ROLE_PROFILE_DOWNGRADE",
            "role_parity_packet": {
                "validated": True,
                "domain_owner": "bears-gateway-platform-engineer",
                "fallback_agent_type": "backend-developer",
                "developer_instructions_packet_attached": True,
                "exact_role_profile_attached": True,
                "role_gate_result_attached": True,
            },
            "mutation_authority_lane": {
                "lane_id": "operator-approved-pr-mutation",
                "approved": True,
                "approved_actions": ["pr_publish", "pr_ready_for_review"],
                "approval_reference": "operator-approval-issue-159",
            },
        }

        classification = policy_module.classify_role_profile_fallback_assignment(
            assignment,
            self.policy,
        )
        errors = policy_module.validate_read_only_assignment_packet(assignment, self.policy)

        self.assertEqual(classification["status"], policy_module.PR_ALLOWED_STATUS)
        self.assertEqual(
            classification["reason"],
            policy_module.ROLE_PROFILE_FALLBACK_ALLOWED_REASON,
        )
        self.assertFalse(classification["blocked"])
        self.assertEqual(errors, [])

    def test_rejects_read_only_assignment_with_write_authority(self) -> None:
        assignment = {
            "agent_name": "bears-platform-security-reviewer",
            "sandbox_mode": "read-only",
            "assignment_authority": ["file_write"],
            "write_scope": "agents/bears-platform-security-reviewer.toml",
        }
        errors = policy_module.validate_read_only_assignment_packet(assignment, self.policy)
        self.assertTrue(any("file_write" in error for error in errors), errors)
        self.assertTrue(any("write_scope" in error for error in errors), errors)


    def test_issue161_rejects_read_only_raw_secret_authority(self) -> None:
        assignment = {
            "agent_name": "bears-platform-security-reviewer",
            "sandbox_mode": "read-only",
            "allowed_actions": ["raw_secret_read"],
        }

        errors = policy_module.validate_read_only_assignment_packet(assignment, self.policy)

        self.assertTrue(any("raw_secret_read" in error for error in errors), errors)

    def test_issue161_rejects_read_only_secret_phrase_authority(self) -> None:
        assignment = {
            "agent_name": "bears-platform-security-reviewer",
            "sandbox_mode": "read-only",
            "allowed_actions": ["read secrets"],
        }

        errors = policy_module.validate_read_only_assignment_packet(assignment, self.policy)

        self.assertTrue(any("secret_read" in error for error in errors), errors)

    def test_issue161_rejects_read_only_env_file_authority(self) -> None:
        assignment = {
            "agent_name": "bears-platform-security-reviewer",
            "sandbox_mode": "read-only",
            "allowed_actions": ["env_file_read"],
        }

        errors = policy_module.validate_read_only_assignment_packet(assignment, self.policy)

        self.assertTrue(any("env_file_read" in error for error in errors), errors)

    def test_issue161_rejects_read_only_env_phrase_authority(self) -> None:
        assignment = {
            "agent_name": "bears-platform-security-reviewer",
            "sandbox_mode": "read-only",
            "allowed_actions": ["read .env"],
        }

        errors = policy_module.validate_read_only_assignment_packet(assignment, self.policy)

        self.assertTrue(any("env_file_read" in error for error in errors), errors)

    def test_rejects_parent_override_widening_read_only_assignment(self) -> None:
        assignment = {
            "agent_name": "bears-platform-security-reviewer",
            "sandbox_mode": "read-only",
            "parent_live_sandbox_override": "workspace-write",
        }
        errors = policy_module.validate_read_only_assignment_packet(assignment, self.policy)
        self.assertTrue(any("cannot widen" in error for error in errors), errors)

    def test_rejects_parent_override_even_with_boolean_allowance_when_policy_has_none(self) -> None:
        assignment = {
            "agent_name": "bears-platform-security-reviewer",
            "sandbox_mode": "read-only",
            "parent_live_sandbox_override": "workspace-write",
            "explicit_bears_policy_allowance": True,
        }
        errors = policy_module.validate_read_only_assignment_packet(assignment, self.policy)
        self.assertTrue(any("policy allows no read-only widening allowances" in error for error in errors), errors)

    def test_issue122_rejects_current_day_collector_memory_and_broad_session_scan(self) -> None:
        assignment = {
            "agent_name": "workflow-artifact-validator",
            "sandbox_mode": "read-only",
            "current_day_collector": True,
            "task_summary": "current-day checkpoint collector",
            "session_checkpoints": [
                {
                    "session_id": "019ece26-9738-7660-af4e-62ed3d470ddc",
                    "path": "/home/ai1/.codex/sessions/2026/06/16/rollout-2026-06-16T01-58-16-019ece26-9738-7660-af4e-62ed3d470ddc.jsonl",
                    "line_range": "10-30",
                }
            ],
            "evidence_scope": {
                "file_paths": [
                    "/home/ai1/.codex/sessions/2026/06/16/rollout-2026-06-16T01-58-16-019ece26-9738-7660-af4e-62ed3d470ddc.jsonl"
                ],
                "line_ranges": ["10-30"],
            },
            "commands": [
                "grep current /home/ai1/.codex/memories/MEMORY.md",
                "find /home/ai1/.codex/sessions -type f -name '*.jsonl'",
            ],
        }

        errors = policy_module.validate_read_only_assignment_packet(assignment, self.policy)

        self.assertTrue(any("memory_read" in error for error in errors), errors)
        self.assertTrue(any("broad_session_scan" in error for error in errors), errors)
        self.assertTrue(any("SCOPE_EXPANSION_REQUIRED" in error for error in errors), errors)

    def test_issue122_accepts_current_day_collector_with_explicit_checkpoint_scope(self) -> None:
        assignment = {
            "agent_name": "workflow-artifact-validator",
            "sandbox_mode": "read-only",
            "current_day_collector": True,
            "session_checkpoints": [
                {
                    "session_id": "019ece26-9738-7660-af4e-62ed3d470ddc",
                    "path": "/home/ai1/.codex/sessions/2026/06/16/rollout-2026-06-16T01-58-16-019ece26-9738-7660-af4e-62ed3d470ddc.jsonl",
                    "line_range": "10-30",
                }
            ],
            "evidence_scope": {
                "file_paths": [
                    "/home/ai1/.codex/sessions/2026/06/16/rollout-2026-06-16T01-58-16-019ece26-9738-7660-af4e-62ed3d470ddc.jsonl"
                ],
                "line_ranges": ["10-30"],
            },
            "commands": [
                "sed -n '10,30p' /home/ai1/.codex/sessions/2026/06/16/rollout-2026-06-16T01-58-16-019ece26-9738-7660-af4e-62ed3d470ddc.jsonl"
            ],
        }

        self.assertEqual(
            policy_module.validate_read_only_assignment_packet(assignment, self.policy),
            [],
        )

    def test_issue127_rejects_current_state_memory_as_evidence(self) -> None:
        assignment = {
            "agent_name": "bears-platform-security-reviewer",
            "sandbox_mode": "read-only",
            "current_state_audit": True,
            "assignment_summary": "final audit for current PR heads",
            "commands": ["grep issue /home/ai1/.codex/memories/MEMORY.md"],
            "source_authority": {
                "claim": "open PR state",
                "authority": "PR API",
            },
            "fresh_source_proof": "gh pr list --json number,headRefOid",
        }

        errors = policy_module.validate_read_only_assignment_packet(assignment, self.policy)

        self.assertTrue(any("memory_read" in error for error in errors), errors)

    def test_issue127_rejects_current_state_broad_scan_without_allowlist(self) -> None:
        assignment = {
            "agent_name": "bears-platform-security-reviewer",
            "sandbox_mode": "read-only",
            "current_state_audit": True,
            "assignment_summary": "current-state final audit",
            "commands": ["rg remaining_gap .worktrees dev/platform"],
            "source_authority": {
                "claim": "remaining objective gaps",
                "authority": "exact repo path",
            },
            "fresh_source_proof": "git -C /srv/bears/plugins/bears rev-parse HEAD",
        }

        errors = policy_module.validate_read_only_assignment_packet(assignment, self.policy)

        self.assertTrue(any("broad_scan" in error for error in errors), errors)
        self.assertTrue(any("allowlist" in error for error in errors), errors)

    def test_issue127_accepts_current_state_source_authority_per_claim(self) -> None:
        packet = {
            "status": "PASS",
            "current_state_audit": True,
            "memory_locator_only": True,
            "commands": [
                "grep locator /home/ai1/.codex/memories/MEMORY.md",
                "gh pr view 301 --json number,headRefOid,files",
            ],
            "claims": [
                {
                    "claim": "PR 301 head is authoritative for subagent policy conflict",
                    "source_authority": "PR API",
                    "fresh_api_evidence": "gh pr view 301 --json number,headRefOid,files",
                },
                {
                    "claim": "Policy file validation target is exact",
                    "exact_file_list": ["assets/catalog/subagent-orchestration-policy.v1.json"],
                    "fresh_command_evidence": "python3 scripts/subagent_orchestration_policy.py validate",
                },
            ],
            "bounded_read_allowlist": [
                "assets/catalog/subagent-orchestration-policy.v1.json",
                "scripts/subagent_orchestration_policy.py",
            ],
            "max_output_lines": 120,
        }

        self.assertEqual(policy_module.validate_subagent_closeout_quality_packet(packet), [])

    def test_issue127_rejects_top_level_authority_when_claim_lacks_authority(self) -> None:
        packet = {
            "status": "PASS",
            "current_state_audit": True,
            "source_authority": {
                "claim": "PR state",
                "authority": "PR API",
            },
            "fresh_source_proof": "gh pr view 348 --json number,headRefOid,files",
            "claims": [
                {
                    "claim": "PR 348 head is current",
                    "source_authority": "PR API",
                    "fresh_api_evidence": "gh pr view 348 --json number,headRefOid,files",
                },
                {
                    "claim": "Issue 127 is fully covered",
                },
            ],
        }

        errors = policy_module.validate_subagent_closeout_quality_packet(packet)

        self.assertTrue(
            any("claims[1].source_authority" in error for error in errors),
            errors,
        )

    def test_rejects_audit_subagent_reuse_for_writable_task(self) -> None:
        assignment = {
            "agent_name": "bears-platform-security-reviewer",
            "sandbox_mode": "read-only",
            "audit_subagent": True,
            "reuse_requested": True,
            "assigned_to_writable_task": True,
        }
        errors = policy_module.validate_read_only_assignment_packet(assignment, self.policy)
        self.assertTrue(any("reuse_requested" in error for error in errors), errors)
        self.assertTrue(any("writable" in error for error in errors), errors)

    def test_rejects_read_only_safety_claim_without_validator_coverage(self) -> None:
        assignment = {
            "agent_name": "bears-platform-security-reviewer",
            "sandbox_mode": "read-only",
            "read_only_safety_claim": True,
            "validator_evidence_command": "not-run",
        }
        errors = policy_module.validate_read_only_assignment_packet(assignment, self.policy)
        self.assertTrue(any("validator_evidence_command" in error for error in errors), errors)

    def test_read_only_agent_toml_has_blocking_markers(self) -> None:
        reviewer = tomllib.loads(
            (PLUGIN_ROOT / "agents" / "bears-platform-security-reviewer.toml").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(reviewer["sandbox_mode"], "read-only")
        instructions = reviewer["developer_instructions"]
        self.assertIn("sandbox_mode is not authority proof", instructions)
        self.assertIn("READ_ONLY_ASSIGNMENT_BLOCKED", instructions)
        self.assertIn(
            "audit subagent sessions cannot be reused for writable tasks",
            instructions,
        )


if __name__ == "__main__":
    unittest.main()
