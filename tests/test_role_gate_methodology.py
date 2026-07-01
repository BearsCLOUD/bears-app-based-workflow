from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.function_test_loader import load_function_tests

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PLUGIN_ROOT / "scripts" / "role_gate_methodology.py"
spec = importlib.util.spec_from_file_location("role_gate_methodology", SCRIPT_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)  # type: ignore[arg-type]


def _methodology() -> dict:
    return json.loads((PLUGIN_ROOT / "assets/catalog/role-gate-methodology.v1.json").read_text())


def _catalog() -> dict:
    return json.loads((PLUGIN_ROOT / "assets/catalog/platform-role-catalog.v1.json").read_text())


def test_methodology_validates_current_catalog_alignment() -> None:
    errors = module.validate_all(
        PLUGIN_ROOT / "assets/catalog/role-gate-methodology.v1.json",
        PLUGIN_ROOT / "assets/catalog/platform-role-catalog.v1.json",
        plugin_root=PLUGIN_ROOT,
    )
    assert errors == []


def test_exact_blocker_packet_shape_is_enforced() -> None:
    methodology = _methodology()
    methodology["blocker_packet"]["required_fields"].remove("why_blocked")
    errors = module.validate_methodology(methodology)
    assert any("required_fields" in error for error in errors)


def test_canonical_methodology_items_are_enforced() -> None:
    methodology = _methodology()
    methodology["methodology_items"] = methodology["methodology_items"][:-1]
    errors = module.validate_methodology(methodology)
    assert any("methodology_items ids/order must match canonical methodology" in error for error in errors)


def test_control_audit_evidence_document_is_enforced() -> None:
    methodology = _methodology()
    methodology["control_audit_evidence"]["required_document"] = "docs/reference/missing-evidence.md"
    errors = module.validate_methodology(methodology)
    assert any("control_audit_evidence.required_document missing" in error for error in errors)


def test_broad_fallback_flag_is_enforced() -> None:
    methodology = _methodology()
    catalog = _catalog()
    catalog["mandatory_policy"]["broad_fallback_matching_allowed"] = True
    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert any("broad_fallback_matching_allowed" in error for error in errors)


def test_parent_only_alignment_is_enforced() -> None:
    methodology = _methodology()
    catalog = _catalog()
    policy = catalog["mandatory_policy"]
    policy["parent_only_targets"] = [
        item for item in policy["parent_only_targets"] if item != "/srv/bears/projects/seller/apps"
    ]
    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert any("/srv/bears/projects/seller/apps" in error and "why_blocked" in error for error in errors)


def test_deploy_core_must_keep_exact_primary_role() -> None:
    methodology = _methodology()
    catalog = _catalog()
    for part in catalog["platform_parts"]:
        if part["name"] == "auth_gateway_deploy_core":
            part["required_role"] = "bears-workflow-overlay-controller"
            break
    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert any("auth-gateway-deploy-core" in error for error in errors)


def test_dev_core_and_theants_alignment_targets_are_enforced() -> None:
    methodology = _methodology()
    catalog = _catalog()
    required_targets = {
        "/srv/bears/dev",
        "kube",
        "/srv/bears/kubernetes",
        "/srv/bears/plugins/bears",
        "android-emulator",
        "sentry",
        "/srv/bears/dev/products/theants",
        "/srv/bears/projects/theants",
        "BearsCLOUD/bears_plugin",
        "BearsCLOUD/bears-codex-workspace",
        "/srv/bears/.gitmodules",
    }
    alignment_targets = {item["target"] for item in methodology["catalog_alignment_checks"]}
    assert required_targets <= alignment_targets

    for part in catalog["platform_parts"]:
        if part["name"] == "theants_product_dev_layer":
            part["required_role"] = "bears-telegram-platform-engineer"
            break

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert any("/srv/bears/projects/theants" in error for error in errors)


def test_audit_completion_criteria_are_generic_and_complete() -> None:
    methodology = _methodology()
    confirmations = set(methodology["independent_control_audit"]["must_confirm"])
    assert module.REQUIRED_AUDIT_CONFIRMATIONS <= confirmations
    item_rules = "\n".join(item["rule"] for item in methodology["methodology_items"]).casefold()
    joined = ("\n".join(confirmations) + "\n" + item_rules).casefold()
    assert "telegram" not in joined
    assert "seller-only" not in joined


def test_primary_role_selection_rule_mentions_exact_match_and_ambiguity() -> None:
    methodology = _methodology()
    selection_item = next(item for item in methodology["methodology_items"] if item["id"] == "choose_exactly_one_primary_role")
    rule = selection_item["rule"]
    assert "exact aliases" in rule
    assert "declared write roots" in rule
    assert "ambiguous_owner" in rule
    assert "Source repository identities" in rule
    assert "classification-only" in rule
    assert "gitlink" in rule
    assert "/srv/bears/kubernetes is a kubernetes_deploy_core repo-root route" in rule


def test_plugin_root_submodule_gitlink_alignment_is_matched() -> None:
    methodology = _methodology()
    catalog = _catalog()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}

    check = checks["/srv/bears/plugins/bears"]
    assert check["expected_status"] == "matched"
    assert check["required_route_id"] == "workspace_root_submodule_gitlinks"
    assert check["required_role"] == "bears-platform-role-governor"

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert errors == []


def test_kubernetes_root_alignment_routes_to_deploy_core() -> None:
    methodology = _methodology()
    catalog = _catalog()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}

    check = checks["/srv/bears/kubernetes"]
    assert check["expected_status"] == "matched"
    assert check["required_route_id"] == "kubernetes_deploy_core"
    assert check["required_role"] == "bears-deploy-platform-engineer"

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert errors == []


