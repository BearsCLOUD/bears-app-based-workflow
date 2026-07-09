from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import metadata_store, workspace_dictionary, workspace_semantic_graph


class WorkspaceSemanticGraphTest(unittest.TestCase):
    def test_graph_schema_validates(self) -> None:
        self.assertEqual(workspace_semantic_graph.validate_all(), [])

    def test_extractor_builds_compact_graph_from_fixture(self) -> None:
        packet = workspace_semantic_graph.build(["scripts/file_context_index.py"])
        node_types = {row["node_type"] for row in packet["nodes"]}
        edge_types = {row["edge_type"] for row in packet["edges"]}
        self.assertIn("script", node_types)
        self.assertIn("context_surface", node_types)
        self.assertIn("has_context", edge_types)

    def test_dictionary_canonicalizes_repeated_terms(self) -> None:
        packet = workspace_dictionary.canonicalize("CPG")
        self.assertEqual(packet["status"], "pass")
        self.assertEqual(packet["canonical_term"], "code property graph")
        candidates = workspace_dictionary.extract_candidates()
        self.assertEqual(candidates["status"], "pass")

    def test_metadata_policy_blocks_external_authority(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            policy = Path(tmp) / "policy.json"
            packet = dict(metadata_store.load(metadata_store.POLICY))
            packet["materialized_stores"] = [{"store": "postgresql", "status": "optional", "authority": "primary", "export_required": True}]
            policy.write_text(json.dumps(packet), encoding="utf-8")
            with mock.patch.object(metadata_store, "POLICY", policy):
                errors = metadata_store.validate_policy()
        self.assertTrue(any("cache_only" in item for item in errors))

    def test_query_uses_context_selector_for_bounded_context(self) -> None:
        packet = workspace_semantic_graph.build(["scripts/file_context_index.py"])
        self.assertLessEqual(len(packet["nodes"]), 200)
        self.assertTrue(any(row["node_type"] == "context_surface" for row in packet["nodes"]))


if __name__ == "__main__":
    unittest.main()
