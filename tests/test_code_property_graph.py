from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import code_property_graph


class CodePropertyGraphTest(unittest.TestCase):
    def test_python_fixture_extracts_imports_classes_functions_and_calls(self) -> None:
        packet = code_property_graph.extract_path("scripts/code_property_graph.py")
        node_types = {row["node_type"] for row in packet["nodes"]}
        fact_types = {row["fact_type"] for row in packet["edges"]}
        self.assertIn("function", node_types)
        self.assertIn("symbol_imports_module", fact_types)
        self.assertIn("function_calls_symbol", fact_types)
        self.assertIn("function_reads_name", fact_types)

    def test_argparse_subcommands_are_extracted(self) -> None:
        packet = code_property_graph.extract_path("scripts/code_property_graph.py")
        commands = [row for row in packet["edges"] if row["fact_type"] == "script_exposes_command"]
        self.assertTrue(any("validate" in row["target"] for row in commands))

    def test_json_catalog_extracts_schema_and_command_refs(self) -> None:
        packet = code_property_graph.extract_path("assets/catalog/code-property-graph.v1.json")
        self.assertTrue(packet["nodes"])
        self.assertTrue(any(row["fact_type"] == "script_exposes_command" for row in packet["edges"]))

    def test_stale_source_hash_invalidates_stored_facts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            catalog = Path(tmp) / "catalog.json"
            packet = dict(code_property_graph.load(code_property_graph.CATALOG))
            packet["tracked_sources"] = [{"path": "scripts/code_property_graph.py", "source_hash": "0" * 64}]
            catalog.write_text(json.dumps(packet), encoding="utf-8")
            with mock.patch.object(code_property_graph, "CATALOG", catalog):
                stale = code_property_graph.stale_sources()
        self.assertEqual(stale, ["scripts/code_property_graph.py"])

    def test_doctor_validate_passes(self) -> None:
        self.assertEqual(code_property_graph.validate_catalog(), [])


if __name__ == "__main__":
    unittest.main()