def test_kubernetes_dev_core_router_layer_alignment_is_matched() -> None:
    methodology = _methodology()
    catalog = _catalog()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}
    check = checks["/srv/bears/dev/infrastructure/kubernetes"]
    assert check["expected_status"] == "matched"
    assert check["required_route_id"] == "kubernetes_dev_core_router_layer"
    assert check["required_role"] == "bears-deploy-platform-engineer"
    assert check.get("semantics") == "reference_router_only"

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert errors == []


def test_bears_platform_auth_child_alignment_is_matched() -> None:
    methodology = _methodology()
    catalog = _catalog()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}
    check = checks["/srv/bears/dev/platform/src/bears_platform/auth"]
    assert check["expected_status"] == "matched"
    assert check["required_route_id"] == "auth_core"
    assert check["required_role"] == "bears-auth-platform-engineer"

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert errors == []


def test_bears_platform_tenant_registry_alias_alignment_is_matched() -> None:
    methodology = _methodology()
    catalog = _catalog()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}
    check = checks["tenant_registry"]
    assert check["expected_status"] == "matched"
    assert check["required_route_id"] == "bears_platform_tenant_registry_surface"
    assert check["required_role"] == "bears-tenant-registry-platform-engineer"

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert errors == []


def test_bears_platform_tenant_registry_alias_path_drift_stays_unmapped() -> None:
    methodology = _methodology()
    catalog = _catalog()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}
    check = checks["tenant_registry/unknown_future_child"]
    assert check["expected_status"] == "ROLE_COVERAGE_BLOCKER"
    assert check["why_blocked"] == "unmapped"

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert errors == []


def test_bears_platform_tenant_registry_surface_alignment_is_matched() -> None:
    methodology = _methodology()
    catalog = _catalog()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}
    check = checks["/srv/bears/dev/platform/src/bears_platform/tenant_registry"]
    assert check["expected_status"] == "matched"
    assert check["required_route_id"] == "bears_platform_tenant_registry_surface"
    assert check["required_role"] == "bears-tenant-registry-platform-engineer"

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert errors == []


def test_pr128_registry_test_path_alignment_is_matched() -> None:
    methodology = _methodology()
    catalog = _catalog()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}
    cases = {
        "tests/test_tenant_registry_contracts.py": "bears_platform_tenant_registry_contract_tests",
        "tests/test_zone_registry_contracts.py": "bears_platform_zone_registry_contract_tests",
        "tests/test_zone_registry_runtime.py": "bears_platform_zone_registry_runtime_tests",
    }
    for target, expected_route in cases.items():
        check = checks[target]
        assert check["expected_status"] == "matched"
        assert check["required_route_id"] == expected_route
        assert check["required_role"] == "bears-tenant-registry-platform-engineer"

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert errors == []


def test_bears_platform_repo_root_alignment_is_matched() -> None:
    methodology = _methodology()
    catalog = _catalog()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}

    exact_check = checks["/srv/bears/dev/platform"]
    assert exact_check["expected_status"] == "matched"
    assert exact_check["required_route_id"] == "bears_platform_repo_root"
    assert exact_check["required_role"] == "bears-platform-role-governor"

    repo_check = checks["BearsCLOUD/bears-platform"]
    assert repo_check["expected_status"] == "matched"
    assert repo_check["required_route_id"] == "bears_platform_repo_root"
    assert repo_check["required_role"] == "bears-platform-role-governor"

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert errors == []


def test_bears_platform_repo_router_docs_alignment_is_matched() -> None:
    methodology = _methodology()
    catalog = _catalog()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}

    for target in [
        "/srv/bears/dev/platform/AGENTS.md",
        "/srv/bears/dev/platform/docs/stage-rules.md",
    ]:
        check = checks[target]
        assert check["expected_status"] == "matched"
        assert check["required_route_id"] == "bears_platform_repo_router_docs"
        assert check["required_role"] == "bears-platform-role-governor"

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert errors == []


def test_bears_platform_deploy_child_alignment_is_matched() -> None:
    methodology = _methodology()
    catalog = _catalog()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}
    check = checks["/srv/bears/dev/platform/src/bears_platform/deploy"]
    assert check["expected_status"] == "matched"
    assert check["required_route_id"] == "cd_deploy_stage"
    assert check["required_role"] == "bears-deploy-platform-engineer"

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert errors == []


def test_bears_platform_deploy_contract_test_alignment_is_matched() -> None:
    methodology = _methodology()
    catalog = _catalog()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}
    check = checks["/srv/bears/dev/platform/tests/test_deploy_contracts.py"]
    assert check["expected_status"] == "matched"
    assert check["required_route_id"] == "cd_deploy_stage_contract_tests"
    assert check["required_role"] == "bears-deploy-platform-engineer"

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert errors == []


def test_bears_platform_auth_contract_test_alignment_is_matched() -> None:
    methodology = _methodology()
    catalog = _catalog()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}
    check = checks["/srv/bears/dev/platform/tests/test_auth_contracts.py"]
    assert check["expected_status"] == "matched"
    assert check["required_route_id"] == "auth_core_contract_tests"
    assert check["required_role"] == "bears-auth-platform-engineer"

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert errors == []


def test_bears_platform_feature_008_auth_exact_file_alignment_is_matched() -> None:
    methodology = _methodology()
    catalog = _catalog()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}

    for target in [
        "/srv/bears/dev/platform/docs/migration/auth-source-to-target-matrix.md",
        "/srv/bears/dev/platform/tests/fixtures/auth_session_contracts.py",
        "/srv/bears/dev/platform/tests/test_auth_session_contracts.py",
        "/srv/bears/dev/platform/tests/test_integration_token_contracts.py",
    ]:
        check = checks[target]
        assert check["expected_status"] == "matched"
        assert check["required_route_id"] == "bears_platform_auth_feature_008_contract_scope"
        assert check["required_role"] == "bears-auth-platform-engineer"

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert errors == []


