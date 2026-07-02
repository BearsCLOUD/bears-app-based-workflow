"""Doc-level governance tests for the Telegram workflow skill bundle."""
from __future__ import annotations

import json
from pathlib import Path
import unittest


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
AGENTS_PATH = PLUGIN_ROOT / "AGENTS.md"
SPEC_PATH = PLUGIN_ROOT / "SPEC.md"
REQUIREMENTS_PATH = PLUGIN_ROOT / "requirements.md"
README_PATH = PLUGIN_ROOT / "README.md"
PLUGIN_MANIFEST_PATH = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
DISABLED_SKILL_PATH = PLUGIN_ROOT / "skills" / "telegram-plugin-skill-factory" / "SKILL.md"
PRESERVED_SKILL_PATH = PLUGIN_ROOT / "skills" / "telegram-plugin-skill-factory" / "SKILL.disabled.md"
OPENAI_PATH = PLUGIN_ROOT / "skills" / "telegram-plugin-skill-factory" / "agents" / "openai.yaml"
LIFECYCLE_PATH = (
    PLUGIN_ROOT / "skills" / "telegram-plugin-skill-factory" / "references" / "skill-lifecycle.md"
)
CHECKLIST_PATH = (
    PLUGIN_ROOT / "skills" / "telegram-plugin-skill-factory" / "references" / "review-checklist.md"
)
FORWARD_TEST_PATH = (
    PLUGIN_ROOT
    / "skills"
    / "telegram-plugin-skill-factory"
    / "references"
    / "subagent-forward-test.md"
)
CANONICAL_GATE = "/srv/bears/plugins/bears/scripts/platform_roles.py"
CANONICAL_ROLE = "bears-telegram-platform-engineer"
SKILL_BUNDLE = "/srv/bears/plugins/bears/skills/bears-telegram-workflow"
POLICY_PATH = PLUGIN_ROOT / "assets" / "catalog" / "telegram-plugin-skill-factory-policy.v1.json"
ROADMAP_CATALOG_PATH = PLUGIN_ROOT / "assets" / "catalog" / "roadmap-control.v1.json"
ROADMAP_SCRIPT_PATH = PLUGIN_ROOT / "scripts" / "roadmap_control.py"
PROJECT_MANDATE_SKILL_PATH = PLUGIN_ROOT / "skills" / "project-mandate" / "SKILL.md"
BEARS_SDD_WORKFLOW_PATH = PLUGIN_ROOT / "workflows" / "bears-sdd" / "workflow.yml"
YANDEX_LIVE_DNS_README_FORBIDDEN_CLAIMS = [
    "DNS operations",
    "DNS writes",
    "before writes",
    "operator confirmation before writes",
    "operator confirmation before apply",
    "dry-run-first DNS writes",
    "before apply",
    "live DNS",
]


