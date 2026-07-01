"""Tests for the Bears plugin skill catalog source of truth."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts import skill_catalog


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = PLUGIN_ROOT / "assets/catalog/plugin-skill-catalog.v1.json"


class SkillCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = skill_catalog.load_catalog(CATALOG_PATH)

    def test_default_catalog_validates_and_generated_fragments_match(self) -> None:
        errors = skill_catalog.validate_catalog(self.catalog, PLUGIN_ROOT)
        errors.extend(skill_catalog.generate(self.catalog, PLUGIN_ROOT, check=True))
        errors.extend(skill_catalog.sync_embedded_owner_docs(self.catalog, PLUGIN_ROOT, check=True))
        self.assertEqual(errors, [])

    def test_generated_readme_inventory_includes_secret_factory(self) -> None:
        readme_path = PLUGIN_ROOT / "docs/generated/README.skill-inventory.md"
        readme = readme_path.read_text(encoding="utf-8")
        self.assertIn(
            "- `skills/secret-factory` — Govern write-only local secret generation and Infisical creation with provider handoff refusals.",
            readme,
        )

    def test_generated_readme_inventory_includes_codex_health(self) -> None:
        readme_path = PLUGIN_ROOT / "docs/generated/README.skill-inventory.md"
        readme = readme_path.read_text(encoding="utf-8")
        self.assertIn(
            "- `skills/bears-codex-health` — Diagnose Codex desktop/app-server freezes, MCP fan-out, session growth, and safe evidence-first remediation planning.",
            readme,
        )

    def test_disabled_skills_do_not_expose_skill_md(self) -> None:
        for entry in self.catalog["disabled_skills"]:
            with self.subTest(skill=entry["name"]):
                skill_dir = PLUGIN_ROOT / entry["path"]
                self.assertFalse((skill_dir / "SKILL.md").exists())
                self.assertTrue((skill_dir / "SKILL.disabled.md").is_file())

    def test_active_skills_are_exact_catalog_include_list(self) -> None:
        expected = {entry["path"] for entry in self.catalog["active_skills"]}
        actual = {
            f"skills/{path.parent.name}"
            for path in (PLUGIN_ROOT / "skills").glob("*/SKILL.md")
        }
        self.assertEqual(actual, expected)

    def test_rejects_disabled_skill_with_active_discovery_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "plugin"
            shutil.copytree(PLUGIN_ROOT / "skills", root / "skills")
            catalog_dir = root / "assets/catalog"
            catalog_dir.mkdir(parents=True)
            shutil.copy2(CATALOG_PATH, catalog_dir / "plugin-skill-catalog.v1.json")
            bad = root / "skills/telegram-quality-testing/SKILL.md"
            bad.write_text("---\nname: telegram-quality-testing\ndescription: bad\n---\n")

            errors = skill_catalog.validate_catalog(self.catalog, root)

        self.assertTrue(
            any("disabled skill must not expose SKILL.md" in error for error in errors),
            errors,
        )

    def test_generated_fragment_drift_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "plugin"
            shutil.copytree(PLUGIN_ROOT / "skills", root / "skills")
            catalog_dir = root / "assets/catalog"
            catalog_dir.mkdir(parents=True)
            shutil.copy2(CATALOG_PATH, catalog_dir / "plugin-skill-catalog.v1.json")
            skill_catalog.generate(self.catalog, root)
            (root / "docs/generated/README.skill-inventory.md").write_text("drift\n")

            errors = skill_catalog.generate(self.catalog, root, check=True)

        self.assertIn("generated fragment drift: docs/generated/README.skill-inventory.md", errors)

    def test_owner_doc_inventory_drift_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "plugin"
            shutil.copytree(PLUGIN_ROOT / "skills", root / "skills")
            catalog_dir = root / "assets/catalog"
            catalog_dir.mkdir(parents=True)
            shutil.copy2(CATALOG_PATH, catalog_dir / "plugin-skill-catalog.v1.json")
            (root / "README.md").write_text(
                f"{skill_catalog.INVENTORY_START}\ndrift\n{skill_catalog.INVENTORY_END}\n",
                encoding="utf-8",
            )
            (root / "SPEC.md").write_text(
                f"{skill_catalog.INVENTORY_START}\n"
                + skill_catalog.render_spec_fragment(self.catalog)
                + f"{skill_catalog.INVENTORY_END}\n",
                encoding="utf-8",
            )

            errors = skill_catalog.sync_embedded_owner_docs(self.catalog, root, check=True)

        self.assertIn("owner doc inventory drift: README.md", errors)

    def test_catalog_json_has_unique_active_and_disabled_names(self) -> None:
        data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        active = {entry["name"] for entry in data["active_skills"]}
        disabled = {entry["name"] for entry in data["disabled_skills"]}
        self.assertFalse(active & disabled)
        self.assertEqual(len(active), len(data["active_skills"]))
        self.assertEqual(len(disabled), len(data["disabled_skills"]))


if __name__ == "__main__":
    unittest.main()