def test_bears_platform_gateway_contract_test_alignment_is_matched() -> None:
    methodology = _methodology()
    catalog = _catalog()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}
    check = checks["/srv/bears/dev/platform/tests/test_gateway_contracts.py"]
    assert check["expected_status"] == "matched"
    assert check["required_route_id"] == "bears_gateway_contract_tests"
    assert check["required_role"] == "bears-gateway-platform-engineer"

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert errors == []


def test_bears_platform_gateway_runtime_contract_test_alignment_is_matched() -> None:
    methodology = _methodology()
    catalog = _catalog()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}
    check = checks["/srv/bears/dev/platform/tests/test_gateway_runtime_contracts.py"]
    assert check["expected_status"] == "matched"
    assert check["required_route_id"] == "bears_gateway_runtime_contract_tests"
    assert check["required_role"] == "bears-gateway-platform-engineer"

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert errors == []


def test_bears_platform_feature_008_gateway_exact_file_alignment_is_matched() -> None:
    methodology = _methodology()
    catalog = _catalog()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}

    for target in [
        "/srv/bears/dev/platform/docs/migration/gateway-legacy-route-matrix.md",
        "/srv/bears/dev/platform/tests/fixtures/gateway_route_matrix.py",
    ]:
        check = checks[target]
        assert check["expected_status"] == "matched"
        assert check["required_route_id"] == "bears_gateway_feature_008_route_scope"
        assert check["required_role"] == "bears-gateway-platform-engineer"

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert errors == []


def test_bears_platform_gateway_seller_route_pack_fixture_alignment_is_matched() -> None:
    methodology = _methodology()
    catalog = _catalog()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}
    check = checks["/srv/bears/dev/platform/tests/fixtures/seller_route_pack.py"]
    assert check["expected_status"] == "matched"
    assert check["required_route_id"] == "bears_gateway_seller_route_pack_fixture"
    assert check["required_role"] == "bears-gateway-platform-engineer"

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert errors == []


def test_bears_platform_gateway_route_pack_contract_test_alignment_is_matched() -> None:
    methodology = _methodology()
    catalog = _catalog()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}
    check = checks["/srv/bears/dev/platform/tests/test_gateway_route_pack.py"]
    assert check["expected_status"] == "matched"
    assert check["required_route_id"] == "bears_gateway_route_pack_contract_tests"
    assert check["required_role"] == "bears-gateway-platform-engineer"

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert errors == []


def test_bears_platform_gateway_auth_mode_map_contract_test_alignment_is_matched() -> None:
    methodology = _methodology()
    catalog = _catalog()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}
    check = checks["/srv/bears/dev/platform/tests/test_gateway_auth_mode_map.py"]
    assert check["expected_status"] == "matched"
    assert check["required_route_id"] == "bears_gateway_auth_mode_map_contract_tests"
    assert check["required_role"] == "bears-gateway-platform-engineer"

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert errors == []


def test_bears_platform_gateway_tenant_registry_binding_contract_test_alignment_is_matched() -> None:
    methodology = _methodology()
    catalog = _catalog()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}
    check = checks["/srv/bears/dev/platform/tests/test_gateway_tenant_registry_binding.py"]
    assert check["expected_status"] == "matched"
    assert check["required_route_id"] == "bears_gateway_tenant_registry_binding_contract_tests"
    assert check["required_role"] == "bears-gateway-platform-engineer"

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert errors == []


def test_bears_platform_gateway_runtime_service_contract_test_alignment_is_matched() -> None:
    methodology = _methodology()
    catalog = _catalog()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}
    check = checks["/srv/bears/dev/platform/tests/test_gateway_runtime_service.py"]
    assert check["expected_status"] == "matched"
    assert check["required_route_id"] == "bears_gateway_runtime_service_contract_tests"
    assert check["required_role"] == "bears-gateway-platform-engineer"

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert errors == []


def test_bears_platform_tenant_registry_runtime_contract_test_alignment_is_matched() -> None:
    methodology = _methodology()
    catalog = _catalog()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}
    check = checks["/srv/bears/dev/platform/tests/test_tenant_registry_runtime_contracts.py"]
    assert check["expected_status"] == "matched"
    assert check["required_route_id"] == "bears_platform_tenant_registry_runtime_contract_tests"
    assert check["required_role"] == "bears-tenant-registry-platform-engineer"

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert errors == []


def test_bears_platform_billing_contract_test_alignment_is_matched() -> None:
    methodology = _methodology()
    catalog = _catalog()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}
    billing_alias = checks["billing"]
    assert billing_alias["expected_status"] == "matched"
    assert billing_alias["required_route_id"] == "bears_platform_billing_surface"
    assert billing_alias["required_role"] == "bears-payments-platform-engineer"

    check = checks["/srv/bears/dev/platform/tests/test_billing_contracts.py"]
    assert check["expected_status"] == "matched"
    assert check["required_route_id"] == "bears_platform_billing_contract_tests"
    assert check["required_role"] == "bears-payments-platform-engineer"

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert errors == []


def test_bears_platform_billing_runtime_service_contract_test_alignment_is_matched() -> None:
    methodology = _methodology()
    catalog = _catalog()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}
    check = checks["/srv/bears/dev/platform/tests/test_billing_runtime_service.py"]
    assert check["expected_status"] == "matched"
    assert check["required_route_id"] == "bears_platform_billing_runtime_service_contract_tests"
    assert check["required_role"] == "bears-payments-platform-engineer"

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert errors == []


def test_bears_platform_billing_processing_contract_test_alignment_is_matched() -> None:
    methodology = _methodology()
    catalog = _catalog()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}
    check = checks["/srv/bears/dev/platform/tests/test_billing_processing_contracts.py"]
    assert check["expected_status"] == "matched"
    assert check["required_route_id"] == "bears_platform_billing_processing_contract_tests"
    assert check["required_role"] == "bears-payments-platform-engineer"

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert errors == []


