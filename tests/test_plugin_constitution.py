"""Tests for the Bears plugin constitution governance surface."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest
from unittest import mock

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PLUGIN_ROOT / "scripts/plugin_constitution.py"
CATALOG_PATH = PLUGIN_ROOT / "assets/catalog/plugin-constitution.v1.json"


def load_module():
    spec = importlib.util.spec_from_file_location("plugin_constitution", SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load plugin_constitution.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PluginConstitutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()
        self.catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


    def write_minimal_coverage_tree(self, root: Path, *, readme: str | None = None, manifest: str | None = None) -> None:
        (root / "docs/reference").mkdir(parents=True)
        (root / "docs/reference/plugin-constitution.md").write_text(
            (PLUGIN_ROOT / "docs/reference/plugin-constitution.md").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (root / "tests").mkdir(parents=True)
        (root / "tests/test_plugin_constitution.py").write_text(
            "PluginConstitutionTests inspect-change validate_catalog validate_surface_policy",
            encoding="utf-8",
        )
        (root / ".codex-plugin").mkdir(parents=True)
        (root / ".codex-plugin/plugin.json").write_text(
            manifest if manifest is not None else "plugin constitution scripts/plugin_constitution.py validate assets/catalog/plugin-constitution.v1.json",
            encoding="utf-8",
        )
        (root / "README.md").write_text(
            readme if readme is not None else (PLUGIN_ROOT / "README.md").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (root / "AGENTS.md").write_text(
            "Canonical plugin constitution\nroute gate -> constitution gate -> research gate",
            encoding="utf-8",
        )
        (root / "SPEC.md").write_text(
            "## Plugin Constitution\nscripts/plugin_constitution.py validate",
            encoding="utf-8",
        )

    def valid_packet(self) -> dict[str, object]:
        return {
            "schema": "bears-plugin-constitution-change-check.v1",
            "change_id": "issue-33-plugin-constitution",
            "changed_surfaces": ["assets/catalog/plugin-constitution.v1.json"],
            "agent_simplification_impact": "Future agents use one compact constitution gate before research.",
            "token_budget_impact": "Removes repeated issue reconstruction by naming required packet fields.",
            "bounded_context_plan": "Read AGENTS.md, the constitution catalog, validator, doc, and targeted tests only.",
            "future_reuse_path": "docs/reference/plugin-constitution.md and scripts/plugin_constitution.py",
            "deterministic_validation_added": True,
            "deterministic_validation_evidence": {
                "command": "python3 scripts/plugin_constitution.py validate",
                "target_surface": "assets/catalog/plugin-constitution.v1.json",
                "expected_status": "pass",
                "actual_status": "pass",
                "validator_path": "scripts/plugin_constitution.py",
                "result_summary": "validator exits 0 and reports pass",
            },
            "operator_decision_boundary": "Operator decides redesign; validator checks packet shape and status.",
            "cost_justification_if_any": "No extra process cost beyond one targeted gate.",
            "status": "pass",
            "route_target": "/srv/bears/plugins/bears/assets/catalog/plugin-constitution.v1.json",
            "lifecycle_position_proof": "after route_gate and before research_gate",
        }

    def final_report_packet(self) -> dict[str, object]:
        claim = "Bears Infra PR #40 wrapper dry-run coverage passed."
        return {
            "schema": "bears-plugin-final-report-evidence.v1",
            "claims": [claim],
            "memory_accessed": True,
            "memory_used": True,
            "memory_citations": [
                {
                    "source": "MEMORY.md",
                    "line_start": 1102,
                    "line_end": 1102,
                    "note": "infra wrapper dry-run coverage",
                    "cited_text": "Bears Infra PR #40 wrapper dry-run coverage was validated by the repo command.",
                    "claim": claim,
                }
            ],
        }

    def test_catalog_validates_current_files(self) -> None:
        self.assertEqual(self.module.validate_catalog(self.catalog), [])

    def test_catalog_uses_principles_field(self) -> None:
        self.assertIn("principles", self.catalog)
        self.assertNotIn("required_principles", self.catalog)
        ids = {item["id"] for item in self.catalog["principles"]}
        self.assertEqual(ids, self.module.REQUIRED_PRINCIPLES)


    def test_catalog_missing_principle_fails(self) -> None:
        catalog = json.loads(json.dumps(self.catalog))
        catalog["principles"] = catalog["principles"][1:]
        errors = self.module.validate_catalog(catalog, check_files=False)
        self.assertTrue(any("missing principle: agent_simplification" in error for error in errors))

    def test_catalog_missing_capability_inventory_boundary_fails(self) -> None:
        catalog = json.loads(json.dumps(self.catalog))
        del catalog["boundary_checks"]["capability_inventory_boundary"]
        errors = self.module.validate_catalog(catalog, check_files=False)
        self.assertIn("missing boundary check: capability_inventory_boundary", errors)

    def test_catalog_missing_surface_policy_fails(self) -> None:
        catalog = json.loads(json.dumps(self.catalog))
        del catalog["surface_policy"]
        errors = self.module.validate_catalog(catalog, check_files=False)
        self.assertIn("surface_policy must be an object", errors)

    def test_surface_policy_requires_catalog_backed_forbidden_values(self) -> None:
        catalog = json.loads(json.dumps(self.catalog))
        catalog["surface_policy"]["forbidden_root_entries"].remove("apps")
        errors = self.module.validate_catalog(catalog, check_files=False)
        self.assertIn("surface_policy.forbidden_root_entries missing value: apps", errors)

    def test_surface_policy_requires_catalog_backed_scan_scope(self) -> None:
        catalog = json.loads(json.dumps(self.catalog))
        catalog["surface_policy"]["scan_scope"].remove("git_untracked_unignored_files")
        errors = self.module.validate_catalog(catalog, check_files=False)
        self.assertIn("surface_policy.scan_scope missing value: git_untracked_unignored_files", errors)

    def test_surface_policy_rejects_forbidden_root_surfaces(self) -> None:
        forbidden_paths = [
            "apps/customer-app.json",
            "connectors/slack.json",
            "mcp/server.py",
            "servers/http.py",
            "runtime-services/worker.yaml",
            "services/bears.service",
            "deploy/docker-compose.yml",
        ]
        errors = self.module.validate_surface_policy(self.catalog, listed_paths=forbidden_paths, manifest_data={})
        self.assertTrue(any("apps/customer-app.json uses root entry apps" in error for error in errors), errors)
        self.assertTrue(any("connectors/slack.json uses root entry connectors" in error for error in errors), errors)
        self.assertTrue(any("mcp/server.py uses root entry mcp" in error for error in errors), errors)
        self.assertTrue(any("servers/http.py uses root entry servers" in error for error in errors), errors)
        self.assertTrue(any("runtime-services/worker.yaml uses root entry runtime-services" in error for error in errors), errors)
        self.assertTrue(any("services/bears.service uses root entry services" in error for error in errors), errors)
        self.assertTrue(any("deploy/docker-compose.yml uses root entry deploy" in error for error in errors), errors)

    def test_surface_policy_rejects_registration_files_and_manifest_keys(self) -> None:
        errors = self.module.validate_surface_policy(
            self.catalog,
            listed_paths=[
                "mcp.json",
                "Dockerfile",
                ".codex-plugin/mcp/server.json",
                "templates/systemd/bears.service",
            ],
            manifest_data={"name": "bears", "mcpServers": {"bears": {}}, "nested": {"connectors": []}},
        )
        self.assertTrue(any("forbidden plugin registration file: mcp.json" in error for error in errors), errors)
        self.assertTrue(any("Dockerfile matches Dockerfile" in error for error in errors), errors)
        self.assertTrue(any(".codex-plugin/mcp/server.json matches .codex-plugin/mcp/**" in error for error in errors), errors)
        self.assertTrue(any("forbidden plugin service registration file: templates/systemd/bears.service" in error for error in errors), errors)
        self.assertTrue(any("plugin.json.mcpServers" in error for error in errors), errors)
        self.assertTrue(any("plugin.json.nested.connectors" in error for error in errors), errors)

    def test_surface_policy_ignores_docs_text_and_allowed_governance_paths(self) -> None:
        errors = self.module.validate_surface_policy(
            self.catalog,
            listed_paths=[
                "docs/reference/plugin-constitution.md",
                "docs/reference/session-workers-runtime.md",
                "skills/bears-deploy-gate/SKILL.md",
                "assets/catalog/session-workers-runtime.v1.json",
                "scripts/telegram_runtime_readiness.py",
                "workflows/auth-gateway-deploy-core/workflow.yml",
                "tests/test_telegram_runtime_readiness.py",
            ],
            manifest_data={"name": "bears", "description": "plugin constitution"},
        )
        self.assertEqual(errors, [])

    def test_missing_reference_doc_fails_file_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.object(self.module, "PLUGIN_ROOT", root):
                errors = self.module.validate_file_coverage()
        self.assertTrue(any("missing doc file" in error for error in errors))

    def test_missing_readme_reference_fails_file_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_minimal_coverage_tree(root, readme="route gate -> constitution gate -> research gate")
            with mock.patch.object(self.module, "PLUGIN_ROOT", root):
                errors = self.module.validate_file_coverage()
        self.assertTrue(any("README.md missing constitution fragment" in error for error in errors))

    def test_missing_manifest_prompt_reference_fails_file_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.write_minimal_coverage_tree(root, manifest="{}")
            with mock.patch.object(self.module, "PLUGIN_ROOT", root):
                errors = self.module.validate_file_coverage()
        self.assertTrue(any(".codex-plugin/plugin.json missing constitution fragment" in error for error in errors))

    def test_inspect_change_accepts_complete_pass_packet(self) -> None:
        result = self.module.inspect_change(self.valid_packet(), self.catalog)
        self.assertEqual(result["status"], "pass", result)

    def test_inspect_final_report_accepts_relevant_memory_citation(self) -> None:
        result = self.module.inspect_final_report(self.final_report_packet())
        self.assertEqual(result["status"], "pass", result)

    def test_inspect_final_report_rejects_unrelated_memory_citation(self) -> None:
        packet = self.final_report_packet()
        packet["memory_citations"] = [
            {
                "source": "MEMORY.md",
                "line_start": 1102,
                "line_end": 1102,
                "note": "workspace seller runtime memory hit",
                "cited_text": "workspace-network-map.md network_map_contract seller.bears.ru Proxmox VMID 106",
                "claim": "Bears Infra PR #40 wrapper dry-run coverage passed.",
            }
        ]
        result = self.module.inspect_final_report(packet)
        self.assertEqual(result["status"], "fail")
        self.assertIn("memory_citations[0].cited_text must directly support claim", result["errors"])

    def test_inspect_final_report_rejects_note_cited_text_mismatch(self) -> None:
        packet = self.final_report_packet()
        packet["memory_citations"] = [
            {
                "source": "MEMORY.md",
                "line_start": 400,
                "line_end": 401,
                "note": "platform role validators",
                "cited_text": "Telegram workspace helper history and local bridge context.",
                "claim": "Bears Infra PR #40 wrapper dry-run coverage passed.",
            }
        ]
        result = self.module.inspect_final_report(packet)
        self.assertEqual(result["status"], "fail")
        self.assertIn("memory_citations[0].note must match cited_text content", result["errors"])

    def test_inspect_final_report_requires_citation_when_memory_used(self) -> None:
        packet = self.final_report_packet()
        packet["memory_citations"] = []
        result = self.module.inspect_final_report(packet)
        self.assertEqual(result["status"], "fail")
        self.assertIn("memory_used=true requires memory_citations", result["errors"])

    def test_inspect_final_report_allows_discarded_memory_with_reason(self) -> None:
        result = self.module.inspect_final_report(
            {
                "schema": "bears-plugin-final-report-evidence.v1",
                "claims": ["Role validators passed with current repo evidence."],
                "memory_accessed": True,
                "memory_used": False,
                "memory_discarded_reason": "Memory hits were broad orientation and did not support the closeout.",
                "memory_citations": [],
            }
        )
        self.assertEqual(result["status"], "pass", result)

    def test_inspect_final_report_rejects_discarded_memory_without_reason(self) -> None:
        packet = self.final_report_packet()
        packet["memory_used"] = False
        packet["memory_citations"] = []
        result = self.module.inspect_final_report(packet)
        self.assertEqual(result["status"], "fail")
        self.assertIn(
            "memory_discarded_reason is required when accessed memory is discarded",
            result["errors"],
        )

    def test_inspect_change_fails_closed_for_missing_required_field(self) -> None:
        packet = self.valid_packet()
        del packet["changed_surfaces"]
        result = self.module.inspect_change(packet, self.catalog)
        self.assertEqual(result["status"], "fail")
        self.assertIn("missing required field: changed_surfaces", result["errors"])

    def test_inspect_change_fails_closed_for_unknown_status(self) -> None:
        packet = self.valid_packet()
        packet["status"] = "approved"
        result = self.module.inspect_change(packet, self.catalog)
        self.assertEqual(result["status"], "fail")
        self.assertIn("status must be pass, fail, or needs-redesign", result["errors"])

    def test_inspect_change_rejects_stale_schema(self) -> None:
        packet = self.valid_packet()
        packet["schema"] = "bears-plugin-constitution-change.v1"
        result = self.module.inspect_change(packet, self.catalog)
        self.assertEqual(result["status"], "fail")
        self.assertIn("schema must be bears-plugin-constitution-change-check.v1", result["errors"])

    def test_inspect_change_rejects_pass_without_deterministic_validation(self) -> None:
        packet = self.valid_packet()
        packet["deterministic_validation_added"] = False
        result = self.module.inspect_change(packet, self.catalog)
        self.assertEqual(result["status"], "fail")
        self.assertIn("pass status requires deterministic_validation_added=true", result["errors"])

    def test_inspect_change_rejects_boolean_only_validation_claim(self) -> None:
        packet = self.valid_packet()
        del packet["deterministic_validation_evidence"]
        result = self.module.inspect_change(packet, self.catalog)
        self.assertEqual(result["status"], "fail")
        self.assertIn("missing required field: deterministic_validation_evidence", result["errors"])
        self.assertIn(
            "deterministic_validation_evidence must be a non-empty object",
            result["errors"],
        )

    def test_inspect_change_rejects_empty_deterministic_validation_evidence(self) -> None:
        packet = self.valid_packet()
        packet["deterministic_validation_evidence"] = {}
        result = self.module.inspect_change(packet, self.catalog)
        self.assertEqual(result["status"], "fail")
        self.assertIn(
            "deterministic_validation_evidence must be a non-empty object",
            result["errors"],
        )

    def test_inspect_change_rejects_incomplete_deterministic_validation_evidence(self) -> None:
        packet = self.valid_packet()
        packet["deterministic_validation_evidence"] = {
            "command": "python3 scripts/plugin_constitution.py validate",
            "target_surface": "assets/catalog/plugin-constitution.v1.json",
            "expected_status": "pass",
            "actual_status": "pass",
            "validator_path": "scripts/plugin_constitution.py",
        }
        result = self.module.inspect_change(packet, self.catalog)
        self.assertEqual(result["status"], "fail")
        self.assertIn(
            "deterministic_validation_evidence requires result_summary or evidence_path",
            result["errors"],
        )

    def test_inspect_change_rejects_non_repo_validation_command(self) -> None:
        packet = self.valid_packet()
        evidence = dict(packet["deterministic_validation_evidence"])
        evidence["command"] = "cat /etc/passwd"
        packet["deterministic_validation_evidence"] = evidence
        result = self.module.inspect_change(packet, self.catalog)
        self.assertEqual(result["status"], "fail")
        self.assertIn(
            "deterministic_validation_evidence.command must be a bounded repo-only validation command",
            result["errors"],
        )

    def test_inspect_change_rejects_outside_validation_command_arguments(self) -> None:
        rejected_commands = [
            "python3 scripts/plugin_constitution.py validate --catalog /etc/passwd",
            "python3 scripts/../../outside.py validate",
            "python3 -m unittest tests/../../outside.py",
        ]
        for command in rejected_commands:
            with self.subTest(command=command):
                packet = self.valid_packet()
                evidence = dict(packet["deterministic_validation_evidence"])
                evidence["command"] = command
                packet["deterministic_validation_evidence"] = evidence
                result = self.module.inspect_change(packet, self.catalog)
                self.assertEqual(result["status"], "fail")
                self.assertIn(
                    "deterministic_validation_evidence.command must be a bounded repo-only validation command",
                    result["errors"],
                )

    def test_inspect_change_accepts_repo_validation_command_arguments(self) -> None:
        accepted_commands = [
            "python3 scripts/plugin_constitution.py validate",
            "python3 scripts/validate_overlay.py --json validate --strict-overlay-skills",
            "python3 scripts/platform_roles.py route /srv/bears/plugins/bears/assets/catalog/plugin-constitution.v1.json",
            "python3 -m unittest tests/test_plugin_constitution.py tests/test_platform_roles.py",
            "python3 -m unittest discover -s tests",
        ]
        for command in accepted_commands:
            with self.subTest(command=command):
                packet = self.valid_packet()
                evidence = dict(packet["deterministic_validation_evidence"])
                evidence["command"] = command
                packet["deterministic_validation_evidence"] = evidence
                result = self.module.inspect_change(packet, self.catalog)
                self.assertEqual(result["status"], "pass", result)

    def test_inspect_change_rejects_missing_agent_simplification_impact(self) -> None:
        packet = self.valid_packet()
        del packet["agent_simplification_impact"]
        result = self.module.inspect_change(packet, self.catalog)
        self.assertEqual(result["status"], "fail")
        self.assertIn("missing required field: agent_simplification_impact", result["errors"])

    def test_inspect_change_rejects_missing_token_budget_impact(self) -> None:
        packet = self.valid_packet()
        del packet["token_budget_impact"]
        result = self.module.inspect_change(packet, self.catalog)
        self.assertEqual(result["status"], "fail")
        self.assertIn("missing required field: token_budget_impact", result["errors"])

    def test_inspect_change_rejects_missing_future_reuse_path(self) -> None:
        packet = self.valid_packet()
        del packet["future_reuse_path"]
        result = self.module.inspect_change(packet, self.catalog)
        self.assertEqual(result["status"], "fail")
        self.assertIn("missing required field: future_reuse_path", result["errors"])

    def test_inspect_change_rejects_process_weight_without_cost_justification(self) -> None:
        packet = self.valid_packet()
        packet["token_budget_impact"] = "Adds a new gate and more handoff checks."
        packet["cost_justification_if_any"] = "none"
        result = self.module.inspect_change(packet, self.catalog)
        self.assertEqual(result["status"], "fail")
        self.assertIn("added process weight requires cost_justification_if_any", result["errors"])

    def test_inspect_change_accepts_routed_plugin_governance_paths(self) -> None:
        packet = self.valid_packet()
        packet["changed_surfaces"] = [
            "assets/catalog/agent-github-dev-cd.v1.json",
            "workflows/agent-github-dev-cd/workflow.yml",
            "scripts/agent_github_dev_cd.py",
            ".github/workflows/validate.yml",
            "docs/reference/agent-github-dev-cd.md",
            "tests/test_agent_github_dev_cd.py",
        ]
        result = self.module.inspect_change(packet, self.catalog)
        self.assertEqual(result["status"], "pass", result)

    def test_inspect_change_rejects_outside_plugin_governance_paths(self) -> None:
        packet = self.valid_packet()
        packet["changed_surfaces"] = ["/srv/bears/plugins/other/README.md"]
        result = self.module.inspect_change(packet, self.catalog)
        self.assertEqual(result["status"], "fail")
        self.assertTrue(
            any("outside plugin governance boundary" in error for error in result["errors"]),
            result["errors"],
        )

    def test_inspect_change_rejects_unrouted_plugin_paths(self) -> None:
        packet = self.valid_packet()
        packet["changed_surfaces"] = ["unknown/new-governance.txt"]
        result = self.module.inspect_change(packet, self.catalog)
        self.assertEqual(result["status"], "fail")
        self.assertTrue(any("lacks exact role route" in error for error in result["errors"]), result["errors"])

    def test_inspect_change_rejects_runtime_app_mcp_connector_claims(self) -> None:
        packet = self.valid_packet()
        packet["bounded_context_plan"] = "Adds app connector and MCP server surfaces."
        result = self.module.inspect_change(packet, self.catalog)
        self.assertEqual(result["status"], "fail")
        self.assertTrue(
            any("forbidden expansion claim" in error for error in result["errors"]),
            result["errors"],
        )

    def test_inspect_change_rejects_missing_route_audit_evidence(self) -> None:
        packet = self.valid_packet()
        del packet["route_target"]
        result = self.module.inspect_change(packet, self.catalog)
        self.assertEqual(result["status"], "fail")
        self.assertIn(
            "packet must include exact route_target or route/audit evidence for plugin constitution",
            result["errors"],
        )

    def test_inspect_change_accepts_route_audit_evidence_without_route_target(self) -> None:
        packet = self.valid_packet()
        del packet["route_target"]
        packet["route_audit_evidence"] = [
            "python3 scripts/platform_roles.py route /srv/bears/plugins/bears/assets/catalog/plugin-constitution.v1.json",
            "python3 scripts/platform_roles.py audit /srv/bears/plugins/bears/assets/catalog/plugin-constitution.v1.json",
        ]
        result = self.module.inspect_change(packet, self.catalog)
        self.assertEqual(result["status"], "pass", result)

    def test_inspect_change_rejects_blocked_pattern_text(self) -> None:
        packet = self.valid_packet()
        packet["future_reuse_path"] = "Creating another Bears governance plugin."
        result = self.module.inspect_change(packet, self.catalog)
        self.assertEqual(result["status"], "fail")
        self.assertTrue(
            any("blocked-pattern text" in error for error in result["errors"]),
            result["errors"],
        )

    def test_inspect_change_rejects_invalid_lifecycle_proof(self) -> None:
        packet = self.valid_packet()
        packet["lifecycle_position_proof"] = "after research_gate"
        result = self.module.inspect_change(packet, self.catalog)
        self.assertEqual(result["status"], "fail")
        self.assertIn(
            "lifecycle_position_proof must be after route_gate and before research_gate",
            result["errors"],
        )

    def test_cli_validate_prints_pass_json(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "validate"],
            cwd=PLUGIN_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "pass")

    def test_cli_inspect_change_reports_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            packet_path = Path(tmp) / "packet.json"
            packet = self.valid_packet()
            packet["status"] = "review"
            packet_path.write_text(json.dumps(packet), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "inspect-change", "--packet", str(packet_path)],
                cwd=PLUGIN_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "fail")


if __name__ == "__main__":
    unittest.main()
