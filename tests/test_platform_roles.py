from __future__ import annotations

import copy
import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PLUGIN_ROOT / "scripts" / "platform_roles.py"
spec = importlib.util.spec_from_file_location("platform_roles", SCRIPT_PATH)
platform_roles = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(platform_roles)  # type: ignore[arg-type]


class PlatformRolesTest(unittest.TestCase):
    EVIDENCE_ROLE_MODEL = "gpt-5.4-mini"
    DEFAULT_ROLE_MODEL = "gpt-5.5"

    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = platform_roles.load_json(PLUGIN_ROOT / "assets/catalog/platform-role-catalog.v1.json")

    def test_catalog_validates(self) -> None:
        self.assertEqual(platform_roles.validate_catalog(self.catalog, plugin_root=PLUGIN_ROOT), [])

    def test_catalog_validation_rejects_stale_route_check_route_id(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        for check in catalog["route_regression_checks"]:
            if check["target"] == "/srv/bears/kubernetes":
                check["required_route_id"] = "workspace_root_submodule_gitlinks"
                break
        errors = platform_roles.validate_catalog(catalog, plugin_root=PLUGIN_ROOT)
        self.assertTrue(
            any(
                "route check /srv/bears/kubernetes: expected route workspace_root_submodule_gitlinks, "
                "got kubernetes_deploy_core" in error
                for error in errors
            )
        )

    def test_cli_validate_route_audit_success_have_clean_stderr(self) -> None:
        cases = (
            (("validate",), 0),
            (("route", "scripts/platform_roles.py"), 0),
            (("audit", "scripts/platform_roles.py"), 0),
        )
        for command, expected_code in cases:
            with self.subTest(command=command):
                result = subprocess.run(
                    [sys.executable, str(SCRIPT_PATH), *command],
                    cwd=PLUGIN_ROOT,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                self.assertEqual(result.returncode, expected_code)
                self.assertEqual(result.stderr, "")
                self.assertNotEqual(result.stdout, "")

    def test_route_packets_label_ci_owned_validation_inventory(self) -> None:
        targets = (
            "scripts/platform_roles.py",
            "agents/bears-docs-maintainer.toml",
        )
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertIn(packet["primary_execution_class"], {"helper", "specialist"})
                self.assertIn("python3 scripts/platform_roles.py validate", packet["validation_required"])
                self.assertIn(
                    "python3 scripts/platform_roles.py validate",
                    packet["validation_required_ci_owned"],
                )
                self.assertFalse(packet["manual_execution_requires_operator_approval"])
                self.assertIn("route/audit gates are agent-local", packet["validation_execution_policy"])
                self.assertTrue(
                    all("platform_roles.py audit " in item for item in packet["validation_required_agent_local"])
                )
                self.assertFalse(
                    any("unittest" in item for item in packet["validation_required_agent_local"])
                )
                self.assertTrue(
                    any("unittest" in item for item in packet["validation_required_ci_owned"])
                )

    def test_render_packet_uses_ci_owned_validation_labels(self) -> None:
        packet = platform_roles.route_target(self.catalog, "scripts/platform_roles.py", plugin_root=PLUGIN_ROOT)
        rendered = platform_roles.render_packet(packet)
        self.assertIn("validation_required_inventory:", rendered)
        self.assertIn("primary_execution_class:", rendered)
        self.assertIn("validation_required_agent_local:", rendered)
        self.assertIn("validation_required_ci_owned:", rendered)
        self.assertIn("manual_execution_requires_operator_approval: false", rendered)
        self.assertIn("Other required checks are CI/local-commit-owned automation", rendered)
        self.assertIn("must not become ad-hoc manual gates", rendered)
        self.assertNotIn("\nvalidation_required:\n", rendered)

    def test_role_execution_class_is_valid_and_independent(self) -> None:
        role_index = {role["name"]: role for role in self.catalog["roles"]}
        self.assertEqual(role_index["bears-platform-role-governor"]["role_kind"], "specialist")
        self.assertEqual(role_index["bears-platform-role-governor"]["execution_class"], "helper")
        self.assertEqual(role_index["bears-auth-platform-engineer"]["execution_class"], "specialist")

        catalog = copy.deepcopy(self.catalog)
        catalog["roles"][0].pop("execution_class")
        errors = platform_roles.validate_catalog(catalog, plugin_root=PLUGIN_ROOT)
        self.assertTrue(any("missing fields" in error and "execution_class" in error for error in errors))

        catalog = copy.deepcopy(self.catalog)
        role = next(item for item in catalog["roles"] if item["name"] == "bears-workflow-overlay-controller")
        role["execution_class"] = "specialist"
        errors = platform_roles.validate_catalog(catalog, plugin_root=PLUGIN_ROOT)
        self.assertTrue(any("orchestrator must set execution_class=helper" in error for error in errors))

    def test_all_agent_tomls_have_catalog_or_profile_mapping_coverage(self) -> None:
        role_files = {role["agent_file"] for role in self.catalog["roles"]}
        mapping_files = {mapping["agent_file"] for mapping in self.catalog["agent_profile_mappings"]}
        actual_files = {
            path.relative_to(PLUGIN_ROOT).as_posix()
            for path in (PLUGIN_ROOT / "agents").glob("*.toml")
        }
        self.assertEqual(actual_files, role_files | mapping_files)
        self.assertFalse(role_files & mapping_files)

        mapped_names = {
            mapping["profile_name"]: mapping["execution_class"]
            for mapping in self.catalog["agent_profile_mappings"]
        }
        self.assertEqual(mapped_names["bears-workflow-overlay-deploy-gate"], "helper")
        self.assertEqual(mapped_names["bears-auth-domain-orchestrator"], "helper")

        catalog = copy.deepcopy(self.catalog)
        catalog["agent_profile_mappings"] = [
            mapping
            for mapping in catalog["agent_profile_mappings"]
            if mapping["agent_file"] != "agents/deploy-impact-gate.toml"
        ]
        errors = platform_roles.validate_catalog(catalog, plugin_root=PLUGIN_ROOT)
        self.assertTrue(
            any(
                "agents/*.toml coverage mismatch" in error
                and "agents/deploy-impact-gate.toml" in error
                for error in errors
            )
        )

    def test_missing_route_and_audit_include_role_development_metadata(self) -> None:
        target = "tests/test_missing_auto_role_example.py"
        for router in (platform_roles.route_target, platform_roles.audit_target):
            with self.subTest(router=router.__name__):
                packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
                self.assertEqual(packet["why_blocked"], "unmapped")
                self.assertFalse(packet.get("implementation_handoff_allowed", False))
                role_development = packet["role_development"]
                self.assertEqual(role_development["lane"], "role-development")
                self.assertEqual(role_development["owner_role"], "bears-platform-role-governor")
                self.assertEqual(role_development["max_attempts"], 2)
                self.assertIn("agents/*.toml", role_development["allowed_write_scope"])
                self.assertIn("python3 scripts/platform_roles.py validate", role_development["required_validations"])
                self.assertIn(
                    "python3 scripts/platform_roles.py role-development-plan <target> --json",
                    role_development["rerun_commands"],
                )
                self.assertIn("owner_conflict", role_development["terminal_blocker_conditions"])

    def test_role_development_plan_ready_for_unmapped_exact_path(self) -> None:
        target = "tests/test_missing_auto_role_example.py"
        packet = platform_roles.role_development_plan(self.catalog, target, plugin_root=PLUGIN_ROOT)
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["lane"], "role-development")
        self.assertEqual(packet["action"], "spawn_role_development_worker")
        self.assertFalse(packet["implementation_handoff_allowed"])
        self.assertFalse(packet["terminal_blocker"])
        self.assertEqual(packet["route"]["status"], "ROLE_COVERAGE_BLOCKER")
        self.assertEqual(packet["route"]["role_development"]["lane"], "role-development")

        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "role-development-plan", target, "--json"],
            cwd=PLUGIN_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        cli_packet = json.loads(result.stdout)
        self.assertEqual(cli_packet["status"], "ready")
        self.assertEqual(cli_packet["action"], "spawn_role_development_worker")

    def test_role_development_plan_noop_for_matched_target(self) -> None:
        packet = platform_roles.role_development_plan(
            self.catalog,
            "assets/catalog/platform-role-catalog.v1.json",
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(packet["status"], "pass")
        self.assertEqual(packet["action"], "noop")
        self.assertTrue(packet["implementation_handoff_allowed"])
        self.assertEqual(packet["route"]["status"], "matched")

    def test_workspace_root_github_actions_workflow_routes_to_exact_config_role(self) -> None:
        target = "/srv/bears/.github/workflows/workspace-gitlink-ci.yml"
        for router in (platform_roles.route_target, platform_roles.audit_target):
            with self.subTest(router=router.__name__):
                packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "workspace_root_github_actions_check_workflow")
                self.assertEqual(packet["primary_role"], "bears-codex-workspace-config-engineer")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertFalse(packet["decomposition_required"])
                self.assertEqual(
                    packet["allowed_write_boundary"],
                    "Only the exact /srv/bears/.github/workflows/workspace-gitlink-ci.yml workspace-root "
                    "GitHub Actions workflow for check generation in BearsCLOUD/bears-codex-workspace; "
                    "no .github/** fallback, no branch protection mutation, no merge-authority bypass, "
                    "no runtime mutation, no provider mutation, no Kubernetes mutation, no Infisical mutation, "
                    "no product, frontend, mobile, or UI mutation, and no secret access.",
                )
                if router is platform_roles.audit_target:
                    self.assertTrue(packet["implementation_handoff_allowed"])

        plan = platform_roles.role_development_plan(self.catalog, target, plugin_root=PLUGIN_ROOT)
        self.assertEqual(plan["status"], "pass")
        self.assertEqual(plan["action"], "noop")
        self.assertTrue(plan["implementation_handoff_allowed"])

    def test_workspace_root_github_actions_workflow_child_stays_unmapped(self) -> None:
        target = "/srv/bears/.github/workflows/workspace-gitlink-ci.yml/child"
        packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
        self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
        self.assertEqual(packet["why_blocked"], "unmapped")
        self.assertNotIn("primary_role", packet)

    def test_parent_group_broad_path_still_cannot_authorize_implementation(self) -> None:
        packet = platform_roles.role_development_plan(self.catalog, "plugins/bears", plugin_root=PLUGIN_ROOT)
        self.assertEqual(packet["status"], "needs_exact_target")
        self.assertEqual(packet["action"], "decompose_to_exact_write_scope")
        self.assertFalse(packet["implementation_handoff_allowed"])
        self.assertEqual(packet["route"]["status"], "ROLE_COVERAGE_BLOCKER")
        self.assertEqual(packet["route"]["why_blocked"], "parent_only")
        self.assertNotIn("primary_role", packet["route"])

    def test_owner_conflict_is_reserved_terminal_role_development_blocker(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        original = next(part for part in catalog["platform_parts"] if part["name"] == "platform_role_governance")
        conflicting = copy.deepcopy(original)
        conflicting["name"] = "platform_role_governance_conflicting_owner"
        catalog["platform_parts"].append(conflicting)
        catalog["mandatory_policy"]["role_required_for"].append(conflicting["name"])

        packet = platform_roles.role_development_plan(catalog, "scripts/platform_roles.py", plugin_root=PLUGIN_ROOT)
        self.assertEqual(packet["status"], "terminal_blocker")
        self.assertEqual(packet["action"], "stop_for_owner_conflict")
        self.assertTrue(packet["terminal_blocker"])
        self.assertEqual(packet["route"]["why_blocked"], "ambiguous_owner")

    def test_cli_missing_catalog_has_stable_stderr_for_validate_route_audit(self) -> None:
        missing_catalog = PLUGIN_ROOT / "tmp-missing-platform-role-catalog.json"
        expected_error = f"ERROR: catalog not found: {missing_catalog}"
        cases = (
            ("validate",),
            ("route", "kube"),
            ("audit", "kube"),
        )
        for command in cases:
            with self.subTest(command=command):
                result = subprocess.run(
                    [sys.executable, str(SCRIPT_PATH), "--catalog", str(missing_catalog), *command],
                    cwd=PLUGIN_ROOT,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=False,
                )
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr.strip(), expected_error)
                self.assertNotIn("[Errno", result.stderr)

    def test_mandatory_policy_role_required_for_matches_role_required_parts(self) -> None:
        expected = {
            part["name"]
            for part in self.catalog["platform_parts"]
            if part.get("role_required") is True
        }
        actual = set(self.catalog["mandatory_policy"]["role_required_for"])
        self.assertEqual(actual, expected)
        self.assertNotIn("auth_gateway_deploy_readiness", actual)
        self.assertIn("telegram_runtime_readiness_catalog", actual)
        self.assertIn("workspace_control_speckit_integration_surfaces", actual)

    def test_all_agent_tomls_route_to_exact_concrete_parts(self) -> None:
        expected = {
            "bears-analytics-quality-engineer.toml": (
                "theants_quality_e2e_layer",
                "bears-analytics-quality-engineer",
            ),
            "bears-android-emulator-platform-engineer.toml": (
                "android_emulator_platform_225",
                "bears-android-emulator-platform-engineer",
            ),
            "bears-codex-workspace-config-engineer.toml": (
                "agent_orchestrator_github_autoscan",
                "bears-codex-workspace-config-engineer",
            ),
            "bears-auth-domain-orchestrator.toml": (
                "development_workflow_orchestration",
                "bears-development-workflow-orchestrator",
            ),
            "bears-auth-platform-engineer.toml": ("auth_core", "bears-auth-platform-engineer"),
            "bears-clarification-architect.toml": (
                "clarification_architect",
                "bears-machine-first-execution-kernel-engineer",
            ),
            "bears-codex-workspace-config-engineer.toml": (
                "codex_workspace_configuration",
                "bears-codex-workspace-config-engineer",
            ),
            "bears-codex-health-engineer.toml": (
                "codex_health_diagnostics",
                "bears-codex-health-engineer",
            ),
            "bears-codex-daemon-engineer.toml": (
                "codexdaemon_runtime",
                "bears-codex-daemon-engineer",
            ),
            "bears-deprecated-git-remote-hygiene-engineer.toml": (
                "deprecated_local_git_remote_hygiene",
                "bears-deprecated-git-remote-hygiene-engineer",
            ),
            "bears-git-workflow-helper.toml": (
                "git_workflow_helper_role_metadata",
                "bears-git-workflow-helper",
            ),
            "bears-kubernetes-data-platform-engineer.toml": (
                "kubernetes_data_platform_role_metadata",
                "bears-platform-role-governor",
            ),
            "bears-machine-first-execution-kernel-engineer.toml": (
                "machine_first_execution_kernel_role_metadata",
                "bears-platform-role-governor",
            ),
            "bears-token-budget-helper.toml": (
                "token_budget_helper_role_metadata",
                "bears-token-budget-helper",
            ),
            "bears-review-fix-helper.toml": (
                "review_fix_helper_role_metadata",
                "bears-review-fix-helper",
            ),
            "bears-deploy-platform-engineer.toml": (
                "auth_gateway_deploy_core",
                "bears-deploy-platform-engineer",
            ),
            "bears-development-workflow-orchestrator.toml": (
                "development_workflow_orchestration",
                "bears-development-workflow-orchestrator",
            ),
            "bears-gateway-domain-orchestrator.toml": (
                "development_workflow_orchestration",
                "bears-development-workflow-orchestrator",
            ),
            "bears-infra-domain-orchestrator.toml": (
                "development_workflow_orchestration",
                "bears-development-workflow-orchestrator",
            ),
            "l2-gitops-domain-orchestrator.toml": (
                "agentic_enterprise_gitops_l2_domain_orchestrator",
                "l2-gitops-domain-orchestrator",
            ),
            "l2-infra-domain-orchestrator.toml": (
                "agentic_enterprise_infra_l2_domain_orchestrator",
                "l2-infra-domain-orchestrator",
            ),
            "l2-platform-domain-orchestrator.toml": (
                "agentic_enterprise_platform_l2_domain_orchestrator",
                "l2-platform-domain-orchestrator",
            ),
            "l2-product-infra-domain-orchestrator.toml": (
                "agentic_enterprise_product_infra_l2_domain_orchestrator",
                "l2-product-infra-domain-orchestrator",
            ),
            "bears-payments-domain-orchestrator.toml": (
                "development_workflow_orchestration",
                "bears-development-workflow-orchestrator",
            ),
            "bears-qa-governance-orchestrator.toml": (
                "development_workflow_orchestration",
                "bears-development-workflow-orchestrator",
            ),
            "bears-tenant-domain-orchestrator.toml": (
                "development_workflow_orchestration",
                "bears-development-workflow-orchestrator",
            ),
            "bears-docs-maintainer.toml": (
                "docs_maintainer_role_metadata",
                "bears-platform-role-governor",
            ),
            "bears-gateway-platform-engineer.toml": ("bears_gateway", "bears-gateway-platform-engineer"),
            "bears-github-actions-access-settings-governor.toml": (
                "platform_role_governance",
                "bears-platform-role-governor",
            ),
            "bears-github-actions-secrets-governor.toml": (
                "platform_role_governance",
                "bears-platform-role-governor",
            ),
            "bears-github-branch-protection-settings-governor.toml": (
                "platform_role_governance",
                "bears-platform-role-governor",
            ),
            "bears-payments-platform-engineer.toml": (
                "bears_platform_billing_surface",
                "bears-payments-platform-engineer",
            ),
            "bears-goal-prompt-generator.toml": ("goal_prompt_generator", "bears-goal-prompt-generator"),
            "bears-infrastructure-network-engineer.toml": (
                "infrastructure_network_role_metadata",
                "bears-platform-role-governor",
            ),
            "bears-notifications-platform-engineer.toml": (
                "platform_role_governance",
                "bears-platform-role-governor",
            ),
            "bears-observability-platform-engineer.toml": (
                "sentry_observability_226",
                "bears-observability-platform-engineer",
            ),
            "bears-ops-runbook-engineer.toml": (
                "theants_ops_runbooks_layer",
                "bears-ops-runbook-engineer",
            ),
            "bears-plugin-constitution-governor.toml": (
                "plugin_constitution_governance",
                "bears-plugin-constitution-governor",
            ),
            "bears-platform-role-governor.toml": (
                "platform_role_governance",
                "bears-platform-role-governor",
            ),
            "bears-platform-security-reviewer.toml": (
                "platform_role_governance",
                "bears-platform-role-governor",
            ),
            "bears-product-app-zone-engineer.toml": (
                "theants_product_dev_layer",
                "bears-product-app-zone-engineer",
            ),
            "bears-vpn-bot-engineer.toml": (
                "vpn_specialist_role_metadata",
                "bears-platform-role-governor",
            ),
            "bears-vpn-client-app-engineer.toml": (
                "vpn_specialist_role_metadata",
                "bears-platform-role-governor",
            ),
            "bears-vpn-ingress-engineer.toml": (
                "vpn_specialist_role_metadata",
                "bears-platform-role-governor",
            ),
            "bears-vpn-project-governance-engineer.toml": (
                "vpn_specialist_role_metadata",
                "bears-platform-role-governor",
            ),
            "bears-vpn-proxy-engineer.toml": (
                "vpn_specialist_role_metadata",
                "bears-platform-role-governor",
            ),
            "bears-secret-factory-engineer.toml": (
                "secret_factory_governance",
                "bears-secret-factory-engineer",
            ),
            "bears-session-worker-runtime-engineer.toml": (
                "session_workers_runtime",
                "bears-session-worker-runtime-engineer",
            ),
            "bears-subagent-orchestration-engineer.toml": (
                "subagent_orchestration_policy",
                "bears-subagent-orchestration-engineer",
            ),
            "bears-telegram-platform-engineer.toml": (
                "bears_telegram_workflow_skill_bundle",
                "bears-telegram-platform-engineer",
            ),
            "bears-tenant-registry-platform-engineer.toml": (
                "bears_platform_tenant_registry_surface",
                "bears-tenant-registry-platform-engineer",
            ),
            "bears-vpn-runtime-engineer.toml": (
                "vpn_runtime_role_metadata",
                "bears-platform-role-governor",
            ),
            "bears-wb-integration-platform-engineer.toml": (
                "platform_role_governance",
                "bears-platform-role-governor",
            ),
            "bears-workflow-overlay-platform-engineer.toml": (
                "workflow_overlay_core_plugin_surface",
                "bears-workflow-overlay-platform-engineer",
            ),
            "blocker-taxonomy-evaluator.toml": (
                "workflow_overlay_core_plugin_surface",
                "bears-workflow-overlay-platform-engineer",
            ),
            "deploy-impact-gate.toml": (
                "workflow_overlay_core_plugin_surface",
                "bears-workflow-overlay-platform-engineer",
            ),
            "governance-project-router.toml": (
                "workflow_overlay_core_plugin_surface",
                "bears-workflow-overlay-platform-engineer",
            ),
            "overlay-controller.toml": (
                "workflow_overlay_core_plugin_surface",
                "bears-workflow-overlay-platform-engineer",
            ),
            "role-coverage-gate.toml": (
                "workflow_overlay_core_plugin_surface",
                "bears-workflow-overlay-platform-engineer",
            ),
            "workflow-artifact-validator.toml": (
                "workflow_overlay_artifact_validator",
                "bears-workflow-overlay-workflow-artifact-validator",
            ),
        }
        agent_files = sorted(path.name for path in (PLUGIN_ROOT / "agents").glob("*.toml"))
        self.assertEqual(agent_files, sorted(expected))
        for filename, (expected_part, expected_role) in expected.items():
            target = PLUGIN_ROOT / "agents" / filename
            with self.subTest(target=str(target)):
                packet = platform_roles.route_target(
                    self.catalog,
                    str(target),
                    plugin_root=PLUGIN_ROOT,
                )
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], expected_part)
                self.assertEqual(packet["primary_role"], expected_role)
                self.assertIn(packet["primary_execution_class"], {"helper", "specialist"})

    def test_git_workflow_helper_exact_file_routes_to_helper_role(self) -> None:
        target = "/srv/bears/plugins/bears/agents/bears-git-workflow-helper.toml"
        for router in (platform_roles.route_target, platform_roles.audit_target):
            with self.subTest(router=router.__name__):
                packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "git_workflow_helper_role_metadata")
                self.assertEqual(packet["primary_role"], "bears-git-workflow-helper")
                self.assertEqual(packet["primary_execution_class"], "helper")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertFalse(packet["decomposition_required"])
                self.assertIn("bears-git-workflow-helper.toml", packet["allowed_write_boundary"])
                self.assertIn("no product, runtime, deployment", packet["allowed_write_boundary"])

    def test_goal_agent_helper_purposes_route_to_explicit_helper_roles(self) -> None:
        workflow = platform_roles.load_json(PLUGIN_ROOT / "assets/catalog/agentic-enterprise-workflow.v1.json")
        purposes: set[str] = set()
        for mode in workflow["goal_agent_modes"].values():
            for helper_key in ("helper_agents", "l2_helper_agents"):
                helper_config = mode.get(helper_key)
                if isinstance(helper_config, dict):
                    purposes.update(helper_config.get("purposes", []))

        expected_roles = {
            "token_economy": "bears-token-budget-helper",
            "git_ci_cache_closeout": "bears-git-workflow-helper",
            "review_fix_support": "bears-review-fix-helper",
        }
        self.assertEqual(purposes, set(expected_roles))

        role_index = {role["name"]: role for role in self.catalog["roles"]}
        for purpose, expected_role in expected_roles.items():
            with self.subTest(purpose=purpose):
                role = role_index[expected_role]
                self.assertEqual(role["role_kind"], "helper")
                self.assertEqual(role["execution_class"], "helper")
                self.assertTrue(role["primary_eligible"])
                self.assertEqual(role["model"], "gpt-5.4-mini")

                packet = platform_roles.route_target(self.catalog, purpose, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["primary_role"], expected_role)
                self.assertEqual(packet["primary_execution_class"], "helper")
                self.assertFalse(packet["decomposition_required"])

        for expected_role in ("bears-token-budget-helper", "bears-review-fix-helper"):
            with self.subTest(agent=expected_role):
                agent_file = PLUGIN_ROOT / role_index[expected_role]["agent_file"]
                agent = tomllib.loads(agent_file.read_text())
                self.assertEqual(agent["role_kind"], "helper")
                self.assertEqual(agent["model"], "gpt-5.4-mini")
                self.assertEqual(agent["model_reasoning_effort"], "medium")
                self.assertIn("Never run local `pytest`, `unittest`", agent["developer_instructions"])
                self.assertIn("Never read secrets", agent["developer_instructions"])

        token_agent = tomllib.loads((PLUGIN_ROOT / "agents/bears-token-budget-helper.toml").read_text())
        self.assertIn("Recommend a split when elapsed or expected work is over 5 minutes", token_agent["developer_instructions"])
        self.assertIn("compact_state_summary", token_agent["developer_instructions"])

        review_agent = tomllib.loads((PLUGIN_ROOT / "agents/bears-review-fix-helper.toml").read_text())
        self.assertIn("Do not stop the owner agent except for a real blocker", review_agent["developer_instructions"])
        self.assertIn("changed_files", review_agent["developer_instructions"])

    def test_routes_spine_legacy_sources_to_legacy_parts(self) -> None:
        cases = {
            "/srv/bears/legacy/seller/apps/auth_core": ("auth_core_legacy_source", "bears-auth-platform-engineer"),
            "/srv/bears/legacy/seller/apps/auth_core/src": ("auth_core_legacy_source", "bears-auth-platform-engineer"),
            "/srv/bears/projects/seller/apps/auth_core": ("auth_core_legacy_source", "bears-auth-platform-engineer"),
            "https://bears.gitlab.yandexcloud.net/bears/auth_core": (
                "auth_core_legacy_source",
                "bears-auth-platform-engineer",
            ),
            "/srv/bears/legacy/seller/apps/gateway": (
                "bears_gateway_legacy_source",
                "bears-gateway-platform-engineer",
            ),
            "/srv/bears/legacy/seller/apps/gateway/src": (
                "bears_gateway_legacy_source",
                "bears-gateway-platform-engineer",
            ),
            "/srv/bears/legacy/seller/apps/bears_gateway": (
                "bears_gateway_legacy_source",
                "bears-gateway-platform-engineer",
            ),
            "/srv/bears/legacy/seller/apps/bears_gateway/src": (
                "bears_gateway_legacy_source",
                "bears-gateway-platform-engineer",
            ),
            "/srv/bears/projects/seller/apps/gateway": (
                "bears_gateway_legacy_source",
                "bears-gateway-platform-engineer",
            ),
            "/srv/bears/projects/seller/apps/bears_gateway": (
                "bears_gateway_legacy_source",
                "bears-gateway-platform-engineer",
            ),
            "https://bears.gitlab.yandexcloud.net/bears/bears_gateway": (
                "bears_gateway_legacy_source",
                "bears-gateway-platform-engineer",
            ),
            "/srv/bears/legacy/seller/apps/cd_deploy_stage": (
                "cd_deploy_stage_legacy_source",
                "bears-deploy-platform-engineer",
            ),
            "/srv/bears/legacy/seller/apps/cd_deploy_stage/.gitlab-ci.yml": (
                "cd_deploy_stage_legacy_source",
                "bears-deploy-platform-engineer",
            ),
            "/srv/bears/projects/seller/apps/cd_deploy_stage": (
                "cd_deploy_stage_legacy_source",
                "bears-deploy-platform-engineer",
            ),
        }
        for target, (expected_part, expected_role) in cases.items():
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], expected_part)
                self.assertEqual(packet["primary_role"], expected_role)
                self.assertFalse(packet["decomposition_required"])

    def test_deprecated_projects_spine_children_do_not_authorize_implementation(self) -> None:
        targets = [
            "/srv/bears/projects/seller/apps/auth_core/src",
            "/srv/bears/projects/seller/apps/gateway/src",
            "/srv/bears/projects/seller/apps/bears_gateway/src",
            "/srv/bears/projects/seller/apps/cd_deploy_stage/.gitlab-ci.yml",
            "/srv/bears/projects/seller/apps/payment_service/app",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
                self.assertEqual(packet["why_blocked"], "unmapped")
                self.assertNotIn("primary_role", packet)

    def test_routes_universal_core_spine_to_neutral_platform_paths(self) -> None:
        cases = {
            "/srv/bears/dev/platform/src/bears_platform/auth": (
                "auth_core",
                "bears-auth-platform-engineer",
            ),
            "/srv/bears/dev/platform/src/bears_platform/gateway": (
                "bears_gateway",
                "bears-gateway-platform-engineer",
            ),
            "/srv/bears/dev/platform/src/bears_platform/deploy": (
                "cd_deploy_stage",
                "bears-deploy-platform-engineer",
            ),
        }
        for target, (expected_part, expected_role) in cases.items():
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], expected_part)
                self.assertEqual(packet["primary_role"], expected_role)
                self.assertFalse(packet["decomposition_required"])

    def test_routes_auth_contract_test_file_to_exact_auth_specialist(self) -> None:
        target = "/srv/bears/dev/platform/tests/test_auth_contracts.py"
        for router in (platform_roles.route_target, platform_roles.audit_target):
            with self.subTest(router=router.__name__):
                packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "auth_core_contract_tests")
                self.assertEqual(packet["primary_role"], "bears-auth-platform-engineer")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertFalse(packet["decomposition_required"])
                self.assertIn(target, packet["allowed_write_boundary"])
                self.assertIn("auth-core contract test coverage", packet["allowed_write_boundary"])
                self.assertNotIn("/srv/bears/projects/seller/apps", packet["allowed_write_boundary"])

        broad_tests = platform_roles.route_target(
            self.catalog,
            "/srv/bears/dev/platform/tests",
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(broad_tests["status"], "ROLE_COVERAGE_BLOCKER")
        self.assertEqual(broad_tests["why_blocked"], "unmapped")
        self.assertNotIn("primary_role", broad_tests)

    def test_routes_gateway_contract_test_file_to_exact_gateway_specialist(self) -> None:
        target = "/srv/bears/dev/platform/tests/test_gateway_contracts.py"
        for router in (platform_roles.route_target, platform_roles.audit_target):
            with self.subTest(router=router.__name__):
                packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "bears_gateway_contract_tests")
                self.assertEqual(packet["primary_role"], "bears-gateway-platform-engineer")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertFalse(packet["decomposition_required"])
                self.assertIn(target, packet["allowed_write_boundary"])
                self.assertIn("gateway-core contract test coverage", packet["allowed_write_boundary"])
                self.assertNotIn("/srv/bears/projects/seller/apps", packet["allowed_write_boundary"])

        broad_tests = platform_roles.route_target(
            self.catalog,
            "/srv/bears/dev/platform/tests",
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(broad_tests["status"], "ROLE_COVERAGE_BLOCKER")
        self.assertEqual(broad_tests["why_blocked"], "unmapped")
        self.assertNotIn("primary_role", broad_tests)

    def test_routes_gateway_runtime_contract_test_file_to_exact_gateway_specialist(self) -> None:
        target = "/srv/bears/dev/platform/tests/test_gateway_runtime_contracts.py"
        for router in (platform_roles.route_target, platform_roles.audit_target):
            with self.subTest(router=router.__name__):
                packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "bears_gateway_runtime_contract_tests")
                self.assertEqual(packet["primary_role"], "bears-gateway-platform-engineer")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertFalse(packet["decomposition_required"])
                self.assertIn(target, packet["allowed_write_boundary"])
                self.assertIn("gateway runtime/auth-matrix contract test coverage", packet["allowed_write_boundary"])

    def test_routes_gateway_seller_route_pack_fixture_to_exact_gateway_specialist(self) -> None:
        target = "/srv/bears/dev/platform/tests/fixtures/seller_route_pack.py"
        for router in (platform_roles.route_target, platform_roles.audit_target):
            with self.subTest(router=router.__name__):
                packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "bears_gateway_seller_route_pack_fixture")
                self.assertEqual(packet["primary_role"], "bears-gateway-platform-engineer")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertFalse(packet["decomposition_required"])
                self.assertIn(target, packet["allowed_write_boundary"])
                self.assertIn("seller-consumer route-pack fixture coverage", packet["allowed_write_boundary"])
                self.assertIn("never a gateway core dependency", packet["allowed_write_boundary"])

        broad_fixtures = platform_roles.route_target(
            self.catalog,
            "/srv/bears/dev/platform/tests/fixtures",
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(broad_fixtures["status"], "ROLE_COVERAGE_BLOCKER")
        self.assertEqual(broad_fixtures["why_blocked"], "unmapped")
        self.assertNotIn("primary_role", broad_fixtures)

    def test_routes_gateway_route_pack_test_file_to_exact_gateway_specialist(self) -> None:
        target = "/srv/bears/dev/platform/tests/test_gateway_route_pack.py"
        for router in (platform_roles.route_target, platform_roles.audit_target):
            with self.subTest(router=router.__name__):
                packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "bears_gateway_route_pack_contract_tests")
                self.assertEqual(packet["primary_role"], "bears-gateway-platform-engineer")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertFalse(packet["decomposition_required"])
                self.assertIn(target, packet["allowed_write_boundary"])
                self.assertIn("gateway route-pack contract test coverage", packet["allowed_write_boundary"])

    def test_routes_gateway_auth_mode_map_test_file_to_exact_gateway_specialist(self) -> None:
        target = "/srv/bears/dev/platform/tests/test_gateway_auth_mode_map.py"
        for router in (platform_roles.route_target, platform_roles.audit_target):
            with self.subTest(router=router.__name__):
                packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "bears_gateway_auth_mode_map_contract_tests")
                self.assertEqual(packet["primary_role"], "bears-gateway-platform-engineer")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertFalse(packet["decomposition_required"])
                self.assertIn(target, packet["allowed_write_boundary"])
                self.assertIn("gateway auth-mode map contract test coverage", packet["allowed_write_boundary"])

    def test_routes_gateway_tenant_registry_binding_test_file_to_exact_gateway_specialist(self) -> None:
        target = "/srv/bears/dev/platform/tests/test_gateway_tenant_registry_binding.py"
        for router in (platform_roles.route_target, platform_roles.audit_target):
            with self.subTest(router=router.__name__):
                packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "bears_gateway_tenant_registry_binding_contract_tests")
                self.assertEqual(packet["primary_role"], "bears-gateway-platform-engineer")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertFalse(packet["decomposition_required"])
                self.assertIn(target, packet["allowed_write_boundary"])
                self.assertIn("gateway tenant-registry binding contract test coverage", packet["allowed_write_boundary"])

    def test_routes_gateway_runtime_service_test_file_to_exact_gateway_specialist(self) -> None:
        target = "/srv/bears/dev/platform/tests/test_gateway_runtime_service.py"
        for router in (platform_roles.route_target, platform_roles.audit_target):
            with self.subTest(router=router.__name__):
                packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "bears_gateway_runtime_service_contract_tests")
                self.assertEqual(packet["primary_role"], "bears-gateway-platform-engineer")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertFalse(packet["decomposition_required"])
                self.assertIn(target, packet["allowed_write_boundary"])
                self.assertIn("gateway runtime-service contract test coverage", packet["allowed_write_boundary"])
                self.assertNotIn("/srv/bears/projects/seller/apps", packet["allowed_write_boundary"])

    def test_routes_tenant_registry_alias_and_surface_to_exact_tenant_registry_specialist(self) -> None:
        targets = (
            "tenant_registry",
            "/srv/bears/dev/platform/src/bears_platform/tenant_registry",
        )
        for target in targets:
            for router in (platform_roles.route_target, platform_roles.audit_target):
                with self.subTest(target=target, router=router.__name__):
                    packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                    self.assertEqual(packet["status"], "matched")
                    self.assertEqual(packet["concrete_part"], "bears_platform_tenant_registry_surface")
                    self.assertEqual(packet["primary_role"], "bears-tenant-registry-platform-engineer")
                    self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                    self.assertFalse(packet["decomposition_required"])
                    self.assertIn("/srv/bears/dev/platform/src/bears_platform/tenant_registry", packet["allowed_write_boundary"])
                    self.assertIn("neutral shared tenant-registry core paths", packet["allowed_write_boundary"])
                    self.assertIn(
                        "python3 scripts/agent_registration_sync.py check --target user --json",
                        packet["validation_required"],
                    )

    def test_tenant_registry_alias_path_drift_stays_unmapped(self) -> None:
        target = "tenant_registry/unknown_future_child"
        for router in (platform_roles.route_target, platform_roles.audit_target):
            with self.subTest(router=router.__name__):
                packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
                self.assertEqual(packet["why_blocked"], "unmapped")
                self.assertNotIn("primary_role", packet)

    def test_routes_tenant_registry_runtime_contract_test_file_to_exact_tenant_registry_specialist(self) -> None:
        target = "/srv/bears/dev/platform/tests/test_tenant_registry_runtime_contracts.py"
        for router in (platform_roles.route_target, platform_roles.audit_target):
            with self.subTest(router=router.__name__):
                packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "bears_platform_tenant_registry_runtime_contract_tests")
                self.assertEqual(packet["primary_role"], "bears-tenant-registry-platform-engineer")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertFalse(packet["decomposition_required"])
                self.assertIn(target, packet["allowed_write_boundary"])
                self.assertIn("tenant-registry runtime contract test coverage", packet["allowed_write_boundary"])
                self.assertNotIn("/srv/bears/projects/seller/apps", packet["allowed_write_boundary"])

    def test_pr128_registry_test_files_route_to_exact_tenant_registry_specialist(self) -> None:
        cases = {
            "tests/test_tenant_registry_contracts.py": "bears_platform_tenant_registry_contract_tests",
            "tests/test_zone_registry_contracts.py": "bears_platform_zone_registry_contract_tests",
            "tests/test_zone_registry_runtime.py": "bears_platform_zone_registry_runtime_tests",
        }
        for target, expected_part in cases.items():
            for router in (platform_roles.route_target, platform_roles.audit_target):
                with self.subTest(target=target, router=router.__name__):
                    packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                    self.assertEqual(packet["status"], "matched")
                    self.assertEqual(packet["concrete_part"], expected_part)
                    self.assertEqual(packet["primary_role"], "bears-tenant-registry-platform-engineer")
                    self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                    self.assertFalse(packet["decomposition_required"])
                    self.assertIn(target, packet["allowed_write_boundary"])
                    self.assertIn("no broad tests directory", packet["allowed_write_boundary"])

    def test_pr128_registry_test_unknown_sibling_stays_unmapped(self) -> None:
        target = "tests/test_zone_registry_unknown_future.py"
        for router in (platform_roles.route_target, platform_roles.audit_target):
            with self.subTest(router=router.__name__):
                packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
                self.assertEqual(packet["why_blocked"], "unmapped")
                self.assertNotIn("primary_role", packet)

    def test_routes_deploy_contract_test_file_to_exact_deploy_specialist(self) -> None:
        target = "/srv/bears/dev/platform/tests/test_deploy_contracts.py"
        for router in (platform_roles.route_target, platform_roles.audit_target):
            with self.subTest(router=router.__name__):
                packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "cd_deploy_stage_contract_tests")
                self.assertEqual(packet["primary_role"], "bears-deploy-platform-engineer")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertFalse(packet["decomposition_required"])
                self.assertIn(target, packet["allowed_write_boundary"])
                self.assertIn("deploy-core contract test coverage", packet["allowed_write_boundary"])
                self.assertNotIn("/srv/bears/projects/seller/apps", packet["allowed_write_boundary"])

        broad_tests = platform_roles.route_target(
            self.catalog,
            "/srv/bears/dev/platform/tests",
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(broad_tests["status"], "ROLE_COVERAGE_BLOCKER")
        self.assertEqual(broad_tests["why_blocked"], "unmapped")
        self.assertNotIn("primary_role", broad_tests)

    def test_routes_billing_contract_test_file_to_exact_payments_specialist(self) -> None:
        target = "/srv/bears/dev/platform/tests/test_billing_contracts.py"
        for router in (platform_roles.route_target, platform_roles.audit_target):
            with self.subTest(router=router.__name__):
                packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "bears_platform_billing_contract_tests")
                self.assertEqual(packet["primary_role"], "bears-payments-platform-engineer")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertFalse(packet["decomposition_required"])
                self.assertIn(target, packet["allowed_write_boundary"])
                self.assertIn("universal billing contract test coverage", packet["allowed_write_boundary"])
                self.assertNotIn("/srv/bears/projects/seller/apps", packet["allowed_write_boundary"])

        broad_tests = platform_roles.route_target(
            self.catalog,
            "/srv/bears/dev/platform/tests",
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(broad_tests["status"], "ROLE_COVERAGE_BLOCKER")
        self.assertEqual(broad_tests["why_blocked"], "unmapped")
        self.assertNotIn("primary_role", broad_tests)

    def test_routes_billing_runtime_service_test_file_to_exact_payments_specialist(self) -> None:
        target = "/srv/bears/dev/platform/tests/test_billing_runtime_service.py"
        for router in (platform_roles.route_target, platform_roles.audit_target):
            with self.subTest(router=router.__name__):
                packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "bears_platform_billing_runtime_service_contract_tests")
                self.assertEqual(packet["primary_role"], "bears-payments-platform-engineer")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertFalse(packet["decomposition_required"])
                self.assertIn(target, packet["allowed_write_boundary"])
                self.assertIn("universal billing runtime-service contract test coverage", packet["allowed_write_boundary"])
                self.assertNotIn("/srv/bears/projects/seller/apps", packet["allowed_write_boundary"])

    def test_routes_billing_processing_contract_test_file_to_exact_payments_specialist(self) -> None:
        target = "/srv/bears/dev/platform/tests/test_billing_processing_contracts.py"
        for router in (platform_roles.route_target, platform_roles.audit_target):
            with self.subTest(router=router.__name__):
                packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "bears_platform_billing_processing_contract_tests")
                self.assertEqual(packet["primary_role"], "bears-payments-platform-engineer")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertFalse(packet["decomposition_required"])
                self.assertIn(target, packet["allowed_write_boundary"])
                self.assertIn("universal billing processing contract test coverage", packet["allowed_write_boundary"])
                self.assertNotIn("/srv/bears/projects/seller/apps", packet["allowed_write_boundary"])

    def test_routes_billing_status_adapter_test_file_to_exact_payments_specialist(self) -> None:
        target = "/srv/bears/dev/platform/tests/test_billing_status_adapters.py"
        for router in (platform_roles.route_target, platform_roles.audit_target):
            with self.subTest(router=router.__name__):
                packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "bears_platform_billing_status_adapter_contract_tests")
                self.assertEqual(packet["primary_role"], "bears-payments-platform-engineer")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertFalse(packet["decomposition_required"])
                self.assertIn(target, packet["allowed_write_boundary"])
                self.assertIn("billing status-adapter contract test coverage", packet["allowed_write_boundary"])
                self.assertNotIn("/srv/bears/projects/seller/apps", packet["allowed_write_boundary"])

    def test_routes_billing_idempotency_test_file_to_exact_payments_specialist(self) -> None:
        target = "/srv/bears/dev/platform/tests/test_billing_idempotency.py"
        for router in (platform_roles.route_target, platform_roles.audit_target):
            with self.subTest(router=router.__name__):
                packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "bears_platform_billing_idempotency_contract_tests")
                self.assertEqual(packet["primary_role"], "bears-payments-platform-engineer")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertFalse(packet["decomposition_required"])
                self.assertIn(target, packet["allowed_write_boundary"])
                self.assertIn("billing idempotency contract test coverage", packet["allowed_write_boundary"])
                self.assertNotIn("/srv/bears/projects/seller/apps", packet["allowed_write_boundary"])

    def test_routes_billing_money_units_test_file_to_exact_payments_specialist(self) -> None:
        target = "/srv/bears/dev/platform/tests/test_billing_money_units.py"
        for router in (platform_roles.route_target, platform_roles.audit_target):
            with self.subTest(router=router.__name__):
                packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "bears_platform_billing_money_units_contract_tests")
                self.assertEqual(packet["primary_role"], "bears-payments-platform-engineer")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertFalse(packet["decomposition_required"])
                self.assertIn(target, packet["allowed_write_boundary"])
                self.assertIn("billing money-unit contract test coverage", packet["allowed_write_boundary"])
                self.assertNotIn("/srv/bears/projects/seller/apps", packet["allowed_write_boundary"])

    def test_routes_payments_worker_isolation_files_to_exact_payments_specialist(self) -> None:
        cases = {
            "tests/test_payments_worker_isolation_contract.py": (
                "bears_platform_payments_worker_isolation_contract_tests",
                "payments worker-isolation contract test coverage",
            ),
            "/srv/bears/dev/platform/tests/test_payments_worker_isolation_contract.py": (
                "bears_platform_payments_worker_isolation_contract_tests",
                "payments worker-isolation contract test coverage",
            ),
            "tests/fixtures/payments_worker_isolation.py": (
                "bears_platform_payments_worker_isolation_fixture",
                "payments worker-isolation fixture coverage",
            ),
            "/srv/bears/dev/platform/tests/fixtures/payments_worker_isolation.py": (
                "bears_platform_payments_worker_isolation_fixture",
                "payments worker-isolation fixture coverage",
            ),
        }
        for target, (part_name, boundary_text) in cases.items():
            for router in (platform_roles.route_target, platform_roles.audit_target):
                with self.subTest(target=target, router=router.__name__):
                    packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                    self.assertEqual(packet["status"], "matched")
                    self.assertEqual(packet["concrete_part"], part_name)
                    self.assertEqual(packet["primary_role"], "bears-payments-platform-engineer")
                    self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                    self.assertFalse(packet["decomposition_required"])
                    self.assertIn(boundary_text, packet["allowed_write_boundary"])
                    self.assertIn("frontend, mobile, UI, web-client", packet["allowed_write_boundary"])
                    self.assertIn("secret-free", packet["trust_boundary"])
                    self.assertNotIn("/srv/bears/projects/seller/apps", packet["allowed_write_boundary"])

    def test_routes_runtime_health_status_validation_files_to_exact_backend_specialist(self) -> None:
        cases = {
            "/srv/bears/dev/platform/tests/test_data_cache_runtime.py": (
                "bears_platform_data_cache_runtime_tests",
                "data cache runtime test file",
            ),
            "/srv/bears/dev/platform/tests/test_managed_backend_runtime.py": (
                "bears_platform_managed_backend_runtime_tests",
                "managed backend runtime test file",
            ),
            "/srv/bears/dev/platform/tests/test_runtime_status_views.py": (
                "bears_platform_managed_backend_runtime_status_views_tests",
                "runtime status-view test file",
            ),
            "/srv/bears/dev/platform/tests/test_health.py": (
                "bears_platform_managed_backend_health_contract_tests",
                "managed backend health contract test file",
            ),
        }
        for target, (part_name, boundary_text) in cases.items():
            for router in (platform_roles.route_target, platform_roles.audit_target):
                with self.subTest(target=target, router=router.__name__):
                    packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                    self.assertEqual(packet["status"], "matched")
                    self.assertEqual(packet["concrete_part"], part_name)
                    self.assertEqual(packet["primary_role"], "bears-wb-integration-platform-engineer")
                    self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                    self.assertFalse(packet["decomposition_required"])
                    self.assertIn(target, packet["allowed_write_boundary"])
                    self.assertIn(boundary_text, packet["allowed_write_boundary"])
                    self.assertIn("frontend, mobile, UI, web-client", packet["allowed_write_boundary"])
                    self.assertIn("live runtime", packet["allowed_write_boundary"])
                    self.assertIn("secret", packet["allowed_write_boundary"])
                    self.assertNotIn("seller default", packet["allowed_write_boundary"])
                    if router is platform_roles.audit_target:
                        self.assertTrue(packet["implementation_handoff_allowed"])

        broad_tests = platform_roles.route_target(
            self.catalog,
            "/srv/bears/dev/platform/tests",
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(broad_tests["status"], "ROLE_COVERAGE_BLOCKER")
        self.assertEqual(broad_tests["why_blocked"], "unmapped")
        self.assertNotIn("primary_role", broad_tests)

    def test_auth_gateway_deploy_workflow_route_targets_stay_neutral(self) -> None:
        route = next(
            item
            for item in self.catalog["workflow_routes"]
            if item["workflow_id"] == "auth-gateway-deploy-core"
        )
        self.assertEqual(route["required_route_targets"], platform_roles.AUTH_GATEWAY_DEPLOY_CORE_PARTS)
        for target in route["required_route_targets"].values():
            self.assertNotIn("/srv/bears/projects/seller/apps/", target)

    def test_routes_vpn_project_and_child_surfaces_to_exact_roles(self) -> None:
        cases = {
            "/srv/bears/projects/vpn": (
                "vpn_project_root",
                "bears-vpn-project-governance-engineer",
            ),
            "/srv/bears/projects/vpn/androidapp": (
                "vpn_client_surfaces",
                "bears-vpn-client-app-engineer",
            ),
            "/srv/bears/projects/vpn/vpnbot": (
                "telegram_runtime_surfaces",
                "bears-telegram-platform-engineer",
            ),
            "/srv/bears/projects/vpn/amnezia-split": (
                "vpn_runtime_surfaces",
                "bears-vpn-runtime-engineer",
            ),
            "/srv/bears/projects/vpn/wireguard-amnezia": (
                "vpn_runtime_surfaces",
                "bears-vpn-runtime-engineer",
            ),
            "/srv/bears/dev/app/vpn": (
                "vpn_project_root",
                "bears-vpn-project-governance-engineer",
            ),
            "/srv/bears/dev/app/vpn/specs/004-telegram-bootstrap-vpn/spec.md": (
                "vpn_project_root",
                "bears-vpn-project-governance-engineer",
            ),
            "/srv/bears/dev/app/vpn/androidapp": (
                "vpn_client_surfaces",
                "bears-vpn-client-app-engineer",
            ),
            "/srv/bears/dev/app/vpn/androidapp/app/src/main/AndroidManifest.xml": (
                "vpn_client_surfaces",
                "bears-vpn-client-app-engineer",
            ),
            "/srv/bears/dev/app/vpn/winapp": (
                "vpn_client_surfaces",
                "bears-vpn-client-app-engineer",
            ),
            "/srv/bears/dev/app/vpn/vpnbot": (
                "vpn_telegram_bot_dev_layer",
                "bears-vpn-bot-engineer",
            ),
            "/srv/bears/dev/app/vpn/amnezia-split": (
                "vpn_runtime_surfaces",
                "bears-vpn-runtime-engineer",
            ),
            "/srv/bears/dev/app/vpn/amnezia-split/auto_split/autosplit_static_ru.py": (
                "vpn_runtime_surfaces",
                "bears-vpn-runtime-engineer",
            ),
            "/srv/bears/dev/app/vpn/amnezia-split/auto_split/telegram_msp_notify.py": (
                "vpn_telegram_bot_dev_layer",
                "bears-vpn-bot-engineer",
            ),
            "/srv/bears/dev/app/vpn/wireguard-amnezia": (
                "vpn_runtime_surfaces",
                "bears-vpn-runtime-engineer",
            ),
            "/srv/bears/dev/app/vpn/traefik": (
                "vpn_traefik_ingress_dev_layer",
                "bears-vpn-ingress-engineer",
            ),
            "/srv/bears/dev/app/vpn/proxy": (
                "vpn_disabled_proxy_dev_layer",
                "bears-vpn-proxy-engineer",
            ),
        }
        for target, (expected_part, expected_role) in cases.items():
            for router in (platform_roles.route_target, platform_roles.audit_target):
                with self.subTest(target=target, router=router.__name__):
                    packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                    self.assertEqual(packet["status"], "matched")
                    self.assertEqual(packet["concrete_part"], expected_part)
                    self.assertEqual(packet["primary_role"], expected_role)
                    self.assertFalse(packet["decomposition_required"])

    def test_routes_codex_telegram_product_to_exact_telegram_role(self) -> None:
        for target in (
            "/srv/bears/dev/app/codex-telegram",
            "/srv/bears/dev/app/codex-telegram/src/codex_telegram_mcp/server.py",
        ):
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "telegram_platform")
                self.assertEqual(packet["primary_role"], "bears-telegram-platform-engineer")

    def test_routes_codexdaemon_to_exact_runtime_role(self) -> None:
        for target in (
            "/srv/bears/dev/app/codexdaemon",
            "/srv/bears/dev/app/codexdaemon/AGENTS.md",
        ):
            for router in (platform_roles.route_target, platform_roles.audit_target):
                with self.subTest(target=target, router=router.__name__):
                    packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                    self.assertEqual(packet["status"], "matched")
                    self.assertEqual(packet["concrete_part"], "codexdaemon_runtime")
                    self.assertEqual(packet["primary_role"], "bears-codex-daemon-engineer")
                    self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                    self.assertIn("codexdaemon runtime only", packet["trust_boundary"])
                    self.assertIn("@Bears policy/catalog/CD edits", packet["trust_boundary"])
                    self.assertNotIn("/srv/bears/dev/platform", packet["allowed_write_boundary"])
                    if router is platform_roles.audit_target:
                        self.assertTrue(packet["implementation_handoff_allowed"])

    def test_routes_leadgen_product_to_product_app_zone_not_bearstg(self) -> None:
        for target in (
            "/srv/bears/dev/app/leadgen",
            "/srv/bears/dev/app/leadgen/AGENTS.md",
        ):
            for router in (platform_roles.route_target, platform_roles.audit_target):
                with self.subTest(target=target, router=router.__name__):
                    packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                    self.assertEqual(packet["status"], "matched")
                    self.assertEqual(
                        packet["concrete_part"], "leadgen_product_dev_layer"
                    )
                    self.assertEqual(
                        packet["primary_role"], "bears-product-app-zone-engineer"
                    )
                    self.assertNotEqual(
                        packet["primary_role"], "bears-telegram-platform-engineer"
                    )
                    self.assertIn(
                        "BearsTG remains a Telegram management tool for agents",
                        packet["trust_boundary"],
                    )
                    self.assertNotIn(
                        "/srv/bears/plugins/bearstg",
                        packet["allowed_write_boundary"],
                    )
                    if router is platform_roles.audit_target:
                        self.assertTrue(packet["implementation_handoff_allowed"])

    def test_bearstg_mcp_plugin_routes_to_telegram_specialist(self) -> None:
        target = "/srv/bears/plugins/bearstg"
        for router in (platform_roles.route_target, platform_roles.audit_target):
            with self.subTest(router=router.__name__):
                packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "bearstg_mcp_plugin")
                self.assertEqual(
                    packet["primary_role"],
                    "bears-telegram-platform-engineer",
                )
                self.assertFalse(packet["decomposition_required"])
                if router is platform_roles.audit_target:
                    self.assertTrue(packet["implementation_handoff_allowed"])

    def test_dev_workspace_codex_telegram_does_not_authorize_product_adapter(self) -> None:
        packet = platform_roles.route_target(
            self.catalog,
            "/srv/bears/dev/workspace/codex-telegram",
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
        self.assertEqual(packet["why_blocked"], "unmapped")
        self.assertNotIn("primary_role", packet)

    def test_deprecated_projects_vpn_children_do_not_authorize_implementation(self) -> None:
        targets = [
            "/srv/bears/projects/vpn/specs/004-telegram-bootstrap-vpn/spec.md",
            "/srv/bears/projects/vpn/androidapp/app/src/main/AndroidManifest.xml",
            "/srv/bears/projects/vpn/amnezia-split/auto_split/autosplit_static_ru.py",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
                self.assertEqual(packet["why_blocked"], "unmapped")
                self.assertNotIn("primary_role", packet)

    def test_dev_vpn_root_does_not_authorize_unknown_child_scope(self) -> None:
        for target in (
            "/srv/bears/dev/app/vpn/unknown-child",
            "/srv/bears/dev/app/vpn/runtime",
        ):
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
                self.assertEqual(packet["why_blocked"], "unmapped")
                self.assertNotIn("primary_role", packet)
    def test_dev_vpn_exact_child_routes_do_not_fall_back_to_project_root(self) -> None:
        cases = {
            "/srv/bears/dev/app/vpn/traefik/dynamic.yml": "vpn_traefik_ingress_dev_layer",
            "/srv/bears/dev/app/vpn/proxy/telegram-amnezia-proxy/compose.yaml": "vpn_disabled_proxy_dev_layer",
            "/srv/bears/dev/app/vpn/wireguard-amnezia/scripts/probe.py": "vpn_runtime_surfaces",
            "/srv/bears/dev/app/vpn/vpnbot/bot.py": "vpn_telegram_bot_dev_layer",
        }
        for target, expected_part in cases.items():
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], expected_part)
                self.assertNotEqual(packet["concrete_part"], "vpn_project_root")

    def test_routes_platform_role_governance_with_one_primary_role(self) -> None:
        targets = [
            "/srv/bears/plugins/bears/assets/catalog/platform-role-catalog.v1.json",
            "/srv/bears/plugins/bears/assets/catalog/plugin-governance-language-policy.v1.json",
            "assets/catalog/platform-role-catalog.v1.json",
            "plugins/bears/README.md",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "platform_role_governance")
                self.assertEqual(packet["primary_role"], "bears-platform-role-governor")
                self.assertIn("bears-platform-security-reviewer", packet["supporting_roles"])

    def test_routes_shorthand_aliases_to_exact_one_primary_role(self) -> None:
        cases = {
            "plugin-governance-language-policy": (
                "platform_role_governance",
                "bears-platform-role-governor",
            ),
            "plugin-constitution": (
                "plugin_constitution_governance",
                "bears-plugin-constitution-governor",
            ),
            "plugin_constitution_governance": (
                "plugin_constitution_governance",
                "bears-plugin-constitution-governor",
            ),
            "plugin-skill-catalog": (
                "workflow_overlay_skill_inventory",
                "bears-workflow-overlay-platform-engineer",
            ),
            "codex-health": (
                "codex_health_diagnostics",
                "bears-codex-health-engineer",
            ),
            "assets/catalog/telegram-plugin-skill-factory-policy.v1.json": (
                "bears_telegram_workflow_skill_bundle",
                "bears-telegram-platform-engineer",
            ),
        }
        for target, (expected_part, expected_role) in cases.items():
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], expected_part)
                self.assertEqual(packet["primary_role"], expected_role)
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertFalse(packet["decomposition_required"])

    def test_routes_telegram_skill_factory_lifecycle_and_doc_test_to_exact_role(self) -> None:
        cases = {
            "skills/telegram-plugin-skill-factory/references/skill-lifecycle.md": (
                "telegram_plugin_skill_factory_lifecycle_reference",
                "specialist",
            ),
            "/srv/bears/plugins/bears/skills/telegram-plugin-skill-factory/references/skill-lifecycle.md": (
                "telegram_plugin_skill_factory_lifecycle_reference",
                "specialist",
            ),
            "tests/test_workflow_governance_docs.py": (
                "telegram_workflow_governance_docs_test",
                "specialist",
            ),
        }
        for target, (expected_part, expected_execution_class) in cases.items():
            with self.subTest(target=target):
                packet = platform_roles.audit_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], expected_part)
                self.assertEqual(packet["primary_role"], "bears-telegram-platform-engineer")
                self.assertEqual(packet["primary_execution_class"], expected_execution_class)
                self.assertTrue(packet["implementation_handoff_allowed"])
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])

    def test_routes_plugin_constitution_to_exact_governor(self) -> None:
        targets = [
            "/srv/bears/plugins/bears/assets/catalog/plugin-constitution.v1.json",
            "assets/catalog/plugin-constitution.v1.json",
            "/srv/bears/plugins/bears/scripts/plugin_constitution.py",
            "scripts/plugin_constitution.py",
            "/srv/bears/plugins/bears/docs/reference/plugin-constitution.md",
            "docs/reference/plugin-constitution.md",
            "/srv/bears/plugins/bears/tests/test_plugin_constitution.py",
            "tests/test_plugin_constitution.py",
            "/srv/bears/plugins/bears/agents/bears-plugin-constitution-governor.toml",
            "agents/bears-plugin-constitution-governor.toml",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "plugin_constitution_governance")
                self.assertEqual(packet["primary_role"], "bears-plugin-constitution-governor")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertFalse(packet["decomposition_required"])

                audit_packet = platform_roles.audit_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(audit_packet["status"], "matched")
                self.assertTrue(audit_packet["implementation_handoff_allowed"])

    def test_routes_agents_readme_to_platform_role_governance(self) -> None:
        targets = [
            "/srv/bears/plugins/bears/agents/README.md",
            "agents/README.md",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "platform_role_governance")
                self.assertEqual(packet["primary_role"], "bears-platform-role-governor")
                self.assertIn("bears-platform-security-reviewer", packet["supporting_roles"])

    def test_plugin_constitution_role_uses_machine_checkable_write_zones(self) -> None:
        role = next(item for item in self.catalog["roles"] if item["name"] == "bears-plugin-constitution-governor")
        expected = {
            "plugins/bears/assets/catalog/plugin-constitution.v1.json",
            "plugins/bears/scripts/plugin_constitution.py",
            "plugins/bears/docs/reference/plugin-constitution.md",
            "plugins/bears/tests/test_plugin_constitution.py",
            "plugins/bears/README.md",
            "plugins/bears/AGENTS.md",
            "plugins/bears/SPEC.md",
            "plugins/bears/.codex-plugin/plugin.json",
            "plugins/bears/capabilities/plugin_constitution",
            "plugins/bears/assets/catalog/platform-role-catalog.v1.json",
            "plugins/bears/tests/test_platform_roles.py",
            "plugins/bears/agents/README.md",
            "plugins/bears/agents/bears-plugin-constitution-governor.toml",
        }
        self.assertEqual(set(role["allowed_write_zones"]), expected)
        for zone in role["allowed_write_zones"]:
            self.assertTrue(zone.startswith("plugins/bears/"), zone)
            self.assertNotIn(" only", zone)
            self.assertNotIn(" and ", zone)

    def test_security_reviewer_has_no_write_authority(self) -> None:
        role = next(
            item
            for item in self.catalog["roles"]
            if item["name"] == "bears-platform-security-reviewer"
        )
        self.assertEqual(role["sandbox_mode"], "read-only")
        self.assertEqual(set(role["allowed_write_zones"]), {"no_write_authority"})
        self.assertTrue(
            platform_roles.REVIEWER_REQUIRED_FORBIDDEN_ACTIONS.issubset(
                set(role["forbidden_actions"])
            )
        )

    def test_rejects_security_reviewer_write_exception(self) -> None:
        packet = copy.deepcopy(self.catalog)
        role = next(
            item
            for item in packet["roles"]
            if item["name"] == "bears-platform-security-reviewer"
        )
        role["allowed_write_zones"] = ["read-only review by default"]
        role["forbidden_actions"] = [
            "repo-local writes unless explicitly assigned a docs-only write scope"
        ]
        errors = platform_roles.validate_catalog(packet, plugin_root=PLUGIN_ROOT)
        self.assertTrue(any("allowed_write_zones" in error for error in errors), errors)
        self.assertTrue(any("write-scope exceptions" in error for error in errors), errors)

    def test_routes_plugin_audit_artifacts_to_platform_role_governance(self) -> None:
        targets = [
            "/srv/bears/plugins/bears/docs/audits/max-plugin-audit-2026-06-07/security-trust-audit.md",
            "docs/audits/max-plugin-audit-2026-06-07/security-trust-audit.md",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "platform_role_governance")
                self.assertEqual(packet["primary_role"], "bears-platform-role-governor")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertFalse(packet["decomposition_required"])

    def test_agents_readme_inventory_matches_current_agent_tomls(self) -> None:
        readme = (PLUGIN_ROOT / "agents" / "README.md").read_text(encoding="utf-8")
        listed = sorted(re.findall(r"`([^`]+\.toml)`", readme))
        actual = sorted(path.name for path in (PLUGIN_ROOT / "agents").glob("*.toml"))
        self.assertTrue(set(listed) <= set(actual))

        missing_from_readme = sorted(set(actual) - set(listed))
        for filename in missing_from_readme:
            with self.subTest(filename=filename):
                packet = platform_roles.route_target(
                    self.catalog,
                    str((PLUGIN_ROOT / "agents" / filename).resolve()),
                    plugin_root=PLUGIN_ROOT,
                )
                self.assertEqual(packet["status"], "matched")

    def test_secret_factory_role_requires_full_control_chain(self) -> None:
        role = tomllib.loads((PLUGIN_ROOT / "agents" / "bears-secret-factory-engineer.toml").read_text(encoding="utf-8"))
        instructions = role["developer_instructions"]
        required_commands = [
            "python3 /srv/bears/plugins/bears/scripts/platform_roles.py route /srv/bears/plugins/bears/assets/catalog/secret-factory.v1.json",
            "python3 /srv/bears/plugins/bears/scripts/platform_roles.py audit /srv/bears/plugins/bears/assets/catalog/secret-factory.v1.json",
            "python3 scripts/platform_roles.py validate",
            "python3 scripts/platform_roles.py route /srv/bears/plugins/bears/assets/catalog/secret-factory.v1.json",
            "python3 scripts/platform_roles.py audit /srv/bears/plugins/bears/assets/catalog/secret-factory.v1.json",
            "python3 scripts/secret_factory.py validate",
            "python3 -m unittest tests/test_secret_factory.py tests/test_platform_roles.py",
        ]
        for command in required_commands:
            with self.subTest(command=command):
                self.assertIn(command, instructions)

    def test_routes_secret_factory_aliases_have_exact_validation_required_chain(self) -> None:
        target = "/srv/bears/plugins/bears/assets/catalog/secret-factory.v1.json"
        packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
        self.assertEqual(packet["status"], "matched")
        expected = [
            "python3 scripts/platform_roles.py validate",
            "python3 scripts/platform_roles.py route /srv/bears/plugins/bears/assets/catalog/secret-factory.v1.json",
            "python3 scripts/platform_roles.py audit /srv/bears/plugins/bears/assets/catalog/secret-factory.v1.json",
            "python3 scripts/secret_factory.py validate",
            "python3 -m unittest tests/test_secret_factory.py tests/test_platform_roles.py",
        ]
        self.assertEqual(packet["validation_required"], expected)

    def test_routes_secret_factory_exact_aliases_to_one_primary_role(self) -> None:
        targets = [
            "/srv/bears/plugins/bears/assets/catalog/secret-factory.v1.json",
            "/srv/bears/plugins/bears/scripts/secret_factory.py",
            "/srv/bears/plugins/bears/skills/secret-factory/SKILL.md",
            "/srv/bears/plugins/bears/docs/reference/secret-factory.md",
            "/srv/bears/plugins/bears/tests/test_secret_factory.py",
            "/srv/bears/plugins/bears/agents/bears-secret-factory-engineer.toml",
            "secret-factory",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "secret_factory_governance")
                self.assertEqual(packet["primary_role"], "bears-secret-factory-engineer")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])

    def test_routes_project_dirty_baseline_exact_aliases_to_one_primary_role(self) -> None:
        targets = [
            "/srv/bears/plugins/bears/assets/catalog/project-dirty-baseline.v1.json",
            "/srv/bears/plugins/bears/scripts/project_dirty_baseline.py",
            "/srv/bears/plugins/bears/tests/test_project_dirty_baseline.py",
            "/srv/bears/plugins/bears/docs/reference/project-dirty-baseline.md",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "project_dirty_baseline")
                self.assertEqual(packet["primary_role"], "bears-platform-role-governor")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertFalse(packet["decomposition_required"])

    def test_routes_agent_github_dev_cd_flow_to_exact_specialist(self) -> None:
        targets = [
            "/srv/bears/plugins/bears/assets/catalog/agent-github-dev-cd.v1.json",
            "/srv/bears/plugins/bears/scripts/agent_github_dev_cd.py",
            "/srv/bears/plugins/bears/tests/test_agent_github_dev_cd.py",
            "/srv/bears/plugins/bears/docs/reference/agent-github-dev-cd.md",
            "/srv/bears/plugins/bears/workflows/agent-github-dev-cd/workflow.yml",
            "scripts/agent_github_dev_cd.py",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "agent_github_dev_cd_flow")
                self.assertEqual(packet["primary_role"], "bears-deploy-platform-engineer")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertIn("python3 scripts/agent_github_dev_cd.py validate", packet["validation_required"])
                self.assertIn(
                    "python3 scripts/ci_requirements.py validate-workflow --workflow .github/workflows/validate.yml --catalog assets/catalog/ci-requirements.v1.json",
                    packet["validation_required"],
                )
                self.assertIn(
                    "python3 scripts/test_selection.py run --changed-file scripts/agent_github_dev_cd.py --changed-file assets/catalog/agent-github-dev-cd.v1.json --tier fast",
                    packet["validation_required"],
                )
                self.assertFalse(packet["decomposition_required"])

    def test_routes_subagent_orchestration_policy_to_exact_specialist(self) -> None:
        targets = [
            "/srv/bears/plugins/bears/assets/catalog/subagent-orchestration-policy.v1.json",
            "/srv/bears/plugins/bears/scripts/subagent_orchestration_policy.py",
            "/srv/bears/plugins/bears/tests/test_subagent_orchestration_policy.py",
            "/srv/bears/plugins/bears/agents/bears-subagent-orchestration-engineer.toml",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "subagent_orchestration_policy")
                self.assertEqual(packet["primary_role"], "bears-subagent-orchestration-engineer")
                self.assertIn("bears-platform-security-reviewer", packet["supporting_roles"])
                self.assertFalse(packet["decomposition_required"])

    def test_routes_subagent_start_packet_contract_to_exact_specialist(self) -> None:
        target = "/srv/bears/dev/contracts/subagent_start_packet.md"
        packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
        self.assertEqual(packet["status"], "matched")
        self.assertEqual(packet["concrete_part"], "subagent_start_packet_contract")
        self.assertEqual(packet["primary_role"], "bears-subagent-orchestration-engineer")
        self.assertIn("bears-platform-security-reviewer", packet["supporting_roles"])
        self.assertIn(target, packet["allowed_write_boundary"])
        self.assertIn("no broad /srv/bears/dev/contracts authority", packet["allowed_write_boundary"])
        self.assertFalse(packet["decomposition_required"])

        audit_packet = platform_roles.audit_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
        self.assertEqual(audit_packet["status"], "matched")
        self.assertTrue(audit_packet["implementation_handoff_allowed"])

    def test_repo_local_subagent_policy_exists_without_external_dev_checkout(self) -> None:
        self.assertTrue((PLUGIN_ROOT / "assets/catalog/subagent-orchestration-policy.v1.json").is_file())
        for target in (
            "/srv/bears/dev/AGENTS.md",
            "/srv/bears/dev/contracts/subagent_start_packet.md",
        ):
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")

    def test_default_evidence_paths_do_not_require_missing_dev_router(self) -> None:
        self.assertNotIn("/srv/bears/dev/AGENTS.md", platform_roles.DEFAULT_EVIDENCE_PATHS)

    def test_blocker_evidence_checked_filters_missing_paths(self) -> None:
        existing = str(PLUGIN_ROOT / "AGENTS.md")
        missing = "/srv/bears/dev/contracts/missing-evidence-path.md"
        original = list(platform_roles.DEFAULT_EVIDENCE_PATHS)
        try:
            platform_roles.DEFAULT_EVIDENCE_PATHS = [existing, missing]
            packet = platform_roles.route_target(self.catalog, "plugins/bears", plugin_root=PLUGIN_ROOT)
        finally:
            platform_roles.DEFAULT_EVIDENCE_PATHS = original
        self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
        self.assertIn(existing, packet["evidence_checked"])
        self.assertNotIn(missing, packet["evidence_checked"])

    def test_broad_dev_contracts_route_stays_blocked(self) -> None:
        packet = platform_roles.route_target(self.catalog, "/srv/bears/dev/contracts", plugin_root=PLUGIN_ROOT)
        self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
        self.assertIn(packet["why_blocked"], {"parent_only", "unmapped"})
        self.assertTrue(packet["decomposition_required"])
        self.assertNotIn("primary_role", packet)

    def test_routes_project_registry_gate_and_project_mandate(self) -> None:
        cases = {
            "/srv/bears/plugins/bears/scripts/project_registry_gate.py": "project_registry_gate",
            "/srv/bears/plugins/bears/tests/test_project_registry_gate.py": "project_registry_gate",
            "/srv/bears/plugins/bears/skills/project-mandate": "project_mandate_skill",
            "/srv/bears/plugins/bears/skills/project-mandate/SKILL.md": "project_mandate_skill",
            "/srv/bears/dev/registry/projects.v1.json": "workspace_governance_canonical_plugin_docs",
        }
        for target, expected_part in cases.items():
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], expected_part)
                self.assertEqual(packet["primary_role"], "bears-platform-role-governor")
                self.assertIn("bears-platform-security-reviewer", packet["supporting_roles"])
                self.assertFalse(packet["decomposition_required"])

    def test_routes_workspace_control_speckit_integration_surfaces_to_governor(self) -> None:
        cases = {
            "/srv/bears": "workspace_control_speckit_integration_surfaces",
            "/srv/bears/.specify/feature.json": "workspace_control_speckit_integration_surfaces",
            "/srv/bears/specs/004-dev-e2e-foundation/spec.md": "workspace_control_speckit_integration_surfaces",
            "/srv/bears/contracts/project_start_contract.md": "workspace_control_speckit_integration_surfaces",
            "/srv/bears/scripts/validate_workspace_workflow.py": "workspace_control_speckit_integration_surfaces",
        }
        for target, expected_part in cases.items():
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], expected_part)
                self.assertEqual(packet["primary_role"], "bears-platform-role-governor")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertFalse(packet["decomposition_required"])

    def test_routes_t110_workspace_control_agent_reviewer_tests_to_governor(self) -> None:
        cases = (
            "/srv/bears/control-plane/workspace-control/tests",
            "/srv/bears/control-plane/workspace-control/tests/test_agent_reviewer_roles.py",
        )
        for target in cases:
            for router in (platform_roles.route_target, platform_roles.audit_target):
                with self.subTest(target=target, router=router.__name__):
                    packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                    self.assertEqual(packet["status"], "matched")
                    self.assertEqual(packet["concrete_part"], "workspace_control_agent_reviewer_role_tests")
                    self.assertEqual(packet["primary_role"], "bears-platform-role-governor")
                    self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                    self.assertFalse(packet["decomposition_required"])

    def test_routes_t110_feature_006_spec_and_governance_to_telegram_platform_role(self) -> None:
        cases = (
            "/srv/bears/specs/006-bears-platform-telegram/spec.md",
            "/srv/bears/specs/006-bears-platform-telegram/plan.md",
            "/srv/bears/specs/006-bears-platform-telegram/governance",
            "/srv/bears/specs/006-bears-platform-telegram/governance/t110-hygiene.md",
        )
        for target in cases:
            for router in (platform_roles.route_target, platform_roles.audit_target):
                with self.subTest(target=target, router=router.__name__):
                    packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                    self.assertEqual(packet["status"], "matched")
                    self.assertEqual(
                        packet["concrete_part"],
                        "telegram_platform_feature_006_spec_governance_artifacts",
                    )
                    self.assertEqual(packet["primary_role"], "bears-telegram-platform-engineer")
                    self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                    self.assertFalse(packet["decomposition_required"])

    def test_routes_infrastructure_network_surfaces_to_exact_specialist(self) -> None:
        cases = {
            "/srv/bears/dev/infrastructure/network": "dev_core_infrastructure_network_lane",
            "/srv/bears/dev/infrastructure/network/AGENTS.md": "dev_core_infrastructure_network_lane",
            "/srv/bears/docs/architecture/workspace-network-map.md": "workspace_network_map_docs",
            "/srv/bears/docs/reference/network-infrastructure-requirements.md": "workspace_network_map_docs",
            "/srv/bears/projects/infra/requirements.md": "infra_mcp_project_surface",
            "infra legacy cache": "infra_mcp_project_surface",
            "/srv/bears/plugins/bears/skills/yandex360-dns": "yandex360_dns_skill_bundle",
        }
        for target, expected_part in cases.items():
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], expected_part)
                self.assertEqual(packet["primary_role"], "bears-infrastructure-network-engineer")
                self.assertIn("bears-platform-security-reviewer", packet["supporting_roles"])
                self.assertFalse(packet["decomposition_required"])

    def test_yandex360_dns_route_audit_output_is_apply_disabled(self) -> None:
        target = "/srv/bears/plugins/bears/skills/yandex360-dns"
        cases = (
            ("route", platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)),
            ("audit", platform_roles.audit_target(self.catalog, target, plugin_root=PLUGIN_ROOT)),
        )
        for command, packet in cases:
            with self.subTest(command=command):
                rendered = platform_roles.render_packet(packet)
                self.assertNotIn("DNS writes require", rendered)
                self.assertNotIn("before writes", rendered)
                self.assertIn("dry-run/presence-only", rendered)
                self.assertIn("dry-run/apply-disabled", rendered)
                self.assertIn("apply-disabled", rendered)
                self.assertIn("separate approved production path outside this plugin", rendered)

    def test_dev_network_path_stays_unmapped(self) -> None:
        for target in ["/srv/bears/dev/network", "/srv/bears/dev/network/anything"]:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
                self.assertEqual(packet["why_blocked"], "unmapped")
                self.assertNotIn("primary_role", packet)

    def test_deprecated_yandex360_standalone_path_is_not_current_implementation_alias(self) -> None:
        targets = [
            "/home/ai1/.codex/skills/yandex360-dns",
            "/home/ai1/.codex/skills/yandex360-dns/SKILL.md",
        ]
        for target in targets:
            with self.subTest(target=target):
                route_packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(route_packet["status"], "ROLE_COVERAGE_BLOCKER")
                self.assertEqual(route_packet["why_blocked"], "unmapped")
                self.assertNotIn("primary_role", route_packet)

                audit_packet = platform_roles.audit_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(audit_packet["status"], "ROLE_COVERAGE_BLOCKER")
                self.assertEqual(audit_packet["why_blocked"], "unmapped")

    def test_deprecated_local_git_remote_hygiene_routes_exact_targets_and_keeps_root_blocked(self) -> None:
        config_targets = [
            "/srv/bears/deprecated/legacy-2026-05-11/docs/docs-core/.git/config",
            "/srv/bears/deprecated/legacy-2026-05-11/docs/docs-mcp/repo/.git/config",
            "/srv/bears/deprecated/legacy-2026-05-11/docs/docs-mcp/orphaned-from-docs-repo-20260419T1300Z/ad_stat/.git/config",
        ]
        lock_targets = [f"{target}.lock" for target in config_targets]

        for target in [*config_targets, *lock_targets]:
            with self.subTest(target=target):
                route_packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(route_packet["status"], "matched")
                self.assertEqual(route_packet["concrete_part"], "deprecated_local_git_remote_hygiene")
                self.assertEqual(route_packet["primary_role"], "bears-deprecated-git-remote-hygiene-engineer")
                self.assertEqual(route_packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertIn(".git/config.lock", route_packet["allowed_write_boundary"])
                self.assertIn("FLAGGED_ENDPOINTS 0", "\n".join(route_packet["validation_required"]))

                audit_packet = platform_roles.audit_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(audit_packet["status"], "matched")
                self.assertEqual(audit_packet["concrete_part"], "deprecated_local_git_remote_hygiene")
                self.assertTrue(audit_packet["implementation_handoff_allowed"])

        for target in ["/srv/bears/deprecated", "/srv/bears/deprecated/legacy-2026-05-11"]:
            with self.subTest(target=target):
                route_packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(route_packet["status"], "ROLE_COVERAGE_BLOCKER")
                self.assertEqual(route_packet["why_blocked"], "unmapped")
                audit_packet = platform_roles.audit_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(audit_packet["status"], "ROLE_COVERAGE_BLOCKER")
                self.assertFalse(audit_packet["implementation_handoff_allowed"])

    def test_routes_infrastructure_role_metadata_to_governor(self) -> None:
        target = "/srv/bears/plugins/bears/agents/bears-infrastructure-network-engineer.toml"
        packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
        self.assertEqual(packet["status"], "matched")
        self.assertEqual(packet["concrete_part"], "infrastructure_network_role_metadata")
        self.assertEqual(packet["primary_role"], "bears-platform-role-governor")
        self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
        self.assertFalse(packet["decomposition_required"])

    def test_legacy_infra_mcp_alias_is_blocked(self) -> None:
        packet = platform_roles.route_target(self.catalog, "infra MCP", plugin_root=PLUGIN_ROOT)
        self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
        self.assertEqual(packet["why_blocked"], "unknown")
        self.assertTrue(packet["decomposition_required"])
        self.assertNotIn("primary_role", packet)

    def test_catalog_uses_expected_role_models(self) -> None:
        expected_models = {
            "bears-workflow-overlay-workflow-artifact-validator": self.EVIDENCE_ROLE_MODEL,
            "bears-git-workflow-helper": self.EVIDENCE_ROLE_MODEL,
            "bears-token-budget-helper": self.EVIDENCE_ROLE_MODEL,
            "bears-review-fix-helper": self.EVIDENCE_ROLE_MODEL,
        }
        for role in self.catalog["roles"]:
            with self.subTest(role=role["name"]):
                expected_model = expected_models.get(role["name"], self.DEFAULT_ROLE_MODEL)
                self.assertEqual(role["model"], expected_model)

    def test_audit_allows_handoff_only_after_validation(self) -> None:
        packet = platform_roles.audit_target(
            self.catalog,
            "/srv/bears/plugins/bears/assets/catalog/platform-role-catalog.v1.json",
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(packet["status"], "matched")
        self.assertTrue(packet["implementation_handoff_allowed"])
        self.assertEqual(packet["independent_control_audit"]["auditor_role"], "bears-platform-role-governor")

    def test_validation_failure_blocks_implementation_handoff(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["roles"][0].pop("role_kind")
        route_packet = platform_roles.route_target(
            catalog,
            "/srv/bears/plugins/bears/assets/catalog/platform-role-catalog.v1.json",
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(route_packet["status"], "matched")

        audit_packet = platform_roles.audit_target(
            catalog,
            "/srv/bears/plugins/bears/assets/catalog/platform-role-catalog.v1.json",
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(audit_packet["status"], "ROLE_COVERAGE_BLOCKER")
        self.assertFalse(audit_packet["implementation_handoff_allowed"])
        self.assertIn("validation_errors", audit_packet)

    def test_validation_rejects_role_required_for_parity_drift(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["mandatory_policy"]["role_required_for"].remove("telegram_runtime_readiness_catalog")
        errors = platform_roles.validate_catalog(catalog, plugin_root=PLUGIN_ROOT)
        self.assertTrue(
            any("mandatory_policy.role_required_for parity mismatch" in error for error in errors)
        )

    def test_validation_rejects_seller_bound_core_defaults(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        for part in catalog["platform_parts"]:
            if part["name"] == "cd_deploy_stage":
                part["write_roots"] = ["/srv/bears/legacy/seller/apps/cd_deploy_stage"]
                break
        for route in catalog["workflow_routes"]:
            if route["workflow_id"] == "auth-gateway-deploy-core":
                route["required_route_targets"]["cd_deploy_stage"] = (
                    "/srv/bears/legacy/seller/apps/cd_deploy_stage"
                )
                break
        errors = platform_roles.validate_catalog(catalog, plugin_root=PLUGIN_ROOT)
        self.assertTrue(any("no-seller-bound-core" in error for error in errors))

    def test_validation_rejects_unrouteable_role_agent_file(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        for part in catalog["platform_parts"]:
            if part["name"] == "auth_core":
                part["aliases"] = [
                    alias
                    for alias in part["aliases"]
                    if "bears-auth-platform-engineer.toml" not in alias
                ]
                part["write_roots"] = [
                    root
                    for root in part["write_roots"]
                    if "bears-auth-platform-engineer.toml" not in root
                ]
                break
        errors = platform_roles.validate_catalog(catalog, plugin_root=PLUGIN_ROOT)
        self.assertTrue(
            any(
                "role agent_file must route to a matched concrete part: "
                "agents/bears-auth-platform-engineer.toml" in error
                for error in errors
            )
        )

    def test_validation_rejects_missing_role_agent_classification_field(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_root = Path(tmpdir)
            shutil.copytree(PLUGIN_ROOT / "agents", plugin_root / "agents")
            target = plugin_root / "agents" / "bears-git-workflow-helper.toml"
            text = target.read_text(encoding="utf-8").replace('execution_class = "helper"\n', "")
            target.write_text(text, encoding="utf-8")
            errors = platform_roles.validate_catalog(copy.deepcopy(self.catalog), plugin_root=plugin_root)
        self.assertTrue(
            any(
                "agents/bears-git-workflow-helper.toml: missing role classification fields" in error
                for error in errors
            )
        )

    def test_validation_rejects_role_agent_classification_mismatch(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        for role in catalog["roles"]:
            if role["name"] == "bears-git-workflow-helper":
                role["execution_class"] = "specialist"
                break
        errors = platform_roles.validate_catalog(catalog, plugin_root=PLUGIN_ROOT)
        self.assertTrue(
            any(
                "agents/bears-git-workflow-helper.toml: execution_class 'helper' must match expected 'specialist'"
                in error
                for error in errors
            )
        )

    def test_validation_rejects_profile_agent_classification_mismatch(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        target_file = catalog["agent_profile_mappings"][0]["agent_file"]
        catalog["agent_profile_mappings"][0]["execution_class"] = "specialist"
        errors = platform_roles.validate_catalog(catalog, plugin_root=PLUGIN_ROOT)
        self.assertTrue(
            any(f"{target_file}: execution_class 'helper' must match expected 'specialist'" in error for error in errors)
        )

    def test_relative_plugin_root_routes_to_parent_only_governance_router(self) -> None:
        packet = platform_roles.route_target(self.catalog, "plugins/bears", plugin_root=PLUGIN_ROOT)
        self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
        self.assertEqual(packet["why_blocked"], "parent_only")
        self.assertEqual(packet["matched_platform_part"], "bears_plugin")
        self.assertEqual(packet["matched_part_kind"], "group")
        self.assertEqual(packet["required_role_shape"]["name"], "bears-workflow-overlay-controller")
        self.assertTrue(packet["decomposition_required"])

    def test_plugin_root_submodule_gitlink_routes_to_exact_governor(self) -> None:
        target = "/srv/bears/plugins/bears"
        packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
        self.assertEqual(packet["status"], "matched")
        self.assertEqual(packet["concrete_part"], "workspace_root_submodule_gitlinks")
        self.assertEqual(packet["primary_role"], "bears-platform-role-governor")
        self.assertIn("parent /srv/bears Git gitlink pointer entry", packet["allowed_write_boundary"])
        self.assertIn("no child working-tree files", packet["allowed_write_boundary"])
        audit_packet = platform_roles.audit_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
        self.assertEqual(audit_packet["status"], "matched")
        self.assertTrue(audit_packet["implementation_handoff_allowed"])

    def test_kubernetes_root_and_child_route_to_deploy_core(self) -> None:
        for target in (
            "/srv/bears/kubernetes",
            "/srv/bears/kubernetes/scripts/validate_serverspace_wrapper_dry_run.py",
        ):
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "kubernetes_deploy_core")
                self.assertEqual(packet["primary_role"], "bears-deploy-platform-engineer")
                self.assertIn("/srv/bears/kubernetes", packet["allowed_write_boundary"])
                self.assertNotIn("gitlink pointer", packet["allowed_write_boundary"])
                audit_packet = platform_roles.audit_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(audit_packet["status"], "matched")
                self.assertTrue(audit_packet["implementation_handoff_allowed"])

    def test_plugin_source_repo_identity_requires_decomposition(self) -> None:
        targets = [
            "BearsCLOUD/bears_plugin",
            "https://github.com/BearsCLOUD/bears_plugin",
            "https://github.com/BearsCLOUD/bears_plugin.git",
            "git@github.com:BearsCLOUD/bears_plugin.git",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
                self.assertEqual(packet["why_blocked"], "parent_only")
                self.assertTrue(packet["decomposition_required"])

    def test_workspace_repo_identity_requires_decomposition(self) -> None:
        targets = [
            "BearsCLOUD/bears-codex-workspace",
            "https://github.com/BearsCLOUD/bears-codex-workspace",
            "https://github.com/BearsCLOUD/bears-codex-workspace.git",
            "git@github.com:BearsCLOUD/bears-codex-workspace.git",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
                self.assertEqual(packet["why_blocked"], "parent_only")
                self.assertTrue(packet["decomposition_required"])

    def test_unknown_github_repo_identity_stays_unmapped(self) -> None:
        for target in (
            "BearsCLOUD/not-bears-plugin",
            "https://github.com/BearsCLOUD/not-bears-plugin",
        ):
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
                self.assertEqual(packet["why_blocked"], "unmapped")

    def test_deploy_core_routes_to_exact_deploy_specialist(self) -> None:
        packet = platform_roles.route_target(
            self.catalog,
            "/srv/bears/plugins/bears/workflows/auth-gateway-deploy-core/workflow.yml",
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(packet["status"], "matched")
        self.assertEqual(packet["concrete_part"], "auth_gateway_deploy_core")
        self.assertEqual(packet["primary_role"], "bears-deploy-platform-engineer")
        self.assertFalse(packet["decomposition_required"])
        self.assertEqual(
            packet["allowed_write_boundary"],
            "Only the auth-gateway-deploy-core workflow, readiness catalog, readiness validator, readiness tests, and listed dev-core docs; no production deploy, runtime, CI/CD state mutation, or repo-local auth/gateway/deploy implementation.",
        )

    def test_deploy_core_routes_readiness_artifacts_to_exact_deploy_specialist(self) -> None:
        targets = [
            "/srv/bears/plugins/bears/assets/catalog/auth-gateway-deploy-readiness.v1.json",
            "/srv/bears/plugins/bears/scripts/auth_gateway_deploy_readiness.py",
            "/srv/bears/plugins/bears/tests/test_auth_gateway_deploy_readiness.py",
            "/srv/bears/dev/contracts/auth_gateway_deploy_core_contract.md",
            "/srv/bears/dev/docs/reference/auth-core-baseline-unblock.md",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "auth_gateway_deploy_core")
                self.assertEqual(packet["primary_role"], "bears-deploy-platform-engineer")
                self.assertIn("bears-platform-security-reviewer", packet["supporting_roles"])
                self.assertFalse(packet["decomposition_required"])

    def test_overlay_validator_routes_to_exact_validator_specialist(self) -> None:
        targets = [
            "/srv/bears/plugins/bears/scripts/validate_overlay.py",
            "/srv/bears/plugins/bears/tests/test_validate_overlay.py",
            "/srv/bears/plugins/bears/schemas/policy-packet.schema.json",
            "/srv/bears/plugins/bears/skills/bears-workflow-validate",
            "skills/bears-workflow-validate/SKILL.md",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "workflow_overlay_artifact_validator")
                self.assertEqual(
                    packet["primary_role"],
                    "bears-workflow-overlay-workflow-artifact-validator",
                )
                self.assertIn("bears-platform-security-reviewer", packet["supporting_roles"])
                self.assertFalse(packet["decomposition_required"])

    def test_workflow_overlay_core_routes_to_exact_specialist(self) -> None:
        targets = [
            "/srv/bears/plugins/bears/.codex-plugin/plugin.json",
            "/srv/bears/plugins/bears/skills/speckit-bears-flow/SKILL.md",
            "skills/speckit-bears-flow/SKILL.md",
            "/srv/bears/plugins/bears/skills/speckit-bears-research/SKILL.md",
            "/srv/bears/plugins/bears/skills/bears-blocker-eval/SKILL.md",
            "/srv/bears/plugins/bears/skills/bears-deploy-gate/SKILL.md",
            "/srv/bears/plugins/bears/skills/bears-governance-check/SKILL.md",
            "/srv/bears/plugins/bears/templates/research-template.md",
            "/srv/bears/plugins/bears/workflows/bears-sdd/workflow.yml",
            "workflows/bears-sdd/workflow.yml",
            "/srv/bears/plugins/bears/agents/bears-workflow-overlay-platform-engineer.toml",
            "plugins/bears/docs/reference/capability-governance-rules.md",
            "/srv/bears/plugins/bears/docs/reference/capability-governance-rules.md",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "workflow_overlay_core_plugin_surface")
                self.assertEqual(packet["primary_role"], "bears-workflow-overlay-platform-engineer")
                self.assertIn("bears-platform-security-reviewer", packet["supporting_roles"])
                self.assertIn("capability governance rules", packet["allowed_write_boundary"])
                self.assertFalse(packet["decomposition_required"])

    def test_routes_codex_health_to_exact_specialist(self) -> None:
        targets = [
            "/srv/bears/plugins/bears/agents/bears-codex-health-engineer.toml",
            "agents/bears-codex-health-engineer.toml",
            "/srv/bears/plugins/bears/skills/bears-codex-health",
            "/srv/bears/plugins/bears/skills/bears-codex-health/SKILL.md",
            "skills/bears-codex-health/SKILL.md",
            "codex-health",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "codex_health_diagnostics")
                self.assertEqual(packet["primary_role"], "bears-codex-health-engineer")
                self.assertIn("bears-platform-security-reviewer", packet["supporting_roles"])
                self.assertIn("raw logs", packet["trust_boundary"])
                self.assertIn("requires exact active-turn operator approval", packet["allowed_write_boundary"])
                self.assertFalse(packet["decomposition_required"])

    def test_routes_workflow_overlay_python_dev_tooling_to_exact_specialist(self) -> None:
        targets = [
            "/srv/bears/plugins/bears/pyproject.toml",
            "/srv/bears/plugins/bears/requirements-dev.txt",
            "pyproject.toml",
            "requirements-dev.txt",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "workflow_overlay_python_dev_tooling")
                self.assertEqual(packet["primary_role"], "bears-workflow-overlay-platform-engineer")
                self.assertIn("bears-platform-security-reviewer", packet["supporting_roles"])
                self.assertFalse(packet["decomposition_required"])

                audit_packet = platform_roles.audit_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(audit_packet["status"], "matched")
                self.assertTrue(audit_packet["implementation_handoff_allowed"])

    def test_routes_bears_platform_python_package_metadata_to_deploy_specialist(self) -> None:
        targets = [
            "/srv/bears/dev/platform/pyproject.toml",
            "dev/platform/pyproject.toml",
            "/srv/bears/dev/platform-worktrees/pr143-gateway-ci-activation-20260619T170808Z/pyproject.toml",
            "/srv/bears/.worktrees/bears-platform-gateway-authoring-20260615/pyproject.toml",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "bears_platform_python_package_metadata")
                self.assertEqual(packet["primary_role"], "bears-deploy-platform-engineer")
                self.assertIn("bears-platform-security-reviewer", packet["supporting_roles"])
                self.assertIn("no source code", packet["allowed_write_boundary"])
                self.assertFalse(packet["decomposition_required"])

                audit_packet = platform_roles.audit_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(audit_packet["status"], "matched")
                self.assertTrue(audit_packet["implementation_handoff_allowed"])

    def test_routes_platform_worktree_archive_manifests_only_to_storage_governor(self) -> None:
        targets = [
            "/srv/bears/dev/workspace/platform-worktrees/20260627T205030Z/MANIFEST.md",
            "dev/workspace/platform-worktrees/20260627T205030Z/MANIFEST.json",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "bears_platform_worktrees_archive")
                self.assertEqual(packet["primary_role"], "bears-platform-role-governor")
                self.assertIn("preserved checkout storage", packet["allowed_write_boundary"])

                audit_packet = platform_roles.audit_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(audit_packet["status"], "matched")
                self.assertTrue(audit_packet["implementation_handoff_allowed"])

    def test_rejects_bears_platform_worktree_source_and_test_paths_without_pyproject_mapping(self) -> None:
        targets = [
            "/srv/bears/dev/platform-worktrees/pr143-gateway-ci-activation-20260619T170808Z/src/bears_platform/auth/session.py",
            "/srv/bears/dev/platform-worktrees/pr143-gateway-ci-activation-20260619T170808Z/tests/test_provider_gateway_runtime.py",
            "/srv/bears/dev/workspace/platform-worktrees/pr143/src/bears_platform/auth/session.py",
            "/srv/bears/dev/workspace/platform-worktrees/pr143/tests/test_gateway.py",
            "/srv/bears/.worktrees/bears-platform-gateway-authoring-20260615/src/bears_platform/auth/session.py",
            "/srv/bears/.worktrees/bears-platform-gateway-authoring-20260615/tests/test_provider_gateway_runtime.py",
        ]
        for target in targets:
            for router in (platform_roles.route_target, platform_roles.audit_target):
                with self.subTest(target=target, router=router.__name__):
                    packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                    self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
                    self.assertEqual(packet["why_blocked"], "unmapped")
                    self.assertFalse(packet.get("implementation_handoff_allowed", False))
                    self.assertNotIn("primary_role", packet)
                    self.assertNotEqual(packet.get("concrete_part"), "bears_platform_python_package_metadata")

    def test_routes_kubernetes_data_platform_services_without_parent_fallback(self) -> None:
        service_targets = {
            "kubernetes-dev-platform-redis": "kubernetes_dev_platform_redis",
            "/srv/bears/kubernetes/manifests/bears-platform-stateful-backend-dev/base/redis-statefulset.yaml": (
                "kubernetes_dev_platform_redis"
            ),
            "kubernetes-dev-platform-taskiq": "kubernetes_dev_platform_taskiq",
            "/srv/bears/kubernetes/manifests/bears-platform-stateful-backend-dev/base/taskiq-worker-deployment.yaml": (
                "kubernetes_dev_platform_taskiq"
            ),
            "kubernetes-dev-platform-clickhouse": "kubernetes_dev_platform_clickhouse",
            "/srv/bears/kubernetes/manifests/bears-platform-stateful-backend-dev/base/clickhouse-statefulset.yaml": (
                "kubernetes_dev_platform_clickhouse"
            ),
            "kubernetes-dev-platform-postgresql": "kubernetes_dev_platform_postgresql",
            "/srv/bears/kubernetes/manifests/bears-platform-stateful-backend-dev/base/postgresql-statefulset.yaml": (
                "kubernetes_dev_platform_postgresql"
            ),
        }
        for target, expected_part in service_targets.items():
            for router in (platform_roles.route_target, platform_roles.audit_target):
                with self.subTest(target=target, router=router.__name__):
                    packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                    self.assertEqual(packet["status"], "matched")
                    self.assertEqual(packet["concrete_part"], expected_part)
                    self.assertEqual(packet["primary_role"], "bears-kubernetes-data-platform-engineer")
                    self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                    self.assertFalse(packet["decomposition_required"])
                    if router is platform_roles.audit_target:
                        self.assertTrue(packet["implementation_handoff_allowed"])

        package_root = "/srv/bears/kubernetes/manifests/bears-platform-stateful-backend-dev"
        for router in (platform_roles.route_target, platform_roles.audit_target):
            with self.subTest(target=package_root, router=router.__name__):
                packet = router(self.catalog, package_root, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "kubernetes_deploy_core")
                self.assertEqual(packet["primary_role"], "bears-deploy-platform-engineer")
                if router is platform_roles.audit_target:
                    self.assertTrue(packet["implementation_handoff_allowed"])

        parent_targets = [
            "/srv/bears/kubernetes/manifests/bears-platform-stateful-backend-dev/base",
            "/srv/bears/kubernetes/manifests/bears-platform-stateful-backend-dev/base/unknown.yaml",
        ]
        for target in parent_targets:
            for router in (platform_roles.route_target, platform_roles.audit_target):
                with self.subTest(target=target, router=router.__name__):
                    packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                    self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
                    self.assertEqual(packet["why_blocked"], "parent_only")
                    self.assertEqual(
                        packet.get("matched_platform_part"),
                        "kubernetes_dev_platform_stateful_backend_group",
                    )
                    self.assertFalse(packet.get("implementation_handoff_allowed", False))
                    self.assertNotIn("primary_role", packet)

    def test_routes_git_discipline_to_platform_role_governor(self) -> None:
        targets = [
            "/srv/bears/plugins/bears/scripts/git_discipline.py",
            "scripts/git_discipline.py",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "git_discipline")
                self.assertEqual(packet["primary_role"], "bears-platform-role-governor")
                self.assertIn("bears-platform-security-reviewer", packet["supporting_roles"])
                self.assertFalse(packet["decomposition_required"])

                audit_packet = platform_roles.audit_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(audit_packet["status"], "matched")
                self.assertTrue(audit_packet["implementation_handoff_allowed"])

    def test_routes_agent_workflow_state_schemas_and_plugin_gitignore_to_workflow_orchestrator(self) -> None:
        targets = [
            "/srv/bears/plugins/bears/assets/schemas/agent-workflow-state.v1.schema.json",
            "/srv/bears/plugins/bears/assets/schemas/agent-workflow-worker-state.v1.schema.json",
            "/srv/bears/plugins/bears/.gitignore",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "agent_workflow_map")
                self.assertEqual(packet["primary_role"], "bears-development-workflow-orchestrator")
                self.assertIn("bears-platform-security-reviewer", packet["supporting_roles"])
                self.assertFalse(packet["decomposition_required"])

                audit_packet = platform_roles.audit_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(audit_packet["status"], "matched")
                self.assertTrue(audit_packet["implementation_handoff_allowed"])

    def test_routes_plugin_validate_workflow_to_deploy_specialist(self) -> None:
        targets = [
            "/srv/bears/plugins/bears/.github/workflows/validate.yml",
            ".github/workflows/validate.yml",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "workflow_overlay_validation_ci_workflow")
                self.assertEqual(packet["primary_role"], "bears-deploy-platform-engineer")
                self.assertIn("bears-platform-security-reviewer", packet["supporting_roles"])
                self.assertIn("python3 scripts/agent_github_dev_cd.py validate", packet["validation_required"])
                self.assertIn(
                    "python3 scripts/ci_requirements.py validate-workflow --workflow .github/workflows/validate.yml --catalog assets/catalog/ci-requirements.v1.json",
                    packet["validation_required"],
                )
                self.assertIn(
                    "python3 scripts/test_selection.py run --changed-file .github/workflows/validate.yml --tier fast",
                    packet["validation_required"],
                )
                self.assertFalse(packet["decomposition_required"])

                audit_packet = platform_roles.audit_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(audit_packet["status"], "matched")
                self.assertTrue(audit_packet["implementation_handoff_allowed"])

    def test_routes_exact_github_actions_access_setting_to_settings_governor(self) -> None:
        targets = [
            "/repos/BearsCLOUD/bears_plugin/actions/permissions/access",
            "repos/BearsCLOUD/bears_plugin/actions/permissions/access",
            "https://api.github.com/repos/BearsCLOUD/bears_plugin/actions/permissions/access",
        ]
        for target in targets:
            for router in (platform_roles.route_target, platform_roles.audit_target):
                with self.subTest(target=target, router=router.__name__):
                    packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                    self.assertEqual(packet["status"], "matched")
                    self.assertEqual(
                        packet["concrete_part"],
                        "github_actions_access_setting_bears_codex_workflow_plugin",
                    )
                    self.assertEqual(packet["primary_role"], "bears-github-actions-access-settings-governor")
                    self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                    self.assertIn("access_level=user", packet["allowed_write_boundary"])
                    self.assertIn("rollback access_level=none", packet["allowed_write_boundary"])
                    self.assertIn("no branch protection", packet["allowed_write_boundary"])
                    self.assertIn("user-owned private repository", packet["trust_boundary"])
                    self.assertIn("external GitHub settings mutation", packet["trust_boundary"])
                    self.assertIn("access_level=user", packet["trust_boundary"])
                    self.assertIn("rollback access_level=none", packet["trust_boundary"])
                    self.assertTrue(any("access_level=user" in trigger or "user-access" in trigger for trigger in packet["reviewer_triggers"]))
                    self.assertNotIn("access_level=organization", packet["allowed_write_boundary"])
                    self.assertNotIn("org-access", packet["allowed_write_boundary"])
                    self.assertTrue(any("rollback access_level=none" in trigger for trigger in packet["reviewer_triggers"]))
                    self.assertFalse(packet["decomposition_required"])
                    if router is platform_roles.audit_target:
                        self.assertTrue(packet["implementation_handoff_allowed"])

    def test_nearby_github_settings_endpoints_remain_blocked(self) -> None:
        targets = [
            "/repos/BearsCLOUD/bears_plugin/actions/permissions",
            "/repos/BearsCLOUD/bears_plugin/actions/permissions/workflow",
            "/repos/BearsCLOUD/bears_plugin/actions/permissions/selected-actions",
            "/repos/BearsCLOUD/bears_plugin/actions/permissions/access/child",
            "/repos/BearsCLOUD/bears_plugin/branches/main/protection",
            "/repos/BearsCLOUD/bears_plugin/settings",
        ]
        for target in targets:
            for router in (platform_roles.route_target, platform_roles.audit_target):
                with self.subTest(target=target, router=router.__name__):
                    packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                    self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
                    self.assertEqual(packet["why_blocked"], "unmapped")
                    self.assertNotIn("primary_role", packet)
                    if router is platform_roles.audit_target:
                        self.assertFalse(packet["implementation_handoff_allowed"])

    def test_plugin_root_audit_blocks_broad_root_handoff(self) -> None:
        audit_packet = platform_roles.audit_target(self.catalog, "plugins/bears", plugin_root=PLUGIN_ROOT)
        self.assertEqual(audit_packet["status"], "ROLE_COVERAGE_BLOCKER")
        self.assertEqual(audit_packet["why_blocked"], "parent_only")
        self.assertEqual(audit_packet["matched_platform_part"], "bears_plugin")
        self.assertFalse(audit_packet["implementation_handoff_allowed"])
        self.assertTrue(audit_packet["decomposition_required"])
        self.assertIn(
            "bears-platform-security-reviewer",
            audit_packet["independent_control_audit"]["attached_reviewers"],
        )

    def test_plugin_root_children_still_require_narrower_exact_parts(self) -> None:
        packet = platform_roles.route_target(self.catalog, "plugins/bears", plugin_root=PLUGIN_ROOT)
        self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
        self.assertEqual(packet["why_blocked"], "parent_only")
        self.assertEqual(packet["matched_platform_part"], "bears_plugin")
        child_packet = platform_roles.route_target(
            self.catalog,
            "/srv/bears/plugins/bears/workflows/unmapped-child/workflow.yml",
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(child_packet["status"], "ROLE_COVERAGE_BLOCKER")
        self.assertEqual(child_packet["why_blocked"], "parent_only")
        self.assertTrue(child_packet["decomposition_required"])

    def test_broad_plugin_root_cannot_substitute_for_exact_child_surfaces(self) -> None:
        root_packet = platform_roles.audit_target(self.catalog, "plugins/bears", plugin_root=PLUGIN_ROOT)
        self.assertEqual(root_packet["status"], "ROLE_COVERAGE_BLOCKER")
        self.assertFalse(root_packet["implementation_handoff_allowed"])

        cases = {
            "/srv/bears/plugins/bears/.github/workflows/validate.yml": (
                "workflow_overlay_validation_ci_workflow",
                "bears-deploy-platform-engineer",
            ),
            "/srv/bears/plugins/bears/scripts/agent_github_dev_cd.py": (
                "agent_github_dev_cd_flow",
                "bears-deploy-platform-engineer",
            ),
            "/srv/bears/plugins/bears/scripts/git_discipline.py": (
                "git_discipline",
                "bears-platform-role-governor",
            ),
            "/srv/bears/plugins/bears/scripts/roadmap_control.py": (
                "roadmap_control",
                "bears-workflow-overlay-platform-engineer",
            ),
            "/srv/bears/plugins/bears/assets/catalog/plugin-governance-language-policy.v1.json": (
                "platform_role_governance",
                "bears-platform-role-governor",
            ),
            "/srv/bears/plugins/bears/assets/catalog/plugin-constitution.v1.json": (
                "plugin_constitution_governance",
                "bears-plugin-constitution-governor",
            ),
            "/srv/bears/plugins/bears/assets/catalog/telegram-runtime-readiness.v1.json": (
                "telegram_runtime_readiness_catalog",
                "bears-telegram-platform-engineer",
            ),
            "/srv/bears/plugins/bears/scripts/skill_catalog.py": (
                "workflow_overlay_skill_inventory",
                "bears-workflow-overlay-platform-engineer",
            ),
        }
        for target, (expected_part, expected_role) in cases.items():
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], expected_part)
                self.assertEqual(packet["primary_role"], expected_role)

    def test_routes_exact_github_branch_protection_required_checks_to_settings_governor(self) -> None:
        targets = [
            "github_branch_protection_settings_bears_platform",
            "github-branch-protection-settings-bears-platform",
            "/repos/BearsCLOUD/bears-platform/branches/main/protection/required_status_checks",
            "repos/BearsCLOUD/bears-platform/branches/main/protection/required_status_checks",
            "https://api.github.com/repos/BearsCLOUD/bears-platform/branches/main/protection/required_status_checks",
        ]
        required_checks = [
            "gateway-required-checks / role-gate",
            "gateway-required-checks / gateway-auth-pytest",
            "gateway-required-checks / diff-check",
        ]
        for target in targets:
            for router in (platform_roles.route_target, platform_roles.audit_target):
                with self.subTest(target=target, router=router.__name__):
                    packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                    self.assertEqual(packet["status"], "matched")
                    self.assertEqual(packet["concrete_part"], "github_branch_protection_settings_bears_platform")
                    self.assertEqual(packet["primary_role"], "bears-github-branch-protection-settings-governor")
                    self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                    self.assertIn("required_status_checks", packet["allowed_write_boundary"])
                    self.assertIn("explicit issue #65 approval packet", packet["allowed_write_boundary"])
                    self.assertIn("owner/repo BearsCLOUD/bears-platform", packet["allowed_write_boundary"])
                    self.assertIn("branch main", packet["allowed_write_boundary"])
                    self.assertIn("before/after", packet["allowed_write_boundary"])
                    self.assertIn("rollback", packet["allowed_write_boundary"])
                    self.assertIn("actor/token permission class without token exposure", packet["allowed_write_boundary"])
                    for check in required_checks:
                        self.assertIn(check, packet["allowed_write_boundary"])
                    self.assertIn("merge eligibility", packet["trust_boundary"])
                    self.assertIn("Live GitHub mutation remains blocked", packet["trust_boundary"])
                    self.assertTrue(any("required-status-check" in trigger for trigger in packet["reviewer_triggers"]))
                    self.assertFalse(packet["decomposition_required"])
                    if router is platform_roles.audit_target:
                        self.assertTrue(packet["implementation_handoff_allowed"])

    def test_nearby_github_branch_protection_endpoints_remain_blocked(self) -> None:
        targets = [
            "/repos/BearsCLOUD/bears-platform/branches/main/protection",
            "/repos/BearsCLOUD/bears-platform/branches/main/protection/required_status_checks/contexts",
            "/repos/BearsCLOUD/bears-platform/branches/develop/protection/required_status_checks",
            "/repos/BearsCLOUD/bears-platform/branches/*/protection/required_status_checks",
            "/repos/BearsCLOUD/other-repo/branches/main/protection/required_status_checks",
            "/repos/OtherOrg/bears-platform/branches/main/protection/required_status_checks",
            "/repos/BearsCLOUD/bears-platform/settings",
            "/repos/BearsCLOUD/bears-platform/secrets/actions",
            "/repos/BearsCLOUD/bears-platform/actions/variables",
            "/repos/BearsCLOUD/bears-platform/collaborators/user",
            "/repos/BearsCLOUD/bears-platform/teams/team-slug",
            "/repos/BearsCLOUD/bears-platform/hooks",
            "/repos/BearsCLOUD/bears-platform/environments/prod",
            "/repos/BearsCLOUD/bears-platform/keys",
            "/repos/BearsCLOUD/bears-platform/installations",
            "/repos/BearsCLOUD/bears-platform/actions/permissions",
            "/repos/BearsCLOUD/bears-platform/actions/permissions/access",
            "/orgs/BearsCLOUD/actions/permissions",
            "/repos/BearsCLOUD/bears_plugin/branches/main/protection",
        ]
        for target in targets:
            for router in (platform_roles.route_target, platform_roles.audit_target):
                with self.subTest(target=target, router=router.__name__):
                    packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                    self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
                    self.assertEqual(packet["why_blocked"], "unmapped")
                    self.assertNotIn("primary_role", packet)
                    if router is platform_roles.audit_target:
                        self.assertFalse(packet["implementation_handoff_allowed"])

    def test_plugin_constitution_capability_routes_to_exact_constitution_role(self) -> None:
        targets = [
            "/srv/bears/plugins/bears/capabilities/plugin_constitution",
            "/srv/bears/plugins/bears/capabilities/plugin_constitution/capability.json",
            "capabilities/plugin_constitution/AGENTS.md",
            "capabilities/plugin_constitution/README.md",
            "capabilities/plugin_constitution/__init__.py",
            "capabilities/plugin_constitution/fixtures/fail/catalog.invalid.json",
            "capabilities/plugin_constitution/fixtures/pass/catalog.valid.json",
            "capabilities/plugin_constitution/schemas/validation-result.schema.json",
            "capabilities/plugin_constitution/scripts/validate.py",
            "capabilities/plugin_constitution/tests/test_validate.py",
        ]
        for target in targets:
            for router in (platform_roles.route_target, platform_roles.audit_target):
                with self.subTest(target=target, router=router.__name__):
                    packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                    self.assertEqual(packet["status"], "matched")
                    self.assertEqual(packet["concrete_part"], "plugin_constitution_governance")
                    self.assertEqual(packet["primary_role"], "bears-plugin-constitution-governor")
                    self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                    self.assertIn(
                        "/srv/bears/plugins/bears/capabilities/plugin_constitution/**",
                        packet["allowed_write_boundary"],
                    )
                    if router is platform_roles.audit_target:
                        self.assertTrue(packet["implementation_handoff_allowed"])

    def test_plugin_parent_paths_do_not_authorize_capability_broad_handoff(self) -> None:
        relative_root = platform_roles.audit_target(self.catalog, "plugins/bears", plugin_root=PLUGIN_ROOT)
        self.assertEqual(relative_root["status"], "ROLE_COVERAGE_BLOCKER")
        self.assertEqual(relative_root["why_blocked"], "parent_only")
        self.assertFalse(relative_root["implementation_handoff_allowed"])

        absolute_root = platform_roles.audit_target(self.catalog, "/srv/bears/plugins/bears", plugin_root=PLUGIN_ROOT)
        self.assertEqual(absolute_root["status"], "matched")
        self.assertEqual(absolute_root["concrete_part"], "workspace_root_submodule_gitlinks")
        self.assertIn("no child working-tree files inside either submodule", absolute_root["allowed_write_boundary"])
        self.assertNotIn("capabilities/plugin_constitution", absolute_root["allowed_write_boundary"])

        capability_parent = platform_roles.audit_target(
            self.catalog,
            "/srv/bears/plugins/bears/capabilities",
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(capability_parent["status"], "ROLE_COVERAGE_BLOCKER")
        self.assertEqual(capability_parent["why_blocked"], "parent_only")
        self.assertFalse(capability_parent["implementation_handoff_allowed"])

    def test_routes_capability_layout_inventory_to_exact_workflow_specialist(self) -> None:
        targets = [
            "/srv/bears/plugins/bears/capabilities/README.md",
            "/srv/bears/plugins/bears/capabilities/capability.schema.json",
            "/srv/bears/plugins/bears/capabilities/inventory.v1.json",
            "/srv/bears/plugins/bears/scripts/capability_layout.py",
            "/srv/bears/plugins/bears/tests/test_capability_layout.py",
            "tests/test_capability_environment_packets.py",
            "tests/test_capability_restricted_data.py",
            "tests/test_capability_hook_claims.py",
            "tests/test_capability_reviewer_lanes.py",
            "tests/test_capability_agent_registration.py",
            "tests/test_capability_optimization_lanes.py",
            "tests/test_capability_effective_config.py",
            "tests/test_capability_performance_lanes.py",
            "tests/test_capability_offload_surfaces.py",
            "tests/test_capability_programmatic_surfaces.py",
            "tests/test_capability_rule_coverage.py",
            "tests/test_capability_refactor_gate.py",
            "/srv/bears/plugins/bears/tests/fixtures/capability_layout/mutations.v1.json",
            "tests/fixtures/capability_layout/environment_packets",
            "tests/fixtures/capability_layout/parity",
            "tests/fixtures/capability_layout/restricted_data",
            "tests/fixtures/capability_layout/p1_06_08_mutations.v1.json",
            "tests/fixtures/capability_layout/optimization_lanes",
            "tests/fixtures/capability_layout/effective_config",
            "tests/fixtures/capability_layout/performance_lanes",
            "tests/fixtures/capability_layout/offload_surfaces",
            "tests/fixtures/capability_layout/programmatic_surfaces",
            "tests/fixtures/capability_layout/rule_coverage",
            "tests/fixtures/capability_layout/refactor_gate",
        ]
        for target in targets:
            for router in (platform_roles.route_target, platform_roles.audit_target):
                with self.subTest(target=target, router=router.__name__):
                    packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                    self.assertEqual(packet["status"], "matched")
                    self.assertEqual(packet["concrete_part"], "capability_layout_inventory")
                    self.assertEqual(packet["primary_role"], "bears-workflow-overlay-platform-engineer")
                    self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                    self.assertIn("capability layout and inventory files", packet["allowed_write_boundary"])
                    self.assertIn("exact P1-06..P1-17 capability test modules", packet["allowed_write_boundary"])
                    self.assertNotIn("/srv/bears/plugins/bears/capabilities/**", packet["allowed_write_boundary"])
                    self.assertNotIn("/srv/bears/plugins/bears/tests/**", packet["allowed_write_boundary"])
                    self.assertNotIn("/srv/bears/plugins/bears/tests/fixtures/**", packet["allowed_write_boundary"])
                    self.assertFalse(packet["decomposition_required"])
                    if router is platform_roles.audit_target:
                        self.assertTrue(packet["implementation_handoff_allowed"])

        broad_targets = {
            "tests/": "unmapped",
            "tests/fixtures": "unmapped",
            "tests/fixtures/capability_layout": "unmapped",
            "/srv/bears/plugins/bears/tests": "parent_only",
            "/srv/bears/plugins/bears/tests/fixtures": "parent_only",
            "/srv/bears/plugins/bears/tests/fixtures/capability_layout": "parent_only",
        }
        for broad_target, why_blocked in broad_targets.items():
            for router in (platform_roles.route_target, platform_roles.audit_target):
                with self.subTest(broad_target=broad_target, router=router.__name__):
                    packet = router(self.catalog, broad_target, plugin_root=PLUGIN_ROOT)
                    self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
                    self.assertEqual(packet["why_blocked"], why_blocked)
                    self.assertNotIn("primary_role", packet)
                    if router is platform_roles.audit_target:
                        self.assertFalse(packet["implementation_handoff_allowed"])

    def test_routes_subagent_orchestration_fixtures_to_exact_subagent_specialist(self) -> None:
        targets = [
            "/srv/bears/plugins/bears/tests/fixtures/subagent_orchestration_policy",
            "/srv/bears/plugins/bears/tests/fixtures/subagent_orchestration_policy/*.json",
        ]
        for target in targets:
            for router in (platform_roles.route_target, platform_roles.audit_target):
                with self.subTest(target=target, router=router.__name__):
                    packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                    self.assertEqual(packet["status"], "matched")
                    self.assertEqual(packet["concrete_part"], "subagent_orchestration_policy")
                    self.assertEqual(packet["primary_role"], "bears-subagent-orchestration-engineer")
                    self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                    self.assertIn("tests/fixtures/subagent_orchestration_policy/**", packet["allowed_write_boundary"])
                    self.assertFalse(packet["decomposition_required"])
                    if router is platform_roles.audit_target:
                        self.assertTrue(packet["implementation_handoff_allowed"])


    def test_routes_workflow_overlay_skill_inventory_to_exact_specialist(self) -> None:
        targets = [
            "/srv/bears/plugins/bears/assets/catalog/plugin-skill-catalog.v1.json",
            "/srv/bears/plugins/bears/scripts/skill_catalog.py",
            "/srv/bears/plugins/bears/tests/test_skill_catalog.py",
            "/srv/bears/plugins/bears/docs/generated/README.skill-inventory.md",
            "/srv/bears/plugins/bears/docs/generated/SPEC.skill-inventory.md",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "workflow_overlay_skill_inventory")
                self.assertEqual(packet["primary_role"], "bears-workflow-overlay-platform-engineer")
                self.assertIn("bears-platform-security-reviewer", packet["supporting_roles"])
                self.assertFalse(packet["decomposition_required"])

    def test_routes_roadmap_control_to_exact_specialist(self) -> None:
        targets = [
            "/srv/bears/plugins/bears/assets/catalog/roadmap-control.v1.json",
            "/srv/bears/plugins/bears/scripts/roadmap_control.py",
            "/srv/bears/plugins/bears/tests/test_roadmap_control.py",
            "/srv/bears/plugins/bears/docs/reference/roadmap-control.md",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "roadmap_control")
                self.assertEqual(packet["primary_role"], "bears-workflow-overlay-platform-engineer")
                self.assertIn("bears-platform-security-reviewer", packet["supporting_roles"])
                self.assertFalse(packet["decomposition_required"])

                audit_packet = platform_roles.audit_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(audit_packet["status"], "matched")
                self.assertTrue(audit_packet["implementation_handoff_allowed"])

    def test_routes_workflow_backlog_lane_doc_to_exact_specialist(self) -> None:
        targets = [
            "docs/reference/workflow-backlog-lane.md",
            "/srv/bears/plugins/bears/docs/reference/workflow-backlog-lane.md",
        ]
        for target in targets:
            for router in (platform_roles.route_target, platform_roles.audit_target):
                with self.subTest(target=target, router=router.__name__):
                    packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                    self.assertEqual(packet["status"], "matched")
                    self.assertEqual(packet["concrete_part"], "workflow_backlog_lane")
                    self.assertEqual(packet["primary_role"], "bears-workflow-overlay-platform-engineer")
                    self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                    self.assertIn("operator-approved and local-commit-owned", packet["trust_boundary"])
                    self.assertIn("Only docs/reference/workflow-backlog-lane.md", packet["allowed_write_boundary"])
                    self.assertFalse(packet["decomposition_required"])
                    if router is platform_roles.audit_target:
                        self.assertTrue(packet["implementation_handoff_allowed"])

    def test_child_under_group_blocks(self) -> None:
        packet = platform_roles.route_target(
            self.catalog,
            "/srv/bears/plugins/bears/workflows/unmapped-child/workflow.yml",
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
        self.assertEqual(packet["why_blocked"], "parent_only")
        self.assertTrue(packet["decomposition_required"])

    def test_parent_project_group_blocks(self) -> None:
        for target in ("/srv/bears/legacy/seller/apps", "/srv/bears/projects/seller/apps"):
            with self.subTest(target=target):
                packet = platform_roles.route_target(
                    self.catalog,
                    target,
                    plugin_root=PLUGIN_ROOT,
                )
                self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
                self.assertEqual(packet["why_blocked"], "parent_only")

    def test_broad_projects_root_still_blocks(self) -> None:
        packet = platform_roles.route_target(
            self.catalog,
            "/srv/bears/projects",
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
        self.assertEqual(packet["why_blocked"], "parent_only")
        self.assertTrue(packet["decomposition_required"])

    def test_legacy_telegram_workflow_plugin_root_stays_blocked(self) -> None:
        packet = platform_roles.route_target(
            self.catalog,
            "/srv/bears/plugins/bears-telegram-workflow",
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
        self.assertEqual(packet["why_blocked"], "unmapped")

    def test_unknown_target_blocks(self) -> None:
        packet = platform_roles.route_target(self.catalog, "totally-unknown-platform-surface", plugin_root=PLUGIN_ROOT)
        self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
        self.assertEqual(packet["why_blocked"], "unknown")

    def test_unmapped_target_blocks(self) -> None:
        packet = platform_roles.route_target(
            self.catalog,
            "/srv/bears/projects/seller/apps/unknown_future_app",
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
        self.assertEqual(packet["why_blocked"], "unmapped")

    def test_missing_role_artifact_blocks(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        for part in catalog["platform_parts"]:
            if part["name"] == "platform_role_governance":
                part["required_role"] = "bears-missing-role"
                break
        packet = platform_roles.route_target(
            catalog,
            "/srv/bears/plugins/bears/assets/catalog/platform-role-catalog.v1.json",
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
        self.assertEqual(packet["why_blocked"], "missing_role")

    def test_invalid_broad_role_blocks(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        for part in catalog["platform_parts"]:
            if part["name"] == "platform_role_governance":
                part["required_role"] = "bears-workflow-overlay-controller"
                break
        packet = platform_roles.route_target(
            catalog,
            "/srv/bears/plugins/bears/assets/catalog/platform-role-catalog.v1.json",
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
        self.assertEqual(packet["why_blocked"], "invalid_broad_role")

    def test_ambiguous_owner_blocks(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["platform_parts"].append(
            {
                "name": "platform_role_governance_shadow",
                "aliases": ["/srv/bears/plugins/bears/assets/catalog/platform-role-catalog.v1.json"],
                "group": "workflow",
                "required_role": "bears-goal-prompt-generator",
                "role_required": True,
                "no_role_policy": "blocker",
                "source": "/srv/bears/plugins/bears/README.md",
                "part_kind": "concrete",
                "write_roots": [],
                "concrete_scope": "Shadow ownership for test only.",
                "allowed_write_boundary": "test only",
                "trust_boundary": "test only",
                "required_validations": ["test only"],
                "supporting_roles": [],
                "reviewer_triggers": [],
                "decomposition_required": False,
            }
        )
        packet = platform_roles.route_target(
            catalog,
            "/srv/bears/plugins/bears/assets/catalog/platform-role-catalog.v1.json",
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
        self.assertEqual(packet["why_blocked"], "ambiguous_owner")

    def test_alias_path_drift_cannot_widen_coverage(self) -> None:
        packet = platform_roles.route_target(self.catalog, "/srv/bears/plugins/bears-shadow", plugin_root=PLUGIN_ROOT)
        self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
        self.assertEqual(packet["why_blocked"], "unmapped")

    def test_exact_gitlab_aliases_do_not_widen_host_coverage(self) -> None:
        packet = platform_roles.route_target(
            self.catalog,
            "https://bears.gitlab.yandexcloud.net/bears/unknown_future_app",
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
        self.assertEqual(packet["why_blocked"], "unmapped")

    def test_routes_session_worker_runtime_to_exact_specialist(self) -> None:
        packet = platform_roles.route_target(
            self.catalog,
            "/srv/bears/plugins/bears/assets/catalog/session-workers-runtime.v1.json",
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(packet["status"], "matched")
        self.assertEqual(packet["primary_role"], "bears-session-worker-runtime-engineer")

    def test_routes_codex_workspace_configuration_surfaces_to_exact_specialist(self) -> None:
        targets = [
            "/srv/bears/.codex/config.toml",
            "/srv/bears/.codex/bears_model_instructions.md",
            "/srv/bears/.codex/agents/bears-worker.toml",
            "/srv/bears/.codex/agents/bears-orchestrator.toml",
            "/srv/bears/local-agent-runner.yaml",
            "/srv/bears/.agents/plugins/marketplace.json",
            "tests/test_plugin_marketplace.py",
            "/srv/bears/plugins/bears/tests/test_plugin_marketplace.py",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "codex_workspace_configuration")
                self.assertEqual(packet["primary_role"], "bears-codex-workspace-config-engineer")
                self.assertIn("bears-platform-security-reviewer", packet["supporting_roles"])

    def test_routes_agent_orchestrator_github_autoscan_to_exact_specialist(self) -> None:
        targets = [
            "/srv/bears/local-agent-runner",
            "/srv/bears/local-agent-runner/AGENTS.md",
            "/srv/bears/control-plane/agent-github-issues",
            "/srv/bears/control-plane/agent-github-issues/scan_and_spawn.py",
            "/srv/bears/control-plane/AGENTS.md",
            "/srv/bears/control-plane/README.md",
            "/srv/bears/control-plane/workspace-control/supervisor.py",
            "/srv/bears/control-plane/workspace-control/Dockerfile",
            "/srv/bears/control-plane/workspace-control/healthcheck.py",
            "/srv/bears/control-plane/workspace-control/mcp_selector.py",
            "/srv/bears/control-plane/workspace-control/admin_adapter/app.py",
            "/srv/bears/specs/009-agent-github-issue-autoscan/spec.md",
            "agents/bears-orchestrator.toml",
            "/srv/bears/plugins/bears/agents/bears-orchestrator.toml",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "agent_orchestrator_github_autoscan")
                self.assertEqual(packet["primary_role"], "bears-codex-workspace-config-engineer")
                self.assertIn("bears-platform-security-reviewer", packet["supporting_roles"])

    def test_routes_agent_orchestrator_codex_session_watchdog_to_exact_specialist(self) -> None:
        targets = [
            "/srv/bears/control-plane/agent-codex-watchdog",
            "/srv/bears/control-plane/agent-codex-watchdog/watchdog.py",
            "/srv/bears/control-plane/agent-codex-watchdog/config.json",
            "/srv/bears/specs/010-agent-codex-session-watchdog/spec.md",
            "/srv/bears/specs/010-agent-codex-session-watchdog/governance/role-coverage.json",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "agent_orchestrator_codex_session_watchdog")
                self.assertEqual(packet["primary_role"], "bears-codex-workspace-config-engineer")
                self.assertIn("bears-platform-security-reviewer", packet["supporting_roles"])
                self.assertIn("BearsCLOUD/bears_plugin", packet["trust_boundary"])
                self.assertIn("dry-run performs no mutation", packet["trust_boundary"])

    def test_unmapped_child_under_codex_workspace_configuration_still_blocks(self) -> None:
        packet = platform_roles.route_target(
            self.catalog,
            "/srv/bears/.codex/tmp/unmapped-child",
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
        self.assertEqual(packet["why_blocked"], "unmapped")

    def test_routes_workspace_governance_canonical_plugin_docs_to_governor(self) -> None:
        targets = [
            "/srv/bears/.gitignore",
            "/srv/bears/AGENTS.md",
            "/srv/bears/dev/AGENTS.md",
            "/srv/bears/.gitmodules",
            "/srv/bears/dev",
            "/srv/bears/dev/WORKSPACE.md",
            "/srv/bears/dev/contracts/repository_creation_gate.md",
            "/srv/bears/dev/contracts/platform_role_gate_contract.md",
            "/srv/bears/dev/docs/reference/telegram-surface-map.md",
            "/srv/bears/contracts/workspace_control_contract.md",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "workspace_governance_canonical_plugin_docs")
                self.assertEqual(packet["primary_role"], "bears-platform-role-governor")
                self.assertIn("bears-platform-security-reviewer", packet["supporting_roles"])

    def test_top_level_projects_docs_are_blocked_compatibility_references(self) -> None:
        targets = [
            "/srv/bears/projects/AGENTS.md",
            "/srv/bears/projects/README.md",
            "/srv/bears/projects/contracts/README.md",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
                self.assertEqual(packet["why_blocked"], "parent_only")
                self.assertTrue(packet["decomposition_required"])
                self.assertNotIn("primary_role", packet)

    def test_dev_core_group_roots_require_narrow_layer(self) -> None:
        targets = [
            "/srv/bears/dev/control",
            "/srv/bears/dev/products",
            "/srv/bears/dev/quality",
            "/srv/bears/dev/infrastructure",
            "/srv/bears/dev/ops",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
                self.assertEqual(packet["why_blocked"], "parent_only")
                self.assertTrue(packet["decomposition_required"])

    def test_routes_dev_core_migration_lanes_to_exact_roles(self) -> None:
        cases = {
            "kube": ("kubernetes_deploy_core", "bears-deploy-platform-engineer"),
            "/srv/bears/kubernetes/contracts/kubernetes_deploy_core_contract.md": (
                "kubernetes_deploy_core",
                "bears-deploy-platform-engineer",
            ),
            "BearsCLOUD/bears-infra": (
                "kubernetes_deploy_core",
                "bears-deploy-platform-engineer",
            ),
            "bears-infra": (
                "kubernetes_deploy_core",
                "bears-deploy-platform-engineer",
            ),
            "android-emulator": (
                "android_emulator_platform_225",
                "bears-android-emulator-platform-engineer",
            ),
            "/srv/bears/dev/platform/android-emulator": (
                "android_emulator_platform_225",
                "bears-android-emulator-platform-engineer",
            ),
            "sentry": (
                "sentry_observability_226",
                "bears-observability-platform-engineer",
            ),
            "sentry-runtime-plugin": (
                "sentry_observability_226",
                "bears-observability-platform-engineer",
            ),
            "BearsCLOUD/bears-sentry-runtime-plugin": (
                "sentry_observability_226",
                "bears-observability-platform-engineer",
            ),
            "/srv/bears/runtime-plugins/sentry": (
                "sentry_observability_226",
                "bears-observability-platform-engineer",
            ),
            "/srv/bears/dev/quality/sentry-observability": (
                "sentry_observability_226",
                "bears-observability-platform-engineer",
            ),
            "/srv/bears/dev/app/theants": (
                "theants_product_dev_layer",
                "bears-product-app-zone-engineer",
            ),
            "/srv/bears/projects/theants": (
                "theants_product_dev_layer",
                "bears-product-app-zone-engineer",
            ),
            "/srv/bears/dev/quality/e2e": (
                "theants_quality_e2e_layer",
                "bears-analytics-quality-engineer",
            ),
            "/srv/bears/dev/ops/runbooks": (
                "theants_ops_runbooks_layer",
                "bears-ops-runbook-engineer",
            ),
            "/srv/bears/dev/control/provenance": (
                "theants_control_provenance_layer",
                "bears-platform-role-governor",
            ),
            "current-infra-runtime": (
                "current_infra_runtime_future_kube_lane",
                "bears-deploy-platform-engineer",
            ),
        }
        for target, (expected_part, expected_role) in cases.items():
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], expected_part)
                self.assertEqual(packet["primary_role"], expected_role)
                self.assertFalse(packet["decomposition_required"])

    def test_routes_backend_continuation_labels_to_exact_roles(self) -> None:
        cases = {
            "users/auth_core": ("auth_core", "bears-auth-platform-engineer"),
            "kubernetes-duplicate-plane-readiness": (
                "kubernetes_deploy_core",
                "bears-deploy-platform-engineer",
            ),
            "gitlab-backend-inventory-handoff": (
                "bears_platform_migration_docs",
                "bears-docs-maintainer",
            ),
        }
        for target, (expected_part, expected_role) in cases.items():
            for router in (platform_roles.route_target, platform_roles.audit_target):
                with self.subTest(target=target, router=router.__name__):
                    packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                    self.assertEqual(packet["status"], "matched")
                    self.assertEqual(packet["concrete_part"], expected_part)
                    self.assertEqual(packet["primary_role"], expected_role)
                    self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                    self.assertFalse(packet["decomposition_required"])
                    if router is platform_roles.audit_target:
                        self.assertTrue(packet["implementation_handoff_allowed"])

    def test_routes_telegram_dev_core_platform_aliases_to_exact_role(self) -> None:
        targets = [
            "/srv/bears/dev/platform/telegram",
            "dev/platform/telegram",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "telegram_platform_dev_layer")
                self.assertEqual(packet["primary_role"], "bears-telegram-platform-engineer")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertFalse(packet["decomposition_required"])

    def test_routes_bears_platform_repo_root_aliases_to_governor(self) -> None:
        targets = [
            "bears-platform",
            "BearsCLOUD/bears-platform",
            "https://github.com/BearsCLOUD/bears-platform",
            "git@github.com:BearsCLOUD/bears-platform.git",
            "/srv/bears/dev/platform",
            "dev/platform",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "bears_platform_repo_root")
                self.assertEqual(packet["primary_role"], "bears-platform-role-governor")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertFalse(packet["decomposition_required"])

    def test_routes_platform_migration_docs_to_docs_maintainer(self) -> None:
        target = "/srv/bears/dev/platform/docs/migration/platform-source-inventory.md"
        route_packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
        self.assertEqual(route_packet["status"], "matched")
        self.assertEqual(route_packet["concrete_part"], "bears_platform_migration_docs")
        self.assertEqual(route_packet["primary_role"], "bears-docs-maintainer")
        self.assertEqual(route_packet["supporting_roles"], ["bears-platform-security-reviewer"])
        self.assertIn("seller", route_packet["trust_boundary"].lower())

        audit_packet = platform_roles.audit_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
        self.assertEqual(audit_packet["status"], "matched")
        self.assertEqual(audit_packet["primary_role"], "bears-docs-maintainer")
        self.assertTrue(audit_packet["implementation_handoff_allowed"])

    def test_routes_docs_maintainer_agent_profile_to_role_metadata_governance(self) -> None:
        targets = [
            "/srv/bears/plugins/bears/agents/bears-docs-maintainer.toml",
            "plugins/bears/agents/bears-docs-maintainer.toml",
            "agents/bears-docs-maintainer.toml",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "docs_maintainer_role_metadata")
                self.assertEqual(packet["primary_role"], "bears-platform-role-governor")
                self.assertIn("role metadata", packet["allowed_write_boundary"])
                self.assertNotIn("migration docs/**", packet["allowed_write_boundary"])

    def test_routes_codex_docs_maintainer_worker_profile_to_workspace_config(self) -> None:
        targets = [
            "/srv/bears/.codex/agents/bears-docs-maintainer.toml",
            ".codex/agents/bears-docs-maintainer.toml",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "codex_workspace_configuration")
                self.assertEqual(packet["primary_role"], "bears-codex-workspace-config-engineer")

    def test_routes_bears_platform_repo_router_docs_to_governor(self) -> None:
        targets = [
            "/srv/bears/dev/platform/AGENTS.md",
            "/srv/bears/dev/platform/docs/stage-rules.md",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "bears_platform_repo_router_docs")
                self.assertEqual(packet["primary_role"], "bears-platform-role-governor")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertFalse(packet["decomposition_required"])

                audit_packet = platform_roles.audit_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(audit_packet["status"], "matched")
                self.assertEqual(audit_packet["primary_role"], "bears-platform-role-governor")
                self.assertTrue(audit_packet["implementation_handoff_allowed"])

    def test_routes_feature_008_auth_exact_files_to_auth_role(self) -> None:
        targets = [
            "/srv/bears/dev/platform/docs/migration/auth-source-to-target-matrix.md",
            "/srv/bears/dev/platform/tests/fixtures/auth_session_contracts.py",
            "/srv/bears/dev/platform/tests/test_auth_session_contracts.py",
            "/srv/bears/dev/platform/tests/test_integration_token_contracts.py",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "bears_platform_auth_feature_008_contract_scope")
                self.assertEqual(packet["primary_role"], "bears-auth-platform-engineer")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertFalse(packet["decomposition_required"])

                audit_packet = platform_roles.audit_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(audit_packet["status"], "matched")
                self.assertEqual(audit_packet["primary_role"], "bears-auth-platform-engineer")
                self.assertTrue(audit_packet["implementation_handoff_allowed"])

    def test_routes_feature_008_gateway_exact_files_to_gateway_role(self) -> None:
        targets = [
            "/srv/bears/dev/platform/docs/migration/gateway-legacy-route-matrix.md",
            "/srv/bears/dev/platform/tests/fixtures/gateway_route_matrix.py",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "bears_gateway_feature_008_route_scope")
                self.assertEqual(packet["primary_role"], "bears-gateway-platform-engineer")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertFalse(packet["decomposition_required"])

                audit_packet = platform_roles.audit_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(audit_packet["status"], "matched")
                self.assertEqual(audit_packet["primary_role"], "bears-gateway-platform-engineer")
                self.assertTrue(audit_packet["implementation_handoff_allowed"])

    def test_routes_feature_008_billing_exact_files_to_billing_role(self) -> None:
        targets = [
            "/srv/bears/dev/platform/docs/migration/billing-status-adapter-matrix.md",
            "/srv/bears/dev/platform/tests/fixtures/billing_status_adapters.py",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "bears_platform_billing_feature_008_adapter_scope")
                self.assertEqual(packet["primary_role"], "bears-payments-platform-engineer")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertFalse(packet["decomposition_required"])

                audit_packet = platform_roles.audit_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(audit_packet["status"], "matched")
                self.assertEqual(audit_packet["primary_role"], "bears-payments-platform-engineer")
                self.assertTrue(audit_packet["implementation_handoff_allowed"])

    def test_routes_feature_008_plan_to_platform_role_governor(self) -> None:
        target = "/srv/bears/specs/008-bears-platform-core-migration/plan.md"
        route_packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
        self.assertEqual(route_packet["status"], "matched")
        self.assertEqual(route_packet["concrete_part"], "platform_core_migration_feature_008_plan")
        self.assertEqual(route_packet["primary_role"], "bears-platform-role-governor")
        self.assertEqual(route_packet["supporting_roles"], ["bears-platform-security-reviewer"])
        self.assertIn(target, route_packet["allowed_write_boundary"])
        self.assertIn("seller", route_packet["trust_boundary"].lower())

        audit_packet = platform_roles.audit_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
        self.assertEqual(audit_packet["status"], "matched")
        self.assertEqual(audit_packet["primary_role"], "bears-platform-role-governor")
        self.assertTrue(audit_packet["implementation_handoff_allowed"])

    def test_routes_feature_008_tasks_plan_to_platform_role_governor(self) -> None:
        target = "/srv/bears/specs/008-bears-platform-core-migration/tasks.md"
        route_packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
        self.assertEqual(route_packet["status"], "matched")
        self.assertEqual(route_packet["concrete_part"], "platform_core_migration_feature_008_tasks_plan")
        self.assertEqual(route_packet["primary_role"], "bears-platform-role-governor")
        self.assertEqual(route_packet["supporting_roles"], ["bears-platform-security-reviewer"])
        self.assertIn("seller", route_packet["trust_boundary"].lower())

        audit_packet = platform_roles.audit_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
        self.assertEqual(audit_packet["status"], "matched")
        self.assertEqual(audit_packet["primary_role"], "bears-platform-role-governor")
        self.assertTrue(audit_packet["implementation_handoff_allowed"])

    def test_feature_006_root_routes_to_exact_telegram_workspace_lane(self) -> None:
        target = "/srv/bears/specs/006-bears-platform-telegram"
        for router in (platform_roles.route_target, platform_roles.audit_target):
            with self.subTest(router=router.__name__):
                packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "telegram_platform_feature_006_workspace_lane")
                self.assertEqual(packet["primary_role"], "bears-telegram-platform-engineer")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertFalse(packet["decomposition_required"])
                self.assertIn(target, packet["allowed_write_boundary"])
                self.assertIn("no product implementation", packet["allowed_write_boundary"])
                self.assertIn("no runtime", packet["allowed_write_boundary"])
                self.assertIn("no live deploy", packet["allowed_write_boundary"])
                self.assertIn("no live Telegram", packet["allowed_write_boundary"])
                if router is platform_roles.audit_target:
                    self.assertTrue(packet["implementation_handoff_allowed"])

    def test_routes_bears_platform_telegram_subtree_to_telegram_role(self) -> None:
        target = "/srv/bears/dev/platform/telegram/AGENTS.md"
        packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
        self.assertEqual(packet["status"], "matched")
        self.assertEqual(packet["concrete_part"], "telegram_platform_dev_layer")
        self.assertEqual(packet["primary_role"], "bears-telegram-platform-engineer")
        self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
        self.assertFalse(packet["decomposition_required"])

    def test_routes_telegram_history_contract_package_to_telegram_role(self) -> None:
        cases = {
            "/srv/bears/dev/platform/src/bears_platform/telegram_history": (
                "telegram_platform_history_source_package",
                "contract-only Telegram history archive schemas",
            ),
            "/srv/bears/dev/platform/tests/test_telegram_history_contracts.py": (
                "telegram_platform_history_contract_tests",
                "static contract tests",
            ),
        }
        for target, (expected_part, expected_boundary) in cases.items():
            with self.subTest(target=target):
                packet = platform_roles.route_target(
                    self.catalog,
                    target,
                    plugin_root=PLUGIN_ROOT,
                )
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], expected_part)
                self.assertEqual(packet["primary_role"], "bears-telegram-platform-engineer")
                self.assertEqual(
                    packet["supporting_roles"],
                    ["bears-platform-security-reviewer"],
                )
                self.assertFalse(packet["decomposition_required"])
                self.assertIn(expected_boundary, packet["allowed_write_boundary"])

                audit_packet = platform_roles.audit_target(
                    self.catalog,
                    target,
                    plugin_root=PLUGIN_ROOT,
                )
                self.assertEqual(audit_packet["status"], "matched")
                self.assertTrue(audit_packet["implementation_handoff_allowed"])

    def test_routes_bears_platform_gateway_child_to_gateway_role(self) -> None:
        target = "/srv/bears/dev/platform/src/bears_platform/gateway"
        packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
        self.assertEqual(packet["status"], "matched")
        self.assertEqual(packet["concrete_part"], "bears_gateway")
        self.assertEqual(packet["primary_role"], "bears-gateway-platform-engineer")
        self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
        self.assertFalse(packet["decomposition_required"])

        audit_packet = platform_roles.audit_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
        self.assertEqual(audit_packet["status"], "matched")
        self.assertTrue(audit_packet["implementation_handoff_allowed"])
        self.assertEqual(audit_packet["primary_role"], "bears-gateway-platform-engineer")
        self.assertEqual(
            audit_packet["independent_control_audit"]["attached_reviewers"],
            ["bears-platform-security-reviewer"],
        )

    def test_routes_bears_platform_auth_runtime_contract_test_to_auth_role(self) -> None:
        target = "/srv/bears/dev/platform/tests/test_auth_runtime_contracts.py"
        packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
        self.assertEqual(packet["status"], "matched")
        self.assertEqual(packet["concrete_part"], "auth_core_runtime_contract_tests")
        self.assertEqual(packet["primary_role"], "bears-auth-platform-engineer")
        self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
        self.assertFalse(packet["decomposition_required"])
        self.assertIn(target, packet["allowed_write_boundary"])
        self.assertNotIn("tests/**", packet["allowed_write_boundary"])

        audit_packet = platform_roles.audit_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
        self.assertEqual(audit_packet["status"], "matched")
        self.assertTrue(audit_packet["implementation_handoff_allowed"])
        self.assertEqual(audit_packet["primary_role"], "bears-auth-platform-engineer")
        self.assertEqual(
            audit_packet["independent_control_audit"]["attached_reviewers"],
            ["bears-platform-security-reviewer"],
        )

    def test_routes_bears_platform_auth_child_to_auth_role(self) -> None:
        target = "/srv/bears/dev/platform/src/bears_platform/auth"
        packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
        self.assertEqual(packet["status"], "matched")
        self.assertEqual(packet["concrete_part"], "auth_core")
        self.assertEqual(packet["primary_role"], "bears-auth-platform-engineer")
        self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
        self.assertFalse(packet["decomposition_required"])

        audit_packet = platform_roles.audit_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
        self.assertEqual(audit_packet["status"], "matched")
        self.assertTrue(audit_packet["implementation_handoff_allowed"])
        self.assertEqual(audit_packet["primary_role"], "bears-auth-platform-engineer")
        self.assertEqual(
            audit_packet["independent_control_audit"]["attached_reviewers"],
            ["bears-platform-security-reviewer"],
        )

    def test_routes_payment_service_only_as_legacy_source(self) -> None:
        targets = [
            "/srv/bears/legacy/seller/apps/payment_service",
            "/srv/bears/legacy/seller/apps/payment_service/app",
            "/srv/bears/projects/seller/apps/payment_service",
            "https://bears.gitlab.yandexcloud.net/bears/payment_service",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "payment_service_legacy_source")
                self.assertEqual(packet["primary_role"], "bears-payments-platform-engineer")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertFalse(packet["decomposition_required"])
                self.assertIn("only as a legacy source", packet["allowed_write_boundary"])
                self.assertNotIn("/srv/bears/dev/platform/src/bears_platform/billing", packet["allowed_write_boundary"])

        seller_audit = platform_roles.audit_target(
            self.catalog,
            "/srv/bears/legacy/seller/apps/payment_service",
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(seller_audit["status"], "matched")
        self.assertTrue(seller_audit["implementation_handoff_allowed"])
        self.assertEqual(seller_audit["concrete_part"], "payment_service_legacy_source")
        self.assertNotIn(
            "/srv/bears/dev/platform/src/bears_platform/billing",
            seller_audit["allowed_write_boundary"],
        )

    def test_routes_billing_child_to_universal_payments_role(self) -> None:
        targets = [
            "/srv/bears/dev/platform/src/bears_platform/billing",
            "/srv/bears/dev/platform/src/bears_platform/billing/payments",
            "/srv/bears/dev/platform/billing/payments",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "bears_platform_billing_surface")
                self.assertEqual(packet["primary_role"], "bears-payments-platform-engineer")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertFalse(packet["decomposition_required"])
                self.assertNotIn("/srv/bears/projects/seller/apps/payment_service", packet["allowed_write_boundary"])

        billing_audit = platform_roles.audit_target(
            self.catalog,
            "/srv/bears/dev/platform/billing/payments",
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(billing_audit["status"], "matched")
        self.assertTrue(billing_audit["implementation_handoff_allowed"])
        self.assertEqual(billing_audit["concrete_part"], "bears_platform_billing_surface")
        self.assertEqual(billing_audit["primary_role"], "bears-payments-platform-engineer")
        self.assertEqual(
            billing_audit["independent_control_audit"]["attached_reviewers"],
            ["bears-platform-security-reviewer"],
        )

    def test_routes_plain_payments_alias_to_universal_payments_role(self) -> None:
        for alias in ("billing", "payments"):
            for router in (platform_roles.route_target, platform_roles.audit_target):
                with self.subTest(alias=alias, router=router.__name__):
                    packet = router(self.catalog, alias, plugin_root=PLUGIN_ROOT)
                    self.assertEqual(packet["status"], "matched")
                    self.assertEqual(packet["concrete_part"], "bears_platform_billing_surface")
                    self.assertEqual(packet["primary_role"], "bears-payments-platform-engineer")
                    self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                    self.assertFalse(packet["decomposition_required"])
                    self.assertNotIn("/srv/bears/projects/seller/apps/payment_service", packet["allowed_write_boundary"])
                    self.assertNotIn("/srv/bears/legacy/seller/apps/payment_service", packet["allowed_write_boundary"])

        audit_packet = platform_roles.audit_target(self.catalog, "billing", plugin_root=PLUGIN_ROOT)
        self.assertEqual(audit_packet["status"], "matched")
        self.assertTrue(audit_packet["implementation_handoff_allowed"])
        self.assertEqual(audit_packet["concrete_part"], "bears_platform_billing_surface")
        self.assertEqual(audit_packet["primary_role"], "bears-payments-platform-engineer")
        self.assertEqual(
            audit_packet["independent_control_audit"]["attached_reviewers"],
            ["bears-platform-security-reviewer"],
        )

    def test_routes_integration_token_test_files_to_exact_wb_specialist(self) -> None:
        targets = {
            "/srv/bears/dev/platform/tests/test_integration_contracts.py": "bears_platform_integration_contract_tests",
            "/srv/bears/dev/platform/tests/test_integration_runtime_contracts.py": "bears_platform_integration_runtime_contract_tests",
        }
        for target, expected_part in targets.items():
            for router in (platform_roles.route_target, platform_roles.audit_target):
                with self.subTest(target=target, router=router.__name__):
                    packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                    self.assertEqual(packet["status"], "matched")
                    self.assertEqual(packet["concrete_part"], expected_part)
                    self.assertEqual(packet["primary_role"], "bears-wb-integration-platform-engineer")
                    self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                    self.assertFalse(packet["decomposition_required"])
                    self.assertIn(target, packet["allowed_write_boundary"])
                    self.assertIn("universal integration-token broker test coverage", packet["allowed_write_boundary"])
                    self.assertNotIn("/srv/bears/projects/seller/apps", packet["allowed_write_boundary"])

        broad_tests = platform_roles.route_target(
            self.catalog,
            "/srv/bears/dev/platform/tests",
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(broad_tests["status"], "ROLE_COVERAGE_BLOCKER")
        self.assertEqual(broad_tests["why_blocked"], "unmapped")
        self.assertNotIn("primary_role", broad_tests)


    def test_routes_t907_provider_adapter_stage_packet_to_telegram_role(self) -> None:
        target = "/srv/bears/specs/006-bears-platform-telegram/governance/github-pr-t907-provider-adapter-contracts-stage-evidence.json"
        for router in (platform_roles.route_target, platform_roles.audit_target):
            with self.subTest(router=router.__name__):
                packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(
                    packet["concrete_part"],
                    "telegram_platform_feature_006_t907_provider_adapter_stage_evidence",
                )
                self.assertEqual(packet["primary_role"], "bears-telegram-platform-engineer")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertFalse(packet["decomposition_required"])
                self.assertIn(target, packet["allowed_write_boundary"])
                self.assertNotIn("/srv/bears/specs/006-bears-platform-telegram/governance/**", packet["allowed_write_boundary"])

    def test_routes_pr36_local_source_ref_merge_stage_packet_to_deploy_role(self) -> None:
        target = "/srv/bears/specs/006-bears-platform-telegram/governance/github-pr36-t903-local-source-ref-merge-stage-evidence.json"
        for router in (platform_roles.route_target, platform_roles.audit_target):
            with self.subTest(router=router.__name__):
                packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(
                    packet["concrete_part"],
                    "telegram_platform_feature_006_pr36_local_source_ref_merge_stage_evidence",
                )
                self.assertEqual(packet["primary_role"], "bears-deploy-platform-engineer")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertFalse(packet["decomposition_required"])
                self.assertIn(target, packet["allowed_write_boundary"])
                self.assertIn("no-frontend checks pass", packet["trust_boundary"])
                self.assertNotIn("/srv/bears/specs/006-bears-platform-telegram/governance/**", packet["allowed_write_boundary"])

    def test_routes_t903_local_image_cache_remediation_evidence_to_deploy_role(self) -> None:
        target = "/srv/bears/specs/006-bears-platform-telegram/governance/t903-local-image-cache-remediation-evidence.json"
        for router in (platform_roles.route_target, platform_roles.audit_target):
            with self.subTest(router=router.__name__):
                packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(
                    packet["concrete_part"],
                    "telegram_platform_feature_006_t903_local_image_cache_remediation_evidence",
                )
                self.assertEqual(packet["primary_role"], "bears-deploy-platform-engineer")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertFalse(packet["decomposition_required"])
                self.assertIn(target, packet["allowed_write_boundary"])
                self.assertIn("Infisical get/list", packet["allowed_write_boundary"])
                self.assertIn("no-frontend checks pass", packet["trust_boundary"])
                self.assertNotIn("/srv/bears/specs/006-bears-platform-telegram/governance/**", packet["allowed_write_boundary"])

    def test_routes_t353_nonprod_validation_request_and_checklist_to_telegram_role(self) -> None:
        targets = [
            "/srv/bears/specs/006-bears-platform-telegram/governance/nonprod-validation-request.json",
            "/srv/bears/specs/006-bears-platform-telegram/governance/nonprod-validation-checklist.md",
        ]
        for target in targets:
            for router in (platform_roles.route_target, platform_roles.audit_target):
                with self.subTest(target=target, router=router.__name__):
                    packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                    self.assertEqual(packet["status"], "matched")
                    self.assertEqual(
                        packet["concrete_part"],
                        "telegram_platform_feature_006_t353_nonprod_validation_request_checklist",
                    )
                    self.assertEqual(packet["primary_role"], "bears-telegram-platform-engineer")
                    self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                    self.assertFalse(packet["decomposition_required"])
                    self.assertIn(target, packet["allowed_write_boundary"])
                    self.assertIn("live Telegram", packet["allowed_write_boundary"])
                    self.assertIn("T354", packet["allowed_write_boundary"])
                    self.assertNotIn("/srv/bears/specs/006-bears-platform-telegram/governance/**", packet["allowed_write_boundary"])

    def test_routes_t354_live_telegram_approval_request_and_checklist_to_telegram_role(self) -> None:
        targets = [
            "/srv/bears/specs/006-bears-platform-telegram/governance/live-telegram-approval-request.json",
            "/srv/bears/specs/006-bears-platform-telegram/governance/live-telegram-checklist.md",
        ]
        for target in targets:
            for router in (platform_roles.route_target, platform_roles.audit_target):
                with self.subTest(target=target, router=router.__name__):
                    packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                    self.assertEqual(packet["status"], "matched")
                    self.assertEqual(
                        packet["concrete_part"],
                        "telegram_platform_feature_006_t354_live_telegram_approval_request_checklist",
                    )
                    self.assertEqual(packet["primary_role"], "bears-telegram-platform-engineer")
                    self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                    self.assertFalse(packet["decomposition_required"])
                    self.assertIn(target, packet["allowed_write_boundary"])
                    self.assertIn("no broad governance directory", packet["allowed_write_boundary"])
                    self.assertIn("frontend", packet["allowed_write_boundary"])
                    self.assertIn("live send", packet["trust_boundary"])
                    self.assertNotIn("/srv/bears/specs/006-bears-platform-telegram/governance/**", packet["allowed_write_boundary"])

    def test_routes_bears_platform_integration_tokens_child_to_wb_role(self) -> None:
        target = "/srv/bears/dev/platform/src/bears_platform/integration_tokens"
        packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
        self.assertEqual(packet["status"], "matched")
        self.assertEqual(packet["concrete_part"], "bears_platform_integration_tokens_surface")
        self.assertEqual(packet["primary_role"], "bears-wb-integration-platform-engineer")
        self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
        self.assertFalse(packet["decomposition_required"])

        audit_packet = platform_roles.audit_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
        self.assertEqual(audit_packet["status"], "matched")
        self.assertTrue(audit_packet["implementation_handoff_allowed"])
        self.assertEqual(audit_packet["primary_role"], "bears-wb-integration-platform-engineer")
        self.assertEqual(
            audit_packet["independent_control_audit"]["attached_reviewers"],
            ["bears-platform-security-reviewer"],
        )

    def test_audit_allows_theants_new_and_legacy_paths_after_validation(self) -> None:
        for target in ("/srv/bears/dev/app/theants", "/srv/bears/projects/theants"):
            with self.subTest(target=target):
                packet = platform_roles.audit_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertTrue(packet["implementation_handoff_allowed"])
                self.assertEqual(packet["primary_role"], "bears-product-app-zone-engineer")

    def test_kubernetes_deploy_core_policy_records_repo_boundary_and_subagent_rule(self) -> None:
        packet = platform_roles.route_target(
            self.catalog,
            "/srv/bears/kubernetes/contracts/kubernetes_deploy_core_contract.md",
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(packet["status"], "matched")
        self.assertEqual(packet["primary_role"], "bears-deploy-platform-engineer")
        self.assertIn("bears-infra repo boundary", packet["allowed_write_boundary"])
        self.assertIn("working tree /srv/bears/kubernetes", packet["allowed_write_boundary"])
        self.assertIn("Git/CD contract", packet["allowed_write_boundary"])
        self.assertIn("local @Bears CD from main", packet["allowed_write_boundary"])
        self.assertIn("branch-to-target mapping", packet["trust_boundary"])
        self.assertIn("ordered deploy logic", packet["trust_boundary"])
        self.assertIn("manual approval gates", packet["trust_boundary"])

    def test_old_dev_kubernetes_lane_is_not_a_writable_shim(self) -> None:
        packet = platform_roles.route_target(self.catalog, "/srv/bears/dev/infrastructure/kubernetes", plugin_root=PLUGIN_ROOT)
        self.assertEqual(packet["status"], "matched")
        self.assertEqual(packet["concrete_part"], "kubernetes_dev_core_router_layer")
        self.assertEqual(packet["primary_role"], "bears-deploy-platform-engineer")
        self.assertIn("reference/router docs", packet["allowed_write_boundary"])
        self.assertIn("/srv/bears/kubernetes", packet["allowed_write_boundary"])
        self.assertIn("no Kubernetes production mutation", packet["allowed_write_boundary"])
        audit_packet = platform_roles.audit_target(
            self.catalog,
            "/srv/bears/dev/infrastructure/kubernetes",
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(audit_packet["status"], "matched")
        self.assertTrue(audit_packet["implementation_handoff_allowed"])

    def test_dev_infrastructure_parent_stays_blocked_without_child_route(self) -> None:
        packet = platform_roles.audit_target(self.catalog, "/srv/bears/dev/infrastructure", plugin_root=PLUGIN_ROOT)
        self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
        self.assertEqual(packet["why_blocked"], "parent_only")
        self.assertTrue(packet["decomposition_required"])
        self.assertNotIn("primary_role", packet)

    def test_sentry_alias_routes_to_observability_runtime_plugin_surface(self) -> None:
        targets = ["sentry", "sentry-runtime-plugin", "/srv/bears/runtime-plugins/sentry"]
        for router in (platform_roles.route_target, platform_roles.audit_target):
            for target in targets:
                with self.subTest(router=router.__name__, target=target):
                    packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                    self.assertEqual(packet["status"], "matched")
                    self.assertEqual(packet["concrete_part"], "sentry_observability_226")
                    self.assertEqual(packet["primary_role"], "bears-observability-platform-engineer")
                    self.assertIn("future-lane", packet["allowed_write_boundary"])
                    self.assertIn("no production telemetry mutation", packet["allowed_write_boundary"])
                    self.assertIn("no runtime code in this Codex plugin root", packet["allowed_write_boundary"])
                    self.assertIn("redacted aggregate summaries", packet["trust_boundary"])
                    self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])

    def test_sentry_runtime_plugin_design_is_concrete_and_redacted(self) -> None:
        part = next(part for part in self.catalog["platform_parts"] if part["name"] == "sentry_observability_226")
        design = part["runtime_plugin_capability"]
        self.assertEqual(design["runtime_plugin_repo"], "BearsCLOUD/bears-sentry-runtime-plugin")
        self.assertEqual(design["runtime_plugin_path"], "/srv/bears/runtime-plugins/sentry")
        self.assertEqual(design["governance_path"], "/srv/bears/plugins/bears")
        self.assertEqual(design["owner_role"], "bears-observability-platform-engineer")
        self.assertEqual(design["reviewer_role"], "bears-platform-security-reviewer")
        self.assertEqual(design["evidence_default"], "redacted_only")
        self.assertIn("read-only issue summaries", design["allowed_operations"])
        self.assertIn("Sentry settings mutation", design["forbidden_operations"])
        self.assertIn("raw event payload export", design["forbidden_operations"])
        self.assertIn(
            "runtime code, app, connector, MCP server, or service implementation inside /srv/bears/plugins/bears",
            design["forbidden_operations"],
        )
        self.assertEqual(design["redaction_rules"]["default"], "deny every Sentry field unless this allowlist names it")
        self.assertIn("issue_key", design["redaction_rules"]["allowed_fields"])
        self.assertIn("raw_event_payload", design["redaction_rules"]["blocked_fields"])
        self.assertNotIn("raw_event_payload", design["redaction_rules"]["allowed_fields"])
        self.assertIn("runtime-plugin capability design asserts redacted-only output", part["required_validations"])
        self.assertIn("runtime-plugin code stays outside /srv/bears/plugins/bears", part["required_validations"])

    def test_routes_role_gate_methodology_to_governor(self) -> None:
        packet = platform_roles.route_target(
            self.catalog,
            "/srv/bears/plugins/bears/assets/catalog/role-gate-methodology.v1.json",
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(packet["status"], "matched")
        self.assertEqual(packet["primary_role"], "bears-platform-role-governor")

    def test_routes_telegram_runtime_readiness_catalog_to_exact_specialist(self) -> None:
        packet = platform_roles.route_target(
            self.catalog,
            "/srv/bears/plugins/bears/assets/catalog/telegram-runtime-readiness.v1.json",
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(packet["status"], "matched")
        self.assertEqual(packet["concrete_part"], "telegram_runtime_readiness_catalog")
        self.assertEqual(packet["primary_role"], "bears-telegram-platform-engineer")
        self.assertIn("bears-platform-security-reviewer", packet["supporting_roles"])

    def test_routes_telegram_validator_scripts_to_exact_specialist(self) -> None:
        cases = {
            "/srv/bears/plugins/bears/assets/catalog/telegram-aiogram-migration-backlog.v1.json": "telegram_aiogram",
            "/srv/bears/plugins/bears/scripts/telegram_migration_backlog.py": "telegram_aiogram",
            "/srv/bears/plugins/bears/scripts/telegram_runtime_readiness.py": "telegram_runtime_readiness_catalog",
            "/srv/bears/plugins/bears/tests/test_telegram_runtime_readiness.py": "telegram_runtime_readiness_catalog",
        }
        for target, expected_part in cases.items():
            with self.subTest(target=target):
                packet = platform_roles.route_target(
                    self.catalog,
                    target,
                    plugin_root=PLUGIN_ROOT,
                )
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], expected_part)
                self.assertEqual(packet["primary_role"], "bears-telegram-platform-engineer")
                self.assertIn("bears-platform-security-reviewer", packet["supporting_roles"])

    def test_routes_feature_005_spec_truth_layer_to_exact_specialist(self) -> None:
        packet = platform_roles.route_target(
            self.catalog,
            "/srv/bears/specs/005-telegram-workflow-plugin/spec.md",
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(packet["status"], "matched")
        self.assertEqual(packet["concrete_part"], "telegram_workflow_plugin_feature_005_truth_layer")
        self.assertEqual(packet["primary_role"], "bears-telegram-platform-engineer")
        self.assertIn("bears-platform-security-reviewer", packet["supporting_roles"])

    def test_routes_feature_005_checklists_to_exact_specialist(self) -> None:
        targets = [
            "/srv/bears/specs/005-telegram-workflow-plugin/checklists/feature.json",
            "/srv/bears/specs/005-telegram-workflow-plugin/checklists/requirements.md",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(
                    self.catalog,
                    target,
                    plugin_root=PLUGIN_ROOT,
                )
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "telegram_workflow_plugin_feature_005_checklists")
                self.assertEqual(packet["primary_role"], "bears-telegram-platform-engineer")
                self.assertIn("bears-platform-security-reviewer", packet["supporting_roles"])

    def test_routes_feature_005_governance_packets_to_exact_specialist(self) -> None:
        targets = [
            "/srv/bears/specs/005-telegram-workflow-plugin/governance/policy-packet.json",
            "/srv/bears/specs/005-telegram-workflow-plugin/governance/role-coverage.json",
            "/srv/bears/specs/005-telegram-workflow-plugin/governance/blocker-review.json",
            "/srv/bears/specs/005-telegram-workflow-plugin/governance/deploy-gate.json",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(
                    self.catalog,
                    target,
                    plugin_root=PLUGIN_ROOT,
                )
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "telegram_workflow_plugin_feature_005_governance_packets")
                self.assertEqual(packet["primary_role"], "bears-telegram-platform-engineer")
                self.assertIn("bears-platform-security-reviewer", packet["supporting_roles"])

    def test_routes_feature_006_migration_map_governance_to_exact_specialist(self) -> None:
        targets = [
            "/srv/bears/specs/006-bears-platform-telegram/governance/universal-platform-repo-migration-map.md",
            "/srv/bears/specs/006-bears-platform-telegram/governance/universal-platform-repo-migration-map.json",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(
                    self.catalog,
                    target,
                    plugin_root=PLUGIN_ROOT,
                )
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "telegram_platform_feature_006_migration_map_governance")
                self.assertEqual(packet["primary_role"], "bears-telegram-platform-engineer")
                self.assertIn("bears-platform-security-reviewer", packet["supporting_roles"])

    def test_audit_feature_005_checklist_handoff_is_allowed_after_validation(self) -> None:
        packet = platform_roles.audit_target(
            self.catalog,
            "/srv/bears/specs/005-telegram-workflow-plugin/checklists/feature.json",
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(packet["status"], "matched")
        self.assertTrue(packet["implementation_handoff_allowed"])
        self.assertEqual(packet["primary_role"], "bears-telegram-platform-engineer")

    def test_unmapped_child_under_feature_005_truth_layer_still_blocks(self) -> None:
        packet = platform_roles.route_target(
            self.catalog,
            "/srv/bears/specs/005-telegram-workflow-plugin/notes.md",
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
        self.assertEqual(packet["why_blocked"], "unmapped")

    def test_legacy_telegram_plugin_root_stays_blocked(self) -> None:
        packet = platform_roles.route_target(
            self.catalog,
            "/srv/bears/plugins/bears-telegram-workflow",
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
        self.assertEqual(packet["why_blocked"], "unmapped")

    def test_routes_known_telegram_runtime_surfaces(self) -> None:
        targets = [
            "/srv/bears/projects/vpn/vpnbot",
            "/srv/bears/projects/seller/apps/bot_admin",
            "/srv/bears/projects/seller/apps/sticker_bot",
            "/srv/bears/projects/seller/apps/telegram_bot_bears",
            "/srv/bears/projects/seller/apps/bot_find_pos",
            "/srv/bears/projects/seller/apps/bot_marketplace_fbs",
            "/srv/bears/projects/metamask/src/bot.mjs",
        ]
        for target in targets:
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["primary_role"], "bears-telegram-platform-engineer")

    def test_product_apps_monorepo_root_routes_to_exact_product_role(self) -> None:
        for target in ("/srv/bears/dev/app", "BearsCLOUD/apps"):
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "product_apps_monorepo_root")
                self.assertEqual(packet["primary_role"], "bears-product-app-zone-engineer")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])

    def test_invalid_apps_monorepo_paths_stay_blocked(self) -> None:
        for target in ("/srv/bears/dev/app/apps", "/srv/bears/dev/apps", "/srv/bears/dev/app/newapp"):
            with self.subTest(target=target):
                packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
                self.assertEqual(packet["why_blocked"], "unmapped")

    def test_product_apps_monorepo_policy_rejects_new_standalone_app_repo(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        part = copy.deepcopy(next(item for item in catalog["platform_parts"] if item["name"] == "desk_product_dev_layer"))
        part["name"] = "future_standalone_product_app"
        part["aliases"] = ["/srv/bears/dev/app/future", "dev/app/future", "BearsCLOUD/future"]
        part["write_roots"] = ["/srv/bears/dev/app/future"]
        part.pop("legacy_compatibility", None)
        catalog["platform_parts"].append(part)
        catalog["mandatory_policy"]["role_required_for"].append("future_standalone_product_app")

        errors = platform_roles.validate_catalog(catalog, plugin_root=PLUGIN_ROOT)

        self.assertTrue(
            any(
                "product-apps-monorepo: future_standalone_product_app old app route must declare legacy_compatibility"
                in error
                for error in errors
            )
        )

    def test_product_apps_monorepo_policy_rejects_new_canonical_app_remote(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        part = copy.deepcopy(next(item for item in catalog["platform_parts"] if item["name"] == "product_apps_monorepo_root"))
        part["name"] = "future_canonical_product_app"
        part["aliases"] = ["/srv/bears/dev/app/future", "dev/app/future", "BearsCLOUD/future"]
        part["write_roots"] = ["/srv/bears/dev/app/future"]
        part["canonical_repository"] = {
            "local_root": "/srv/bears/dev/app/future",
            "remote": "BearsCLOUD/future",
            "github_repo": "BearsCLOUD/future",
        }
        catalog["platform_parts"].append(part)
        catalog["mandatory_policy"]["role_required_for"].append("future_canonical_product_app")

        errors = platform_roles.validate_catalog(catalog, plugin_root=PLUGIN_ROOT)

        self.assertTrue(
            any(
                "product-apps-monorepo: future_canonical_product_app.canonical_repository.remote must be BearsCLOUD/apps"
                in error
                for error in errors
            )
        )

    def test_product_apps_old_remote_aliases_must_be_deprecated_refs(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        part = next(item for item in catalog["platform_parts"] if item["name"] == "desk_product_dev_layer")
        part["legacy_compatibility"]["deprecated_refs"] = []

        errors = platform_roles.validate_catalog(catalog, plugin_root=PLUGIN_ROOT)

        self.assertTrue(
            any(
                "desk_product_dev_layer.legacy_compatibility.deprecated_refs must include old repository aliases ['BearsCLOUD/desk']"
                in error
                for error in errors
            )
        )

    def test_product_apps_archive_readiness_requires_project_infra_and_platform_guards(self) -> None:
        policy = self.catalog["mandatory_policy"]["product_apps_monorepo_policy"]
        self.assertIn("infra_local_cd_safety_invariant", policy["required_legacy_fields"])
        self.assertIn("platform_boundary_exclusion_invariant", policy["required_legacy_fields"])
        self.assertIn("canonical BearsCLOUD/apps planning Project", policy["archive_readiness_invariant"])
        self.assertIn("local_cd", policy["archive_readiness_invariant"])
        self.assertIn("platform boundary exclusion", policy["archive_readiness_invariant"])
        self.assertNotIn("source_project_name_template", policy)
        planning_project = policy["canonical_planning_project"]
        self.assertEqual(planning_project["owner_repository"], "BearsCLOUD/apps")
        self.assertIn("source_repo/app_module", planning_project["required_issue_fields"])
        self.assertIn("archive_readiness", planning_project["required_issue_fields"])
        self.assertIn("existing per-source Projects may exist only as legacy evidence and must not be required, created, or used for PASS", planning_project["scope"])
        self.assertEqual(
            policy["platform_temp_checkout_exclusion"]["classification_required_by"],
            "platform auditor",
        )
        self.assertIn("/srv/bears/dev/platform", policy["platform_temp_checkout_exclusion"]["excluded_roots"])

        catalog = copy.deepcopy(self.catalog)
        part = next(item for item in catalog["platform_parts"] if item["name"] == "desk_product_dev_layer")
        part["legacy_compatibility"].pop("infra_local_cd_safety_invariant", None)

        errors = platform_roles.validate_catalog(catalog, plugin_root=PLUGIN_ROOT)

        self.assertTrue(
            any(
                "desk_product_dev_layer.legacy_compatibility missing ['infra_local_cd_safety_invariant']"
                in error
                for error in errors
            )
        )

    def test_platform_repo_root_stays_outside_apps_archive_workflow(self) -> None:
        packet = platform_roles.route_target(self.catalog, "/srv/bears/dev/platform", plugin_root=PLUGIN_ROOT)
        self.assertEqual(packet["status"], "matched")
        self.assertEqual(packet["concrete_part"], "bears_platform_repo_root")
        self.assertEqual(packet["primary_role"], "bears-platform-role-governor")

        catalog = copy.deepcopy(self.catalog)
        platform_part = next(item for item in catalog["platform_parts"] if item["name"] == "bears_platform_repo_root")
        platform_part["aliases"].append("BearsCLOUD/platform-temp")

        errors = platform_roles.validate_catalog(catalog, plugin_root=PLUGIN_ROOT)

        self.assertFalse(
            any("bears_platform_repo_root old app route must declare legacy_compatibility" in error for error in errors)
        )

    def test_plugin_docs_do_not_assign_canonical_authority_to_old_app_repos(self) -> None:
        docs = {
            rel: (PLUGIN_ROOT / rel).read_text(encoding="utf-8")
            for rel in (
                "AGENTS.md",
                "README.md",
                "SPEC.md",
                "requirements.md",
                "skills/platform-role-governance/SKILL.md",
                "skills/bears-role-gate/SKILL.md",
                "agents/bears-product-app-zone-engineer.toml",
            )
        }
        joined = "\n".join(docs.values())

        self.assertIn("BearsCLOUD/apps", joined)
        self.assertIn("/srv/bears/dev/app", joined)
        self.assertNotIn("canonical The Ants", joined)
        self.assertNotIn("BearsCLOUD/codexdaemon` owns daemon source", joined)
        self.assertNotIn("live in `BearsCLOUD/codexdaemon`", joined)

        for rel, text in docs.items():
            if "BearsCLOUD/codexdaemon" in text:
                with self.subTest(rel=rel):
                    self.assertIn("deprecated", text)
                    self.assertIn("archive", text)

    def test_dev_registry_root_routes_to_exact_workspace_governance_docs(self) -> None:
        for router in (platform_roles.route_target, platform_roles.audit_target):
            with self.subTest(router=router.__name__):
                packet = router(self.catalog, "/srv/bears/dev/registry", plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "workspace_governance_canonical_plugin_docs")
                self.assertEqual(packet["primary_role"], "bears-platform-role-governor")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertTrue(packet["implementation_handoff_allowed"] if router is platform_roles.audit_target else True)

    def test_desk_product_dev_layer_routes_to_exact_product_role(self) -> None:
        target = "/srv/bears/dev/app/desk"
        for router in (platform_roles.route_target, platform_roles.audit_target):
            with self.subTest(router=router.__name__):
                packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "desk_product_dev_layer")
                self.assertEqual(packet["primary_role"], "bears-product-app-zone-engineer")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertIn(target, packet["allowed_write_boundary"])
                self.assertNotIn("/srv/bears/dev/platform", packet["allowed_write_boundary"])

    def test_desk_shared_platform_surfaces_route_to_exact_specialists(self) -> None:
        cases = {
            "/srv/bears/dev/platform/src/bears_platform/module_registry": (
                "bears_platform_module_registry_surface",
                "bears-wb-integration-platform-engineer",
            ),
            "/srv/bears/dev/platform/src/bears_platform/provider_gateway": (
                "bears_platform_provider_gateway_surface",
                "bears-gateway-platform-engineer",
            ),
            "/srv/bears/dev/platform/src/bears_platform/data_cache": (
                "bears_platform_data_cache_surface",
                "bears-wb-integration-platform-engineer",
            ),
            "/srv/bears/dev/platform/src/bears_platform/managed_backend": (
                "bears_platform_managed_backend_surface",
                "bears-wb-integration-platform-engineer",
            ),
        }
        for target, (expected_part, expected_role) in cases.items():
            for router in (platform_roles.route_target, platform_roles.audit_target):
                with self.subTest(target=target, router=router.__name__):
                    packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                    self.assertEqual(packet["status"], "matched")
                    self.assertEqual(packet["concrete_part"], expected_part)
                    self.assertEqual(packet["primary_role"], expected_role)
                    self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                    self.assertIn(target, packet["allowed_write_boundary"])
                    self.assertNotIn("/srv/bears/dev/platform/src/bears_platform/auth", packet["allowed_write_boundary"])

    def test_runtime_packet_doc_routes_to_exact_telegram_role_with_security_reviewer(self) -> None:
        target = "/srv/bears/dev/platform/docs/runtime-implementation-packet-after-rotation.md"
        for router in (platform_roles.route_target, platform_roles.audit_target):
            with self.subTest(router=router.__name__):
                packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["concrete_part"], "bears_platform_runtime_implementation_packet_after_rotation")
                self.assertEqual(packet["primary_role"], "bears-telegram-platform-engineer")
                self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                self.assertIn("secret/redaction boundary change", packet["reviewer_triggers"])

    def test_plugin_root_gitlink_and_child_file_routes_are_disambiguated(self) -> None:
        root_packet = platform_roles.route_target(self.catalog, "/srv/bears/plugins/bears", plugin_root=PLUGIN_ROOT)
        child_packet = platform_roles.route_target(self.catalog, "/srv/bears/plugins/bears/AGENTS.md", plugin_root=PLUGIN_ROOT)
        child_audit = platform_roles.audit_target(self.catalog, "/srv/bears/plugins/bears/AGENTS.md", plugin_root=PLUGIN_ROOT)
        self.assertEqual(root_packet["status"], "matched")
        self.assertEqual(root_packet["concrete_part"], "workspace_root_submodule_gitlinks")
        self.assertEqual(child_packet["status"], "matched")
        self.assertEqual(child_packet["concrete_part"], "platform_role_governance")
        self.assertEqual(child_packet["primary_role"], "bears-platform-role-governor")
        self.assertEqual(child_audit["status"], "matched")
        self.assertTrue(child_audit["implementation_handoff_allowed"])

    def test_plugin_issue_template_lane_routes_to_exact_workflow_overlay_role(self) -> None:
        targets = [
            "/srv/bears/plugins/bears/.github/ISSUE_TEMPLATE/config.yml",
            "/srv/bears/plugins/bears/.github/ISSUE_TEMPLATE/bug_report.yml",
        ]
        for target in targets:
            for router in (platform_roles.route_target, platform_roles.audit_target):
                with self.subTest(target=target, router=router.__name__):
                    packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                    self.assertEqual(packet["status"], "matched")
                    self.assertEqual(packet["concrete_part"], "workflow_overlay_issue_templates")
                    self.assertEqual(packet["primary_role"], "bears-workflow-overlay-platform-engineer")
                    self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                    self.assertIn(".github/ISSUE_TEMPLATE/**", packet["allowed_write_boundary"])
                    self.assertIn("no .github/workflows/**", packet["allowed_write_boundary"])


    def test_notifications_platform_backend_paths_route_to_exact_notifications_specialist(self) -> None:
        cases = {
            "/srv/bears/dev/platform/src/bears_platform/notifications": "bears_platform_notifications_surface",
            "/srv/bears/dev/platform/src/bears_platform/notifications/delivery.py": "bears_platform_notifications_surface",
            "/srv/bears/dev/platform/tests/test_notifications_contracts.py": "bears_platform_notifications_contracts_tests",
            "/srv/bears/dev/platform/tests/test_notifications_runtime.py": "bears_platform_notifications_runtime_tests",
        }
        for target, expected_part in cases.items():
            for router in (platform_roles.route_target, platform_roles.audit_target):
                with self.subTest(target=target, router=router.__name__):
                    packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                    self.assertEqual(packet["status"], "matched")
                    self.assertEqual(packet["concrete_part"], expected_part)
                    self.assertEqual(packet["primary_role"], "bears-notifications-platform-engineer")
                    self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                    self.assertIn("notifications", packet["allowed_write_boundary"])
                    self.assertIn("repo-root fallback", packet["allowed_write_boundary"])

    def test_provider_backend_contract_tests_route_to_exact_specialists(self) -> None:
        cases = {
            "/srv/bears/dev/platform/tests/test_provider_gateway_contracts.py": (
                "bears_platform_provider_gateway_contracts_tests",
                "bears-gateway-platform-engineer",
            ),
            "/srv/bears/dev/platform/tests/test_managed_backend_contracts.py": (
                "bears_platform_managed_backend_contracts_tests",
                "bears-wb-integration-platform-engineer",
            ),
            "/srv/bears/dev/platform/tests/test_module_registry_contracts.py": (
                "bears_platform_module_registry_contracts_tests",
                "bears-wb-integration-platform-engineer",
            ),
            "/srv/bears/dev/platform/tests/test_data_cache_contracts.py": (
                "bears_platform_data_cache_contracts_tests",
                "bears-wb-integration-platform-engineer",
            ),
        }
        for target, (expected_part, expected_role) in cases.items():
            for router in (platform_roles.route_target, platform_roles.audit_target):
                with self.subTest(target=target, router=router.__name__):
                    packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                    self.assertEqual(packet["status"], "matched")
                    self.assertEqual(packet["concrete_part"], expected_part)
                    self.assertEqual(packet["primary_role"], expected_role)
                    self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                    self.assertIn(target, packet["allowed_write_boundary"])
                    self.assertNotIn("/srv/bears/dev/platform/src/bears_platform/auth", packet["allowed_write_boundary"])

    def test_platform_backend_issue_docs_tests_and_ci_routes_are_exact(self) -> None:
        cases = {
            "/srv/bears/dev/platform/README.md": (
                "bears_platform_repo_readme_docs",
                "bears-docs-maintainer",
                "documentation",
            ),
            "/srv/bears/dev/platform/SPEC.md": (
                "bears_platform_repo_spec_docs",
                "bears-docs-maintainer",
                "documentation",
            ),
            "/srv/bears/dev/platform/docs/consumers/desk.md": (
                "bears_platform_desk_consumer_docs",
                "bears-docs-maintainer",
                "Desk consumer",
            ),
            "/srv/bears/dev/platform/tests/test_provider_gateway_runtime.py": (
                "bears_platform_provider_gateway_runtime_tests",
                "bears-gateway-platform-engineer",
                "no broad tests directory",
            ),
            "/srv/bears/dev/platform/tests/test_gateway_desk_auth_propagation.py": (
                "bears_gateway_desk_auth_propagation_tests",
                "bears-gateway-platform-engineer",
                "no broad tests directory",
            ),
            "/srv/bears/dev/platform/docs/ci": (
                "bears_platform_ci_docs",
                "bears-deploy-platform-engineer",
                "CI planning documentation",
            ),
            "/srv/bears/dev/platform/docs/ci/gateway-required-checks.md": (
                "bears_platform_ci_docs",
                "bears-deploy-platform-engineer",
                "CI planning documentation",
            ),
            "/srv/bears/dev/platform/.github/workflows/gateway-required-checks.yml.disabled": (
                "bears_platform_disabled_workflow_planning",
                "bears-deploy-platform-engineer",
                "gateway-required-checks.yml.disabled",
            ),
            "/srv/bears/dev/platform/.github/workflows/gateway-validation.yml.disabled": (
                "bears_platform_disabled_workflow_planning",
                "bears-deploy-platform-engineer",
                "gateway-validation.yml.disabled",
            ),
            "/srv/bears/dev/platform/.github/workflows/gateway-validation.yml": (
                "bears_platform_gateway_validation_workflow_governance",
                "bears-deploy-platform-engineer",
                "operator-approved workflow activation packet",
            ),
        }
        for target, (expected_part, expected_role, boundary_text) in cases.items():
            for router in (platform_roles.route_target, platform_roles.audit_target):
                with self.subTest(target=target, router=router.__name__):
                    packet = router(self.catalog, target, plugin_root=PLUGIN_ROOT)
                    self.assertEqual(packet["status"], "matched")
                    self.assertEqual(packet["concrete_part"], expected_part)
                    self.assertEqual(packet["primary_role"], expected_role)
                    self.assertEqual(packet["supporting_roles"], ["bears-platform-security-reviewer"])
                    self.assertIn(boundary_text, packet["allowed_write_boundary"])
                    self.assertNotIn("seller default", packet["allowed_write_boundary"].casefold())

    def test_platform_backend_unknown_siblings_stay_blocked(self) -> None:
        blocked_targets = [
            "/srv/bears/dev/platform/docs/consumers/unknown.md",
            "/srv/bears/dev/platform/tests/test_provider_gateway_unknown.py",
            "/srv/bears/dev/platform/tests/test_gateway_unknown_sibling.py",
            "/srv/bears/dev/platform/.github/workflows",
            "/srv/bears/dev/platform/.github/workflows/publish-local-images.yml",
            "/srv/bears/dev/platform/.github/workflows/unknown.yml",
            "/srv/bears/dev/platform/.github/workflows/gateway-validation.yml.disabled/child",
            "/srv/bears/dev/platform/.github/workflows/gateway-validation.yml/child",
            "/srv/bears/dev/platform/.github/actions",
        ]
        for target in blocked_targets:
            packet = platform_roles.route_target(self.catalog, target, plugin_root=PLUGIN_ROOT)
            with self.subTest(target=target):
                self.assertEqual(packet["status"], "ROLE_COVERAGE_BLOCKER")
                self.assertEqual(packet["why_blocked"], "unmapped")
                self.assertNotIn("primary_role", packet)

if __name__ == "__main__":
    unittest.main()
