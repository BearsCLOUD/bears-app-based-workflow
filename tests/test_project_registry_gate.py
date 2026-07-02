from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PLUGIN_ROOT / "scripts" / "project_registry_gate.py"
LIVE_WORKSPACE_REGISTRY = Path("/srv/bears/dev/registry/projects.v1.json")
spec = importlib.util.spec_from_file_location("project_registry_gate", SCRIPT_PATH)
project_registry_gate = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(project_registry_gate)  # type: ignore[arg-type]


def _make_spec_required_registry(registry: dict) -> dict:
    updated = copy.deepcopy(registry)
    entry = updated["entries"][0]
    entry["spec_required"] = True
    entry["spec_path"] = "/srv/bears/specs/test/spec.md"
    entry["plan_path"] = "/srv/bears/specs/test/plan.md"
    entry["tasks_path"] = "/srv/bears/specs/test/tasks.md"
    return updated


def _speckit_analyze_payload(
    *,
    schema: str = "bears.speckit-analyze.v1",
    status: str = "PASS",
    spec_path: str = "/srv/bears/specs/test/spec.md",
) -> str:
    return json.dumps(
        {
            "schema": schema,
            "status": status,
            "spec_path": spec_path,
            "plan_path": "/srv/bears/specs/test/plan.md",
            "tasks_path": "/srv/bears/specs/test/tasks.md",
        }
    )


def _patch_spec_files(tasks_text: str, *, analyze_payload: str | None = None, include_analyze: bool = True):
    original_is_file = project_registry_gate.Path.is_file
    original_read_text = project_registry_gate.Path.read_text
    analyze_path = "/srv/bears/specs/test/governance/speckit-analyze.json"
    if analyze_payload is None:
        analyze_payload = _speckit_analyze_payload()

    def fake_is_file(path: Path) -> bool:
        if str(path) == analyze_path:
            return include_analyze
        if str(path).startswith("/srv/bears/specs/test/"):
            return True
        return original_is_file(path)

    def fake_read_text(path: Path, *args, **kwargs) -> str:
        if str(path) == analyze_path and include_analyze:
            return analyze_payload
        if str(path) == "/srv/bears/specs/test/tasks.md":
            return tasks_text
        if str(path).startswith("/srv/bears/specs/test/"):
            return "# Spec Kit artifact fixture\n"
        return original_read_text(path, *args, **kwargs)

    return patch.object(project_registry_gate.Path, "is_file", fake_is_file), patch.object(
        project_registry_gate.Path,
        "read_text",
        fake_read_text,
    )


class ProjectRegistryGateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        fixture = PLUGIN_ROOT / "tests" / "fixtures" / "projects.v1.json"
        cls.registry = json.loads(fixture.read_text(encoding="utf-8"))

    def test_registry_validates(self) -> None:
        self.assertEqual(project_registry_gate.validate_registry(self.registry), [])

    def test_missing_registration_blocks_project_mandate(self) -> None:
        packet = project_registry_gate.gate_project_mandate(
            "/srv/bears/projects/unregistered",
            registry=self.registry,
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(packet["status"], "PROJECT_REGISTRATION_BLOCKER")
        self.assertEqual(packet["why_blocked"], "missing_project_registration")
        self.assertFalse(packet["project_mandate_allowed"])

    def test_registered_theants_path_allows_project_mandate_after_role_gate(self) -> None:
        packet = project_registry_gate.gate_project_mandate(
            "/srv/bears/dev/app/theants",
            registry=self.registry,
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(packet["status"], "matched")
        self.assertEqual(packet["project_id"], "theants-product")
        self.assertEqual(packet["primary_role"], "bears-product-app-zone-engineer")
        self.assertTrue(packet["project_mandate_allowed"])
        self.assertIs(packet["spec_required"], False)
        self.assertIsNone(packet["spec_path"])
        self.assertIsNone(packet["plan_path"])
        self.assertIsNone(packet["tasks_path"])

    def test_registered_codex_telegram_product_routes_to_telegram_role(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["entries"].insert(
            0,
            {
                "id": "codex-telegram-mcp-product",
                "name": "Codex Telegram MCP product service",
                "kind": "product",
                "artifact_profile": "repo_project",
                "status": "registered",
                "paths": ["/srv/bears/dev/app/codex-telegram"],
                "role_target": "/srv/bears/dev/app/codex-telegram",
                "match_policy": "self_or_child",
                "project_mandate_allowed": True,
                "spec_required": False,
                "spec_path": None,
                "plan_path": None,
                "tasks_path": None,
            },
        )
        packet = project_registry_gate.gate_project_mandate(
            "/srv/bears/dev/app/codex-telegram",
            registry=registry,
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(packet["status"], "matched")
        self.assertEqual(packet["project_id"], "codex-telegram-mcp-product")
        self.assertEqual(packet["primary_role"], "bears-telegram-platform-engineer")
        self.assertTrue(packet["project_mandate_allowed"])

    def test_registered_product_outside_dev_app_is_invalid(self) -> None:
        registry = copy.deepcopy(self.registry)
        entry = copy.deepcopy(registry["entries"][0])
        entry.update(
            {
                "id": "bad-product-path",
                "kind": "product",
                "paths": ["/srv/bears/projects/codex-telegram"],
                "role_target": "/srv/bears/projects/codex-telegram",
            }
        )
        registry["entries"].insert(0, entry)
        errors = project_registry_gate.validate_registry(registry)
        self.assertTrue(
            any("product entries must live under /srv/bears/dev/app/**" in error for error in errors)
        )

    def test_registered_child_path_matches_only_declared_self_or_child_entry(self) -> None:
        packet = project_registry_gate.gate_project_mandate(
            "/srv/bears/dev/app/theants/tests",
            registry=self.registry,
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(packet["status"], "matched")
        self.assertEqual(packet["project_id"], "theants-product")

    def test_registered_workspace_control_agent_reviewer_tests_route_to_governor(self) -> None:
        cases = (
            "/srv/bears/control-plane/workspace-control/tests",
            "/srv/bears/control-plane/workspace-control/tests/test_agent_reviewer_roles.py",
        )
        for target in cases:
            with self.subTest(target=target):
                packet = project_registry_gate.gate_project_mandate(
                    target,
                    registry=self.registry,
                    plugin_root=PLUGIN_ROOT,
                )
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["project_id"], "workspace-control-agent-reviewer-role-tests")
                self.assertEqual(packet["primary_role"], "bears-platform-role-governor")
                self.assertEqual(packet["role_target"], "/srv/bears/control-plane/workspace-control/tests")
                self.assertTrue(packet["project_mandate_allowed"])
                self.assertFalse(packet["spec_required"])

    def test_registered_plugin_local_yandex360_dns_skill_routes_to_network_role(self) -> None:
        packet = project_registry_gate.gate_project_mandate(
            "/srv/bears/plugins/bears/skills/yandex360-dns",
            registry=self.registry,
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(packet["status"], "matched")
        self.assertEqual(packet["project_id"], "bears-workflow-plugin-yandex360-dns")
        self.assertEqual(packet["primary_role"], "bears-infrastructure-network-engineer")
        self.assertTrue(packet["project_mandate_allowed"])
        self.assertFalse(packet["spec_required"])

    def test_registered_plugin_root_routes_to_governance_role_with_exact_match(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["entries"].append(
            {
                "id": "bears-workflow-plugin-root",
                "name": "Bears workflow plugin canonical governance repo",
                "kind": "plugin_governance",
                "artifact_profile": "plugin_repo",
                "status": "registered",
                "paths": [
                    "/srv/bears/plugins/bears",
                ],
                "role_target": "/srv/bears/plugins/bears/AGENTS.md",
                "match_policy": "exact",
                "project_mandate_allowed": True,
                "spec_required": False,
                "spec_path": None,
                "plan_path": None,
                "tasks_path": None,
                "classification": "canonical_plugin_governance_repo",
                "canonical_remote": "BearsCLOUD/bears_plugin",
                "root_owned_payload": False,
                "primary_role": "bears-platform-role-governor",
                "supporting_roles": ["bears-platform-security-reviewer"],
            }
        )
        packet = project_registry_gate.gate_project_mandate(
            "/srv/bears/plugins/bears",
            registry=registry,
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(packet["status"], "matched")
        self.assertEqual(packet["project_id"], "bears-workflow-plugin-root")
        self.assertEqual(packet["primary_role"], "bears-platform-role-governor")
        self.assertEqual(packet["role_target"], "/srv/bears/plugins/bears/AGENTS.md")
        self.assertTrue(packet["project_mandate_allowed"])
        self.assertIs(packet["spec_required"], False)
        self.assertIsNone(packet["spec_path"])
        self.assertIsNone(packet["plan_path"])
        self.assertIsNone(packet["tasks_path"])


    def test_registered_vpn_paths_route_to_exact_roles(self) -> None:
        cases = {
            "/srv/bears/dev/app/vpn": (
                "vpn-project-root",
                "bears-vpn-project-governance-engineer",
            ),
            "/srv/bears/dev/app/vpn/androidapp": (
                "vpn-android-client",
                "bears-vpn-client-app-engineer",
            ),
            "/srv/bears/dev/app/vpn/androidapp/app/src/main/AndroidManifest.xml": (
                "vpn-android-client",
                "bears-vpn-client-app-engineer",
            ),
            "/srv/bears/dev/app/vpn/amnezia-split": (
                "vpn-amnezia-split-runtime",
                "bears-vpn-runtime-engineer",
            ),
            "/srv/bears/dev/app/vpn/amnezia-split/auto_split/autosplit_static_ru.py": (
                "vpn-amnezia-split-runtime",
                "bears-vpn-runtime-engineer",
            ),
        }
        for target, (expected_project_id, expected_role) in cases.items():
            with self.subTest(target=target):
                packet = project_registry_gate.gate_project_mandate(
                    target,
                    registry=self.registry,
                    plugin_root=PLUGIN_ROOT,
                )
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["project_id"], expected_project_id)
                self.assertEqual(packet["primary_role"], expected_role)
                self.assertTrue(packet["project_mandate_allowed"])

    def test_registered_dev_core_infrastructure_network_lane_routes_to_exact_role(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["entries"].append(
            {
                "id": "dev-core-infrastructure-network",
                "name": "Bears dev-core infrastructure network planning/docs lane",
                "kind": "infrastructure",
                "artifact_profile": "module_service",
                "status": "registered",
                "paths": [
                    "/srv/bears/dev/infrastructure/network",
                ],
                "role_target": "/srv/bears/dev/infrastructure/network",
                "match_policy": "self_or_child",
                "project_mandate_allowed": True,
                "spec_required": False,
                "spec_path": None,
                "plan_path": None,
                "tasks_path": None,
            }
        )
        packet = project_registry_gate.gate_project_mandate(
            "/srv/bears/dev/infrastructure/network",
            registry=registry,
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(packet["status"], "matched")
        self.assertEqual(packet["project_id"], "dev-core-infrastructure-network")
        self.assertEqual(packet["primary_role"], "bears-infrastructure-network-engineer")
        self.assertTrue(packet["project_mandate_allowed"])

    def test_registered_bears_platform_local_checkout_allows_repo_root_governance_route(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["entries"].append(
            {
                "id": "bears-platform-local-checkout",
                "name": "Bears platform local checkout broad root",
                "kind": "external_local_checkout",
                "artifact_profile": "repo_project",
                "status": "registered",
                "paths": [
                    "/srv/bears/dev/platform",
                ],
                "role_target": "/srv/bears/dev/platform",
                "match_policy": "self_or_child",
                "project_mandate_allowed": True,
                "spec_required": True,
                "spec_path": "/srv/bears/specs/test/spec.md",
                "plan_path": "/srv/bears/specs/test/plan.md",
                "tasks_path": "/srv/bears/specs/test/tasks.md",
                "classification": "external_local_checkout",
                "canonical_remote": "BearsCLOUD/bears-platform",
                "root_owned_payload": False,
            }
        )
        is_file_patch, read_text_patch = _patch_spec_files(
            "# Tasks\n- [ ] bears-platform-role-governor handles registered local checkout repo-root governance.\n"
        )
        with is_file_patch, read_text_patch:
            packet = project_registry_gate.gate_project_mandate(
                "/srv/bears/dev/platform",
                registry=registry,
                plugin_root=PLUGIN_ROOT,
            )
        self.assertEqual(packet["status"], "matched")
        self.assertEqual(packet["project_id"], "bears-platform-local-checkout")
        self.assertEqual(packet["primary_role"], "bears-platform-role-governor")
        self.assertEqual(packet["concrete_part"], "bears_platform_repo_root")
        self.assertTrue(packet["project_mandate_allowed"])

    def test_registered_universal_core_subtrees_route_to_exact_specialist_roles(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["entries"].extend(
            [
                {
                    "id": "bears-platform-auth-core",
                    "name": "Bears universal auth core subtree",
                    "kind": "platform",
                    "artifact_profile": "module_service",
                    "status": "registered",
                    "paths": ["/srv/bears/dev/platform/src/bears_platform/auth"],
                    "role_target": "/srv/bears/dev/platform/src/bears_platform/auth",
                    "match_policy": "self_or_child",
                    "project_mandate_allowed": True,
                    "spec_required": False,
                    "spec_path": None,
                    "plan_path": None,
                    "tasks_path": None,
                },
                {
                    "id": "bears-platform-gateway-core",
                    "name": "Bears universal gateway core subtree",
                    "kind": "platform",
                    "artifact_profile": "module_service",
                    "status": "registered",
                    "paths": ["/srv/bears/dev/platform/src/bears_platform/gateway"],
                    "role_target": "/srv/bears/dev/platform/src/bears_platform/gateway",
                    "match_policy": "self_or_child",
                    "project_mandate_allowed": True,
                    "spec_required": False,
                    "spec_path": None,
                    "plan_path": None,
                    "tasks_path": None,
                },
                {
                    "id": "bears-platform-billing-core",
                    "name": "Bears universal billing core subtree",
                    "kind": "platform",
                    "artifact_profile": "module_service",
                    "status": "registered",
                    "paths": ["/srv/bears/dev/platform/src/bears_platform/billing"],
                    "role_target": "/srv/bears/dev/platform/src/bears_platform/billing",
                    "match_policy": "self_or_child",
                    "project_mandate_allowed": True,
                    "spec_required": False,
                    "spec_path": None,
                    "plan_path": None,
                    "tasks_path": None,
                },
            ]
        )
        cases = {
            "/srv/bears/dev/platform/src/bears_platform/auth": (
                "bears-platform-auth-core",
                "bears-auth-platform-engineer",
            ),
            "/srv/bears/dev/platform/src/bears_platform/gateway": (
                "bears-platform-gateway-core",
                "bears-gateway-platform-engineer",
            ),
            "/srv/bears/dev/platform/src/bears_platform/billing": (
                "bears-platform-billing-core",
                "bears-payments-platform-engineer",
            ),
        }
        for target, (expected_project_id, expected_role) in cases.items():
            with self.subTest(target=target):
                packet = project_registry_gate.gate_project_mandate(
                    target,
                    registry=registry,
                    plugin_root=PLUGIN_ROOT,
                )
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["project_id"], expected_project_id)
                self.assertEqual(packet["primary_role"], expected_role)
                self.assertTrue(packet["project_mandate_allowed"])

    def test_registered_seller_legacy_sources_route_to_exact_specialist_roles(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["entries"].extend(
            [
                {
                    "id": "seller-auth-core-legacy-source",
                    "name": "Seller auth legacy source",
                    "kind": "legacy_source_checkout",
                    "artifact_profile": "repo_project",
                    "status": "registered",
                    "paths": ["/srv/bears/projects/seller/apps/auth_core"],
                    "role_target": "/srv/bears/projects/seller/apps/auth_core",
                    "match_policy": "self_or_child",
                    "project_mandate_allowed": True,
                    "spec_required": False,
                    "spec_path": None,
                    "plan_path": None,
                    "tasks_path": None,
                },
                {
                    "id": "seller-gateway-legacy-source",
                    "name": "Seller gateway legacy source",
                    "kind": "legacy_source_checkout",
                    "artifact_profile": "repo_project",
                    "status": "registered",
                    "paths": ["/srv/bears/projects/seller/apps/gateway"],
                    "role_target": "/srv/bears/projects/seller/apps/gateway",
                    "match_policy": "self_or_child",
                    "project_mandate_allowed": True,
                    "spec_required": False,
                    "spec_path": None,
                    "plan_path": None,
                    "tasks_path": None,
                },
                {
                    "id": "seller-payment-service-legacy-source",
                    "name": "Seller payment legacy source",
                    "kind": "legacy_source_checkout",
                    "artifact_profile": "repo_project",
                    "status": "registered",
                    "paths": ["/srv/bears/projects/seller/apps/payment_service"],
                    "role_target": "/srv/bears/projects/seller/apps/payment_service",
                    "match_policy": "self_or_child",
                    "project_mandate_allowed": True,
                    "spec_required": False,
                    "spec_path": None,
                    "plan_path": None,
                    "tasks_path": None,
                },
            ]
        )
        cases = {
            "/srv/bears/projects/seller/apps/auth_core": (
                "seller-auth-core-legacy-source",
                "bears-auth-platform-engineer",
            ),
            "/srv/bears/projects/seller/apps/gateway": (
                "seller-gateway-legacy-source",
                "bears-gateway-platform-engineer",
            ),
            "/srv/bears/projects/seller/apps/payment_service": (
                "seller-payment-service-legacy-source",
                "bears-payments-platform-engineer",
            ),
        }
        for target, (expected_project_id, expected_role) in cases.items():
            with self.subTest(target=target):
                packet = project_registry_gate.gate_project_mandate(
                    target,
                    registry=registry,
                    plugin_root=PLUGIN_ROOT,
                )
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["project_id"], expected_project_id)
                self.assertEqual(packet["primary_role"], expected_role)
                self.assertTrue(packet["project_mandate_allowed"])

    def test_dev_network_path_stays_unregistered(self) -> None:
        packet = project_registry_gate.gate_project_mandate(
            "/srv/bears/dev/network",
            registry=self.registry,
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(packet["status"], "PROJECT_REGISTRATION_BLOCKER")
        self.assertEqual(packet["why_blocked"], "missing_project_registration")
        self.assertFalse(packet["project_mandate_allowed"])

    def test_registered_entry_with_project_mandate_disabled_blocks(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["entries"][0]["project_mandate_allowed"] = False
        packet = project_registry_gate.gate_project_mandate(
            "/srv/bears/dev/app/theants",
            registry=registry,
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(packet["status"], "PROJECT_REGISTRATION_BLOCKER")
        self.assertEqual(packet["why_blocked"], "project_mandate_disabled")
        self.assertFalse(packet["project_mandate_allowed"])

    def test_registered_entry_with_unmapped_role_target_blocks_safely(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["entries"][0]["role_target"] = "/srv/bears/dev/app/unmapped-role-target"
        packet = project_registry_gate.gate_project_mandate(
            "/srv/bears/dev/app/theants",
            registry=registry,
            plugin_root=PLUGIN_ROOT,
        )
        self.assertNotEqual(packet["status"], "matched")
        self.assertEqual(packet["project_registration_status"], "registered")
        self.assertEqual(packet["project_id"], "theants-product")
        self.assertFalse(packet["project_mandate_allowed"])

    def test_cli_exit_codes_for_matched_and_missing_paths(self) -> None:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json") as handle:
            json.dump(self.registry, handle)
            handle.flush()

            matched = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--registry",
                    handle.name,
                    "gate",
                    "/srv/bears/dev/app/theants",
                ],
                check=False,
                text=True,
                capture_output=True,
            )
            self.assertEqual(matched.returncode, 0, matched.stderr + matched.stdout)
            self.assertIn("status: matched", matched.stdout)
            self.assertIn("spec_required: false", matched.stdout)

            missing = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--registry",
                    handle.name,
                    "gate",
                    "/srv/bears/projects/unregistered",
                ],
                check=False,
                text=True,
                capture_output=True,
            )
            self.assertEqual(missing.returncode, 2, missing.stderr + missing.stdout)
            self.assertIn("why_blocked: missing_project_registration", missing.stdout)
            self.assertIn("project_mandate_allowed: false", missing.stdout)

    def test_cli_missing_role_catalog_returns_stable_error_without_traceback(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--role-catalog",
                "/tmp/does-not-exist.json",
                "gate",
                "/srv/bears/dev",
            ],
            check=False,
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "ERROR: role catalog not found: /tmp/does-not-exist.json\n")
        self.assertNotIn("Traceback", result.stderr)

    def test_cli_validate_registry_missing_path_fails_without_traceback(self) -> None:
        missing_path = "/tmp/bears-project-registry-missing-for-test.json"
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "--registry",
                missing_path,
                "validate-registry",
            ],
            check=False,
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, f"ERROR: project registry not found: {missing_path}\n")
        self.assertNotIn("Traceback", result.stderr)

    def test_cli_validate_registry_explicit_skip_applies_only_to_default_external_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            default_missing = Path(tmpdir) / "projects.v1.json"
            explicit_missing = Path(tmpdir) / "other-projects.v1.json"
            stdout = io.StringIO()
            stderr = io.StringIO()
            original_default = project_registry_gate.DEFAULT_REGISTRY
            project_registry_gate.DEFAULT_REGISTRY = default_missing
            try:
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    exit_code = project_registry_gate.main(
                        ["--allow-missing-external-registry", "validate-registry"]
                    )
            finally:
                project_registry_gate.DEFAULT_REGISTRY = original_default

            self.assertEqual(exit_code, 0, stderr.getvalue() + stdout.getvalue())
            self.assertEqual(stderr.getvalue(), "")
            self.assertIn(
                f"project registry skipped: external registry missing: {default_missing}",
                stdout.getvalue(),
            )
            self.assertIn("skip_reason: external_registry_missing_in_clean_repo", stdout.getvalue())
            self.assertIn("without --allow-missing-external-registry still fails", stdout.getvalue())

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--allow-missing-external-registry",
                    "--registry",
                    str(explicit_missing),
                    "validate-registry",
                ],
                check=False,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
            self.assertEqual(result.stdout, "")
            self.assertEqual(
                result.stderr, f"ERROR: project registry not found: {explicit_missing}\n"
            )
            self.assertNotIn("Traceback", result.stderr)

    def test_registered_project_mandate_skill_routes_to_governor(self) -> None:
        packet = project_registry_gate.gate_project_mandate(
            "/srv/bears/plugins/bears/skills/project-mandate",
            registry=self.registry,
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(packet["status"], "matched")
        self.assertEqual(packet["primary_role"], "bears-platform-role-governor")


    def test_mandate_packet_is_target_bound_and_forbids_workspace_scan(self) -> None:
        packet = project_registry_gate.build_mandate_packet(
            "/srv/bears/plugins/bears/skills/project-mandate/SKILL.md",
            registry=self.registry,
            registry_path=PLUGIN_ROOT / "tests" / "fixtures" / "projects.v1.json",
            plugin_root=PLUGIN_ROOT,
        )

        self.assertEqual(packet["status"], "matched")
        self.assertEqual(packet["packet_type"], "project_mandate_packet")
        self.assertEqual(packet["nearest_router"], "/srv/bears/plugins/bears/AGENTS.md")
        self.assertIn(".worktrees", packet["forbidden_scan_roots"])
        self.assertIn("runtime", packet["forbidden_scan_roots"])
        self.assertNotIn("required_artifacts", packet)
        self.assertIn("/srv/bears/plugins/bears/skills/project-mandate/SKILL.md", packet["read_paths"])
        self.assertNotIn("/srv/bears", packet["read_paths"])

    def test_mandate_packet_cli_renders_bounded_checklist(self) -> None:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json") as handle:
            json.dump(self.registry, handle)
            handle.flush()

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--registry",
                    handle.name,
                    "mandate-packet",
                    "/srv/bears/plugins/bears/skills/project-mandate/SKILL.md",
                ],
                check=False,
                text=True,
                capture_output=True,
            )

        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("packet_type: project_mandate_packet", result.stdout)
        self.assertIn("workspace_scan: forbidden", result.stdout)
        self.assertNotIn("required_artifacts", result.stdout)

    def test_registered_workspace_control_speckit_surfaces_route_to_governor(self) -> None:
        cases = {
            "/srv/bears": "bears-workspace-control-root",
            "/srv/bears/.specify/feature.json": "bears-workspace-specify-home",
            "/srv/bears/specs/004-dev-e2e-foundation/spec.md": "bears-workspace-feature-004-spec-kit",
            "/srv/bears/contracts/project_start_contract.md": "bears-workspace-project-start-contract",
            "/srv/bears/scripts/validate_workspace_workflow.py": "bears-workspace-workflow-validator",
        }
        for target, expected_project_id in cases.items():
            with self.subTest(target=target):
                packet = project_registry_gate.gate_project_mandate(
                    target,
                    registry=self.registry,
                    plugin_root=PLUGIN_ROOT,
                )
                self.assertEqual(packet["status"], "matched")
                self.assertEqual(packet["project_id"], expected_project_id)
                self.assertEqual(packet["primary_role"], "bears-platform-role-governor")
                self.assertTrue(packet["project_mandate_allowed"])
                self.assertIs(packet["spec_required"], False)
                self.assertIsNone(packet["spec_path"])
                self.assertIsNone(packet["plan_path"])
                self.assertIsNone(packet["tasks_path"])

    def test_invalid_registry_blocks_before_checklist(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["entries"][0]["paths"] = ["/tmp/not-bears"]
        packet = project_registry_gate.gate_project_mandate(
            "/srv/bears/dev/app/theants",
            registry=registry,
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(packet["status"], "PROJECT_REGISTRATION_BLOCKER")
        self.assertEqual(packet["why_blocked"], "registry_invalid")

    def test_registry_requires_spec_fields(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["entries"][0].pop("spec_required")
        errors = project_registry_gate.validate_registry(registry)
        self.assertTrue(any("missing fields" in error and "spec_required" in error for error in errors))

    def test_spec_required_requires_all_artifact_paths(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["entries"][0]["spec_required"] = True
        registry["entries"][0]["spec_path"] = None
        registry["entries"][0]["plan_path"] = None
        registry["entries"][0]["tasks_path"] = None
        errors = project_registry_gate.validate_registry(registry)
        self.assertTrue(any("spec_path is required" in error for error in errors))
        self.assertTrue(any("plan_path is required" in error for error in errors))
        self.assertTrue(any("tasks_path is required" in error for error in errors))

    def test_spec_required_blocks_missing_artifacts(self) -> None:
        registry = _make_spec_required_registry(self.registry)
        packet = project_registry_gate.gate_project_mandate(
            "/srv/bears/dev/app/theants",
            registry=registry,
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(packet["status"], "PROJECT_REGISTRATION_BLOCKER")
        self.assertEqual(packet["why_blocked"], "spec_kit_gate_failed")
        self.assertTrue(any("missing Spec Kit artifact" in error for error in packet["validation_errors"]))

    def test_spec_required_blocks_tasks_without_route_or_role_link(self) -> None:
        registry = _make_spec_required_registry(self.registry)
        is_file_patch, read_text_patch = _patch_spec_files("# Tasks\n- [ ] unrelated work\n")
        with is_file_patch, read_text_patch:
            packet = project_registry_gate.gate_project_mandate(
                "/srv/bears/dev/app/theants",
                registry=registry,
                plugin_root=PLUGIN_ROOT,
            )
        self.assertEqual(packet["status"], "PROJECT_REGISTRATION_BLOCKER")
        self.assertEqual(packet["why_blocked"], "spec_kit_gate_failed")
        self.assertTrue(any("role_target or primary_role" in error for error in packet["validation_errors"]))

    def test_spec_required_blocks_missing_speckit_analyze(self) -> None:
        registry = _make_spec_required_registry(self.registry)
        tasks = "# Tasks\n- [ ] bears-product-app-zone-engineer handles project work.\n"
        is_file_patch, read_text_patch = _patch_spec_files(tasks, include_analyze=False)
        with is_file_patch, read_text_patch:
            packet = project_registry_gate.gate_project_mandate(
                "/srv/bears/dev/app/theants",
                registry=registry,
                plugin_root=PLUGIN_ROOT,
            )
        self.assertEqual(packet["status"], "PROJECT_REGISTRATION_BLOCKER")
        self.assertTrue(any("missing Spec Kit analyze artifact" in error for error in packet["validation_errors"]))

    def test_spec_required_blocks_failed_speckit_analyze(self) -> None:
        registry = _make_spec_required_registry(self.registry)
        tasks = "# Tasks\n- [ ] bears-product-app-zone-engineer handles project work.\n"
        is_file_patch, read_text_patch = _patch_spec_files(
            tasks,
            analyze_payload=_speckit_analyze_payload(status="FAIL"),
        )
        with is_file_patch, read_text_patch:
            packet = project_registry_gate.gate_project_mandate(
                "/srv/bears/dev/app/theants",
                registry=registry,
                plugin_root=PLUGIN_ROOT,
            )
        self.assertEqual(packet["status"], "PROJECT_REGISTRATION_BLOCKER")
        self.assertTrue(any("speckit-analyze.json.status must be PASS" in error for error in packet["validation_errors"]))

    def test_spec_required_accepts_speckit_analyze_pass_case_insensitively(self) -> None:
        registry = _make_spec_required_registry(self.registry)
        tasks = "# Tasks\n- [ ] bears-product-app-zone-engineer handles project work.\n"
        is_file_patch, read_text_patch = _patch_spec_files(
            tasks,
            analyze_payload=_speckit_analyze_payload(status="pass"),
        )
        with is_file_patch, read_text_patch:
            packet = project_registry_gate.gate_project_mandate(
                "/srv/bears/dev/app/theants",
                registry=registry,
                plugin_root=PLUGIN_ROOT,
            )
        self.assertEqual(packet["status"], "matched")
        self.assertTrue(packet["project_mandate_allowed"])

    def test_spec_required_blocks_speckit_analyze_schema_mismatch(self) -> None:
        registry = _make_spec_required_registry(self.registry)
        tasks = "# Tasks\n- [ ] bears-product-app-zone-engineer handles project work.\n"
        is_file_patch, read_text_patch = _patch_spec_files(
            tasks,
            analyze_payload=_speckit_analyze_payload(schema="wrong.schema"),
        )
        with is_file_patch, read_text_patch:
            packet = project_registry_gate.gate_project_mandate(
                "/srv/bears/dev/app/theants",
                registry=registry,
                plugin_root=PLUGIN_ROOT,
            )
        self.assertEqual(packet["status"], "PROJECT_REGISTRATION_BLOCKER")
        self.assertTrue(any("speckit-analyze.json.schema must be bears.speckit-analyze.v1" in error for error in packet["validation_errors"]))

    def test_spec_required_blocks_speckit_analyze_path_mismatch(self) -> None:
        registry = _make_spec_required_registry(self.registry)
        tasks = "# Tasks\n- [ ] bears-product-app-zone-engineer handles project work.\n"
        is_file_patch, read_text_patch = _patch_spec_files(
            tasks,
            analyze_payload=_speckit_analyze_payload(spec_path="/srv/bears/specs/wrong/spec.md"),
        )
        with is_file_patch, read_text_patch:
            packet = project_registry_gate.gate_project_mandate(
                "/srv/bears/dev/app/theants",
                registry=registry,
                plugin_root=PLUGIN_ROOT,
            )
        self.assertEqual(packet["status"], "PROJECT_REGISTRATION_BLOCKER")
        self.assertTrue(any("speckit-analyze.json.spec_path must match current file" in error for error in packet["validation_errors"]))

    def test_spec_required_blocks_restricted_mutation_without_approval(self) -> None:
        registry = _make_spec_required_registry(self.registry)
        tasks = "# Tasks\n- [ ] bears-product-app-zone-engineer handles production mutation.\n"
        is_file_patch, read_text_patch = _patch_spec_files(tasks)
        with is_file_patch, read_text_patch:
            packet = project_registry_gate.gate_project_mandate(
                "/srv/bears/dev/app/theants",
                registry=registry,
                plugin_root=PLUGIN_ROOT,
            )
        self.assertEqual(packet["status"], "PROJECT_REGISTRATION_BLOCKER")
        self.assertTrue(any("operator approval" in error for error in packet["validation_errors"]))

    def test_spec_required_allows_role_link_and_operator_approval(self) -> None:
        registry = _make_spec_required_registry(self.registry)
        tasks = (
            "# Tasks\n"
            "- [ ] bears-product-app-zone-engineer handles production mutation only after operator approval.\n"
        )
        is_file_patch, read_text_patch = _patch_spec_files(tasks)
        with is_file_patch, read_text_patch:
            packet = project_registry_gate.gate_project_mandate(
                "/srv/bears/dev/app/theants",
                registry=registry,
                plugin_root=PLUGIN_ROOT,
            )
        self.assertEqual(packet["status"], "matched")
        self.assertTrue(packet["project_mandate_allowed"])


if __name__ == "__main__":
    unittest.main()


class ProjectRegistryLiveRegistryDeskTest(unittest.TestCase):
    @unittest.skipUnless(
        LIVE_WORKSPACE_REGISTRY.exists(),
        "live workspace registry is outside this plugin checkout",
    )
    def test_live_registry_routes_desk_checkout_to_exact_product_role(self) -> None:
        live_registry = json.loads(LIVE_WORKSPACE_REGISTRY.read_text(encoding='utf-8'))
        packet = project_registry_gate.gate_project_mandate(
            '/srv/bears/dev/app/desk',
            registry=live_registry,
            plugin_root=PLUGIN_ROOT,
        )
        self.assertEqual(packet['status'], 'matched')
        self.assertEqual(packet['project_id'], 'desk-project')
        self.assertEqual(packet['primary_role'], 'bears-product-app-zone-engineer')
        self.assertEqual(packet['role_target'], '/srv/bears/dev/app/desk')
        self.assertTrue(packet['project_mandate_allowed'])
