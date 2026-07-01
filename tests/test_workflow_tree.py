import json
import tempfile
import unittest
from pathlib import Path

from scripts import workflow_tree


GOOD = workflow_tree.PLUGIN_ROOT / "tests/fixtures/workflow_tree/good/minimal.json"
BAD = workflow_tree.PLUGIN_ROOT / "tests/fixtures/workflow_tree/bad/missing-owner.json"


class WorkflowTreeTests(unittest.TestCase):
    def test_validate_all_accepts_good_and_rejects_bad_fixtures(self) -> None:
        self.assertEqual(workflow_tree.validate_all(), [])

    def test_good_fixture_closeout_passes(self) -> None:
        tree = workflow_tree.load_json(GOOD)
        self.assertEqual(workflow_tree.closeout_errors(tree), [])

    def test_bad_fixture_reports_owner_and_scope_errors(self) -> None:
        tree = workflow_tree.load_json(BAD)
        errors = workflow_tree.validate_tree(tree)
        joined = "\n".join(errors)
        self.assertIn("owner_role", joined)
        self.assertIn("target outside allowed_write_scope", joined)

    def test_init_outputs_required_root_fields(self) -> None:
        tree = workflow_tree.init_tree("goal-1", "387")
        self.assertEqual(tree["schema"], "bears-workflow-tree.v1")
        self.assertEqual(tree["root_issue"], "#387")
        for field in ("nodes", "edges", "required_validations", "closeout_gate"):
            self.assertIn(field, tree)

    def test_add_node_rejects_duplicate_id(self) -> None:
        tree = workflow_tree.load_json(GOOD)
        node = tree["nodes"][0]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tree_path = root / "tree.json"
            node_path = root / "node.json"
            tree_path.write_text(json.dumps(tree), encoding="utf-8")
            node_path.write_text(json.dumps(node), encoding="utf-8")
            with self.assertRaises(ValueError):
                workflow_tree.add_node(tree_path, node_path)

    def test_emit_report_is_bounded_json(self) -> None:
        tree = workflow_tree.load_json(GOOD)
        packet = workflow_tree.report(tree)
        self.assertEqual(packet["schema"], "bears-workflow-tree-report.v1")
        self.assertEqual(packet["status"], "pass")
        self.assertNotIn("raw", json.dumps(packet).lower())


if __name__ == "__main__":
    unittest.main()