def test_bears_platform_billing_next_exact_contract_test_alignment_is_matched() -> None:
    methodology = _methodology()
    catalog = _catalog()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}

    for target, route_id in [
        (
            "/srv/bears/dev/platform/tests/test_billing_status_adapters.py",
            "bears_platform_billing_status_adapter_contract_tests",
        ),
        (
            "/srv/bears/dev/platform/tests/test_billing_idempotency.py",
            "bears_platform_billing_idempotency_contract_tests",
        ),
        (
            "/srv/bears/dev/platform/tests/test_billing_money_units.py",
            "bears_platform_billing_money_units_contract_tests",
        ),
    ]:
        check = checks[target]
        assert check["expected_status"] == "matched"
        assert check["required_route_id"] == route_id
        assert check["required_role"] == "bears-payments-platform-engineer"

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert errors == []


def test_bears_platform_payments_worker_isolation_alignment_is_matched() -> None:
    methodology = _methodology()
    catalog = _catalog()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}

    for target, route_id in [
        (
            "tests/test_payments_worker_isolation_contract.py",
            "bears_platform_payments_worker_isolation_contract_tests",
        ),
        (
            "/srv/bears/dev/platform/tests/test_payments_worker_isolation_contract.py",
            "bears_platform_payments_worker_isolation_contract_tests",
        ),
        (
            "tests/fixtures/payments_worker_isolation.py",
            "bears_platform_payments_worker_isolation_fixture",
        ),
        (
            "/srv/bears/dev/platform/tests/fixtures/payments_worker_isolation.py",
            "bears_platform_payments_worker_isolation_fixture",
        ),
    ]:
        check = checks[target]
        assert check["expected_status"] == "matched"
        assert check["required_route_id"] == route_id
        assert check["required_role"] == "bears-payments-platform-engineer"

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert errors == []


def test_bears_platform_feature_008_billing_exact_file_alignment_is_matched() -> None:
    methodology = _methodology()
    catalog = _catalog()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}

    for target in [
        "/srv/bears/dev/platform/docs/migration/billing-status-adapter-matrix.md",
        "/srv/bears/dev/platform/tests/fixtures/billing_status_adapters.py",
    ]:
        check = checks[target]
        assert check["expected_status"] == "matched"
        assert check["required_route_id"] == "bears_platform_billing_feature_008_adapter_scope"
        assert check["required_role"] == "bears-payments-platform-engineer"

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert errors == []


def test_legacy_seller_source_alignment_targets_are_enforced() -> None:
    methodology = _methodology()
    catalog = _catalog()
    required_targets = {
        "/srv/bears/legacy/seller/apps/auth_core",
        "/srv/bears/legacy/seller/apps/gateway",
        "/srv/bears/legacy/seller/apps/cd_deploy_stage",
        "/srv/bears/legacy/seller/apps/payment_service",
    }
    alignment_targets = {item["target"] for item in methodology["catalog_alignment_checks"]}
    assert required_targets <= alignment_targets

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert errors == []


def test_broad_dev_infrastructure_remains_parent_only_blocked() -> None:
    methodology = _methodology()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}
    check = checks["/srv/bears/dev/infrastructure"]
    assert check["expected_status"] == "ROLE_COVERAGE_BLOCKER"
    assert check["why_blocked"] == "parent_only"

    import sys

    sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
    try:
        import platform_roles  # type: ignore
    finally:
        sys.path.remove(str(PLUGIN_ROOT / "scripts"))

    packet = platform_roles.route_target(_catalog(), "/srv/bears/dev/infrastructure", plugin_root=PLUGIN_ROOT)
    assert packet["status"] == "ROLE_COVERAGE_BLOCKER"
    assert packet["why_blocked"] == "parent_only"


def test_deprecated_git_remote_hygiene_alignment_is_narrow_and_exact() -> None:
    methodology = _methodology()
    catalog = _catalog()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}

    exact_targets = [
        "/srv/bears/deprecated/legacy-2026-05-11/docs/docs-core/.git/config",
        "/srv/bears/deprecated/legacy-2026-05-11/docs/docs-mcp/repo/.git/config",
        "/srv/bears/deprecated/legacy-2026-05-11/docs/docs-mcp/orphaned-from-docs-repo-20260419T1300Z/ad_stat/.git/config",
    ]
    for target in exact_targets:
        check = checks[target]
        assert check["expected_status"] == "matched"
        assert check["required_route_id"] == "deprecated_local_git_remote_hygiene"
        assert check["required_role"] == "bears-deprecated-git-remote-hygiene-engineer"

    blocked = checks["/srv/bears/deprecated"]
    assert blocked["expected_status"] == "ROLE_COVERAGE_BLOCKER"
    assert blocked["why_blocked"] == "unmapped"

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert errors == []


def test_subagent_start_packet_alignment_has_exact_route_without_broad_contracts_fallback() -> None:
    methodology = _methodology()
    catalog = _catalog()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}

    exact_check = checks["/srv/bears/dev/contracts/subagent_start_packet.md"]
    assert exact_check["expected_status"] == "matched"
    assert exact_check["required_route_id"] == "subagent_start_packet_contract"
    assert exact_check["required_role"] == "bears-subagent-orchestration-engineer"

    broad_check = checks["/srv/bears/dev/contracts"]
    assert broad_check["expected_status"] == "ROLE_COVERAGE_BLOCKER"
    assert broad_check["why_blocked"] in {"parent_only", "unmapped"}

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert errors == []


def test_sentry_alias_keeps_observability_route_id() -> None:
    methodology = _methodology()
    catalog = _catalog()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}
    assert checks["sentry"]["required_route_id"] == "sentry_observability_226"

    for part in catalog["platform_parts"]:
        if part["name"] == "sentry_observability_226":
            part["name"] = "sentry_observability_drift"
            break
    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert any("sentry" in error and "expected route sentry_observability_226" in error for error in errors)


