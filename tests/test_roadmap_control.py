from __future__ import annotations

import copy
import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PLUGIN_ROOT / "scripts" / "roadmap_control.py"
spec = importlib.util.spec_from_file_location("roadmap_control", SCRIPT_PATH)
roadmap_module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(roadmap_module)  # type: ignore[arg-type]


class RoadmapControlTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = roadmap_module.load_json(PLUGIN_ROOT / "assets" / "catalog" / "roadmap-control.v1.json")
        cls.role_catalog = roadmap_module.load_json(PLUGIN_ROOT / "assets" / "catalog" / "platform-role-catalog.v1.json")
        cls.subagent_policy = roadmap_module.load_json(PLUGIN_ROOT / "assets" / "catalog" / "subagent-orchestration-policy.v1.json")

    def validate(self, catalog: dict) -> list[str]:
        return roadmap_module.validate_catalog(catalog, self.role_catalog, self.subagent_policy)

    def test_current_catalog_validates(self) -> None:
        self.assertEqual(self.validate(self.catalog), [])

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
        self.assertIn("roadmap control catalog ok", result.stdout)

    def test_cli_missing_catalog_has_stable_stderr(self) -> None:
        missing_catalog = PLUGIN_ROOT / "tmp-missing-roadmap-control.json"
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

    def test_requires_goal_entrypoint_only(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["entrypoint"]["required_command"] = "plans.md"
        catalog["entrypoint"]["roadmap_runs_only_through_goal"] = False
        errors = self.validate(catalog)
        self.assertTrue(any("required_command must be /goal" in error for error in errors))
        self.assertTrue(any("roadmap_runs_only_through_goal" in error for error in errors))

    def test_requires_goal_fields(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["entrypoint"]["required_goal_fields"].remove("goal_id")
        errors = self.validate(catalog)
        self.assertTrue(any("required_goal_fields missing fields: goal_id" in error for error in errors))

    def test_controls_multiple_specs_with_scope_locks(self) -> None:
        control = self.catalog["multi_spec_control"]
        self.assertTrue(control["enabled"])
        self.assertIn("spec_snapshot_digest", control["required_spec_fields"])
        self.assertIn("owner_worker_id", control["scope_lock_fields"])
        joined_rules = " ".join(rule["rule"] for rule in control["concurrency_rules"])
        self.assertIn("Multiple Spec Kit specs", joined_rules)
        self.assertIn("non-overlapping write scope locks", joined_rules)

    def test_rejects_removed_multi_spec_scope_lock_rule(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["multi_spec_control"]["scope_lock_fields"].remove("owner_worker_id")
        catalog["multi_spec_control"]["concurrency_rules"] = [
            rule for rule in catalog["multi_spec_control"]["concurrency_rules"] if rule["id"] != "multiple-specs-allowed-with-locks"
        ]
        errors = self.validate(catalog)
        self.assertTrue(any("scope_lock_fields missing fields: owner_worker_id" in error for error in errors))
        self.assertTrue(any("Multiple Spec Kit specs" in error for error in errors))

    def test_pre_task_hook_requires_missing_data_and_drift_answers_before_spawn(self) -> None:
        hook = self.catalog["pre_task_hook"]
        self.assertTrue(hook["blocks_worker_spawn_until_answers"])
        self.assertEqual(set(hook["operator_answers_required_before_spawn"]), {"missing_data_answers", "drift_answers"})
        self.assertIn("operator_missing_data_answers", hook["required_evidence_fields"])
        self.assertIn("operator_drift_answers", hook["required_evidence_fields"])
        self.assertIn("missing_data_answers_absent", hook["spawn_blockers"])
        self.assertIn("drift_answers_absent", hook["spawn_blockers"])

    def test_rejects_weakened_pre_task_hook(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["pre_task_hook"]["blocks_worker_spawn_until_answers"] = False
        catalog["pre_task_hook"]["operator_answers_required_before_spawn"] = ["missing_data_answers"]
        errors = self.validate(catalog)
        self.assertTrue(any("blocks_worker_spawn_until_answers" in error for error in errors))
        self.assertTrue(any("drift_answers" in error for error in errors))

    def test_main_agent_uses_exact_orchestration_tokens(self) -> None:
        policy = self.catalog["main_agent_policy"]
        self.assertEqual(policy["mode"], "orchestration_only")
        self.assertEqual(policy["allowed_actions"], list(roadmap_module.EXPECTED_MAIN_AGENT_ALLOWED_ACTIONS))
        self.assertEqual(policy["forbidden_actions"], list(roadmap_module.EXPECTED_MAIN_AGENT_FORBIDDEN_ACTIONS))

    def test_rejects_drifted_prose_allowed_action(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["main_agent_policy"]["allowed_actions"][0] = "route and audit the target"
        errors = self.validate(catalog)
        self.assertTrue(any("missing required tokens: route" in error for error in errors))
        self.assertTrue(any("contains unexpected tokens: route and audit the target" in error for error in errors))

    def test_rejects_duplicate_allowed_action(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["main_agent_policy"]["allowed_actions"][2] = "route"
        errors = self.validate(catalog)
        self.assertTrue(any("missing required tokens: assign" in error for error in errors))
        self.assertTrue(any("contains duplicate tokens: route" in error for error in errors))

    def test_rejects_reordered_allowed_actions(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        allowed = catalog["main_agent_policy"]["allowed_actions"]
        allowed[0], allowed[1] = allowed[1], allowed[0]
        errors = self.validate(catalog)
        self.assertTrue(any("allowed_actions must match exact ordered tokens" in error for error in errors))

    def test_rejects_drifted_prose_forbidden_action(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["main_agent_policy"]["forbidden_actions"][0] = "direct implementation"
        errors = self.validate(catalog)
        self.assertTrue(any("missing required tokens: file_read_as_content_collector" in error for error in errors))
        self.assertTrue(any("contains unexpected tokens: direct implementation" in error for error in errors))

    def test_rejects_removed_orchestration_only_mode(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["main_agent_policy"]["mode"] = "implementation_allowed"
        errors = self.validate(catalog)
        self.assertTrue(any("mode must be orchestration_only" in error for error in errors))

    def test_limits_are_hard(self) -> None:
        self.assertEqual(self.catalog["limits"]["max_active_subagents"], 100)
        self.assertEqual(self.catalog["limits"]["max_depth"], 3)

    def test_rejects_changed_limits(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["limits"]["max_active_subagents"] = 101
        catalog["limits"]["max_depth"] = 4
        errors = self.validate(catalog)
        self.assertTrue(any("max_active_subagents must be 100" in error for error in errors))
        self.assertTrue(any("max_depth must be 3" in error for error in errors))

    def test_multiple_orchestrators_only_explicit_controller_roles(self) -> None:
        control = self.catalog["orchestrator_control"]
        self.assertTrue(control["multiple_orchestrators_allowed"])
        self.assertTrue(control["allowed_only_for_explicit_controller_roles"])
        self.assertEqual(set(control["explicit_controller_roles"]), roadmap_module.REQUIRED_EXPLICIT_CONTROLLER_ROLES)

    def test_rejects_non_controller_orchestrator_role(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["orchestrator_control"]["explicit_controller_roles"].append("bears-auth-platform-engineer")
        errors = self.validate(catalog)
        self.assertTrue(any("unknown in subagent policy" in error for error in errors))

    def test_audit_subagents_are_fresh_without_parent_context(self) -> None:
        audit = self.catalog["audit_policy"]
        self.assertTrue(audit["fresh_subagent_required_every_audit"])
        self.assertEqual(audit["context_policy"], "fresh_no_parent_context")
        self.assertEqual(audit["context_policy_rule"], "context_policy = fresh_no_parent_context")
        self.assertFalse(audit["parent_context_allowed"])
        self.assertFalse(audit["reuse_allowed"])
        self.assertFalse(audit["resume_allowed"])
        self.assertIn("context_policy=fresh_no_parent_context", audit["required_audit_fields"])
        self.assertIn("parent_context_allowed=false", audit["required_audit_fields"])

    def test_rejects_audit_reuse(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["audit_policy"]["reuse_allowed"] = True
        catalog["audit_policy"]["context_policy"] = "inherited_parent_context"
        catalog["audit_policy"]["required_audit_fields"].remove("parent_context_allowed=false")
        errors = self.validate(catalog)
        self.assertTrue(any("reuse_allowed must be false" in error for error in errors))
        self.assertTrue(any("context_policy must be fresh_no_parent_context" in error for error in errors))
        self.assertTrue(any("parent_context_allowed=false" in error for error in errors))

    def test_session_reuse_binds_goal_roadmap_spec_role_scope_repo_validation(self) -> None:
        reuse = self.catalog["session_reuse"]
        expected = {
            "goal_id",
            "roadmap_id",
            "roadmap_slice",
            "spec_snapshot_id",
            "spec_snapshot_digest",
            "lane",
            "role",
            "scope_fingerprint",
            "repo_state",
            "validation_target",
        }
        self.assertTrue(expected.issubset(set(reuse["required_binding_fields"])))
        self.assertIn("validation_target_compatible", reuse["compatibility_fields"])
        self.assertIn("Audit workers never reuse", reuse["rule"])

    def test_rejects_missing_session_reuse_binding(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["session_reuse"]["required_binding_fields"].remove("goal_id")
        catalog["session_reuse"]["compatibility_fields"].remove("validation_target_compatible")
        errors = self.validate(catalog)
        self.assertTrue(any("required_binding_fields missing fields: goal_id" in error for error in errors))
        self.assertTrue(any("compatibility_fields missing fields: validation_target_compatible" in error for error in errors))

    def test_records_concrete_roadmap_for_this_objective(self) -> None:
        roadmap = self.catalog["roadmap_for_this_objective"]
        self.assertEqual(roadmap["goal_id"], "goal-roadmap-control-surface-2026-06-06")
        phases = {phase["id"]: phase for phase in roadmap["phases"]}
        self.assertEqual(set(phases), roadmap_module.REQUIRED_PHASE_IDS)
        for phase_id, expected in roadmap_module.EXPECTED_PHASE_MAP.items():
            self.assertEqual(phases[phase_id]["lane"], expected["lane"])
            self.assertEqual(phases[phase_id]["role"], expected["role"])
            self.assertEqual(phases[phase_id]["scope"], expected["scope"])
        commands = {command for phase in phases.values() for command in phase["validation_commands"]}
        self.assertTrue(roadmap_module.REQUIRED_VALIDATION_COMMANDS.issubset(commands))

    def test_rejects_phase_lane_drift(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["roadmap_for_this_objective"]["phases"][0]["lane"] = "implementation"
        errors = self.validate(catalog)
        self.assertTrue(
            any("phases[phase-1-route-and-baseline].lane must be audit" in error for error in errors)
        )

    def test_rejects_phase_role_drift(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["roadmap_for_this_objective"]["phases"][1]["role"] = "bears-subagents-roles-governor"
        errors = self.validate(catalog)
        self.assertTrue(
            any(
                "phases[phase-2-catalog-and-validator].role must be bears-workflow-overlay-platform-engineer"
                in error
                for error in errors
            )
        )

    def test_rejects_phase_scope_drift(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["roadmap_for_this_objective"]["phases"][2]["scope"].append("README.md")
        errors = self.validate(catalog)
        self.assertTrue(
            any("phases[phase-3-tests-and-reference].scope must match exact expected scope" in error for error in errors)
        )

    def test_rejects_missing_objective_validation_command(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        for phase in catalog["roadmap_for_this_objective"]["phases"]:
            phase["validation_commands"] = [
                command for command in phase["validation_commands"] if command != "python3 scripts/roadmap_control.py validate"
            ]
        errors = self.validate(catalog)
        self.assertTrue(any("validation commands missing" in error for error in errors))

    def test_validation_section_names_required_commands(self) -> None:
        self.assertEqual(self.catalog["validation"]["validator"], "scripts/roadmap_control.py")
        self.assertEqual(set(self.catalog["validation"]["commands"]), roadmap_module.REQUIRED_VALIDATION_COMMANDS)

    def test_validation_commands_match_role_catalog_roadmap_control(self) -> None:
        route_required = roadmap_module._roadmap_control_required_validations(self.role_catalog)
        self.assertEqual(set(self.catalog["validation"]["commands"]), route_required)

    def test_rejects_missing_role_catalog_validation_command(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["validation"]["commands"].remove("python3 scripts/subagents_roles.py validate")
        errors = self.validate(catalog)
        self.assertTrue(
            any("validation.commands missing fields: python3 scripts/subagents_roles.py validate" in error for error in errors)
        )



    def test_issue20_research_contract_validates(self) -> None:
        self.assertEqual([], roadmap_module.validate_research_artifact_contract(self.catalog["research_artifact_contract"]))

    def test_issue20_operator_research_skip_validates(self) -> None:
        packet = self._issue22_design_packet()
        packet["research_artifacts"] = None
        packet["research_skip"] = {"type": "operator_skip", "approved_by": "operator", "approval_reference": "issue-20", "reason": "bounded override"}
        self.assertEqual([], roadmap_module.validate_implementation_packet(packet, self.catalog["design_artifact_contract"]))

    def test_issue20_narrow_exact_file_research_skip_validates(self) -> None:
        packet = self._issue22_design_packet()
        packet["research_artifacts"] = None
        packet["research_skip"] = {
            "type": "narrow_exact_file_skip",
            "exact_file_scope": "scripts/roadmap_control.py",
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
        self.assertEqual([], roadmap_module.validate_implementation_packet(packet, self.catalog["design_artifact_contract"]))

    def test_issue20_rejects_broad_workflow_packet_without_research(self) -> None:
        packet = self._issue22_design_packet()
        packet["research_artifacts"] = None
        errors = roadmap_module.validate_implementation_packet(packet, self.catalog["design_artifact_contract"])
        self.assertTrue(any("research_artifacts missing required artifacts" in error for error in errors))

    def test_issue20_rejects_missing_ux_research_for_cli_status_error_recovery(self) -> None:
        packet = self._issue22_design_packet()
        packet["cli_change"] = True
        packet["status_behavior_change"] = True
        packet["error_behavior_change"] = True
        packet["recovery_behavior_change"] = True
        packet["research_artifacts"].pop("ux_research")
        errors = roadmap_module.validate_implementation_packet(packet, self.catalog["design_artifact_contract"])
        self.assertTrue(any("ux_research missing required artifact" in error for error in errors))

    def test_issue20_rejects_unbounded_or_proprietary_research_claim(self) -> None:
        packet = self._issue22_design_packet()
        packet["research_artifacts"]["research"]["bounded_summary"] = False
        packet["research_artifacts"]["research"]["no_proprietary_copy"] = False
        errors = roadmap_module.validate_implementation_packet(packet, self.catalog["design_artifact_contract"])
        self.assertTrue(any("bounded_summary" in error for error in errors))
        self.assertTrue(any("no_proprietary_copy" in error for error in errors))

    def test_issue20_requires_sources_when_repository_research_used(self) -> None:
        packet = self._issue22_design_packet()
        packet["research_artifacts"]["prior_art"]["sources"] = []
        errors = roadmap_module.validate_implementation_packet(packet, self.catalog["design_artifact_contract"])
        self.assertTrue(any("sources are required" in error for error in errors))

    def test_issue22_design_contract_validates(self) -> None:
        self.assertEqual([], roadmap_module.validate_design_artifact_contract(self.catalog["design_artifact_contract"]))
        self.assertEqual("README.md#issue-22-design-artifact-contract", self.catalog["design_artifact_contract"]["artifact_path"])

    def test_issue22_required_design_packet_validates(self) -> None:
        packet = self._issue22_design_packet()
        self.assertEqual([], roadmap_module.validate_implementation_packet(packet, self.catalog["design_artifact_contract"]))

    def test_issue22_approved_skip_validates(self) -> None:
        packet = self._issue22_design_packet()
        packet["design_artifact"] = None
        packet["design_skip"] = {"type": "approved_skip", "approved_by": "operator", "approval_reference": "issue-22", "reason": "bounded override"}
        self.assertEqual([], roadmap_module.validate_implementation_packet(packet, self.catalog["design_artifact_contract"]))

    def test_issue22_narrow_bugfix_skip_validates(self) -> None:
        packet = self._issue22_design_packet()
        packet["design_artifact"] = None
        packet["design_skip"] = {
            "type": "narrow_bugfix_skip",
            "exact_file_scope": "scripts/roadmap_control.py",
            "no_boundary_change": True,
            "no_runtime_change": True,
            "no_deploy_change": True,
            "no_restricted_data_change": True,
            "no_public_behavior_change": True,
        }
        self.assertEqual([], roadmap_module.validate_implementation_packet(packet, self.catalog["design_artifact_contract"]))

    def test_issue22_rejects_missing_decision_table_for_branch_behavior(self) -> None:
        packet = self._issue22_design_packet()
        packet["design_artifact"]["sections"].remove("decision table or policy matrix")
        errors = roadmap_module.validate_implementation_packet(packet, self.catalog["design_artifact_contract"])
        self.assertTrue(any("decision table" in error for error in errors))

    def test_issue22_rejects_missing_validator_impact(self) -> None:
        packet = self._issue22_design_packet()
        packet["validator_impact"] = []
        errors = roadmap_module.validate_implementation_packet(packet, self.catalog["design_artifact_contract"])
        self.assertTrue(any("validator_impact" in error for error in errors))

    def test_issue22_rejects_missing_design(self) -> None:
        packet = self._issue22_design_packet()
        packet["design_artifact"] = None
        errors = roadmap_module.validate_implementation_packet(packet, self.catalog["design_artifact_contract"])
        self.assertTrue(any("missing required design" in error for error in errors))

    def _issue20_research_artifacts(self) -> dict[str, object]:
        def artifact(path: str) -> dict[str, object]:
            return {
                "path": path,
                "sections": list(roadmap_module.REQUIRED_RESEARCH_SECTIONS),
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
            "change_type": "roadmap control",
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
                "sections": list(roadmap_module.REQUIRED_DESIGN_SECTIONS),
            },
            "design_skip": None,
            "affected_artifacts": ["assets/catalog/roadmap-control.v1.json"],
            "validator_impact": ["validate_design_artifact_contract"],
            "documentation_impact": ["README.md"],
            "test_plan": ["issue #22 tests"],
            "safety_boundaries": ["repo-only governance files"],
            "behavior_branches": ["required design", "approved skip"],
        }

    def test_issue21_prototype_contract_validates(self) -> None:
        self.assertEqual([], roadmap_module.validate_prototype_artifact_contract(self.catalog["prototype_artifact_contract"]))

    def test_issue21_required_prototype_packet_validates(self) -> None:
        packet = self._issue21_prototype_packet()
        self.assertEqual([], roadmap_module.validate_implementation_packet(packet, self.catalog["design_artifact_contract"]))

    def test_issue21_narrow_bugfix_prototype_skip_validates(self) -> None:
        packet = self._issue21_prototype_packet()
        packet["prototype_artifact"] = None
        packet["prototype_skip"] = {
            "type": "narrow_bugfix_skip",
            "exact_file_scope": "scripts/roadmap_control.py",
            "no_boundary_change": True,
            "no_runtime_change": True,
            "no_deploy_change": True,
            "no_restricted_data_change": True,
            "no_public_behavior_change": True,
        }
        self.assertEqual([], roadmap_module.validate_implementation_packet(packet, self.catalog["design_artifact_contract"]))

    def test_issue21_already_proven_pattern_prototype_skip_validates(self) -> None:
        packet = self._issue21_prototype_packet()
        packet["prototype_artifact"] = None
        packet["prototype_skip"] = {
            "type": "already_proven_pattern_skip",
            "pattern_reference": "issue-22 design gate validator shape",
            "evidence": "validated catalog and unit tests",
        }
        self.assertEqual([], roadmap_module.validate_implementation_packet(packet, self.catalog["design_artifact_contract"]))

    def test_issue21_rejects_production_mutation_prototype_claim(self) -> None:
        packet = self._issue21_prototype_packet()
        packet["prototype_artifact"]["production_mutation"] = True
        errors = roadmap_module.validate_implementation_packet(packet, self.catalog["design_artifact_contract"])
        self.assertTrue(any("production_mutation" in error for error in errors))

    def test_issue21_rejects_restricted_data_read_prototype_claim(self) -> None:
        packet = self._issue21_prototype_packet()
        packet["prototype_artifact"]["restricted_data_reads"] = True
        errors = roadmap_module.validate_implementation_packet(packet, self.catalog["design_artifact_contract"])
        self.assertTrue(any("restricted_data_reads" in error for error in errors))

    def test_issue21_rejects_broad_implementation_prototype_claim(self) -> None:
        packet = self._issue21_prototype_packet()
        packet["prototype_artifact"]["broad_implementation"] = True
        errors = roadmap_module.validate_implementation_packet(packet, self.catalog["design_artifact_contract"])
        self.assertTrue(any("broad_implementation" in error for error in errors))

    def test_issue21_rejects_missing_decision_outcome(self) -> None:
        packet = self._issue21_prototype_packet()
        packet["prototype_artifact"].pop("decision")
        errors = roadmap_module.validate_implementation_packet(packet, self.catalog["design_artifact_contract"])
        self.assertTrue(any("decision" in error for error in errors))

    def test_issue21_rejects_missing_prototype_artifact_when_required(self) -> None:
        packet = self._issue21_prototype_packet()
        packet["prototype_artifact"] = None
        errors = roadmap_module.validate_implementation_packet(packet, self.catalog["design_artifact_contract"])
        self.assertTrue(any("prototype_artifact missing required artifact" in error for error in errors))

    def test_issue21_requires_operator_approval_for_remaining_material_change(self) -> None:
        packet = self._issue21_prototype_packet()
        packet["runtime_change"] = True
        packet["prototype_review"] = None
        errors = roadmap_module.validate_implementation_packet(packet, self.catalog["design_artifact_contract"])
        self.assertTrue(any("operator approval" in error for error in errors))

    def _issue21_prototype_packet(self) -> dict[str, object]:
        packet = self._issue22_design_packet()
        packet.update({
            "prototype_required": True,
            "research_or_design_unresolved_high_risk_uncertainty": True,
            "cheaply_testable_before_implementation": True,
            "prototype_artifact": {
                "path": "features/issue-21/prototype.md",
                "sections": list(roadmap_module.PROTOTYPE_REQUIRED_SECTIONS),
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


if __name__ == "__main__":
    unittest.main()