class WorkflowGovernanceDocTests(unittest.TestCase):
    def test_agents_router_places_telegram_inside_canonical_plugin(self):
        text = AGENTS_PATH.read_text(encoding="utf-8")
        self.assertIn(CANONICAL_GATE, text)
        self.assertIn(CANONICAL_ROLE, text)
        self.assertIn("skill/catalog/script bundle", text)
        self.assertIn("There is exactly one Codex plugin", text)
        self.assertIn("Do not recreate a standalone Telegram plugin", text)

    def test_spec_describes_skill_bundle_and_no_app_surface(self):
        text = SPEC_PATH.read_text(encoding="utf-8")
        self.assertIn(CANONICAL_GATE, text)
        self.assertIn(SKILL_BUNDLE, text)
        self.assertIn("skill-bundle", text)
        self.assertIn("not a separate plugin", text)
        self.assertNotIn("/srv/bears/plugins/bears-telegram-workflow/.app.json", text)

    def test_requirements_bind_gate_order_factory_scope_and_no_standalone_plugin(self):
        text = REQUIREMENTS_PATH.read_text(encoding="utf-8")
        self.assertIn("canonical Bears role gate MUST be the first mandatory gate", text)
        self.assertIn("telegram-plugin-skill-factory", text)
        self.assertIn("no standalone Telegram plugin/product-app/MCP/runtime surface", text)
        self.assertIn("connector", text)
        self.assertIn("bears-telegram-workflow", text)

    def test_skill_factory_requires_canonical_first_and_bundle_work(self):
        text = PRESERVED_SKILL_PATH.read_text(encoding="utf-8")
        self.assertIn("canonical Bears role gate first", text)
        self.assertIn("skill-bundle discovery", text)
        self.assertIn("plugin discovery metadata", text)
        self.assertIn("Forward-test central skills", text)
        self.assertIn("No unvalidated Telegram skill bundle", text)

    def test_skill_factory_disabled_doc_is_preserved_without_active_discovery(self):
        preserved = PRESERVED_SKILL_PATH.read_text(encoding="utf-8")
        self.assertFalse(DISABLED_SKILL_PATH.exists())
        self.assertTrue(preserved.lstrip().startswith("---"))
        self.assertIn("name: telegram-plugin-skill-factory", preserved)

    def test_skill_openai_prompt_mentions_bundle_and_forward_tests(self):
        text = OPENAI_PATH.read_text(encoding="utf-8")
        self.assertIn("skill-bundle discovery metadata", text)
        self.assertIn("forward tests", text)

    def test_lifecycle_and_checklist_reference_canonical_validation(self):
        lifecycle = LIFECYCLE_PATH.read_text(encoding="utf-8")
        checklist = CHECKLIST_PATH.read_text(encoding="utf-8")
        self.assertIn(CANONICAL_GATE, lifecycle)
        self.assertIn("Local agents may run exact route/audit gates", lifecycle)
        self.assertIn("git diff --check", lifecycle)
        self.assertIn("Skill validation suites and test execution are local-commit-owned", lifecycle)
        self.assertIn("explicit operator approval", lifecycle)
        self.assertIn("canonical Bears role gate first", checklist)
        self.assertIn("Telegram validators stay secondary", checklist)
        self.assertIn("heartbeat/status packet", checklist)

    def test_forward_test_reference_covers_canonical_gate_and_no_live_runtime(self):
        text = FORWARD_TEST_PATH.read_text(encoding="utf-8")
        self.assertIn("canonical Bears role gate first", text)
        self.assertIn("skill-bundle", text)
        self.assertIn("validation commands", text)
        self.assertIn("factory-policy regression list", text)

    def test_spec_records_shared_spine_routing_matrix_and_subagent_contract(self):
        text = SPEC_PATH.read_text(encoding="utf-8")
        self.assertIn("Shared spine dependency", text)
        self.assertIn("auth_core -> bears_gateway -> cd_deploy_stage", text)
        self.assertIn("Workflow routing", text)
        self.assertIn("telegram-quality-testing", text)
        self.assertIn("telegram-aiogram-migration", text)
        self.assertIn("telegram-plugin-skill-factory", text)
        self.assertIn("Subagent packet contract", text)
        self.assertIn("role artifact path", text)
        self.assertIn("disjoint-scope statement", text)
        self.assertIn("heartbeat/status packet", text)
        self.assertIn("ROLE_COVERAGE_BLOCKER", text)

    def test_requirements_record_factory_policy_spine_and_sync(self):
        text = REQUIREMENTS_PATH.read_text(encoding="utf-8")
        self.assertIn("machine-verifiable policy", text)
        self.assertIn("telegram_skill_factory_policy.py validate", text)
        self.assertIn("disabled from active plugin-discovery inventory", text)
        self.assertIn("telegram-quality-testing", text)
        self.assertIn("at most 100 active subagents", text)
        self.assertIn("auth_core -> bears_gateway -> cd_deploy_stage", text)
        self.assertIn("stay synchronized", text)
        self.assertIn("child subagents MUST rerun role routing", text)

    def test_project_mandate_is_registry_gated_checklist(self):
        text = PROJECT_MANDATE_SKILL_PATH.read_text(encoding="utf-8")
        self.assertIn("This skill is a checklist", text)
        self.assertIn("project_registry_gate.py gate <target-path>", text)
        self.assertIn("PROJECT_REGISTRATION_BLOCKER", text)
        self.assertIn("/srv/bears/dev/registry/projects.v1.json", text)
        self.assertIn("project_mandate_allowed: true", text)

    def test_bears_sdd_workflow_requires_parallel_delegation_for_p_tasks(self):
        text = BEARS_SDD_WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertIn("[P] tasks MUST use parallel delegation", text)
        self.assertIn("scopes are disjoint", text)

    def test_readme_keeps_yandex360_dns_governance_only(self):
        text = README_PATH.read_text(encoding="utf-8")
        yandex_line = next(
            line for line in text.splitlines()
            if "`skills/yandex360-dns`" in line
        )
        self.assertIn("DNS governance workflow", yandex_line)
        self.assertIn("presence-only checks", yandex_line)
        self.assertIn("dry-run plan review", yandex_line)
        self.assertIn("read-only governance evidence only", yandex_line)
        for snippet in YANDEX_LIVE_DNS_README_FORBIDDEN_CLAIMS:
            with self.subTest(snippet=snippet):
                self.assertNotIn(snippet.lower(), yandex_line.lower())

    def test_readme_reflects_roadmap_control_rules(self):
        text = README_PATH.read_text(encoding="utf-8")
        self.assertIn("Roadmap runs are deterministic and must be started through `/goal` only.", text)
        self.assertIn("Multiple active Spec Kit specs are allowed only via roadmap slices and non-overlapping scope locks.", text)
        self.assertIn("A pre-task hook runs before `spawn`, `resume`, `reuse`, `manage`, and `close`", text)
        self.assertIn("Maximum concurrency for active subagents is 100", text)
        self.assertIn("depth max 3", text)

    def test_spec_records_roadmap_slice_scope_lock_and_pre_task_rules(self):
        text = SPEC_PATH.read_text(encoding="utf-8")
        self.assertIn("## Roadmap Control", text)
        self.assertIn("Roadmap control is a dedicated gate", text)
        self.assertIn("Roadmap runs can start only via `/goal`", text)
        self.assertIn("roadmap_slice", text)
        self.assertIn("non-overlapping scope locks", text)
        self.assertIn("missing data", text)
        self.assertIn("drift", text)

    def test_spec_session_reuse_field_matrix_present(self):
        text = SPEC_PATH.read_text(encoding="utf-8")
        required_fields = [
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
        ]
        for field in required_fields:
            with self.subTest(field=field):
                self.assertIn(field, text)

    def test_spec_limits_depth_and_subagent_count_are_hardened(self):
        text = SPEC_PATH.read_text(encoding="utf-8")
        self.assertIn("Subagent mode has a hard limit of 100 active subagents", text)
        self.assertIn("max depth 3", text)

    def test_workflow_docs_align_manifest_roadmap_controls(self):
        manifest = json.loads(PLUGIN_MANIFEST_PATH.read_text(encoding="utf-8"))
        readme = README_PATH.read_text(encoding="utf-8").lower()
        spec = SPEC_PATH.read_text(encoding="utf-8").lower()
        joined_prompt = "\n".join(manifest["interface"]["defaultPrompt"]).lower()
        self.assertIn("roadmap control", manifest["interface"]["longDescription"].lower())
        self.assertIn("/goal", manifest["interface"]["longDescription"].lower() + joined_prompt)
        self.assertIn("assets/catalog/roadmap-control.v1.json", manifest["interface"]["longDescription"].lower() + joined_prompt)
        self.assertIn("roadmap control", readme)
        self.assertIn("roadmap control", spec)