def test_cli_missing_role_catalog_reports_stable_error_without_traceback() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--role-catalog",
            "/tmp/does-not-exist.json",
            "validate",
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == "ERROR: role catalog not found: /tmp/does-not-exist.json\n"
    assert "Traceback" not in result.stderr


def _issue22_design_packet() -> dict[str, object]:
    return {
        "change_type": "role gate",
        "design_required": True,
        "design_artifact": {
            "path": "README.md#issue-22-design-artifact-contract",
            "sections": list(module.REQUIRED_DESIGN_SECTIONS),
        },
        "design_skip": None,
        "affected_artifacts": ["assets/catalog/role-gate-methodology.v1.json"],
        "validator_impact": ["validate_design_artifact_contract"],
        "documentation_impact": ["README.md"],
        "test_plan": ["issue #22 tests"],
        "safety_boundaries": ["repo-only governance files"],
        "behavior_branches": ["required design", "approved skip"],
    }


def test_issue22_design_contract_validates() -> None:
    methodology = _methodology()
    assert module.validate_design_artifact_contract(methodology["design_artifact_contract"]) == []
    assert methodology["design_artifact_contract"]["artifact_path"] == "README.md#issue-22-design-artifact-contract"


def test_issue22_required_design_packet_validates() -> None:
    methodology = _methodology()
    assert module.validate_implementation_packet(_issue22_design_packet(), methodology["design_artifact_contract"]) == []


def test_issue22_approved_skip_validates() -> None:
    methodology = _methodology()
    packet = _issue22_design_packet()
    packet["design_artifact"] = None
    packet["design_skip"] = {"type": "approved_skip", "approved_by": "operator", "approval_reference": "issue-22", "reason": "bounded override"}
    assert module.validate_implementation_packet(packet, methodology["design_artifact_contract"]) == []


def test_issue22_narrow_bugfix_skip_validates() -> None:
    methodology = _methodology()
    packet = _issue22_design_packet()
    packet["design_artifact"] = None
    packet["design_skip"] = {
        "type": "narrow_bugfix_skip",
        "exact_file_scope": "scripts/role_gate_methodology.py",
        "no_boundary_change": True,
        "no_runtime_change": True,
        "no_deploy_change": True,
        "no_restricted_data_change": True,
        "no_public_behavior_change": True,
        "no_contract_or_proof_schema_change": True,
    }
    assert module.validate_implementation_packet(packet, methodology["design_artifact_contract"]) == []


def test_issue75_rejects_contract_shape_change_under_silent_narrow_bugfix_skip() -> None:
    methodology = _methodology()
    packet = _issue22_design_packet()
    packet["design_artifact"] = None
    packet["affected_artifacts"] = ["docs/reference/packets/t903-proof.json"]
    packet["validator_impact"] = ["validator field addition for local_image_cache_observed_proof"]
    packet["test_plan"] = ["contract test defines a new proof field"]
    packet["design_skip"] = {
        "type": "narrow_bugfix_skip",
        "exact_file_scope": "scripts/validate_t903.py",
        "no_boundary_change": True,
        "no_runtime_change": True,
        "no_deploy_change": True,
        "no_restricted_data_change": True,
        "no_public_behavior_change": True,
        "no_contract_or_proof_schema_change": True,
    }
    errors = module.validate_implementation_packet(packet, methodology["design_artifact_contract"])
    assert any("contract/proof/schema field changes requires Spec Kit" in error for error in errors)


def test_issue75_accepts_contract_shape_change_with_internal_rationale_and_route_checklist() -> None:
    methodology = _methodology()
    packet = _issue22_design_packet()
    packet["design_artifact"] = None
    packet["affected_artifacts"] = ["scripts/validate_t903.py"]
    packet["validator_impact"] = ["internal validator field only; no packet field accepted from operators"]
    packet["design_skip"] = {
        "type": "narrow_bugfix_skip",
        "exact_file_scope": "scripts/validate_t903.py",
        "no_boundary_change": True,
        "no_runtime_change": True,
        "no_deploy_change": True,
        "no_restricted_data_change": True,
        "no_public_behavior_change": True,
        "no_contract_or_proof_schema_change": False,
        "non_interface_contract_rationale": "The field is internal-only and is not accepted in proof packets.",
        "route_specific_checklist_accepts_internal_only": True,
    }
    assert module.validate_implementation_packet(packet, methodology["design_artifact_contract"]) == []


def test_issue77_validation_command_policy_uses_repo_relative_unittest_command() -> None:
    methodology = _methodology()
    errors = module.validate_validation_command_policy(methodology["validation_command_policy"])
    assert errors == []
    policy = methodology["validation_command_policy"]
    assert policy["working_directory"] == "/srv/bears/plugins/bears"
    assert policy["canonical_unittest_command"] == "python3 -m unittest tests/test_platform_roles.py tests/test_role_gate_methodology.py"
    assert "/srv/bears/plugins/bears/tests/" not in policy["canonical_unittest_command"]


def test_issue77_validation_command_policy_rejects_absolute_unittest_command() -> None:
    methodology = _methodology()
    policy = dict(methodology["validation_command_policy"])
    policy["canonical_unittest_command"] = "python3 -m unittest /srv/bears/plugins/bears/tests/test_platform_roles.py"
    errors = module.validate_validation_command_policy(policy)
    assert any("repo-relative test paths" in error for error in errors)


def test_issue22_rejects_missing_decision_table_for_branch_behavior() -> None:
    methodology = _methodology()
    packet = _issue22_design_packet()
    packet["design_artifact"]["sections"].remove("decision table or policy matrix")
    errors = module.validate_implementation_packet(packet, methodology["design_artifact_contract"])
    assert any("decision table" in error for error in errors)


def test_issue22_rejects_missing_validator_impact() -> None:
    methodology = _methodology()
    packet = _issue22_design_packet()
    packet["validator_impact"] = []
    errors = module.validate_implementation_packet(packet, methodology["design_artifact_contract"])
    assert any("validator_impact" in error for error in errors)


