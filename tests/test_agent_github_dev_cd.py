from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

import yaml

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PLUGIN_ROOT / "scripts/agent_github_dev_cd.py"
CATALOG_PATH = PLUGIN_ROOT / "assets/catalog/agent-github-dev-cd.v1.json"
ROLE_CATALOG_PATH = PLUGIN_ROOT / "assets/catalog/platform-role-catalog.v1.json"

spec = importlib.util.spec_from_file_location("agent_github_dev_cd", SCRIPT_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("cannot load scripts/agent_github_dev_cd.py")
agent_cd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent_cd)


class AgentGithubDevCdValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        cls.role_catalog = json.loads(ROLE_CATALOG_PATH.read_text(encoding="utf-8"))

    def test_validate_catalog_passes_for_current_files(self) -> None:
        errors = agent_cd.validate_catalog(deepcopy(self.catalog), role_catalog=self.role_catalog)
        self.assertEqual(errors, [])

    def test_route_target_matches_exact_role(self) -> None:
        platform_roles = agent_cd._load_platform_roles_module()
        packet = platform_roles.route_target(
            self.role_catalog,
            "/srv/bears/plugins/bears/.github/workflows/validate.yml",
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(packet["status"], "matched")
        self.assertEqual(packet["concrete_part"], "workflow_overlay_validation_ci_workflow")
        self.assertEqual(packet["primary_role"], "bears-deploy-platform-engineer")
        self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])

    def test_parent_agent_policy_is_orchestration_only(self) -> None:
        policy = self.catalog["parent_agent_policy"]
        self.assertEqual(policy["mode"], "orchestration_only_in_subagent_mode")
        self.assertFalse(policy["parent_context_allowed"])
        self.assertEqual(policy["parent_actions"], list(agent_cd.REQUIRED_PARENT_AGENT_ACTIONS))
        self.assertEqual(policy["forbidden_actions"], list(agent_cd.REQUIRED_PARENT_AGENT_FORBIDDEN_ACTIONS))
        for forbidden in ("file_read_as_content_collector", "file_write", "git_add", "git_commit"):
            self.assertNotIn(forbidden, policy["parent_actions"])

    def _valid_agent_pickup_packet(self) -> dict[str, object]:
        return {
            "schema": agent_cd.AGENT_PICKUP_PACKET_SCHEMA,
            "labels": ["type:develop-ready"],
            "body": self._valid_develop_ready_body(),
            "route_gate": {
                "status": "matched",
                "target": "assets/catalog/agent-github-dev-cd.v1.json",
                "concrete_part": "agent_github_dev_cd_flow",
                "primary_role": "bears-deploy-platform-engineer",
            },
            "constitution_evidence": {
                "status": "pass",
                "evidence_path": "docs/evidence/constitution.md",
                "command": "python3 scripts/plugin_constitution.py validate",
                "result": "exit 0",
            },
            "research_evidence": {
                "status": "approved",
                "source_ref": "docs/evidence/research.md",
                "decision_reason": "Existing Bears agent pickup policy is reused.",
            },
            "accepted_operator_decision_evidence": {
                "status": "accepted",
                "source_ref": "issues/1",
                "decision_reason": "Operator accepted develop-ready scope.",
            },
            "owning_role": "bears-deploy-platform-engineer",
            "task_packet": {
                "issue": "#1",
                "bounded_target": "scripts/agent_github_dev_cd.py",
                "allowed_write_surfaces": ["scripts/agent_github_dev_cd.py", "tests/test_agent_github_dev_cd.py"],
                "allowed_read_surfaces": ["assets/catalog/agent-github-dev-cd.v1.json"],
                "owning_role": "bears-deploy-platform-engineer",
                "validation_commands": ["python3 scripts/agent_github_dev_cd.py validate"],
                "safety_boundary": "metadata-only; no secrets, raw logs, raw chat, raw VPN configs, or production data",
            },
            "duplicate_guard": {
                "status": "unique",
                "duplicates_found": False,
                "repository": "BearsCLOUD/bears_plugin",
                "normalized_scope_key": "agent-github-dev-cd:agent-pickup-gates",
                "search_query": "repo:BearsCLOUD/bears_plugin is:issue is:open agent pickup gates",
                "checked_at": "2026-06-19T00:00:00Z",
                "evidence_summary": "No matching open issue or active worker for this bounded scope.",
            },
            "dry_run": {
                "status": "pass",
                "command": "python3 scripts/agent_github_dev_cd.py verify-agent-pickup --issue-packet packet.json --dry-run",
                "result": "exit 0",
            },
        }

    def _valid_develop_ready_body(self) -> str:
        return "\n".join(
            [
                "## Concrete problem",
                "Automation-created governance issues can enter agent pickup without bounded readiness metadata.",
                "## Exact targets/surfaces",
                "`assets/catalog/agent-github-dev-cd.v1.json`, `scripts/agent_github_dev_cd.py`, and `tests/test_agent_github_dev_cd.py`.",
                "## Required change",
                "Require fixed type labels and canonical develop-ready body fields before agent pickup.",
                "## Acceptance criteria",
                "Unlabeled issues, conflicting type labels, empty bodies, and vague bodies fail closed.",
                "## Validation commands",
                "python3 scripts/agent_github_dev_cd.py validate",
                "python3 -m unittest tests/test_agent_github_dev_cd.py",
                "## Duplicate guard",
                "Duplicate search found no open issue covering this bounded metadata guard.",
                "## Safety boundary",
                "Metadata-only change; do not read secrets, production data, raw logs, raw chat, or VPN configs.",
            ]
        )

    def _issue_metadata_packet(self, issues: list[dict[str, object]]) -> dict[str, object]:
        return {
            "schema": agent_cd.ISSUE_METADATA_PACKET_SCHEMA,
            "repository": "BearsCLOUD/bears_plugin",
            "issues": issues,
        }

    def _valid_merge_authority_packet(self) -> dict[str, object]:
        return {
            "schema": agent_cd.MERGE_AUTHORITY_PACKET_SCHEMA,
            "request_source": {
                "actor": "merge_authority_lane",
                "channel": "assignment_packet",
                "instruction_text": "merge PR #132",
            },
            "pre_task_hook": {"status": "pass"},
            "assignment_packet": {
                "id": "issue-132",
                "role": "bears-deploy-platform-engineer",
                "merge_authority": {
                    "repository": "BearsCLOUD/bears_plugin",
                    "pull_request_number": 132,
                    "head_ref": "codex/merge-authority-lane",
                    "head_sha": "1234567890abcdef1234567890abcdef12345678",
                    "base_ref": "main",
                },
            },
            "repository": "BearsCLOUD/bears_plugin",
            "pull_request": {"number": 132, "url": "https://github.com/BearsCLOUD/bears_plugin/pull/132"},
            "head_ref": "codex/merge-authority-lane",
            "head_sha": "1234567890abcdef1234567890abcdef12345678",
            "base_ref": "main",
            "action": "merge",
            "check_policy": {"status": "pass", "check_count": 1, "required_contexts": ["ci-summary"], "passed_contexts": ["ci-summary"]},
            "state_file_policy": {
                "status": "pass",
                "authoritative_state_source": "machine_readable_state_files",
                "authority_sources": ["workflow_state", "merge_authority_state"],
                "required_state_refs": ["workflow_state", "merge_authority_state"],
                "state_refs": {
                    "workflow_state": "runtime/agent-workflow/demo/workflow-state.v1.json",
                    "merge_authority_state": "runtime/agent-workflow/demo/merge-authority-state.v1.json",
                },
                "non_state_authority_allowed": False,
            },
            "title_policy": {
                "status": "pass",
                "validated_before_ready": True,
                "validated_before_merge": True,
            },
            "draft_policy": {"status": "pass", "is_draft": False},
            "rollback_note": "Revert the merge commit if validation regresses.",
            "authority": {"source": "operator_request", "evidence": "issue #132 accepted slice"},
            "conflict_policy": {"mergeable_state": "CLEAN"},
        }

    def _valid_merge_authority_expected(self) -> dict[str, object]:
        return {
            "repository": "BearsCLOUD/bears_plugin",
            "pull_request_number": 132,
            "head_ref": "codex/merge-authority-lane",
            "head_sha": "1234567890abcdef1234567890abcdef12345678",
            "base_ref": "main",
        }

    def _valid_dev_auto_merge_expected(self) -> dict[str, object]:
        expected = self._valid_merge_authority_expected()
        expected["base_ref"] = "dev"
        expected["head_ref"] = "goal/demo"
        return expected

    def _valid_dev_auto_merge_packet(self) -> dict[str, object]:
        merge_packet = self._valid_merge_authority_packet()
        merge_packet["head_ref"] = "goal/demo"
        merge_packet["base_ref"] = "dev"
        merge_packet["authority"] = {
            "source": "contract_authority",
            "evidence": "dev_auto_merge_policy after state-file gate and ci-summary",
        }
        merge_packet["check_policy"] = {
            "status": "pass",
            "check_count": 1,
            "required_contexts": ["ci-summary"],
            "passed_contexts": ["ci-summary"],
        }
        merge_packet["assignment_packet"]["merge_authority"]["head_ref"] = "goal/demo"
        merge_packet["assignment_packet"]["merge_authority"]["base_ref"] = "dev"
        return {
            "schema": agent_cd.DEV_AUTO_MERGE_PACKET_SCHEMA,
            "target_branch": "dev",
            "source_branch": "goal/demo",
            "topology_policy": {
                "status": "pass",
                "verification_command": "python3 scripts/agent_github_dev_cd.py verify-live-topology --goal-id demo --expected-mode sequential",
            },
            "merge_authority_packet": merge_packet,
        }

    def test_dev_cd_policy_is_deprecated_reference_only(self) -> None:
        cd_policy = self.catalog["cd_policy"]
        self.assertEqual(cd_policy["authority_status"], "deprecated_reference_only")
        self.assertFalse(cd_policy["active_authority"])
        self.assertEqual(cd_policy["dev_branch"], "dev")
        self.assertEqual(cd_policy["agent_current_runtime"], "/srv/bears")
        self.assertFalse(cd_policy["auto_deploy_to_dev_on_merge"])
        self.assertEqual(cd_policy["deploy_source_of_truth"], "/srv/bears/kubernetes")
        self.assertFalse(cd_policy["cluster_mutation_allowed_from_plugin"])
        self.assertFalse(cd_policy["production_deploy_allowed"])
        self.assertIn("deprecated reference only", cd_policy["plugin_root_production_mutation_policy"])
        contract = cd_policy["dispatch_plan_contract"]
        self.assertEqual(contract["schema"], "bears-agent-github-dev-cd-dispatch-gate.v1")
        self.assertEqual(contract["mode"], "deprecated_reference_only")
        self.assertFalse(contract["active_authority"])
        self.assertEqual(contract["artifact_path"], "artifacts/dev-cd-dispatch-gate.json")
        self.assertEqual(contract["artifact_name"], "dev-cd-dispatch-gate")
        self.assertTrue(contract["operator_approval_required"])
        self.assertTrue(contract["fail_closed_when_evidence_missing"])
        self.assertIn("Goal-Id", contract["required_commit_trailers"])
        self.assertIn("Workflow-State", contract["required_commit_trailers"])
        self.assertIn("Kubernetes-Dispatch-Plan: artifacts/dev-cd-dispatch-gate.json", contract["required_commit_trailers"])
        self.assertEqual(contract["evidence_path_contract"], agent_cd.REQUIRED_EVIDENCE_PATH_CONTRACT)

    def test_catalog_defines_development_scenario_policy(self) -> None:
        policy = self.catalog["scenario_policy"]
        self.assertEqual(policy, agent_cd.REQUIRED_SCENARIO_POLICY)
        self.assertEqual(policy["runtime"]["agent_current_runtime"], "/srv/bears")
        self.assertFalse(policy["defaults"]["auto_merge_to_main_allowed"])
        self.assertFalse(policy["scenarios"]["dev"]["auto_cd_allowed"])
        self.assertFalse(policy["scenarios"]["prod"]["auto_merge_to_main_allowed"])
        self.assertFalse(policy["scenarios"]["bugfix"]["auto_merge_to_main_allowed"])
        self.assertTrue(policy["scenarios"]["hot_bugfix"]["git_backfill_required"])
        self.assertFalse(policy["scenarios"]["hot_bugfix"]["plugin_root_production_mutation_allowed"])

    def test_classifier_single_marker_classifies_each_development_scenario(self) -> None:
        cases = {
            "dev rollout": "dev",
            "prod release": "prod",
            "bugfix login crash": "bugfix",
            "hot bugfix checkout outage": "hot_bugfix",
            "issue #364 metadata": "issue",
            "/goal roadmap update": "goal",
        }
        for prompt, scenario in cases.items():
            with self.subTest(prompt=prompt):
                payload = agent_cd.classify_task_prompt(prompt)
                self.assertEqual(payload["schema"], agent_cd.TASK_CLASSIFICATION_SCHEMA)
                self.assertEqual(payload["status"], "classified")
                self.assertEqual(payload["detected_scenarios"], [scenario])
                self.assertFalse(payload["split_required"])
                self.assertEqual(len(payload["tasks"]), 1)
                task = payload["tasks"][0]
                self.assertEqual(task["development_scenario"], scenario)
                self.assertEqual(task["route"], agent_cd.SCENARIO_TASK_ROUTES[scenario])
                self.assertFalse(task["requires_separate_subagent"])
                if scenario == "hot_bugfix":
                    self.assertFalse(payload["markers"]["bugfix"])

    def test_classifier_mixed_markers_split_into_separate_subagent_tasks(self) -> None:
        payload = agent_cd.classify_task_prompt("hot bugfix prod issue #364")

        self.assertEqual(payload["status"], "split_required")
        self.assertTrue(payload["split_required"])
        self.assertEqual(payload["detected_scenarios"], ["prod", "hot_bugfix", "issue"])
        self.assertEqual([task["development_scenario"] for task in payload["tasks"]], ["prod", "hot_bugfix", "issue"])
        self.assertTrue(all(task["requires_separate_subagent"] for task in payload["tasks"]))
        self.assertEqual(len({task["task_id"] for task in payload["tasks"]}), 3)

    def test_classifier_without_marker_fails_closed(self) -> None:
        payload = agent_cd.classify_task_prompt("please continue")

        self.assertEqual(payload["status"], "needs_scenario_marker")
        self.assertEqual(payload["detected_scenarios"], [])
        self.assertEqual(payload["tasks"], [])
        self.assertIn("no development scenario marker found", payload["reasons"])

    def _scenario_packet(self, scenario: str, **extra: object) -> dict[str, object]:
        packet: dict[str, object] = {
            "schema": agent_cd.SCENARIO_POLICY_PACKET_SCHEMA,
            "development_scenario": scenario,
        }
        packet.update(extra)
        return packet

    def test_scenario_policy_dev_uses_main_only_delivery(self) -> None:
        packet = self._scenario_packet(
            "dev",
            target_branch="main",
            runtime_target="main_only_delivery",
        )

        payload = agent_cd.evaluate_scenario_policy_packet(packet)

        self.assertEqual(payload["status"], "pass", payload)
        self.assertTrue(payload["allowed"])
        self.assertFalse(payload["scenario_policy"]["auto_cd_allowed"])
        self.assertEqual(payload["scenario_policy"]["runtime_target"], "main_only_delivery")

    def test_scenario_policy_prod_blocks_auto_main_merge(self) -> None:
        packet = self._scenario_packet(
            "prod",
            target_branch="main",
            runtime_target="ci_cd",
            auto_merge_to_main_requested=True,
            main_merge_actor="operator_direct_main_commit",
        )

        payload = agent_cd.evaluate_scenario_policy_packet(packet)

        self.assertEqual(payload["status"], "fail")
        self.assertFalse(payload["allowed"])
        self.assertIn("auto merge to main is blocked for development_scenario=prod", payload["reasons"])

    def test_scenario_policy_bugfix_blocks_auto_main_under_main_only_delivery(self) -> None:
        packet = self._scenario_packet(
            "bugfix",
            target_branch="main",
            auto_merge_to_main_requested=True,
        )

        payload = agent_cd.evaluate_scenario_policy_packet(packet)

        self.assertEqual(payload["status"], "fail")
        self.assertFalse(payload["allowed"])
        self.assertFalse(payload["scenario_policy"]["auto_merge_to_main_allowed"])
        self.assertIn("bugfix auto merge to main is blocked under main-only delivery", payload["reasons"])

    def test_scenario_policy_hot_bugfix_requires_emergency_backfill_and_external_authority(self) -> None:
        blocked = self._scenario_packet(
            "hot_bugfix",
            plugin_root_production_mutation_requested=True,
            hot_bugfix={"emergency_task_first": True},
        )

        blocked_payload = agent_cd.evaluate_scenario_policy_packet(blocked)

        self.assertEqual(blocked_payload["status"], "fail")
        self.assertIn(
            "plugin root does not mutate production; scenario may route external emergency authority",
            blocked_payload["reasons"],
        )
        self.assertIn("hot_bugfix requires git_backfill_packet", blocked_payload["reasons"])
        self.assertIn("hot_bugfix requires external_emergency_authority", blocked_payload["reasons"])

        allowed = self._scenario_packet(
            "hot_bugfix",
            hot_bugfix={
                "emergency_task_first": True,
                "git_backfill_packet": True,
                "external_emergency_authority": True,
            },
        )
        allowed_payload = agent_cd.evaluate_scenario_policy_packet(allowed)
        self.assertEqual(allowed_payload["status"], "pass", allowed_payload)

    def test_scenario_policy_issue_and_goal_require_their_gates(self) -> None:
        issue_blocked = agent_cd.evaluate_scenario_policy_packet(self._scenario_packet("issue"))
        self.assertEqual(issue_blocked["status"], "fail")
        self.assertIn("issue scenario requires issue_metadata_gate_passed", issue_blocked["reasons"])
        self.assertIn("issue scenario requires agent_pickup_gate_passed", issue_blocked["reasons"])

        issue_allowed = agent_cd.evaluate_scenario_policy_packet(
            self._scenario_packet(
                "issue",
                issue={"metadata_gate_passed": True, "agent_pickup_gate_passed": True},
            )
        )
        self.assertEqual(issue_allowed["status"], "pass", issue_allowed)

        goal_blocked = agent_cd.evaluate_scenario_policy_packet(self._scenario_packet("goal"))
        self.assertEqual(goal_blocked["status"], "fail")
        self.assertIn("goal scenario requires roadmap_control_gate_passed", goal_blocked["reasons"])

        goal_allowed = agent_cd.evaluate_scenario_policy_packet(
            self._scenario_packet("goal", goal={"roadmap_control_gate_passed": True})
        )
        self.assertEqual(goal_allowed["status"], "pass", goal_allowed)

    def test_issue_type_policy_defines_develop_ready_for_agent_pickup(self) -> None:
        policy = self.catalog["issue_type_policy"]
        self.assertEqual(policy, agent_cd.REQUIRED_ISSUE_TYPE_POLICY)
        self.assertEqual(policy["issue_identifiers"]["bugfix"], "type:bugfix")
        self.assertEqual(policy["issue_identifiers"]["idea"], "type:idea")
        self.assertEqual(policy["issue_identifiers"]["develop_ready"], "type:develop-ready")
        self.assertEqual(
            policy["develop_ready"]["produced_by"],
            [
                "repository_constitution_alignment",
                "research",
                "accepted_operator_decision",
            ],
        )
        self.assertIn("duplicate_guard", policy["agent_pickup"]["required_pre_dispatch_gates"])
        self.assertEqual(
            policy["agent_pickup"]["structured_evidence_required"]["duplicate_guard"],
            list(agent_cd.AGENT_PICKUP_DUPLICATE_GUARD_REQUIRED_FIELDS),
        )
        self.assertEqual(
            policy["issue_template"]["required_develop_ready_field_ids"],
            list(agent_cd.ISSUE_TEMPLATE_REQUIRED_DEVELOP_READY_FIELD_IDS),
        )
        self.assertEqual(policy["type_label_guard"]["fixed_type_labels"], list(agent_cd.FIXED_ISSUE_TYPE_LABELS))
        self.assertTrue(policy["type_label_guard"]["open_governance_issue_exactly_one_type_label_required"])
        self.assertTrue(policy["type_label_guard"]["api_and_automation_created_issues_in_scope"])
        self.assertTrue(policy["type_label_guard"]["body_text_must_not_promote_to_type_develop_ready"])
        self.assertEqual(policy["type_label_guard"]["verify_command"], agent_cd.ISSUE_METADATA_VERIFY_COMMAND)
        self.assertEqual(
            policy["develop_ready"]["required_body_fields"],
            list(agent_cd.DEVELOP_READY_BODY_REQUIRED_FIELDS),
        )

    def test_merge_authority_policy_defines_typed_lane(self) -> None:
        policy = self.catalog["merge_authority_policy"]
        self.assertEqual(policy, agent_cd.REQUIRED_MERGE_AUTHORITY_POLICY)
        self.assertFalse(policy["parent_send_input_merge_directive_allowed"])
        self.assertEqual(policy["plain_parent_send_input_classification"], "workflow_drift")
        self.assertIn("title_policy", policy["required_fields"])
        self.assertEqual(policy["merge_eligibility_guards"]["allowed_status"], "MERGE_ALLOWED")
        self.assertEqual(policy["merge_eligibility_guards"]["blocked_status"], "MERGE_BLOCKED")
        self.assertEqual(
            policy["merge_eligibility_guards"]["empty_check_rollup_reason"],
            "MERGE_BLOCKED_EMPTY_CHECK_ROLLUP",
        )
        self.assertEqual(policy["merge_eligibility_guards"]["draft_pr_reason"], "MERGE_BLOCKED_DRAFT_PR")
        self.assertEqual(policy["merge_eligibility_guards"]["outdated_head_reason"], "MERGE_BLOCKED_OUTDATED_HEAD")

    def test_dev_auto_merge_policy_is_deprecated_reference_only(self) -> None:
        policy = self.catalog["dev_auto_merge_policy"]
        self.assertEqual(policy, agent_cd.REQUIRED_DEV_AUTO_MERGE_POLICY)
        self.assertEqual(policy["status"], "deprecated_reference_only")
        self.assertFalse(policy["active_authority"])
        self.assertEqual(policy["target_branch"], "none")
        self.assertEqual(policy["authority_source"], "none")
        self.assertTrue(policy["operator_request_required"])
        self.assertEqual(policy["required_check_contexts"], [])
        self.assertFalse(policy["auto_merge_to_main_allowed"])
        self.assertFalse(policy["production_deploy_allowed"])

    def test_dev_auto_merge_blocks_under_main_only_delivery(self) -> None:
        packet = self._valid_dev_auto_merge_packet()
        payload = agent_cd.evaluate_dev_auto_merge_packet(
            packet,
            expected=self._valid_dev_auto_merge_expected(),
        )
        self.assertFalse(payload["allowed"], payload)
        self.assertEqual(payload["classification"], agent_cd.DEV_AUTO_MERGE_BLOCKED_STATUS)
        self.assertEqual(payload["merge_eligibility_status"], agent_cd.MERGE_ALLOWED_STATUS)
        self.assertIn(agent_cd.DEV_AUTO_MERGE_DEPRECATED_REASON, payload["reasons"])

    def test_dev_auto_merge_blocks_main_target_even_with_valid_merge_packet(self) -> None:
        packet = self._valid_dev_auto_merge_packet()
        packet["target_branch"] = "main"
        packet["merge_authority_packet"]["base_ref"] = "main"
        packet["merge_authority_packet"]["assignment_packet"]["merge_authority"]["base_ref"] = "main"
        expected = self._valid_dev_auto_merge_expected()
        expected["base_ref"] = "main"
        payload = agent_cd.evaluate_dev_auto_merge_packet(packet, expected=expected)
        self.assertFalse(payload["allowed"])
        self.assertEqual(payload["classification"], agent_cd.DEV_AUTO_MERGE_BLOCKED_STATUS)
        self.assertIn(agent_cd.DEV_AUTO_MERGE_BLOCKED_MAIN_TARGET_REASON, payload["reasons"])

    def test_dev_auto_merge_blocks_missing_plugin_validation_context(self) -> None:
        packet = self._valid_dev_auto_merge_packet()
        packet["merge_authority_packet"]["check_policy"]["passed_contexts"] = []
        payload = agent_cd.evaluate_dev_auto_merge_packet(
            packet,
            expected=self._valid_dev_auto_merge_expected(),
        )
        self.assertFalse(payload["allowed"])
        self.assertIn(
            "dev auto-merge check_policy.passed_contexts must include: ci-summary",
            payload["reasons"],
        )

    def test_merge_authority_blocks_plain_parent_send_input(self) -> None:
        packet = {
            "request_source": {
                "actor": "parent_control",
                "channel": "send_input",
                "instruction_text": "merge PR #132 after checks",
            }
        }
        payload = agent_cd.evaluate_merge_authority_packet(packet)
        self.assertFalse(payload["allowed"])
        self.assertEqual(payload["status"], "workflow_drift")
        self.assertEqual(payload["classification"], "MERGE_AUTHORITY_DRIFT")
        self.assertIn("plain parent send_input merge directive is workflow drift", payload["reasons"])

    def test_merge_authority_blocks_empty_checks_without_exception(self) -> None:
        packet = self._valid_merge_authority_packet()
        packet["check_policy"] = {"status": "pass", "check_count": 0}
        payload = agent_cd.evaluate_merge_authority_packet(packet, expected=self._valid_merge_authority_expected())
        self.assertFalse(payload["allowed"])
        self.assertEqual(payload["merge_eligibility_status"], "MERGE_BLOCKED")
        self.assertEqual(payload["merge_eligibility_reason"], "MERGE_BLOCKED_EMPTY_CHECK_ROLLUP")
        self.assertIn("MERGE_BLOCKED_EMPTY_CHECK_ROLLUP", payload["reasons"])

    def test_merge_authority_blocks_empty_checks_even_with_exception(self) -> None:
        packet = self._valid_merge_authority_packet()
        packet["check_policy"] = {
            "status": "pass",
            "check_count": 0,
            "no_ci_exception": {
                "name": "ci-summary-unavailable",
                "reason": "repository has no active GitHub checks for this branch",
                "approved_by": "operator",
            },
        }
        payload = agent_cd.evaluate_merge_authority_packet(packet, expected=self._valid_merge_authority_expected())
        self.assertFalse(payload["allowed"])
        self.assertEqual(payload["merge_eligibility_status"], "MERGE_BLOCKED")
        self.assertEqual(payload["merge_eligibility_reason"], "MERGE_BLOCKED_EMPTY_CHECK_ROLLUP")

    def test_merge_authority_blocks_draft_pr_before_merge_allowed_status(self) -> None:
        packet = self._valid_merge_authority_packet()
        packet["draft_policy"] = {"status": "pass", "is_draft": True}
        payload = agent_cd.evaluate_merge_authority_packet(packet, expected=self._valid_merge_authority_expected())
        self.assertFalse(payload["allowed"])
        self.assertEqual(payload["merge_eligibility_status"], "MERGE_BLOCKED")
        self.assertEqual(payload["merge_eligibility_reason"], "MERGE_BLOCKED_DRAFT_PR")
        self.assertIn("MERGE_BLOCKED_DRAFT_PR", payload["reasons"])

    def test_merge_authority_requires_title_validation_before_ready_and_merge(self) -> None:
        packet = self._valid_merge_authority_packet()
        packet["title_policy"] = {"status": "pass", "validated_before_ready": False, "validated_before_merge": False}
        payload = agent_cd.evaluate_merge_authority_packet(packet, expected=self._valid_merge_authority_expected())
        self.assertFalse(payload["allowed"])
        self.assertIn("PR title validation must run before gh pr ready", payload["reasons"])
        self.assertIn("PR title validation must run before merge", payload["reasons"])

    def test_merge_authority_rejects_assignment_pr_head_mismatch(self) -> None:
        packet = self._valid_merge_authority_packet()
        packet["assignment_packet"]["merge_authority"]["pull_request_number"] = 999
        packet["assignment_packet"]["merge_authority"]["head_ref"] = "codex/wrong"
        packet["assignment_packet"]["merge_authority"]["head_sha"] = "abcdefabcdefabcdefabcdefabcdefabcdefabcd"
        payload = agent_cd.evaluate_merge_authority_packet(packet, expected=self._valid_merge_authority_expected())
        self.assertFalse(payload["allowed"])
        self.assertIn("assignment_packet.merge_authority.pull_request_number must match packet pull_request_number", payload["reasons"])
        self.assertIn("assignment_packet.merge_authority.head_ref must match packet head_ref", payload["reasons"])
        self.assertIn("assignment_packet.merge_authority.head_sha must match packet head_sha", payload["reasons"])

    def test_merge_authority_rejects_missing_live_expected_binding(self) -> None:
        packet = self._valid_merge_authority_packet()
        payload = agent_cd.evaluate_merge_authority_packet(packet)
        self.assertFalse(payload["allowed"])
        self.assertIn("merge authority check requires live expected PR/head binding", payload["reasons"])

    def test_merge_authority_rejects_live_expected_pr_head_mismatch(self) -> None:
        packet = self._valid_merge_authority_packet()
        payload = agent_cd.evaluate_merge_authority_packet(
            packet,
            expected={
                "repository": "BearsCLOUD/bears_plugin",
                "pull_request_number": 999,
                "head_ref": "codex/wrong",
                "head_sha": "abcdefabcdefabcdefabcdefabcdefabcdefabcd",
                "base_ref": "main",
            },
        )
        self.assertFalse(payload["allowed"])
        self.assertIn("expected.pull_request_number must match packet pull_request_number", payload["reasons"])
        self.assertIn("expected.head_ref must match packet head_ref", payload["reasons"])
        self.assertIn("expected.head_sha must match packet head_sha", payload["reasons"])
        self.assertEqual(payload["merge_eligibility_status"], "MERGE_BLOCKED")
        self.assertEqual(payload["merge_eligibility_reason"], "MERGE_BLOCKED_OUTDATED_HEAD")

    def test_merge_authority_rejects_outdated_head_base_condition(self) -> None:
        packet = self._valid_merge_authority_packet()
        packet["pull_request"]["head_is_current"] = False
        packet["pull_request"]["base_is_current"] = False
        packet["pull_request"]["behind_by"] = 2
        payload = agent_cd.evaluate_merge_authority_packet(packet, expected=self._valid_merge_authority_expected())
        self.assertFalse(payload["allowed"])
        self.assertEqual(payload["merge_eligibility_status"], "MERGE_BLOCKED")
        self.assertEqual(payload["merge_eligibility_reason"], "MERGE_BLOCKED_OUTDATED_HEAD")
        self.assertIn("MERGE_BLOCKED_OUTDATED_HEAD", payload["reasons"])

    def test_merge_authority_requires_full_head_sha(self) -> None:
        packet = self._valid_merge_authority_packet()
        packet["head_sha"] = "1234567"
        packet["assignment_packet"]["merge_authority"]["head_sha"] = "1234567"
        payload = agent_cd.evaluate_merge_authority_packet(packet, expected=self._valid_merge_authority_expected())
        self.assertFalse(payload["allowed"])
        self.assertIn("head_sha must be the exact 40-character PR head SHA", payload["reasons"])

    def test_merge_authority_allows_valid_typed_packet_with_current_pr_and_checks(self) -> None:
        packet = self._valid_merge_authority_packet()
        payload = agent_cd.evaluate_merge_authority_packet(packet, expected=self._valid_merge_authority_expected())
        self.assertTrue(payload["allowed"], payload)
        self.assertEqual(payload["classification"], "MERGE_AUTHORITY_READY")
        self.assertEqual(payload["merge_eligibility_status"], "MERGE_ALLOWED")
        self.assertEqual(payload["merge_eligibility_reason"], "MERGE_ALLOWED")

    def test_merge_authority_routes_unknown_mergeability_to_integration_fix(self) -> None:
        packet = self._valid_merge_authority_packet()
        packet["conflict_policy"] = {"mergeable_state": "UNKNOWN"}
        payload = agent_cd.evaluate_merge_authority_packet(packet, expected=self._valid_merge_authority_expected())
        self.assertFalse(payload["allowed"])
        self.assertTrue(payload["handoff_required"])
        self.assertEqual(payload["handoff_target"], "integration-fix")
        self.assertIn("mergeable_state must be CLEAN before merge", payload["reasons"])

    def test_merge_authority_blocks_missing_state_file_policy(self) -> None:
        packet = self._valid_merge_authority_packet()
        packet.pop("state_file_policy")
        payload = agent_cd.evaluate_merge_authority_packet(packet, expected=self._valid_merge_authority_expected())
        self.assertFalse(payload["allowed"])
        self.assertIn("state_file_policy must be an object", payload["reasons"])

    def test_merge_authority_blocks_non_state_authority(self) -> None:
        packet = self._valid_merge_authority_packet()
        packet["state_file_policy"]["non_state_authority_allowed"] = True
        payload = agent_cd.evaluate_merge_authority_packet(packet, expected=self._valid_merge_authority_expected())
        self.assertFalse(payload["allowed"])
        self.assertIn("state_file_policy.non_state_authority_allowed must be false", payload["reasons"])

    def test_merge_authority_blocks_missing_state_file_refs(self) -> None:
        packet = self._valid_merge_authority_packet()
        packet["state_file_policy"]["state_refs"] = {"workflow_state": "runtime/workflow-state.json"}
        payload = agent_cd.evaluate_merge_authority_packet(packet, expected=self._valid_merge_authority_expected())
        self.assertFalse(payload["allowed"])
        self.assertIn("state_file_policy.state_refs.merge_authority_state is required", payload["reasons"])

    def test_agent_pickup_allows_develop_ready_with_required_gates(self) -> None:
        payload = agent_cd.evaluate_agent_pickup_packet(self._valid_agent_pickup_packet(), dry_run_invoked=True)
        self.assertTrue(payload["allowed"])
        self.assertEqual(payload["status"], "pass")

    def test_agent_pickup_blocks_unlabeled_idea_bugfix_only_and_sensitive_labels(self) -> None:
        cases = [
            ([], "agent pickup blocked for unlabeled issue"),
            (["type:idea"], "agent pickup blocked by label: type:idea"),
            (["type:bugfix"], "agent pickup blocked for bugfix-only issue without type:develop-ready"),
            (["type:develop-ready", "blocked"], "agent pickup blocked by label: blocked"),
            (["type:develop-ready", "needs-human"], "agent pickup blocked by label: needs-human"),
            (["type:develop-ready", "needs-design"], "agent pickup blocked by label: needs-design"),
            (["type:develop-ready", "security"], "agent pickup blocked by label: security"),
            (["type:develop-ready", "security-review"], "agent pickup blocked by label: security-review"),
            (["type:develop-ready", "secret"], "agent pickup blocked by label: secret"),
            (["type:develop-ready", "credentials"], "agent pickup blocked by label: credentials"),
            (["type:develop-ready", "deploy"], "agent pickup blocked by label: deploy"),
            (["type:develop-ready", "production"], "agent pickup blocked by label: production"),
            (["type:develop-ready", "manual-only"], "agent pickup blocked by label: manual-only"),
            (["type:develop-ready", "agent:blocked"], "agent pickup blocked by label: agent:blocked"),
        ]
        for labels, reason in cases:
            packet = self._valid_agent_pickup_packet()
            packet["labels"] = labels
            payload = agent_cd.evaluate_agent_pickup_packet(packet, dry_run_invoked=True)
            self.assertFalse(payload["allowed"], labels)
            self.assertIn(reason, payload["reasons"])

    def test_agent_pickup_requires_route_evidence_task_packet_duplicate_guard_and_dry_run(self) -> None:
        packet = self._valid_agent_pickup_packet()
        packet["route_gate"] = {"status": "missing"}
        packet["task_packet"] = {}
        packet["duplicate_guard"] = {"status": "duplicate"}
        packet["dry_run"] = {"status": "not_run"}
        payload = agent_cd.evaluate_agent_pickup_packet(packet, dry_run_invoked=False)
        self.assertFalse(payload["allowed"])
        self.assertIn("agent pickup requires route gate evidence", payload["reasons"])
        self.assertIn("agent pickup requires task_packet", payload["reasons"])
        self.assertIn("agent pickup duplicate guard must prove unique issue scope", payload["reasons"])
        self.assertIn("agent pickup verification must run with --dry-run before dispatch", payload["reasons"])
        self.assertIn("agent pickup requires dry_run.status pass before dispatch", payload["reasons"])

    def test_agent_pickup_rejects_placeholder_duplicate_guard(self) -> None:
        for duplicate_guard in ({"status": "unique"}, {"duplicates_found": False}):
            packet = self._valid_agent_pickup_packet()
            packet["duplicate_guard"] = duplicate_guard
            payload = agent_cd.evaluate_agent_pickup_packet(packet, dry_run_invoked=True)
            self.assertFalse(payload["allowed"])
            self.assertTrue(any("duplicate_guard" in reason for reason in payload["reasons"]))

    def test_agent_pickup_rejects_inconsistent_duplicate_guard(self) -> None:
        for duplicate_guard in (
            {**self._valid_agent_pickup_packet()["duplicate_guard"], "status": "unique", "duplicates_found": True},
            {**self._valid_agent_pickup_packet()["duplicate_guard"], "status": "duplicate", "duplicates_found": False},
        ):
            packet = self._valid_agent_pickup_packet()
            packet["duplicate_guard"] = duplicate_guard
            payload = agent_cd.evaluate_agent_pickup_packet(packet, dry_run_invoked=True)
            self.assertFalse(payload["allowed"])
            self.assertIn("agent pickup duplicate guard must prove unique issue scope", payload["reasons"])

    def test_agent_pickup_rejects_duplicate_issue_or_active_worker_hit(self) -> None:
        packet = self._valid_agent_pickup_packet()
        packet["duplicate_guard"] = {
            **packet["duplicate_guard"],
            "matching_open_issues": ["#141"],
        }
        payload = agent_cd.evaluate_agent_pickup_packet(packet, dry_run_invoked=True)
        self.assertFalse(payload["allowed"])
        self.assertIn("agent pickup duplicate guard found matching open issue or active worker", payload["reasons"])

    def test_agent_pickup_rejects_placeholder_evidence_and_path_escape(self) -> None:
        packet = self._valid_agent_pickup_packet()
        packet["constitution_evidence"] = {"status": "pass", "evidence_path": "../secret", "command": "done", "result": "done"}
        packet["dry_run"] = {"status": "pass"}
        payload = agent_cd.evaluate_agent_pickup_packet(packet, dry_run_invoked=True)
        self.assertFalse(payload["allowed"])
        self.assertIn("agent pickup constitution_evidence requires safe evidence_path or source_ref", payload["reasons"])
        self.assertIn("agent pickup dry_run.command is required", payload["reasons"])

    def test_issue_template_aligns_with_agent_pickup_contract(self) -> None:
        template = agent_cd._load_yaml_mapping(agent_cd.PLUGIN_ROOT / agent_cd.ISSUE_TEMPLATE_PATH)
        config = agent_cd._load_yaml_mapping(agent_cd.PLUGIN_ROOT / ".github/ISSUE_TEMPLATE/config.yml")
        self.assertEqual(agent_cd._validate_issue_template_contract(template, config), [])

    def test_issue_metadata_reports_unlabeled_and_conflicting_open_governance_issues(self) -> None:
        packet = self._issue_metadata_packet(
            [
                {"number": 134, "state": "open", "labels": [], "body": self._valid_develop_ready_body()},
                {
                    "number": 139,
                    "state": "OPEN",
                    "labels": ["type:idea", "type:develop-ready"],
                    "body": self._valid_develop_ready_body(),
                },
            ]
        )
        payload = agent_cd.evaluate_issue_metadata_packet(packet)
        self.assertFalse(payload["allowed"])
        self.assertEqual(payload["checked_open_issues"], 2)
        self.assertEqual([violation["issue"] for violation in payload["violations"]], ["#134", "#139"])
        self.assertEqual(payload["violations"][0]["type_labels"], [])
        self.assertEqual(payload["violations"][1]["type_labels"], ["type:idea", "type:develop-ready"])
        for violation in payload["violations"]:
            self.assertIn(
                "open governance issue must carry exactly one fixed type label among type:bugfix, type:idea, type:develop-ready",
                violation["reasons"],
            )

    def test_issue_metadata_does_not_promote_from_body_text(self) -> None:
        packet = self._issue_metadata_packet(
            [
                {
                    "number": 140,
                    "state": "open",
                    "labels": [],
                    "body": "type:develop-ready\n" + self._valid_develop_ready_body(),
                }
            ]
        )
        payload = agent_cd.evaluate_issue_metadata_packet(packet)
        self.assertFalse(payload["allowed"])
        self.assertEqual(payload["violations"][0]["type_labels"], [])

    def test_develop_ready_empty_body_fails_closed(self) -> None:
        packet = self._issue_metadata_packet(
            [{"number": 139, "state": "open", "labels": ["type:develop-ready"], "body": ""}]
        )
        payload = agent_cd.evaluate_issue_metadata_packet(packet)
        self.assertFalse(payload["allowed"])
        self.assertIn("type:develop-ready issue body must not be empty", payload["violations"][0]["reasons"])

    def test_develop_ready_vague_body_with_only_comments_fails_closed(self) -> None:
        packet = self._issue_metadata_packet(
            [
                {
                    "number": 139,
                    "state": "open",
                    "labels": [{"name": "type:develop-ready"}],
                    "body": "## Concrete problem\nTBD",
                    "comments": [{"body": self._valid_develop_ready_body()}],
                }
            ]
        )
        payload = agent_cd.evaluate_issue_metadata_packet(packet)
        self.assertFalse(payload["allowed"])
        reasons = payload["violations"][0]["reasons"]
        self.assertIn("type:develop-ready issue body requires concrete Concrete problem", reasons)
        self.assertIn("type:develop-ready issue body requires concrete Exact targets/surfaces", reasons)
        self.assertIn("type:develop-ready issue body requires concrete Validation commands", reasons)

    def test_issue_metadata_allows_valid_open_governance_issue_and_ignores_closed(self) -> None:
        packet = self._issue_metadata_packet(
            [
                {
                    "number": 141,
                    "state": "open",
                    "labels": ["type:develop-ready"],
                    "body": self._valid_develop_ready_body(),
                },
                {"number": 142, "state": "closed", "labels": [], "body": ""},
            ]
        )
        payload = agent_cd.evaluate_issue_metadata_packet(packet)
        self.assertTrue(payload["allowed"], payload)
        self.assertEqual(payload["checked_open_issues"], 1)

    def test_agent_pickup_requires_develop_ready_body_fields(self) -> None:
        packet = self._valid_agent_pickup_packet()
        packet["body"] = "## Concrete problem\nTBD"
        packet["comments"] = [{"body": self._valid_develop_ready_body()}]
        payload = agent_cd.evaluate_agent_pickup_packet(packet, dry_run_invoked=True)
        self.assertFalse(payload["allowed"])
        self.assertIn("type:develop-ready issue body requires concrete Concrete problem", payload["reasons"])
        self.assertIn("type:develop-ready issue body requires concrete Safety boundary", payload["reasons"])

    def test_verify_issue_metadata_command_reports_blocked_packet(self) -> None:
        packet = self._issue_metadata_packet([{"number": 134, "state": "open", "labels": [], "body": ""}])
        with tempfile.TemporaryDirectory() as tmpdir:
            packet_path = Path(tmpdir) / "issue-packet.json"
            packet_path.write_text(json.dumps(packet), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "verify-issue-metadata", "--issue-packet", str(packet_path)],
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("#134", result.stderr)

    def test_validate_catalog_fails_when_issue_type_policy_drifts(self) -> None:
        broken_catalog = deepcopy(self.catalog)
        broken_catalog["issue_type_policy"]["agent_pickup"]["blocked_labels"].remove("secret")
        errors = agent_cd.validate_catalog(broken_catalog, role_catalog=self.role_catalog, check_files=False)
        self.assertTrue(
            any("issue_type_policy.agent_pickup must be" in error and "secret" in error for error in errors),
            errors,
        )

    def test_validate_catalog_fails_when_merge_eligibility_guards_missing(self) -> None:
        broken_catalog = deepcopy(self.catalog)
        del broken_catalog["merge_authority_policy"]["merge_eligibility_guards"]
        errors = agent_cd.validate_catalog(broken_catalog, role_catalog=self.role_catalog, check_files=False)
        self.assertTrue(
            any("merge_authority_policy.merge_eligibility_guards must be" in error for error in errors),
            errors,
        )

    def test_validate_workflow_is_operator_only_and_defers_fast_tests_to_local_commit_hooks(self) -> None:
        workflow = yaml.safe_load((PLUGIN_ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8"))
        on_data = workflow.get("on") or workflow.get(True)
        self.assertEqual(set(on_data), {"workflow_dispatch"})
        self.assertIn("emergency_full_suite", on_data["workflow_dispatch"]["inputs"])
        self.assertNotIn("pull_request", on_data)
        self.assertNotIn("merge_group", on_data)
        self.assertNotIn("push", on_data)
        self.assertNotIn("plugin-validation", workflow["jobs"])
        self.assertEqual(sorted(workflow["jobs"]["ci-summary"]["needs"]), sorted(job for job in agent_cd.REQUIRED_PARALLEL_CI_JOBS if job != "ci-summary"))
        self.assertNotIn("unit-fast", workflow["jobs"])
        self.assertNotIn("dev-cd-gate", workflow["jobs"])
        workflow_run = "\n".join(
            str(step.get("run", ""))
            for job in workflow["jobs"].values()
            if isinstance(job, dict)
            for step in job.get("steps", [])
            if isinstance(step, dict)
        )
        self.assertIn("classify-task", workflow_run)
        self.assertIn("verify-scenario-policy", workflow_run)
        self.assertIn("classify-mode", workflow_run)
        self.assertIn("verify-live-topology", workflow_run)
        self.assertIn("BEARS_GOAL_ID", workflow_run)
        self.assertIn("BEARS_DEVELOPMENT_SCENARIO", workflow_run)
        self.assertIn("python3 scripts/test_selection.py validate", workflow_run)
        self.assertIn("python3 scripts/test_selection.py run --suite full --tier full", workflow_run)
        self.assertNotIn("python3 -m pytest -q tests", workflow_run)
        self.assertNotIn("python3 -m unittest discover -s tests", workflow_run)

    def test_validate_catalog_fails_when_pull_request_trigger_is_added(self) -> None:
        broken_catalog = deepcopy(self.catalog)
        with tempfile.TemporaryDirectory() as tmpdir:
            workflow_path = Path(tmpdir) / "validate.yml"
            workflow_path.write_text(
                """name: validate
'on':
  pull_request:
    branches:
      - main
      - dev
      - goal/**
  push:
    branches:
      - '**'
jobs:
  changes:
    runs-on: ubuntu-latest
    steps:
      - run: python3 scripts/ci_requirements.py validate-workflow
  schema-catalog-validation:
    runs-on: ubuntu-latest
    steps:
      - run: python3 scripts/platform_roles.py validate
  hook-policy-validation:
    runs-on: ubuntu-latest
    steps:
      - run: echo ok
  role-workflow-validation:
    runs-on: ubuntu-latest
    steps:
      - run: |
          python3 scripts/platform_roles.py validate
          python3 scripts/validate_overlay.py --json validate --strict-overlay-skills
          python3 scripts/test_selection.py validate
          python3 scripts/test_selection.py run
          python3 scripts/agent_github_dev_cd.py classify-task
          python3 scripts/agent_github_dev_cd.py verify-scenario-policy
          python3 scripts/agent_github_dev_cd.py classify-mode
          python3 scripts/agent_github_dev_cd.py verify-live-topology
          BEARS_GOAL_ID=demo
          BEARS_DEVELOPMENT_SCENARIO=goal
  skill-inventory-validation:
    runs-on: ubuntu-latest
    steps:
      - run: echo ok
  unit-fast:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        shard: [0, 1, 2, 3]
    steps:
      - run: python3 scripts/test_selection.py run --shard-index 0 --shard-total 4 --tier fast
  dirty-boundary-validation:
    runs-on: ubuntu-latest
    steps:
      - run: echo ok
  ci-summary:
    needs: [changes, dirty-boundary-validation, hook-policy-validation, role-workflow-validation, schema-catalog-validation, skill-inventory-validation, unit-fast]
    runs-on: ubuntu-latest
    steps:
      - run: echo ok
""",
                encoding="utf-8",
            )
            broken_catalog["route_target"] = str(workflow_path)
            broken_catalog["ci_policy"]["validation_workflow"] = str(workflow_path)
            broken_catalog["cd_policy"]["dev_cd_validation_workflow"] = str(workflow_path)
            errors = agent_cd.validate_catalog(broken_catalog, role_catalog=self.role_catalog, check_files=True, strict_route=False)
        self.assertIn("validate workflow must not include pull_request or merge_group in main-only delivery", errors)

    def test_validate_catalog_fails_when_github_push_trigger_is_added(self) -> None:
        broken_catalog = deepcopy(self.catalog)
        with tempfile.TemporaryDirectory() as tmpdir:
            workflow_path = Path(tmpdir) / "validate.yml"
            text = (PLUGIN_ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")
            workflow_path.write_text(text.replace("'on':\n  workflow_dispatch:", "'on':\n  push:\n    branches:\n      - main\n  workflow_dispatch:"), encoding="utf-8")
            broken_catalog["route_target"] = str(workflow_path)
            broken_catalog["ci_policy"]["validation_workflow"] = str(workflow_path)
            broken_catalog["cd_policy"]["dev_cd_validation_workflow"] = str(workflow_path)
            errors = agent_cd.validate_catalog(broken_catalog, role_catalog=self.role_catalog, check_files=True, strict_route=False)
        self.assertIn(
            "validate workflow must expose only operator workflow_dispatch; local commit hooks own automatic tests",
            errors,
        )

    def test_validate_catalog_fails_when_branch_dev_cd_gate_is_added(self) -> None:
        broken_catalog = deepcopy(self.catalog)
        with tempfile.TemporaryDirectory() as tmpdir:
            workflow_path = Path(tmpdir) / "validate.yml"
            text = (PLUGIN_ROOT / ".github/workflows/validate.yml").read_text(encoding="utf-8")
            workflow_path.write_text(
                text + "\n  dev-cd-gate:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo forbidden\n",
                encoding="utf-8",
            )
            broken_catalog["route_target"] = str(workflow_path)
            broken_catalog["ci_policy"]["validation_workflow"] = str(workflow_path)
            broken_catalog["cd_policy"]["dev_cd_validation_workflow"] = str(workflow_path)
            errors = agent_cd.validate_catalog(broken_catalog, role_catalog=self.role_catalog, check_files=True, strict_route=False)
        self.assertIn(
            "validate workflow must not define jobs.dev-cd-gate in main-only delivery",
            errors,
        )

    def test_validate_catalog_fails_when_evidence_path_contract_drifts(self) -> None:
        broken_catalog = deepcopy(self.catalog)
        broken_catalog["cd_policy"]["dispatch_plan_contract"]["evidence_path_contract"]["repo_evidence_dir"] = "docs/evidence"
        errors = agent_cd.validate_catalog(broken_catalog, role_catalog=self.role_catalog, check_files=False)
        self.assertIn(
            "cd_policy.dispatch_plan_contract.evidence_path_contract must match the deterministic evidence path contract",
            errors,
        )

    def test_reference_doc_names_deprecated_dev_cd_drift_guard(self) -> None:
        text = (PLUGIN_ROOT / "docs/reference/agent-github-dev-cd.md").read_text(encoding="utf-8")
        self.assertIn("deprecated_reference_only", text)
        self.assertIn("main-only", text)
        self.assertIn("jobs.dev-cd-gate", text)
        self.assertIn("commit trailer", text)
        self.assertIn("artifacts/dev-cd-dispatch-gate.json", text)
        self.assertIn("docs/evidence/dev-cd/", text)
        self.assertIn("/srv/bears/kubernetes", text)
        self.assertIn("referenced evidence files are absent", text)
        self.assertIn("must not run `kubectl`, `helm`, or production deploy commands", text)
        self.assertIn("type:develop-ready", text)
        self.assertIn("verify-agent-pickup", text)
        self.assertIn("duplicate guard", text)
        self.assertIn(agent_cd.REQUIRED_PARENT_ACTIONS_DOC_LINE, text)
        self.assertIn(agent_cd.REQUIRED_FORBIDDEN_ACTIONS_DOC_LINE, text)
        for drifted_action in agent_cd.DRIFTED_PARENT_AGENT_ACTIONS:
            self.assertNotIn(drifted_action, text)

    def test_workflow_contract_contains_issue_type_flow(self) -> None:
        workflow = yaml.safe_load((PLUGIN_ROOT / "workflows/agent-github-dev-cd/workflow.yml").read_text(encoding="utf-8"))
        issue_type_flow = workflow["issue_type_flow"]
        self.assertEqual(issue_type_flow["policy"], agent_cd.REQUIRED_ISSUE_TYPE_POLICY)
        self.assertEqual(issue_type_flow["verify_command"], agent_cd.AGENT_PICKUP_VERIFY_COMMAND)
        self.assertEqual(issue_type_flow["metadata_verify_command"], agent_cd.ISSUE_METADATA_VERIFY_COMMAND)
        step_map = {step["id"]: step for step in workflow["steps"] if isinstance(step, dict) and step.get("id")}
        self.assertEqual(step_map["issue-metadata-gate"]["action"], "verify-issue-metadata")
        self.assertEqual(step_map["issue-metadata-gate"]["command"], agent_cd.ISSUE_METADATA_VERIFY_COMMAND)
        self.assertEqual(step_map["agent-pickup-gate"]["action"], "verify-agent-pickup")
        self.assertEqual(step_map["agent-pickup-gate"]["command"], agent_cd.AGENT_PICKUP_VERIFY_COMMAND)
        self.assertIn("duplicate_guard", step_map["agent-pickup-gate"]["requires"])

    def test_commit_evidence_requires_repo_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            workflow_state_path = repo_root / "docs/evidence/dev-cd/state/workflow-state.json"
            merge_authority_state_path = repo_root / "docs/evidence/dev-cd/state/merge-authority-state.json"
            runtime_path = repo_root / "docs/evidence/dev-cd/runtime/runtime.json"
            rollback_path = repo_root / "docs/evidence/dev-cd/rollback/rollback.md"
            workflow_state_path.parent.mkdir(parents=True, exist_ok=True)
            runtime_path.parent.mkdir(parents=True, exist_ok=True)
            rollback_path.parent.mkdir(parents=True, exist_ok=True)
            workflow_state_path.write_text("ok\n", encoding="utf-8")
            merge_authority_state_path.write_text("ok\n", encoding="utf-8")
            runtime_path.write_text("{}\n", encoding="utf-8")
            rollback_path.write_text("rollback\n", encoding="utf-8")
            trailers = {
                "Goal-Id": "demo",
                "Workflow-State": "docs/evidence/dev-cd/state/workflow-state.json",
                "Merge-Authority-State": "docs/evidence/dev-cd/state/merge-authority-state.json",
                "Runtime-Evidence": "docs/evidence/dev-cd/runtime/runtime.json",
                "Rollback-Note": "docs/evidence/dev-cd/rollback/rollback.md",
                "Kubernetes-Dispatch-Plan": "artifacts/dev-cd-dispatch-gate.json",
                "Production-Deploy": "false",
            }
            errors = agent_cd._validate_commit_evidence(
                trailers,
                repo_root=repo_root,
                dispatch_artifact="artifacts/dev-cd-dispatch-gate.json",
                require_dispatch_file=False,
            )
        self.assertEqual(errors, [])

    def test_commit_evidence_fails_when_repo_file_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            workflow_state_path = repo_root / "docs/evidence/dev-cd/state/workflow-state.json"
            merge_authority_state_path = repo_root / "docs/evidence/dev-cd/state/merge-authority-state.json"
            runtime_path = repo_root / "docs/evidence/dev-cd/runtime/runtime.json"
            workflow_state_path.parent.mkdir(parents=True, exist_ok=True)
            runtime_path.parent.mkdir(parents=True, exist_ok=True)
            workflow_state_path.write_text("ok\n", encoding="utf-8")
            merge_authority_state_path.write_text("ok\n", encoding="utf-8")
            runtime_path.write_text("{}\n", encoding="utf-8")
            trailers = {
                "Goal-Id": "demo",
                "Workflow-State": "docs/evidence/dev-cd/state/workflow-state.json",
                "Merge-Authority-State": "docs/evidence/dev-cd/state/merge-authority-state.json",
                "Runtime-Evidence": "docs/evidence/dev-cd/runtime/runtime.json",
                "Rollback-Note": "docs/evidence/dev-cd/rollback/missing.md",
                "Kubernetes-Dispatch-Plan": "artifacts/dev-cd-dispatch-gate.json",
                "Production-Deploy": "false",
            }
            errors = agent_cd._validate_commit_evidence(
                trailers,
                repo_root=repo_root,
                dispatch_artifact="artifacts/dev-cd-dispatch-gate.json",
                require_dispatch_file=False,
            )
        self.assertIn(
            "commit trailer Rollback-Note references a missing file: docs/evidence/dev-cd/rollback/missing.md",
            errors,
        )

    def test_validate_catalog_fails_when_parent_actions_use_drifted_tokens(self) -> None:
        broken_catalog = deepcopy(self.catalog)
        broken_catalog["parent_agent_policy"]["parent_actions"] = [
            "route",
            "split",
            "assign",
            "wait_for_subagent_evidence",
            "integrate_subagent_evidence",
            "run_validators",
            "close_subagents",
            "report",
        ]
        errors = agent_cd.validate_catalog(broken_catalog, role_catalog=self.role_catalog, check_files=False)
        self.assertIn(
            "parent_agent_policy.parent_actions must match the canonical orchestration token list",
            errors,
        )
        self.assertIn(
            "parent_agent_policy.parent_actions contains drifted tokens: close_subagents, integrate_subagent_evidence, wait_for_subagent_evidence",
            errors,
        )

    def test_validate_catalog_fails_when_forbidden_tokens_drift(self) -> None:
        broken_catalog = deepcopy(self.catalog)
        broken_catalog["parent_agent_policy"]["forbidden_actions"] = [
            "file_read_as_content_collector",
            "file_write",
            "git_commit",
            "git_push",
            "pull_request_mutation",
            "implementation_tool_use",
        ]
        errors = agent_cd.validate_catalog(broken_catalog, role_catalog=self.role_catalog, check_files=False)
        self.assertIn(
            "parent_agent_policy.forbidden_actions must match the canonical forbidden token list",
            errors,
        )

    def test_validate_catalog_fails_when_reference_doc_uses_drifted_tokens(self) -> None:
        broken_catalog = deepcopy(self.catalog)
        with tempfile.TemporaryDirectory() as tmpdir:
            doc_path = Path(tmpdir) / "agent-github-dev-cd.md"
            text = (PLUGIN_ROOT / "docs/reference/agent-github-dev-cd.md").read_text(encoding="utf-8")
            text = text.replace("`wait`, `integrate_evidence`, `run_validators`, `close`, `report`, `pre_task_hook`.", "`wait_for_subagent_evidence`, `integrate_subagent_evidence`, `run_validators`, `close_subagents`, `report`.")
            text = text.replace("`file_read_as_content_collector`, `file_write`, `git_add`, `git_commit`, `git_push`, `pull_request_mutation`, or `implementation_tool_use`.", "`file_read_as_content_collector`, `file_write`, `git_commit`, `git_push`, `pull_request_mutation`, or `implementation_tool_use`.")
            doc_path.write_text(text, encoding="utf-8")
            broken_catalog["reference_doc"] = str(doc_path)
            errors = agent_cd.validate_catalog(broken_catalog, role_catalog=self.role_catalog, check_files=True)
        self.assertIn("reference doc must list the canonical allowed parent action tokens", errors)
        self.assertIn("reference doc must list the canonical forbidden parent action tokens", errors)
        self.assertIn(
            "reference doc must not contain drifted parent action token: wait_for_subagent_evidence",
            errors,
        )


    def test_catalog_defines_sequential_and_parallel_workflow_modes(self) -> None:
        self.assertEqual(self.catalog["workflow_modes"], agent_cd.REQUIRED_WORKFLOW_MODE_RULES)
        for field in (
            "development_scenario",
            "scenario_policy_status",
            "agent_current_runtime",
            "scenario_auto_merge_to_main_allowed",
            "workflow_mode",
            "mode_classification_status",
            "topology_evidence_path",
            "stacked_branches_allowed",
            "mode_transition_recorded",
        ):
            self.assertIn(field, self.catalog["output_contract"]["top_level_required"])
            self.assertIn(field, self.catalog["cd_policy"]["dispatch_plan_contract"]["required_plan_fields"])

    def test_workflow_file_contains_sequential_and_parallel_steps(self) -> None:
        workflow = yaml.safe_load((PLUGIN_ROOT / "workflows/agent-github-dev-cd/workflow.yml").read_text(encoding="utf-8"))
        self.assertEqual(workflow["workflow_modes"], agent_cd.REQUIRED_WORKFLOW_MODE_RULES)
        self.assertEqual(workflow["scenario_policy"], agent_cd.REQUIRED_SCENARIO_POLICY)
        self.assertEqual(workflow["inputs"]["development_scenario"]["allowed"], list(agent_cd.DEVELOPMENT_SCENARIOS))
        self.assertEqual(workflow["sequential_steps"], agent_cd.REQUIRED_WORKFLOW_MODE_SEQUENTIAL_STEPS)
        self.assertEqual(workflow["parallel_steps"], agent_cd.REQUIRED_WORKFLOW_MODE_PARALLEL_STEPS)
        self.assertLess(workflow["parallel_steps"].index("classify-task"), workflow["parallel_steps"].index("classify-mode"))
        self.assertLess(
            workflow["parallel_steps"].index("verify-scenario-policy"),
            workflow["parallel_steps"].index("branch-enforcement"),
        )
        self.assertLess(workflow["parallel_steps"].index("classify-mode"), workflow["parallel_steps"].index("branch-enforcement"))
        self.assertLess(workflow["parallel_steps"].index("branch-enforcement"), workflow["parallel_steps"].index("main-only-delivery"))
        self.assertNotIn("auto-merge-dev", workflow["parallel_steps"])
        self.assertNotIn("dev-cd-gate", workflow["parallel_steps"])
        self.assertNotIn("cd-dev", workflow["parallel_steps"])
        step_map = {step["id"]: step for step in workflow["steps"] if isinstance(step, dict) and step.get("id")}
        self.assertEqual(step_map["classify-task"]["command"], agent_cd.TASK_CLASSIFICATION_COMMAND)
        self.assertEqual(step_map["verify-scenario-policy"]["command"], agent_cd.SCENARIO_POLICY_VERIFY_COMMAND)
        self.assertIn("--development-scenario <development-scenario>", step_map["classify-mode"]["command"])
        self.assertIn("--development-scenario <development-scenario>", step_map["verify-live-topology"]["command"])
        self.assertEqual(step_map["main-only-delivery"]["action"], "reference-main-only-delivery-policy")
        self.assertEqual(
            step_map["main-only-delivery"]["authority"],
            "assets/catalog/agentic-enterprise-workflow.v1.json delivery_policy",
        )
        self.assertNotIn("auto-merge-dev", step_map)
        self.assertNotIn("dev-cd-gate", step_map)
        self.assertNotIn("cd-dev", step_map)

    def test_cli_parser_has_mode_commands(self) -> None:
        parser = agent_cd.build_parser()
        task = parser.parse_args(["classify-task", "--prompt-file", "prompt.txt"])
        scenario = parser.parse_args(["verify-scenario-policy", "--packet", "packet.json"])
        dev_auto_merge = parser.parse_args([
            "verify-dev-auto-merge",
            "--packet",
            "packet.json",
            "--expected-repository",
            "BearsCLOUD/bears_plugin",
            "--expected-pr-number",
            "132",
            "--expected-head-ref",
            "goal/demo",
            "--expected-head-sha",
            "1234567890abcdef1234567890abcdef12345678",
            "--expected-base-ref",
            "dev",
        ])
        classify = parser.parse_args(["classify-mode", "--goal-id", "demo", "--declared-mode", "auto"])
        verify = parser.parse_args(["verify-live-topology", "--goal-id", "demo", "--expected-mode", "sequential"])
        merge = parser.parse_args([
            "merge-authority-check",
            "--packet", "packet.json",
            "--expected-repository", "BearsCLOUD/bears_plugin",
            "--expected-pr-number", "132",
            "--expected-head-ref", "codex/merge-authority-lane",
            "--expected-head-sha", "1234567890abcdef1234567890abcdef12345678",
            "--expected-base-ref", "main",
        ])
        self.assertEqual(task.command, "classify-task")
        self.assertEqual(scenario.command, "verify-scenario-policy")
        self.assertEqual(dev_auto_merge.command, "verify-dev-auto-merge")
        self.assertEqual(dev_auto_merge.expected_base_ref, "dev")
        self.assertEqual(classify.command, "classify-mode")
        self.assertEqual(verify.command, "verify-live-topology")
        self.assertEqual(merge.command, "merge-authority-check")
        self.assertEqual(merge.expected_pr_number, 132)

    def test_cli_parser_requires_merge_authority_expected_args(self) -> None:
        parser = agent_cd.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["merge-authority-check", "--packet", "packet.json"])

    def _write_topology(self, tmpdir: str, payload: dict[str, object]) -> Path:
        path = Path(tmpdir) / "topology.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_sequential_goal_to_dev_passes_without_agent_branches(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            topology = self._write_topology(tmpdir, {
                "goal_id": "demo",
                "current_branch": "goal/demo",
                "refs": ["main", "dev", "goal/demo"],
                "branch_bases": {"goal/demo": "dev"},
            })
            payload = agent_cd.classify_mode(goal_id="demo", declared_mode="sequential", repo_root=PLUGIN_ROOT, topology_file=topology)
        self.assertTrue(payload["topology_valid"], payload)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["active_agent_branch_count"], 0)

    def test_sequential_fails_with_unapproved_stacked_branches(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            topology = self._write_topology(tmpdir, {
                "goal_id": "demo",
                "current_branch": "goal/demo",
                "refs": ["main", "dev", "goal/demo", "codex/one", "codex/two"],
                "branch_bases": {"goal/demo": "dev", "codex/two": "codex/one", "codex/one": "goal/demo"},
                "stacked_branches": ["codex/one", "codex/two"],
            })
            payload = agent_cd.classify_mode(goal_id="demo", declared_mode="sequential", repo_root=PLUGIN_ROOT, topology_file=topology)
        self.assertFalse(payload["topology_valid"])
        self.assertIn("sequential mode has unapproved stacked branches", payload["reasons"])

    def test_parallel_passes_with_agent_to_goal_to_dev(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            topology = self._write_topology(tmpdir, {
                "goal_id": "demo",
                "current_branch": "agent/demo/deploy/slice-a",
                "refs": ["main", "dev", "goal/demo", "agent/demo/deploy/slice-a"],
                "branch_bases": {"agent/demo/deploy/slice-a": "goal/demo", "goal/demo": "dev"},
            })
            payload = agent_cd.classify_mode(goal_id="demo", declared_mode="parallel", repo_root=PLUGIN_ROOT, topology_file=topology)
        self.assertTrue(payload["topology_valid"], payload)
        self.assertEqual(payload["detected_mode"], "parallel")

    def test_parallel_fails_without_agent_branches(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            topology = self._write_topology(tmpdir, {
                "goal_id": "demo",
                "current_branch": "goal/demo",
                "refs": ["main", "dev", "goal/demo"],
                "branch_bases": {"goal/demo": "dev"},
            })
            payload = agent_cd.classify_mode(goal_id="demo", declared_mode="parallel", repo_root=PLUGIN_ROOT, topology_file=topology)
        self.assertFalse(payload["topology_valid"])
        self.assertIn("parallel mode is missing agent branches", payload["reasons"])

    def test_direct_main_target_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            topology = self._write_topology(tmpdir, {
                "goal_id": "demo",
                "current_branch": "goal/demo",
                "refs": ["main", "dev", "goal/demo"],
                "branch_bases": {"goal/demo": "main"},
            })
            payload = agent_cd.classify_mode(goal_id="demo", declared_mode="sequential", repo_root=PLUGIN_ROOT, topology_file=topology)
        self.assertFalse(payload["topology_valid"])
        self.assertTrue(any("main is not an allowed" in reason for reason in payload["reasons"]))

    def test_mixed_topology_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            topology = self._write_topology(tmpdir, {
                "goal_id": "demo",
                "current_branch": "agent/demo/deploy/slice-a",
                "refs": ["main", "dev", "goal/demo", "agent/demo/deploy/slice-a", "codex/stacked"],
                "branch_bases": {"agent/demo/deploy/slice-a": "goal/demo", "codex/stacked": "goal/demo", "goal/demo": "dev"},
                "stacked_branches": ["codex/stacked"],
            })
            payload = agent_cd.classify_mode(goal_id="demo", declared_mode="sequential", repo_root=PLUGIN_ROOT, topology_file=topology)
        self.assertFalse(payload["topology_valid"])
        self.assertEqual(payload["detected_mode"], "invalid_mixed_topology")

    def test_verify_live_topology_uses_goal_id_commit_trailer_on_dev_push(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
            (repo / "README.md").write_text("ok\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "merge\n\nGoal-Id: demo\n"], cwd=repo, check=True, stdout=subprocess.PIPE)
            sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
            topology = self._write_topology(tmpdir, {
                "current_branch": "dev",
                "refs": ["main", "dev", "goal/demo"],
                "branch_bases": {"goal/demo": "dev"},
            })
            args = agent_cd.build_parser().parse_args([
                "verify-live-topology",
                "--commit-sha", sha,
                "--repo-root", str(repo),
                "--topology-file", str(topology),
                "--expected-mode", "sequential",
            ])
            self.assertEqual(agent_cd.cmd_verify_live_topology(args), 0)

    def test_sequential_fails_with_unapproved_agent_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            topology = self._write_topology(tmpdir, {
                "goal_id": "demo",
                "current_branch": "goal/demo",
                "refs": ["main", "dev", "goal/demo", "agent/demo/deploy/slice-a"],
                "branch_bases": {"goal/demo": "dev", "agent/demo/deploy/slice-a": "goal/demo"},
            })
            payload = agent_cd.classify_mode(goal_id="demo", declared_mode="sequential", repo_root=PLUGIN_ROOT, topology_file=topology)
        self.assertFalse(payload["topology_valid"])
        self.assertIn("sequential mode has unapproved agent branches", payload["reasons"])

    def test_dispatch_plan_includes_workflow_mode_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
            for rel, body in {
                "docs/evidence/dev-cd/state/workflow-state.json": "ok\n",
                "docs/evidence/dev-cd/runtime/runtime.json": "{}\n",
                "docs/evidence/dev-cd/rollback/rollback.md": "rollback\n",
            }.items():
                path = repo / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(body, encoding="utf-8")
            (repo / "README.md").write_text("ok\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            message = "test commit\n\nGoal-Id: demo\nWorkflow-State: docs/evidence/dev-cd/state/workflow-state.json\nMerge-Authority-State: docs/evidence/dev-cd/state/workflow-state.json\nRuntime-Evidence: docs/evidence/dev-cd/runtime/runtime.json\nRollback-Note: docs/evidence/dev-cd/rollback/rollback.md\nKubernetes-Dispatch-Plan: artifacts/dev-cd-dispatch-gate.json\nProduction-Deploy: false\n"
            subprocess.run(["git", "commit", "-m", message], cwd=repo, check=True, stdout=subprocess.PIPE)
            sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
            topology = self._write_topology(tmpdir, {
                "goal_id": "demo",
                "current_branch": "goal/demo",
                "refs": ["main", "dev", "goal/demo"],
                "branch_bases": {"goal/demo": "dev"},
            })
            args = agent_cd.build_parser().parse_args([
                "write-dispatch-plan",
                "--commit-sha", sha,
                "--repo-root", str(repo),
                "--goal-id", "demo",
                "--declared-mode", "sequential",
                "--topology-file", str(topology),
            ])
            self.assertEqual(agent_cd.cmd_write_dispatch_plan(args), 0)
            payload = json.loads((repo / "artifacts/dev-cd-dispatch-gate.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["workflow_mode"], "sequential")
        self.assertEqual(payload["mode_classification_status"], "ok")
        self.assertIn("topology_evidence_path", payload)
        self.assertFalse(payload["stacked_branches_allowed"])
        self.assertFalse(payload["mode_transition_recorded"])
        self.assertEqual(payload["development_scenario"], "dev")
        self.assertEqual(payload["scenario_policy_status"], "pass")
        self.assertEqual(payload["agent_current_runtime"], "/srv/bears")
        self.assertFalse(payload["scenario_auto_merge_to_main_allowed"])

    def test_lint_command_snippet_blocks_unsupported_gh_and_stdin_heredoc(self) -> None:
        command = "gh pr diff 126 --repo BearsCLOUD/bears-codex-workspace --name-status | python3 - <<'PY'\nprint('ok')\nPY"

        payload = agent_cd.lint_command_snippet(command, expected_input=True)

        self.assertEqual(payload["status"], "COMMAND_SNIPPET_BLOCKED")
        self.assertIn("GH_PR_DIFF_UNSUPPORTED_NAME_STATUS", payload["reasons"])
        self.assertIn("STDIN_SWALLOWING_HEREDOC", payload["reasons"])

    def test_lint_command_snippet_blocks_unauthenticated_github_and_bad_content_ref(self) -> None:
        command = (
            "python3 - <<'PY'\nimport urllib.request\nurllib.request.urlopen('https://api.github.com/repos/BearsCLOUD/private/pulls/1')\nPY\n"
            "gh api repos/BearsCLOUD/repo/contents/docs/file.md -f ref=abc123"
        )

        payload = agent_cd.lint_command_snippet(command)

        self.assertIn("AUTH_METHOD_INVALID", payload["reasons"])
        self.assertIn("GH_API_CONTENTS_REF_FLAG_UNSUPPORTED", payload["reasons"])

    def test_lint_command_snippet_blocks_soft_rc_and_unsafe_headings(self) -> None:
        command = "printf '--- checks ---\\n'; gh pr checks 152 --repo BearsCLOUD/bears-codex-workspace || true; rc=$?; echo EXIT:$rc"

        payload = agent_cd.lint_command_snippet(command)

        self.assertIn("UNSAFE_PRINTF_HEADING", payload["reasons"])
        self.assertIn("GATE_COMMAND_SOFTENED_WITH_OR_TRUE", payload["reasons"])
        self.assertIn("NONZERO_RC_NOT_PROPAGATED", payload["reasons"])

    def test_lint_command_snippet_blocks_validator_shape_drift(self) -> None:
        command = "python3 -m py_compile scripts/preflight-nonprod.sh && python3 scripts/platform_roles.py route/audit scripts/git_discipline.py"

        payload = agent_cd.lint_command_snippet(command)

        self.assertEqual(payload["status"], "COMMAND_SNIPPET_BLOCKED")
        self.assertIn("COMMAND_SHAPE_DRIFT", payload["reasons"])

    def test_hygiene_gate_blocks_ci_manifest_paths_without_gate(self) -> None:
        packet = {
            "schema": agent_cd.HYGIENE_GATE_PACKET_SCHEMA,
            "changed_paths": [
                ".github/workflows/bears-platform-telegram-nonprod.yml",
                "manifests/bears-platform-telegram/preflight-nonprod.sh",
            ],
            "deploy_ci_gate": {"status": "not-applicable"},
        }

        payload = agent_cd.evaluate_hygiene_gate_packet(packet)

        self.assertEqual(payload["status"], "blocked")
        self.assertIn("deploy_ci_gate.status cannot be not-applicable for triggered paths", payload["reasons"])

    def test_final_verification_requires_fetch_then_verified_commit_then_exact_read(self) -> None:
        stale_packet = {
            "schema": agent_cd.FINAL_VERIFICATION_PACKET_SCHEMA,
            "verified_commit": "a" * 40,
            "steps": [
                {"name": "read_tasks", "reads_dependent_ref": True, "ref": "origin/main", "parallel_with_fetch": True},
                {"name": "fetch"},
                {"name": "verify_commit"},
            ],
        }

        payload = agent_cd.evaluate_final_verification_packet(stale_packet)

        self.assertEqual(payload["status"], "blocked")
        self.assertIn("dependent reads must run after verify_commit", payload["reasons"])
        self.assertIn("dependent reads cannot run in parallel with fetch", payload["reasons"])
        self.assertIn("dependent reads must use verified_commit, not moving ref", payload["reasons"])

    def test_pr_publication_blocks_invalid_title_commit_checks_and_hygiene_gate(self) -> None:
        packet = {
            "schema": agent_cd.PR_PUBLICATION_PACKET_SCHEMA,
            "action": "merge",
            "pr_title": "[codex] Add T110 role coverage routes",
            "commit_headline": "Add T110 role coverage routes",
            "branch_base_preflight": {"status": "BRANCH_BASE_PREFLIGHT_PASS"},
            "github_checks_gate": {"status": "FAIL_NO_CHECKS", "exit_code": 1},
            "hygiene_gate": {
                "schema": agent_cd.HYGIENE_GATE_PACKET_SCHEMA,
                "changed_paths": [".github/workflows/validate.yml"],
                "deploy_ci_gate": {"status": "not-applicable"},
            },
        }

        payload = agent_cd.evaluate_pr_publication_packet(packet)

        self.assertEqual(payload["status"], "blocked")
        self.assertTrue(any(reason.startswith("pr_title:title_contains_agent_marker") for reason in payload["reasons"]))
        self.assertTrue(any(reason.startswith("commit_headline:title_must_match") for reason in payload["reasons"]))
        self.assertIn("github_checks_gate blocks publication", payload["reasons"])
        self.assertTrue(any(reason.startswith("hygiene_gate:") for reason in payload["reasons"]))

    def test_merge_authority_blocks_invalid_title_and_commit_headline(self) -> None:
        packet = self._valid_merge_authority_packet()
        packet["title_policy"]["title"] = "[codex] docs(kube): add packet"
        packet["title_policy"]["commit_headline"] = "Add packet"

        payload = agent_cd.evaluate_merge_authority_packet(
            packet,
            expected=self._valid_merge_authority_expected(),
        )

        self.assertFalse(payload["allowed"])
        self.assertIn("title_policy:title_contains_agent_marker", payload["reasons"])
        self.assertIn("commit_policy:title_must_match_conventional_type_scope", payload["reasons"])

    def test_cli_validate(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "validate"],
            cwd=PLUGIN_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("agent github dev cd catalog ok", result.stdout)


if __name__ == "__main__":
    unittest.main()