if __name__ == "__main__":
    unittest.main()


class WorkflowGovernancePolicyTests(unittest.TestCase):
    def test_policy_enforces_one_plugin_model_and_secondary_telegram_validators(self):
        import json

        data = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        self.assertEqual(data["canonical_plugin"]["name"], "bears")
        self.assertEqual(data["canonical_plugin"]["root"], "/srv/bears/plugins/bears")
        self.assertTrue(data["canonical_plugin"]["exclusive_codex_plugin"])
        self.assertTrue(data["canonical_plugin"]["telegram_is_skill_bundle_only"])
        self.assertEqual(data["gate_order"][0]["step"], "canonical_role_gate")
        self.assertEqual(data["gate_order"][1]["step"], "telegram_skill_bundle_validation")

    def test_policy_preserves_spine_routes_and_handoff_packet_fields(self):
        import json

        data = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        self.assertEqual(data["shared_spine_order"], ["auth_core", "bears_gateway", "cd_deploy_stage"])
        routes = {(item["surface"], item["required_skill"]) for item in data["workflow_routing"]}
        self.assertIn(("telegram formatting/UI", "telegram-quality-testing"), routes)
        self.assertIn(("telegram aiogram migration", "telegram-aiogram-migration"), routes)
        self.assertIn(("telegram skill/policy lifecycle", "telegram-plugin-skill-factory"), routes)
        fields = set(data["subagent_handoff_packet"]["required_fields"])
        self.assertIn("role_artifact_path", fields)
        self.assertIn("disjoint_scope_statement", fields)
        self.assertIn("heartbeat_status_packet", fields)
        self.assertIn("closeout_packet", fields)
