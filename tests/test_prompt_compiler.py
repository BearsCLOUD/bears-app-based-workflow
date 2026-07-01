from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import context_pack, decision_graph, file_context_index, prompt_compiler
from scripts.local_json_schema import validate_json_schema

ROOT = Path(__file__).resolve().parents[1]
GOAL_CONTEXT = "fc:scripts:goal-orchestrator-py"


class PromptCompilerTest(unittest.TestCase):
    def request(self, tmp: Path, **overrides: object) -> dict[str, object]:
        graph = decision_graph.build_graph("goal-441-test")
        graph_path = tmp / "decision-graph.json"
        graph_path.write_text(json.dumps(graph, sort_keys=True), encoding="utf-8")
        packet: dict[str, object] = {
            "schema": "bears-prompt-compile-request.v1",
            "goal_id": "goal-441-test",
            "role_id": "oc_reviewer",
            "execution_unit": "unit-a",
            "task": "Compile a bounded prompt from proof inputs.",
            "required_outputs": ["JSON result packet"],
            "decision_graph": str(graph_path),
            "inference_proofs": [],
            "context_ids": [GOAL_CONTEXT],
            "max_tokens": 20000,
            "allow_full_file_read": False,
            "context_level": "L3",
        }
        packet.update(overrides)
        return packet

    def test_static_catalog_validates(self) -> None:
        self.assertEqual([], context_pack.validate_catalog())

    def test_zero_context_fixture_compiles_bounded_role_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            request = self.request(Path(raw), context_ids=[], context_level="L1")
            result = prompt_compiler.compile_request(request)
        self.assertEqual("pass", result["status"])
        self.assertIn("required_output_schema", result)
        self.assertIn("oc_reviewer", result["prompt_text"])
        self.assertEqual([], validate_json_schema(result, prompt_compiler.RESULT_SCHEMA, "result"))

    def test_missing_decision_proof_blocks_compilation(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            graph = decision_graph.build_graph("goal-441-test")
            graph["nodes"][0]["proof_id"] = "proof-missing"
            graph_path = tmp / "bad-graph.json"
            graph_path.write_text(json.dumps(graph, sort_keys=True), encoding="utf-8")
            result = prompt_compiler.compile_request(self.request(tmp, decision_graph=str(graph_path)))
        self.assertEqual("blocked", result["status"])
        self.assertTrue(any("proof" in item for item in result["errors"]))

    def test_stale_context_blocks_context_pack(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            index_path = tmp / "index.v1.json"
            packet = file_context_index.index_packet()
            record = dict(next(row for row in packet["records"] if row["context_id"] == GOAL_CONTEXT))
            record["status"] = "stale"
            record["write_policy"] = "manual_review"
            packet["records"] = [record]
            index_path.write_text(json.dumps(packet), encoding="utf-8")
            with mock.patch.object(file_context_index, "INDEX", index_path):
                pack = context_pack.build_context_pack(self.request(tmp))
        self.assertEqual("blocked", pack["status"])
        self.assertTrue(any("stale" in item for item in pack["errors"]))

    def test_budget_exceed_blocks_compilation(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            result = prompt_compiler.compile_request(self.request(Path(raw), max_tokens=1))
        self.assertEqual("blocked", result["status"])
        self.assertTrue(any("budget" in item for item in result["errors"]))

    def test_unproved_full_file_read_blocks_compilation(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            request = self.request(
                Path(raw),
                context_ids=[{"context_id": GOAL_CONTEXT, "level": "L4"}],
                allow_full_file_read=True,
                context_level="L4",
            )
            result = prompt_compiler.compile_request(request)
        self.assertEqual("blocked", result["status"])
        self.assertTrue(any("full-file" in item for item in result["errors"]))

    def test_proved_full_file_read_compiles_l4(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            request = self.request(
                Path(raw),
                context_ids=[{"context_id": GOAL_CONTEXT, "level": "L4"}],
                allow_full_file_read=True,
                context_level="L4",
                inference_proofs=[
                    {
                        "proof_id": "proof-l4-goal-orchestrator",
                        "predicate": "full_file_read_allowed",
                        "arguments": [GOAL_CONTEXT],
                        "status": "accepted",
                        "proof_trace": ["proof-437-source-git-json"],
                    }
                ],
                max_tokens=80000,
            )
            result = prompt_compiler.compile_request(request)
        self.assertEqual("pass", result["status"])
        self.assertIn("full_file_content", result["prompt_text"])

    def test_compile_output_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            request = self.request(Path(raw), context_ids=[], context_level="L1")
            first = prompt_compiler.compile_request(request)
            second = prompt_compiler.compile_request(request)
        self.assertEqual(first["prompt_hash"], second["prompt_hash"])
        self.assertEqual(first["prompt_text"], second["prompt_text"])

    def test_cli_commands_emit_json(self) -> None:
        validate = subprocess.run([sys.executable, "scripts/context_pack.py", "validate"], cwd=ROOT, text=True, stdout=subprocess.PIPE, check=False)
        self.assertEqual(0, validate.returncode)
        self.assertEqual("pass", json.loads(validate.stdout)["status"])
        doctor = subprocess.run([sys.executable, "scripts/prompt_compiler.py", "doctor", "--json"], cwd=ROOT, text=True, stdout=subprocess.PIPE, check=False)
        self.assertEqual(0, doctor.returncode)
        self.assertEqual("pass", json.loads(doctor.stdout)["status"])


if __name__ == "__main__":
    unittest.main()