def test_issue22_rejects_missing_design() -> None:
    methodology = _methodology()
    packet = _issue22_design_packet()
    packet["design_artifact"] = None
    errors = module.validate_implementation_packet(packet, methodology["design_artifact_contract"])
    assert any("missing required design" in error for error in errors)


class Issue22RoleGateMethodologyUnittest(unittest.TestCase):
    def test_auto_role_development_contract_validates_unittest(self) -> None:
        methodology = _methodology()
        catalog = _catalog()
        role_development = methodology["blocker_packet"]["role_development"]
        self.assertEqual(role_development["lane"], "role-development")
        self.assertEqual(role_development["owner_role"], "bears-platform-role-governor")
        self.assertIn(
            "python3 scripts/platform_roles.py role-development-plan <target> --json",
            role_development["rerun_commands"],
        )
        self.assertEqual([], module.validate_methodology(methodology))
        self.assertEqual([], module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT))

    def test_auto_role_development_contract_is_required_unittest(self) -> None:
        methodology = _methodology()
        methodology["blocker_packet"].pop("role_development")
        methodology["blocker_packet"]["required_fields"].remove("role_development")
        errors = module.validate_methodology(methodology)
        self.assertTrue(any("role_development" in error for error in errors))

    def test_catalog_auto_role_development_contract_is_required_unittest(self) -> None:
        methodology = _methodology()
        catalog = _catalog()
        catalog["mandatory_policy"].pop("role_development")
        errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
        self.assertTrue(any("role_development" in error for error in errors))

    def test_issue22_design_contract_validates_unittest(self) -> None:
        methodology = _methodology()
        self.assertEqual([], module.validate_design_artifact_contract(methodology["design_artifact_contract"]))
        self.assertEqual("README.md#issue-22-design-artifact-contract", methodology["design_artifact_contract"]["artifact_path"])

    def test_issue22_required_design_packet_validates_unittest(self) -> None:
        methodology = _methodology()
        self.assertEqual([], module.validate_implementation_packet(_issue22_design_packet(), methodology["design_artifact_contract"]))

    def test_issue22_approved_skip_validates_unittest(self) -> None:
        methodology = _methodology()
        packet = _issue22_design_packet()
        packet["design_artifact"] = None
        packet["design_skip"] = {"type": "approved_skip", "approved_by": "operator", "approval_reference": "issue-22", "reason": "bounded override"}
        self.assertEqual([], module.validate_implementation_packet(packet, methodology["design_artifact_contract"]))

    def test_issue22_narrow_bugfix_skip_validates_unittest(self) -> None:
        methodology = _methodology()
        packet = _issue22_design_packet()
        packet["design_artifact"] = None
        packet["design_skip"] = {
            "type": "narrow_bugfix_skip",
            "exact_file_scope": "scripts/role_gate_methodology.py",
            "no_boundary_change": True,
            "no_runtime_change": True,
            "no_deploy_change": True,
            "no_restricted_data_change": True,
            "no_public_behavior_change": True,
            "no_contract_or_proof_schema_change": True,
        }
        self.assertEqual([], module.validate_implementation_packet(packet, methodology["design_artifact_contract"]))

    def test_issue22_rejects_missing_decision_table_for_branch_behavior_unittest(self) -> None:
        methodology = _methodology()
        packet = _issue22_design_packet()
        packet["design_artifact"]["sections"].remove("decision table or policy matrix")
        errors = module.validate_implementation_packet(packet, methodology["design_artifact_contract"])
        self.assertTrue(any("decision table" in error for error in errors))

    def test_issue22_rejects_missing_validator_impact_unittest(self) -> None:
        methodology = _methodology()
        packet = _issue22_design_packet()
        packet["validator_impact"] = []
        errors = module.validate_implementation_packet(packet, methodology["design_artifact_contract"])
        self.assertTrue(any("validator_impact" in error for error in errors))

    def test_issue22_rejects_missing_design_unittest(self) -> None:
        methodology = _methodology()
        packet = _issue22_design_packet()
        packet["design_artifact"] = None
        errors = module.validate_implementation_packet(packet, methodology["design_artifact_contract"])
        self.assertTrue(any("missing required design" in error for error in errors))


def _issue85_route_blocker_packet() -> dict[str, object]:
    return {
        "status": "ROLE_COVERAGE_BLOCKER",
        "missing_part": "/srv/bears/plugins/bears/future-role-surface",
        "why_blocked": "unmapped",
    }


def _issue85_source_freshness_packet(safe_next_action: str = "sync plugin checkout") -> dict[str, object]:
    return {
        "status": "STALE_ROLE_GATE_SOURCE",
        "requested_target": "/srv/bears/plugins/bears/future-role-surface",
        "current_plugin_checkout_sha": "1" * 40,
        "root_gitlink_sha": "2" * 40,
        "root_origin_main_plugin_gitlink_sha": "3" * 40,
        "requested_mapping_exists_in_newer_merged_plugin_state": True,
        "safe_next_action": safe_next_action,
        "exact_role_policy": "Exact-role policy remains active; generic role substitution is forbidden.",
    }


