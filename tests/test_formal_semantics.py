from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import formal_semantics

ROOT = Path(__file__).resolve().parents[1]


class FormalSemanticsTest(unittest.TestCase):
    def test_catalog_validates(self) -> None:
        self.assertEqual([], formal_semantics.validate_all())

    def test_unknown_semantic_type_fails(self) -> None:
        result = formal_semantics.check_relation("ghost", "implements", "contract")
        self.assertEqual("blocked", result["status"])
        self.assertIn("unknown source semantic_type: ghost", result["errors"])

    def test_unknown_relation_fails_graph_write(self) -> None:
        result = formal_semantics.check_relation("issue", "imagines", "contract")
        self.assertEqual("blocked", result["status"])
        self.assertFalse(result["graph_write_allowed"])

    def test_invalid_relation_direction_fails(self) -> None:
        result = formal_semantics.check_relation("contract", "implements", "issue")
        self.assertEqual("blocked", result["status"])
        self.assertFalse(result["direction_valid"])

    def test_candidate_fact_cannot_unlock_execution(self) -> None:
        packet = {
            "fact": {
                "id": "candidate-1",
                "subject": {"id": "candidate-decision", "semantic_type": "decision"},
                "relation": "enables",
                "object": {"id": "codex-exec", "semantic_type": "executor"},
                "status": "candidate",
                "authority_source": "llm-proposal",
            },
            "material_decision": True,
            "unlock_execution": True,
        }
        result = formal_semantics.check_fact_packet(packet)
        self.assertEqual("blocked", result["status"])
        self.assertFalse(result["unlocks_execution"])

    def test_accepted_semantic_fact_can_be_queried(self) -> None:
        result = formal_semantics.query_fact("fact-435-implements-formal-semantics-kernel")
        self.assertEqual("pass", result["status"])
        self.assertTrue(result["accepted"])

    def test_cli_check_relation_json(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump({"source_type": "issue", "relation": "implements", "target_type": "contract"}, handle)
            packet_path = handle.name
        completed = subprocess.run(
            [sys.executable, "scripts/formal_semantics.py", "check-relation", "--packet", packet_path, "--json"],
            cwd=ROOT,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
        )
        self.assertEqual(0, completed.returncode)
        self.assertEqual("pass", json.loads(completed.stdout)["status"])

    def test_doctor_reports_formal_semantics_status(self) -> None:
        result = formal_semantics.doctor_result()
        self.assertEqual("pass", result["formal_semantics_status"])
        self.assertEqual(14, result["types"])
        self.assertEqual(17, result["relations"])


if __name__ == "__main__":
    unittest.main()
