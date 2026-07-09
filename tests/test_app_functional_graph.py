from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts import app_functional_graph as afg

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "app_functional_graph"


class AppFunctionalGraphTests(unittest.TestCase):
    def _copy_fixture(self, name: str) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temp = tempfile.TemporaryDirectory(prefix="app-functional-graph-")
        root = Path(temp.name) / name
        shutil.copytree(FIXTURES / name, root)
        for rel in ("docs/app-functional-graph.v1.json", "docs/app-task-ledger.v1.json"):
            path = root / rel
            data = json.loads(path.read_text(encoding="utf-8"))
            data["app_directory"] = root.as_posix()
            path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return temp, root

    def test_valid_graph_and_ledger_pass(self) -> None:
        temp, app_dir = self._copy_fixture("valid_app")
        with temp:
            packet = afg.validate_app(app_dir)
        self.assertEqual(packet["status"], "pass", packet["errors"])

    def test_missing_functionality_ref_fails(self) -> None:
        temp, app_dir = self._copy_fixture("invalid_missing_functionality")
        with temp:
            packet = afg.validate_app(app_dir)
        self.assertEqual(packet["status"], "fail")
        self.assertTrue(any("functionality_ref not found" in error for error in packet["errors"]))

    def test_missing_edge_node_fails(self) -> None:
        temp, app_dir = self._copy_fixture("invalid_missing_node")
        with temp:
            packet = afg.validate_app(app_dir)
        self.assertEqual(packet["status"], "fail")
        self.assertTrue(any("edge.to missing node" in error for error in packet["errors"]))

    def test_secret_like_auth_ref_fails(self) -> None:
        temp, app_dir = self._copy_fixture("invalid_secret_ref")
        with temp:
            packet = afg.validate_app(app_dir)
        self.assertEqual(packet["status"], "fail")
        self.assertTrue(any("auth_ref" in error for error in packet["errors"]))

    def test_ready_task_requires_refs(self) -> None:
        temp, app_dir = self._copy_fixture("valid_app")
        with temp:
            ledger_path = app_dir / "docs" / afg.LEDGER_NAME
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
            ledger["tasks"][0]["functionality_refs"] = []
            ledger["tasks"][0]["graph_node_refs"] = []
            ledger_path.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            packet = afg.validate_app(app_dir)
        self.assertEqual(packet["status"], "fail")
        self.assertTrue(any("requires functionality_refs" in error for error in packet["errors"]))
        self.assertTrue(any("requires graph_node_refs" in error for error in packet["errors"]))

    def test_legacy_unbound_without_refs_passes(self) -> None:
        temp, app_dir = self._copy_fixture("valid_app")
        with temp:
            ledger_path = app_dir / "docs" / afg.LEDGER_NAME
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
            task = ledger["tasks"][0]
            task["status"] = "legacy_unbound"
            task["functionality_refs"] = []
            task["graph_node_refs"] = []
            ledger_path.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            packet = afg.validate_app(app_dir)
        self.assertEqual(packet["status"], "pass", packet["errors"])

    def test_ready_task_requires_autoci_zone_and_expected_status(self) -> None:
        temp, app_dir = self._copy_fixture("valid_app")
        with temp:
            ledger_path = app_dir / "docs" / afg.LEDGER_NAME
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
            ledger["tasks"][0]["autoci_zones"] = []
            ledger["tasks"][0]["expected_statuses"] = []
            ledger_path.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            packet = afg.validate_app(app_dir)
        self.assertEqual(packet["status"], "fail")
        self.assertTrue(any("requires autoci_zones" in error for error in packet["errors"]))
        self.assertTrue(any("requires expected_statuses" in error for error in packet["errors"]))

    def test_l3_claim_and_mark_task_status_update_only_assigned_task(self) -> None:
        temp, app_dir = self._copy_fixture("valid_app")
        original_app_root = afg.APP_ROOT
        with temp:
            afg.APP_ROOT = app_dir.parent
            try:
                claim_code = afg.command_claim_task(
                    argparse.Namespace(
                        app_dir=app_dir.as_posix(),
                        task_id="valid_app-T001",
                        worker_id="worker-1",
                        worker_role="bears-product-app-zone-engineer",
                    )
                )
                mark_code = afg.command_mark_task_status(
                    argparse.Namespace(
                        app_dir=app_dir.as_posix(),
                        task_id="valid_app-T001",
                        status="done",
                        worker_id="worker-1",
                        worker_role="bears-product-app-zone-engineer",
                        commit_sha="a" * 40,
                        evidence_ref=["dagger://proof/app"],
                        status_evidence_ref=["github-status://fast"],
                        expected_status=["app.autoCI.fast"],
                    )
                )
            finally:
                afg.APP_ROOT = original_app_root
            ledger = json.loads((app_dir / "docs" / afg.LEDGER_NAME).read_text(encoding="utf-8"))
        task = ledger["tasks"][0]
        self.assertEqual(claim_code, 0)
        self.assertEqual(mark_code, 0)
        self.assertEqual(task["status"], "done")
        self.assertEqual(task["worker_id"], "worker-1")
        self.assertEqual(task["commit_sha"], "a" * 40)
        self.assertIn("github-status://fast", task["status_evidence_refs"])
        self.assertIn("dagger://proof/app", task["evidence_refs"])
        self.assertNotEqual(task["started_at"], "none")
        self.assertNotEqual(task["closed_at"], "none")


if __name__ == "__main__":
    unittest.main()