class Issue85RoleGateSourceFreshnessUnittest(unittest.TestCase):
    def test_issue85_sync_plugin_checkout_is_valid_stale_source_closeout(self) -> None:
        decision = module.classify_blocker_decision(
            _issue85_route_blocker_packet(),
            _issue85_source_freshness_packet("sync plugin checkout"),
        )

        self.assertEqual("STALE_ROLE_GATE_SOURCE", decision["status"])
        self.assertEqual("sync plugin checkout", decision["safe_next_action"])
        self.assertIn("generic role substitution is forbidden", decision["exact_role_policy"])

    def test_issue85_clean_root_sync_worktree_is_valid_stale_source_closeout(self) -> None:
        decision = module.classify_blocker_decision(
            _issue85_route_blocker_packet(),
            _issue85_source_freshness_packet("switch to a clean root-sync worktree"),
        )

        self.assertEqual("STALE_ROLE_GATE_SOURCE", decision["status"])
        self.assertEqual("switch to a clean root-sync worktree", decision["safe_next_action"])

    def test_issue85_invalid_safe_next_action_is_packet_invalid_not_stale_source(self) -> None:
        decision = module.classify_blocker_decision(
            _issue85_route_blocker_packet(),
            _issue85_source_freshness_packet("reuse a broad role"),
        )

        self.assertEqual("ROLE_GATE_SOURCE_FRESHNESS_PACKET_INVALID", decision["status"])
        self.assertNotEqual("STALE_ROLE_GATE_SOURCE", decision["status"])
        self.assertIn("source freshness packet safe_next_action must be a canonical safe next action", decision["validation_errors"])
        self.assertEqual(
            ["sync plugin checkout", "switch to a clean root-sync worktree"],
            decision["allowed_safe_next_actions"],
        )
        self.assertIn("generic role substitution is forbidden", decision["exact_role_policy"])

    def test_issue85_invalid_source_packet_status_is_not_stale_source(self) -> None:
        freshness_packet = _issue85_source_freshness_packet("sync plugin checkout")
        freshness_packet["status"] = "ROLE_GATE_SOURCE_FRESH"

        decision = module.classify_blocker_decision(_issue85_route_blocker_packet(), freshness_packet)

        self.assertEqual("ROLE_GATE_SOURCE_FRESHNESS_PACKET_INVALID", decision["status"])
        self.assertIn("source freshness packet status must be STALE_ROLE_GATE_SOURCE", decision["validation_errors"])

    def test_issue85_exact_role_policy_must_forbid_generic_role_substitution(self) -> None:
        freshness_packet = _issue85_source_freshness_packet("sync plugin checkout")
        freshness_packet["exact_role_policy"] = "Exact-role policy mentions generic role substitution."

        decision = module.classify_blocker_decision(_issue85_route_blocker_packet(), freshness_packet)

        self.assertEqual("ROLE_GATE_SOURCE_FRESHNESS_PACKET_INVALID", decision["status"])
        self.assertIn("source freshness packet exact_role_policy must preserve exact-role policy", decision["validation_errors"])

    def test_issue85_classify_cli_rejects_invalid_safe_next_action_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            route_path = tmp_path / "route.json"
            freshness_path = tmp_path / "freshness.json"
            route_path.write_text(json.dumps(_issue85_route_blocker_packet()), encoding="utf-8")
            freshness_path.write_text(
                json.dumps(_issue85_source_freshness_packet("reuse a broad role")),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "classify-blocker",
                    "--route-packet",
                    str(route_path),
                    "--source-freshness-packet",
                    str(freshness_path),
                ],
                cwd=PLUGIN_ROOT,
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        self.assertEqual(1, result.returncode)
        self.assertEqual("", result.stderr)
        decision = json.loads(result.stdout)
        self.assertEqual("ROLE_GATE_SOURCE_FRESHNESS_PACKET_INVALID", decision["status"])
        self.assertNotEqual("STALE_ROLE_GATE_SOURCE", decision["status"])

    def test_issue85_fresh_source_keeps_role_coverage_blocker(self) -> None:
        freshness_packet = _issue85_source_freshness_packet("sync plugin checkout")
        freshness_packet["requested_mapping_exists_in_newer_merged_plugin_state"] = False

        decision = module.classify_blocker_decision(_issue85_route_blocker_packet(), freshness_packet)

        self.assertEqual("ROLE_COVERAGE_BLOCKER", decision["status"])
        self.assertEqual("unmapped", decision["why_blocked"])


def test_dev_app_group_alignment_is_parent_only() -> None:
    methodology = _methodology()
    catalog = _catalog()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}
    check = checks["/srv/bears/dev/app"]
    assert check["expected_status"] == "ROLE_COVERAGE_BLOCKER"
    assert check["why_blocked"] == "parent_only"

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert errors == []



def test_dev_registry_root_alignment_is_matched() -> None:
    methodology = _methodology()
    catalog = _catalog()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}
    check = checks["/srv/bears/dev/registry"]
    assert check["expected_status"] == "matched"
    assert check["required_route_id"] == "workspace_governance_canonical_plugin_docs"
    assert check["required_role"] == "bears-platform-role-governor"

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert errors == []



