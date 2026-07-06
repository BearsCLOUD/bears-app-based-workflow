"""Tests for canonical Bears plugin manifest and hidden internal Telegram docs."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_MANIFEST_PATH = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
AGENTS_PATH = PLUGIN_ROOT / "AGENTS.md"
VALIDATE_OVERLAY_PATH = PLUGIN_ROOT / "scripts" / "validate_overlay.py"
validate_overlay_spec = importlib.util.spec_from_file_location("validate_overlay", VALIDATE_OVERLAY_PATH)
validate_overlay = importlib.util.module_from_spec(validate_overlay_spec)
assert validate_overlay_spec.loader is not None
validate_overlay_spec.loader.exec_module(validate_overlay)  # type: ignore[arg-type]
EXPECTED_SKILL_PATHS = [
    "skills/bears-blocker-eval/SKILL.md",
    "skills/bears-deploy-gate/SKILL.md",
    "skills/bears-goal-prompt/SKILL.md",
    "skills/bears-plugin-update/SKILL.md",
    "skills/subagents-roles/SKILL.md",
    "skills/bears-agents/SKILL.md",
    "skills/secret-factory/SKILL.md",
    "skills/app-constitution/SKILL.md",
    "skills/app-specify/SKILL.md",
    "skills/app-plan/SKILL.md",
    "skills/app-analyze/SKILL.md",
    "skills/app-dev/SKILL.md",
    "skills/app-research/SKILL.md",
    "skills/subagents/SKILL.md",
    "skills/python-codeflow/SKILL.md",
    "skills/yandex360-dns/SKILL.md",
]
EXPECTED_CATALOG_PATHS = [
    "assets/catalog/agent-github-dev-cd.v1.json",
    "assets/catalog/auth-gateway-deploy-readiness.v1.json",
    "assets/catalog/git-discipline.v1.json",
    "assets/catalog/platform-role-catalog.v1.json",
    "assets/catalog/platform-role-catalog.v1.json",
    "assets/catalog/plugin-governance-language-policy.v1.json",
    "assets/catalog/plugin-skill-catalog.v1.json",
    "assets/catalog/project-dirty-baseline.v1.json",
    "assets/catalog/roadmap-control.v1.json",
    "assets/catalog/role-gate-methodology.v1.json",
    "assets/catalog/secret-factory.v1.json",
    "assets/catalog/session-workers-runtime.v1.json",
    "assets/catalog/subagent-orchestration-policy.v1.json",
    "assets/catalog/telegram-aiogram-migration-backlog.v1.json",
    "assets/catalog/telegram-runtime-readiness.v1.json",
]
EXPECTED_VALIDATOR_PATHS = [
    "scripts/agent_github_dev_cd.py",
    "scripts/agent_registration_sync.py",
    "scripts/auth_gateway_deploy_readiness.py",
    "scripts/git_discipline.py",
    "scripts/subagents_roles.py",
    "scripts/subagents_roles.py",
    "scripts/project_dirty_baseline.py",
    "scripts/project_registry_gate.py",
    "scripts/roadmap_control.py",
    "scripts/role_gate_methodology.py",
    "scripts/secret_factory.py",
    "scripts/session_workers_runtime.py",
    "scripts/skill_catalog.py",
    "scripts/subagent_orchestration_policy.py",
    "scripts/telegram_migration_backlog.py",
    "scripts/telegram_runtime_readiness.py",
    "scripts/validate_overlay.py",
]
FORBIDDEN_TEXT_SNIPPETS = [
    "[TODO:",
    "TODO",
    "telegram send",
    "send telegram",
    "live telegram send",
    "webhook mutation",
    "bot token",
    "private key",
]
YANDEX_LIVE_DNS_FORBIDDEN_CLAIMS = [
    "DNS operations",
    "DNS writes",
    "before writes",
    "operator confirmation before writes",
    "operator confirmation before apply",
    "dry-run-first DNS writes",
    "before apply",
    "live DNS",
]
TELEGRAM_SKILL_DIRS = [
]


class PluginManifestTests(unittest.TestCase):
    def setUp(self):
        self.plugin_manifest = json.loads(PLUGIN_MANIFEST_PATH.read_text(encoding="utf-8"))

    def test_no_root_app_or_mcp_manifest_in_canonical_plugin(self):
        self.assertFalse((PLUGIN_ROOT / ".app.json").exists())
        self.assertFalse((PLUGIN_ROOT / ".mcp.json").exists())

    def test_telegram_skill_bundle_inventory_paths_exist(self):
        for rel_path in EXPECTED_SKILL_PATHS + EXPECTED_CATALOG_PATHS + EXPECTED_VALIDATOR_PATHS:
            with self.subTest(rel_path=rel_path):
                self.assertTrue((PLUGIN_ROOT / rel_path).exists(), rel_path)

    def test_manifest_reports_roadmap_control_entrypoint_and_surface(self):
        joined = (
            self.plugin_manifest["interface"]["shortDescription"] + "\n"
            + self.plugin_manifest["interface"]["longDescription"] + "\n"
            + "\n".join(self.plugin_manifest["interface"]["defaultPrompt"])
        ).lower()
        self.assertIn("roadmap control", joined)
        self.assertIn("/goal", joined)
        self.assertIn("assets/catalog/roadmap-control.v1.json", joined)
        self.assertIn("scripts/roadmap_control.py", joined)

    def test_manifest_text_has_no_todo_or_live_mutation_claims(self):
        joined = self.plugin_manifest["interface"]["longDescription"].lower()
        for snippet in FORBIDDEN_TEXT_SNIPPETS:
            with self.subTest(snippet=snippet):
                self.assertNotIn(snippet.lower(), joined)

    def test_manifest_visible_text_secret_policy_is_field_complete(self):
        self.assertEqual(validate_overlay.validate_manifest_visible_text(self.plugin_manifest), [])

        covered_fields = [
            ("description", "Reads raw secret values."),
            ("interface.shortDescription", "Credential reads are available."),
            ("interface.longDescription", "Handles raw secret material."),
            ("interface.defaultPrompt", ["Print secret_value for debugging."]),
            ("keywords", ["bot token"]),
            ("interface.capabilities", ["private key handling"]),
        ]
        for field, value in covered_fields:
            with self.subTest(field=field):
                manifest = json.loads(json.dumps(self.plugin_manifest))
                target = manifest
                parts = field.split(".")
                for part in parts[:-1]:
                    target = target[part]
                target[parts[-1]] = value
                self.assertTrue(validate_overlay.validate_manifest_visible_text(manifest))

    def test_manifest_repository_points_to_canonical_plugin_repo(self):
        self.assertEqual(
            self.plugin_manifest["repository"],
            "https://github.com/BearsCLOUD/bears_plugin",
        )

    def test_plugin_metadata_hides_internal_telegram_skills_from_discovery(self):
        long_description = self.plugin_manifest["interface"]["longDescription"]
        self.assertNotIn("Telegram", long_description)
        self.assertNotIn("telegram", long_description)
        self.assertNotIn("Telegram workflow", self.plugin_manifest["interface"].get("capabilities", []))
        self.assertNotIn("telegram", self.plugin_manifest.get("keywords", []))
        self.assertNotIn("aiogram", self.plugin_manifest.get("keywords", []))

    def test_default_prompt_omits_hidden_telegram_skills(self):
        prompt = "\n".join(self.plugin_manifest["interface"]["defaultPrompt"])
        self.assertNotIn("$bears-telegram-workflow", prompt)
        self.assertNotIn("$telegram-quality-testing", prompt)
        self.assertNotIn("$telegram-aiogram-migration", prompt)
        self.assertIn("App Target Gate", prompt)
        self.assertIn("$app-research", prompt)
        self.assertIn("stage boundary", prompt.lower())
        self.assertIn("legacy post-task wording", prompt)
        self.assertIn("$yandex360-dns", prompt)
        self.assertIn("dry-run", prompt)

    def test_default_prompt_covers_roadmap_pre_task_and_reuse_rules(self):
        prompt = "\n".join(self.plugin_manifest["interface"]["defaultPrompt"]).lower()
        self.assertIn("/goal", prompt)
        self.assertIn("roadmap-control", prompt)
        self.assertIn("pre-task", prompt)
        self.assertIn("subagent", prompt)
        self.assertIn("scripts/roadmap_control.py", prompt)
        self.assertIn("do not run the validator manually unless the operator names that exact command", prompt)

    def test_default_prompt_covers_language_policy_and_governance_validators(self):
        prompt = "\n".join(self.plugin_manifest["interface"]["defaultPrompt"])
        self.assertIn("autoCI/local-commit-validation evidence", prompt)
        self.assertIn("do not run validators manually unless the operator names one exact command", prompt)
        self.assertIn("local_cd", prompt)
        self.assertIn("kubernetes_deployment", prompt)

    def test_yandex360_manifest_prompt_is_governance_only(self):
        prompt = "\n".join(self.plugin_manifest["interface"]["defaultPrompt"])
        yandex_prompt = "\n".join(
            item for item in self.plugin_manifest["interface"]["defaultPrompt"]
            if "$yandex360-dns" in item
        )
        self.assertIn("DNS governance", yandex_prompt)
        self.assertIn("presence checks", yandex_prompt)
        self.assertIn("dry-run plan review", yandex_prompt)
        self.assertIn("read-only evidence only", yandex_prompt)
        for snippet in YANDEX_LIVE_DNS_FORBIDDEN_CLAIMS:
            with self.subTest(snippet=snippet):
                self.assertNotIn(snippet.lower(), prompt.lower())

    def test_telegram_skill_markers_are_disabled_but_preserved(self):
        for relative_dir in TELEGRAM_SKILL_DIRS:
            with self.subTest(relative_dir=relative_dir):
                marker_path = PLUGIN_ROOT / relative_dir / "SKILL.md"
                preserved = (PLUGIN_ROOT / relative_dir / "SKILL.disabled.md").read_text(encoding="utf-8")
                self.assertFalse(marker_path.exists())
                self.assertTrue(preserved.lstrip().startswith("---"))
                self.assertIn("name:", preserved)
                self.assertIn("description:", preserved)

    def test_readme_explains_internal_telegram_workflow_without_listing_skill_inventory(self):
        readme = (PLUGIN_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn('Operator note: in this repo, "Telegram workflow" means governance rules', readme)
        self.assertIn("It does not mean a live Telegram bot, runtime, connector, product app, or MCP surface", readme)
        self.assertIn("Plugin-local Speckit overlay skills are removed from active plugin discovery", readme)
        self.assertIn("Active skills expose `SKILL.md`", readme)

    def test_readme_lists_language_policy_inventory(self):
        readme = (PLUGIN_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("`assets/catalog/plugin-governance-language-policy.v1.json`", readme)
        self.assertIn("`scripts/validate_overlay.py`", readme)
        self.assertIn("local_cd", readme)
        self.assertIn("kubernetes_deployment", readme)

    def test_agents_validation_policy_routes_repo_validators_to_local_commit_validation(self):
        agents = AGENTS_PATH.read_text(encoding="utf-8")
        self.assertIn("Local commit validation owns blocking plugin test proof", agents)
        self.assertIn("GitHub Actions `.github/workflows/validate.yml` runs fast diagnostics on `main` push", agents)
        self.assertIn("Agents must not run repo validator suites or tests manually", agents)
        self.assertIn("Closeout proof must cite `runtime/local-commit-validation/<main_sha>.json`", agents)
        self.assertNotIn("python3 scripts/agent_github_dev_cd.py validate", agents)
        self.assertNotIn("python3 scripts/git_discipline.py validate", agents)
        self.assertNotIn("python3 scripts/roadmap_control.py validate", agents)

    def test_requirements_cover_active_governance_surfaces(self):
        requirements = (PLUGIN_ROOT / "requirements.md").read_text(encoding="utf-8").lower()
        required_fragments = [
            "subagents roles gate",
            "validation hook runner",
            "readme.md and spec.md owner-document skill inventories",
            "requirements and active inventory",
            "bounded delegated execution",
            "governance markdown links",
            "research=skip",
            "project-dirty-baseline",
            "runtime_tool_schema_refresh_required",
        ]
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, requirements)


if __name__ == "__main__":
    unittest.main()
