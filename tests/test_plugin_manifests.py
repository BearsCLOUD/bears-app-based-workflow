"""Tests for the Bears plugin tooling-only manifest boundary."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_MANIFEST_PATH = PLUGIN_ROOT / ".codex-plugin" / "plugin.json"
CATALOG_PATH = PLUGIN_ROOT / "assets/catalog/plugin-skill-catalog.v1.json"
VALIDATE_OVERLAY_PATH = PLUGIN_ROOT / "scripts" / "validate_overlay.py"
validate_overlay_spec = importlib.util.spec_from_file_location("validate_overlay", VALIDATE_OVERLAY_PATH)
validate_overlay = importlib.util.module_from_spec(validate_overlay_spec)
assert validate_overlay_spec.loader is not None
validate_overlay_spec.loader.exec_module(validate_overlay)  # type: ignore[arg-type]

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


class PluginManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plugin_manifest = json.loads(PLUGIN_MANIFEST_PATH.read_text(encoding="utf-8"))
        self.catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))

    def test_no_root_app_or_mcp_manifest_in_canonical_plugin(self) -> None:
        self.assertFalse((PLUGIN_ROOT / ".app.json").exists())
        self.assertFalse((PLUGIN_ROOT / ".mcp.json").exists())
        self.assertNotIn("mcpServers", self.plugin_manifest)

    def test_manifest_is_tooling_only_not_instruction_source(self) -> None:
        self.assertNotIn("skills", self.plugin_manifest)
        self.assertNotIn("hooks", self.plugin_manifest)
        self.assertNotIn("subagentsRolesCheck", self.plugin_manifest)
        self.assertNotIn("defaultPrompt", self.plugin_manifest.get("interface", {}))
        source = self.plugin_manifest["metadata"]["instructionSource"]
        self.assertFalse(source["enabled"])
        self.assertFalse(source["activeSkills"])
        self.assertFalse(source["activeHooks"])
        self.assertFalse(source["activeRoleProfiles"])

    def test_no_active_instruction_files_are_discoverable(self) -> None:
        self.assertFalse(list((PLUGIN_ROOT / "skills").glob("*/SKILL.md")))
        self.assertFalse(list((PLUGIN_ROOT / "agents").glob("*.toml")))
        hooks = json.loads((PLUGIN_ROOT / "hooks.json").read_text(encoding="utf-8"))
        self.assertEqual(hooks.get("hooks"), {})
        self.assertTrue(hooks.get("disabled"))

    def test_preserved_skill_docs_are_disabled_only(self) -> None:
        self.assertEqual(self.catalog["active_skills"], [])
        for entry in self.catalog["disabled_skills"]:
            with self.subTest(skill=entry["name"]):
                skill_dir = PLUGIN_ROOT / entry["path"]
                self.assertFalse((skill_dir / "SKILL.md").exists())
                self.assertTrue((skill_dir / "SKILL.disabled.md").is_file())

    def test_manifest_visible_text_has_no_secret_or_live_mutation_claims(self) -> None:
        self.assertEqual(validate_overlay.validate_manifest_visible_text(self.plugin_manifest), [])
        joined = json.dumps(self.plugin_manifest, ensure_ascii=False).lower()
        for snippet in FORBIDDEN_TEXT_SNIPPETS:
            with self.subTest(snippet=snippet):
                self.assertNotIn(snippet.lower(), joined)

    def test_manifest_repository_points_to_canonical_plugin_repo(self) -> None:
        self.assertEqual(
            self.plugin_manifest["repository"],
            "https://github.com/BearsCLOUD/bears_plugin",
        )

    def test_readme_and_spec_state_instruction_boundary(self) -> None:
        readme = (PLUGIN_ROOT / "README.md").read_text(encoding="utf-8")
        spec = (PLUGIN_ROOT / "SPEC.md").read_text(encoding="utf-8")
        for text in (readme, spec):
            self.assertIn("not an instruction source", text)
            self.assertIn("skills/*/SKILL.md", text)
        self.assertIn("Plugin manifest must not declare `hooks`", spec)
        self.assertIn("`agents/*.toml` must not exist", spec)

    def test_requirements_cover_retained_tooling_surfaces(self) -> None:
        requirements = (PLUGIN_ROOT / "requirements.md").read_text(encoding="utf-8").lower()
        required_fragments = [
            "validation hook runner",
            "local-commit-validation",
            "runtime_tool_schema_refresh_required",
        ]
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, requirements)


if __name__ == "__main__":
    unittest.main()
