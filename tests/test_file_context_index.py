from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import file_context_index


class FileContextIndexTest(unittest.TestCase):
    def test_current_index_validates_and_doctor_passes(self) -> None:
        self.assertEqual(file_context_index.validate_index(), [])
        packet = file_context_index.doctor_packet()
        self.assertEqual(packet["status"], "pass")

    def test_python_scan_uses_ast_extraction(self) -> None:
        record = file_context_index.build_record("scripts/goal_orchestrator.py")
        self.assertEqual(record["language"], "python")
        self.assertIn("start_goal", record["functions"])
        self.assertIn("argparse", record["imports"])

    def test_json_catalog_scan_exposes_commands_and_contract(self) -> None:
        record = file_context_index.build_record("assets/catalog/file-context-policy.v1.json")
        self.assertEqual(record["language"], "json")
        self.assertIn("bears-file-context-policy.v1", record["contracts"])
        self.assertTrue(any("file_context_index.py select" in item for item in record["public_interfaces"]))

    def test_select_blocks_stale_context_for_write_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_index = Path(tmp) / "index.v1.json"
            packet = file_context_index.index_packet()
            records = [dict(packet["records"][0])]
            records[0]["path"] = "scripts/goal_orchestrator.py"
            records[0]["context_id"] = "fc:test-stale"
            records[0]["status"] = "stale"
            records[0]["write_policy"] = "manual_review"
            packet["records"] = records
            temp_index.write_text(json.dumps(packet), encoding="utf-8")
            with mock.patch.object(file_context_index, "INDEX", temp_index):
                with mock.patch("sys.stdout"):
                    result = file_context_index.command_select(
                        type("Args", (), {"path": "scripts/goal_orchestrator.py", "role": "bears-development-workflow-orchestrator"})()
                    )
        self.assertEqual(result, 1)

    def test_selector_treats_hash_mismatch_as_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_index = Path(tmp) / "index.v1.json"
            packet = file_context_index.index_packet()
            record = dict(file_context_index.records_by_path(packet)["scripts/goal_orchestrator.py"])
            record["source_hash"] = "0" * 64
            packet["records"] = [record if row["path"] == "scripts/goal_orchestrator.py" else row for row in packet["records"]]
            temp_index.write_text(json.dumps(packet), encoding="utf-8")
            with mock.patch.object(file_context_index, "INDEX", temp_index):
                with mock.patch("sys.stdout"):
                    result = file_context_index.command_select(
                        type("Args", (), {"path": "scripts/goal_orchestrator.py", "role": "bears-development-workflow-orchestrator"})()
                    )
        self.assertEqual(result, 1)

    def test_gc_detects_and_removes_deleted_file_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_index = Path(tmp) / "index.v1.json"
            packet = file_context_index.index_packet()
            stale_record = dict(packet["records"][0])
            stale_record["path"] = "missing/deleted.py"
            stale_record["context_id"] = "fc:missing-deleted-py"
            packet["records"] = list(packet["records"]) + [stale_record]
            temp_index.write_text(json.dumps(packet), encoding="utf-8")
            with mock.patch.object(file_context_index, "INDEX", temp_index):
                result = file_context_index.gc_index()
                remaining = json.loads(temp_index.read_text(encoding="utf-8"))["records"]
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["removed_records"], ["missing/deleted.py"])
        self.assertFalse(any(row["path"] == "missing/deleted.py" for row in remaining))

    def test_build_index_rewrites_existing_records_with_linkage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_index = Path(tmp) / "index.v1.json"
            packet = file_context_index.index_packet()
            record = dict(file_context_index.records_by_path(packet)["scripts/goal_orchestrator.py"])
            record["decision_refs"] = []
            record["workflow_nodes"] = []
            packet["records"] = [record if row["path"] == "scripts/goal_orchestrator.py" else row for row in packet["records"]]
            temp_index.write_text(json.dumps(packet), encoding="utf-8")
            with mock.patch.object(file_context_index, "INDEX", temp_index):
                with mock.patch("sys.stdout"):
                    result = file_context_index.command_build_index(type("Args", (), {"paths": None})())
                rebuilt_records = file_context_index.records_by_path(json.loads(temp_index.read_text(encoding="utf-8")))
                rebuilt = rebuilt_records["scripts/goal_orchestrator.py"]
        self.assertEqual(result, 0)
        self.assertIn("D-2026-06-25-426-goal-orchestrator", rebuilt["decision_refs"])

    def test_missing_required_context_blocks_doctor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_index = Path(tmp) / "index.v1.json"
            packet = file_context_index.index_packet()
            packet["records"] = [row for row in packet["records"] if row["path"] != "scripts/bears_doctor.py"]
            temp_index.write_text(json.dumps(packet), encoding="utf-8")
            with mock.patch.object(file_context_index, "INDEX", temp_index):
                result = file_context_index.doctor_packet()
        self.assertEqual(result["status"], "fail")
        self.assertIn("scripts/bears_doctor.py", result["missing_context_paths"])


if __name__ == "__main__":
    unittest.main()
