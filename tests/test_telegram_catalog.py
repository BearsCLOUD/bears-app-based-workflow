"""Tests for Telegram workflow catalog contract strictness."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from scripts import telegram_catalog


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = PLUGIN_ROOT / "assets/catalog/telegram-workflow-catalog.v1.json"
REQUIRED_WORKFLOW_PACKET_FIELDS = {
    "input_packet",
    "output_packet",
    "validation",
    "security_rules",
    "reuse_targets",
}


class TelegramCatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog = telegram_catalog.load_catalog(CATALOG_PATH)

    def test_default_catalog_validates(self):
        self.assertEqual(telegram_catalog.validate_catalog(self.catalog), [])

    def test_workflows_have_packet_security_and_reuse_contract(self):
        for workflow in self.catalog["workflows"]:
            with self.subTest(workflow=workflow["name"]):
                self.assertTrue(REQUIRED_WORKFLOW_PACKET_FIELDS <= workflow.keys())
                for field in REQUIRED_WORKFLOW_PACKET_FIELDS:
                    self.assertIsInstance(workflow[field], list)
                    self.assertTrue(workflow[field], field)

    def test_rejects_workflow_without_input_packet(self):
        catalog = json.loads(json.dumps(self.catalog))
        del catalog["workflows"][0]["input_packet"]
        errors = telegram_catalog.validate_catalog(catalog)
        self.assertTrue(any("input_packet" in error for error in errors), errors)

    def test_rejects_empty_security_rules(self):
        catalog = json.loads(json.dumps(self.catalog))
        catalog["workflows"][0]["security_rules"] = []
        errors = telegram_catalog.validate_catalog(catalog)
        self.assertTrue(any("security_rules" in error for error in errors), errors)

    def test_summary_surfaces_packet_counts(self):
        summary = telegram_catalog.render_summary(self.catalog)
        self.assertIn("input_packet:", summary)
        self.assertIn("output_packet:", summary)

    def test_theants_surface_points_to_apps_monorepo_module(self):
        surface = next(item for item in self.catalog["surfaces"] if item["name"] == "theants")

        self.assertEqual(surface["path"], "dev/app/theants")
        self.assertEqual(surface["owner_group"], "products")
        self.assertIn("legacy sources preserved", surface["current_framework_status"])
        self.assertIn("canonical BearsCLOUD/apps", surface["target_state"])
        self.assertIn("dev/app/theants/README.md", surface["evidence_source"])
        self.assertIn("BearsCLOUD/apps", surface["next_action"])


if __name__ == "__main__":
    unittest.main()