def test_desk_and_shared_platform_lane_alignment_is_matched() -> None:
    methodology = _methodology()
    catalog = _catalog()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}
    cases = {
        "/srv/bears/dev/app/desk": ("desk_product_dev_layer", "bears-product-app-zone-engineer"),
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
    for target, (route_id, role_name) in cases.items():
        check = checks[target]
        assert check["expected_status"] == "matched"
        assert check["required_route_id"] == route_id
        assert check["required_role"] == role_name

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert errors == []


def test_platform_backend_issue_alignment_is_exact_and_guarded() -> None:
    methodology = _methodology()
    catalog = _catalog()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}
    matched = {
        "/srv/bears/dev/platform/README.md": (
            "bears_platform_repo_readme_docs",
            "bears-docs-maintainer",
        ),
        "/srv/bears/dev/platform/SPEC.md": (
            "bears_platform_repo_spec_docs",
            "bears-docs-maintainer",
        ),
        "/srv/bears/dev/platform/docs/consumers/desk.md": (
            "bears_platform_desk_consumer_docs",
            "bears-docs-maintainer",
        ),
        "/srv/bears/dev/platform/tests/test_provider_gateway_contracts.py": (
            "bears_platform_provider_gateway_contracts_tests",
            "bears-gateway-platform-engineer",
        ),
        "/srv/bears/dev/platform/tests/test_provider_gateway_runtime.py": (
            "bears_platform_provider_gateway_runtime_tests",
            "bears-gateway-platform-engineer",
        ),
        "/srv/bears/dev/platform/tests/test_gateway_desk_auth_propagation.py": (
            "bears_gateway_desk_auth_propagation_tests",
            "bears-gateway-platform-engineer",
        ),
        "/srv/bears/dev/platform/docs/ci": (
            "bears_platform_ci_docs",
            "bears-deploy-platform-engineer",
        ),
        "/srv/bears/dev/platform/docs/ci/gateway-required-checks.md": (
            "bears_platform_ci_docs",
            "bears-deploy-platform-engineer",
        ),
        "/srv/bears/dev/platform/.github/workflows/build-images.yml.disabled": (
            "bears_platform_disabled_workflow_planning",
            "bears-deploy-platform-engineer",
        ),
        "/srv/bears/dev/platform/.github/workflows/gateway-required-checks.yml.disabled": (
            "bears_platform_disabled_workflow_planning",
            "bears-deploy-platform-engineer",
        ),
        "/srv/bears/dev/platform/.github/workflows/gateway-validation.yml.disabled": (
            "bears_platform_disabled_workflow_planning",
            "bears-deploy-platform-engineer",
        ),
        "/srv/bears/dev/platform/.github/workflows/gateway-validation.yml": (
            "bears_platform_gateway_validation_workflow_governance",
            "bears-deploy-platform-engineer",
        ),
    }
    for target, (route_id, role_name) in matched.items():
        check = checks[target]
        assert check["expected_status"] == "matched"
        assert check["required_route_id"] == route_id
        assert check["required_role"] == role_name

    blocked = [
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
    for target in blocked:
        check = checks[target]
        assert check["expected_status"] == "ROLE_COVERAGE_BLOCKER"
        assert check["why_blocked"] == "unmapped"

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert errors == []


def test_runtime_health_status_validation_alignment_is_matched() -> None:
    methodology = _methodology()
    catalog = _catalog()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}
    cases = {
        "/srv/bears/dev/platform/tests/test_data_cache_runtime.py": (
            "bears_platform_data_cache_runtime_tests",
            "bears-wb-integration-platform-engineer",
        ),
        "/srv/bears/dev/platform/tests/test_managed_backend_runtime.py": (
            "bears_platform_managed_backend_runtime_tests",
            "bears-wb-integration-platform-engineer",
        ),
        "/srv/bears/dev/platform/tests/test_runtime_status_views.py": (
            "bears_platform_managed_backend_runtime_status_views_tests",
            "bears-wb-integration-platform-engineer",
        ),
        "/srv/bears/dev/platform/tests/test_health.py": (
            "bears_platform_managed_backend_health_contract_tests",
            "bears-wb-integration-platform-engineer",
        ),
    }
    for target, (route_id, role_name) in cases.items():
        check = checks[target]
        assert check["expected_status"] == "matched"
        assert check["required_route_id"] == route_id
        assert check["required_role"] == role_name

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert errors == []



def test_runtime_packet_doc_and_issue_templates_alignment_is_matched() -> None:
    methodology = _methodology()
    catalog = _catalog()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}

    runtime_check = checks["/srv/bears/dev/platform/docs/runtime-implementation-packet-after-rotation.md"]
    assert runtime_check["expected_status"] == "matched"
    assert runtime_check["required_route_id"] == "bears_platform_runtime_implementation_packet_after_rotation"
    assert runtime_check["required_role"] == "bears-telegram-platform-engineer"

    child_check = checks["/srv/bears/plugins/bears/AGENTS.md"]
    assert child_check["expected_status"] == "matched"
    assert child_check["required_route_id"] == "platform_role_governance"
    assert child_check["required_role"] == "bears-platform-role-governor"

    template_check = checks["/srv/bears/plugins/bears/.github/ISSUE_TEMPLATE/config.yml"]
    assert template_check["expected_status"] == "matched"
    assert template_check["required_route_id"] == "workflow_overlay_issue_templates"
    assert template_check["required_role"] == "bears-workflow-overlay-platform-engineer"

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert errors == []

def test_github_branch_protection_required_checks_alignment_is_matched() -> None:
    methodology = _methodology()
    catalog = _catalog()
    checks = {item["target"]: item for item in methodology["catalog_alignment_checks"]}
    cases = {
        "github_branch_protection_settings_bears_platform": (
            "matched",
            "github_branch_protection_settings_bears_platform",
            "bears-github-branch-protection-settings-governor",
        ),
        "/repos/BearsCLOUD/bears-platform/branches/main/protection/required_status_checks": (
            "matched",
            "github_branch_protection_settings_bears_platform",
            "bears-github-branch-protection-settings-governor",
        ),
    }
    for target, (status, route_id, role_name) in cases.items():
        check = checks[target]
        assert check["expected_status"] == status
        assert check["required_route_id"] == route_id
        assert check["required_role"] == role_name

    blocked_targets = [
        "/repos/BearsCLOUD/bears-platform/branches/main/protection",
        "/repos/BearsCLOUD/bears-platform/branches/develop/protection/required_status_checks",
        "/repos/BearsCLOUD/other-repo/branches/main/protection/required_status_checks",
        "/repos/BearsCLOUD/bears-platform/secrets/actions",
        "/repos/BearsCLOUD/bears-platform/actions/permissions",
    ]
    for target in blocked_targets:
        check = checks[target]
        assert check["expected_status"] == "ROLE_COVERAGE_BLOCKER"
        assert check["why_blocked"] == "unmapped"

    errors = module.validate_catalog_alignment(methodology, catalog, plugin_root=PLUGIN_ROOT)
    assert errors == []


def load_tests(
    loader: unittest.TestLoader,
    tests: unittest.TestSuite,
    pattern: str | None,
) -> unittest.TestSuite:
    """Expose pytest-style function tests to unittest discovery."""
    del loader, pattern
    return load_function_tests(globals(), tests)
