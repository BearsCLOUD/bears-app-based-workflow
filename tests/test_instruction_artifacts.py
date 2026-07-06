"""Tests for Bears instruction artifact zones."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PLUGIN_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from bears_workflow.instruction_artifacts.application import zones
from bears_workflow.instruction_artifacts.domain import constants


class InstructionArtifactTests(unittest.TestCase):
    def test_default_paths_use_runtime_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "workspace"
            codex_config = Path(tmpdir) / "codex" / "config.toml"
            personal_agents = Path(tmpdir) / "codex" / "AGENTS.md"
            env = {
                constants.ENV_INSTRUCTION_ROOT: str(root),
                constants.ENV_CODEX_CONFIG: str(codex_config),
                constants.ENV_PERSONAL_AGENTS: str(personal_agents),
            }
            with patch.dict(os.environ, env, clear=False):
                self.assertEqual(constants.default_root(), root)
                self.assertEqual(constants.default_codex_config(), codex_config)
                self.assertEqual(constants.default_personal_agents(), personal_agents)

    def test_zones_startup_applies_response_budget(self) -> None:
        payload = {
            "docs": [{"id": index} for index in range(4)],
            "graphs": [{"target": index} for index in range(4)],
        }
        with patch.object(zones, "build_zones", return_value=payload):
            packet = zones.build_zones_startup(response_line_budget=3)
        self.assertEqual(packet["schema"], "bears.instruction_zones.startup.v1")
        self.assertEqual(packet["response_line_budget"], 3)
        self.assertEqual(packet["response_lines"], 3)
        self.assertTrue(packet["truncated"])
        self.assertEqual(packet["counts"]["returned_docs"], 1)
        self.assertEqual(packet["counts"]["returned_graphs"], 2)
        self.assertEqual(packet["next_calls"][0]["tool"], "zones")

    def test_instruction_hardening_graphs_marks_missing_operator_decision(self) -> None:
        payload = {
            "docs": [
                {
                    "id": 0,
                    "kind": "instruction",
                    "path": "$workspace/AGENTS.md",
                    "title": "Router",
                    "sections": [
                        {
                            "heading": "Rules",
                            "blocks": [{"rules": ["Required read AGENTS.md"], "lines": []}],
                        }
                    ],
                }
            ],
            "graphs": [{"target": 0, "chain": [0], "dependencies": []}],
        }
        with patch.object(zones, "build_zones", return_value=payload):
            packet = zones.build_instruction_hardening_graphs()

        graph = packet["graphs"][0]
        self.assertEqual(packet["schema"], "bears.instruction_hardening.graphs.v1")
        self.assertFalse(packet["source"]["instructions_source_of_truth"])
        self.assertEqual(graph["decision"]["status"], "missing")
        self.assertEqual(graph["live_confirmation"]["status"], "missing")
        self.assertEqual(graph["standardization"]["status"], "aligned")

    def test_instruction_hardening_graphs_keeps_scanned_decision_mentions_evidence_only(self) -> None:
        payload = {
            "docs": [
                {
                    "id": 0,
                    "kind": "instruction",
                    "path": "$workspace/AGENTS.md",
                    "title": "Router",
                    "sections": [
                        {
                            "heading": "Decision",
                            "blocks": [
                                {
                                    "rules": [
                                        "Operator decision: use MCP evidence before edits.",
                                        "This conflicts with operator decision in a later rule.",
                                    ],
                                    "lines": ["Allowed inspect graph evidence."],
                                }
                            ],
                        }
                    ],
                }
            ],
            "graphs": [{"target": 0, "chain": [0], "dependencies": []}],
        }
        with patch.object(zones, "build_zones", return_value=payload):
            packet = zones.build_instruction_hardening_graphs()

        graph = packet["graphs"][0]
        self.assertEqual(graph["decision"]["status"], "missing")
        self.assertEqual(graph["live_confirmation"]["status"], "refuted")
        self.assertEqual(graph["decision"]["evidence_doc_ids"], [])
        self.assertEqual(graph["decision"]["evidence_only_doc_ids"], [0])
        self.assertEqual(graph["decision"]["refutable_doc_ids"], [0])

    def test_instruction_hardening_graphs_does_not_promote_target_doc_mentions(self) -> None:
        payload = {
            "docs": [
                {
                    "id": 0,
                    "kind": "instruction",
                    "path": "$workspace/AGENTS.md",
                    "title": "Router",
                    "sections": [
                        {
                            "heading": "Decision",
                            "blocks": [
                                {
                                    "rules": ["Operator decision: target-only graph evidence."],
                                    "lines": ["Forbidden use scanned instructions as source of truth."],
                                }
                            ],
                        }
                    ],
                }
            ],
            "graphs": [{"target": 0, "chain": [], "dependencies": []}],
        }
        with patch.object(zones, "build_zones", return_value=payload):
            packet = zones.build_instruction_hardening_graphs()

        graph = packet["graphs"][0]
        self.assertEqual(graph["decision"]["status"], "missing")
        self.assertEqual(graph["decision"]["evidence_doc_ids"], [])
        self.assertEqual(graph["decision"]["evidence_only_doc_ids"], [0])
        self.assertEqual(graph["live_confirmation"]["status"], "missing")
        self.assertIn("graphs[].target", graph["live_confirmation"]["checked_fields"])
        self.assertEqual(graph["dependency_decision_refs"], [])
        self.assertEqual(graph["escalation_candidate"]["status"], "not_required")

    def test_instruction_hardening_graphs_uses_decision_ledger_source(self) -> None:
        payload = {
            "docs": [
                {
                    "id": 0,
                    "kind": "markdown_reference",
                    "path": "$workspace/docs/reference/instruction-artifacts-mcp.md",
                    "title": "MCP",
                    "sections": [
                        {
                            "heading": "Rules",
                            "blocks": [{"rules": ["Required MCP evidence."], "lines": []}],
                        }
                    ],
                }
            ],
            "graphs": [{"target": 0, "chain": [0], "dependencies": []}],
        }
        decision_ledger = {
            "records": [
                {
                    "affected_paths": ["docs/reference/instruction-artifacts-mcp.md"],
                    "contradictions": [],
                    "decision": "Use the instruction-hardening MCP evidence packet.",
                    "decision_id": "D-test-instruction-hardening",
                    "live_confirmation": {
                        "evidence_paths": ["docs/reference/instruction-artifacts-mcp.md"],
                        "status": "confirmed",
                    },
                    "owner_role": "bears-instruction-hardening-engineer",
                    "scope_id": "instruction-artifacts-hardening-mcp",
                    "status": "accepted",
                    "unresolved_inputs": [],
                }
            ],
            "warnings": [],
        }
        with (
            patch.object(zones, "build_zones", return_value=payload),
            patch.object(zones, "_decision_ledger", return_value=decision_ledger),
        ):
            packet = zones.build_instruction_hardening_graphs()

        graph = packet["graphs"][0]
        self.assertEqual(graph["decision"]["status"], "present")
        self.assertEqual(graph["decision"]["source"], "decision_ledger")
        self.assertEqual(graph["decision"]["decision_ledger_refs"], ["D-test-instruction-hardening"])
        self.assertEqual(graph["live_confirmation"]["status"], "confirmed")
        self.assertEqual(
            graph["live_confirmation"]["confirmable_paths"],
            ["docs/reference/instruction-artifacts-mcp.md"],
        )

    def test_instruction_hardening_graphs_requires_ledger_path_overlap(self) -> None:
        payload = {
            "docs": [
                {
                    "id": 0,
                    "kind": "markdown_reference",
                    "path": "$workspace/docs/reference/instruction-artifacts-mcp.md",
                    "title": "MCP",
                    "sections": [
                        {
                            "heading": "Rules",
                            "blocks": [{"rules": ["Required MCP evidence."], "lines": []}],
                        }
                    ],
                }
            ],
            "graphs": [{"target": 0, "chain": [0], "dependencies": []}],
        }
        decision_ledger = {
            "records": [
                {
                    "affected_paths": ["docs/reference/other.md"],
                    "contradictions": [],
                    "decision": "Use another graph.",
                    "decision_id": "D-test-wrong-path",
                    "live_confirmation": {
                        "evidence_paths": ["docs/reference/other.md"],
                        "status": "confirmed",
                    },
                    "owner_role": "bears-instruction-hardening-engineer",
                    "scope_id": "instruction-artifacts-hardening-mcp",
                    "status": "accepted",
                    "unresolved_inputs": [],
                }
            ],
            "warnings": [],
        }
        with (
            patch.object(zones, "build_zones", return_value=payload),
            patch.object(zones, "_decision_ledger", return_value=decision_ledger),
        ):
            packet = zones.build_instruction_hardening_graphs()

        graph = packet["graphs"][0]
        self.assertEqual(graph["decision"]["status"], "missing")
        self.assertEqual(graph["live_confirmation"]["status"], "missing")

    def test_instruction_hardening_graphs_links_dependency_decisions(self) -> None:
        payload = {
            "docs": [
                {
                    "id": 0,
                    "kind": "instruction",
                    "path": "$workspace/AGENTS.md",
                    "title": "Router",
                    "sections": [
                        {
                            "heading": "Decision",
                            "blocks": [
                                {
                                    "rules": ["Operator decision: route instruction edits through MCP."],
                                    "lines": ["Required inspect linked docs."],
                                }
                            ],
                        }
                    ],
                },
                {
                    "id": 1,
                    "kind": "markdown_reference",
                    "path": "$workspace/contracts/instruction-policy.md",
                    "title": "Policy",
                    "sections": [
                        {
                            "heading": "Rules",
                            "blocks": [{"rules": ["Required preserve operator scope."], "lines": []}],
                        }
                    ],
                },
            ],
            "graphs": [
                {
                    "target": 0,
                    "chain": [0],
                    "dependencies": [{"from": 0, "to": 1, "type": "markdown_reference"}],
                }
            ],
        }
        with patch.object(zones, "build_zones", return_value=payload):
            packet = zones.build_instruction_hardening_graphs()

        graph = packet["graphs"][0]
        dependency_ref = graph["dependency_decision_refs"][0]
        self.assertEqual(dependency_ref["from_doc_id"], 0)
        self.assertEqual(dependency_ref["to_doc_id"], 1)
        self.assertEqual(dependency_ref["from_decision_status"], "missing")
        self.assertEqual(dependency_ref["to_decision_status"], "missing")
        self.assertFalse(dependency_ref["escalation_signal"])
        self.assertEqual(graph["escalation_candidate"]["status"], "not_required")

    def test_instruction_hardening_graphs_marks_escalation_candidate(self) -> None:
        payload = {
            "docs": [
                {
                    "id": 0,
                    "kind": "instruction",
                    "path": "$workspace/AGENTS.md",
                    "title": "Router",
                    "sections": [
                        {
                            "heading": "Decision",
                            "blocks": [
                                {
                                    "rules": ["Operator decision: keep deploy rules higher level."],
                                    "lines": ["Required inspect dependency edges."],
                                }
                            ],
                        }
                    ],
                },
                {
                    "id": 1,
                    "kind": "markdown_reference",
                    "path": "$workspace/kubernetes/AGENTS.md",
                    "title": "Kubernetes",
                    "sections": [
                        {
                            "heading": "Rules",
                            "blocks": [
                                {
                                    "rules": ["Required Kubernetes deploy policy owner review."],
                                    "lines": [],
                                }
                            ],
                        }
                    ],
                },
            ],
            "graphs": [
                {
                    "target": 0,
                    "chain": [0],
                    "dependencies": [{"from": 0, "to": 1, "type": "markdown_reference"}],
                }
            ],
        }
        with patch.object(zones, "build_zones", return_value=payload):
            packet = zones.build_instruction_hardening_graphs()

        graph = packet["graphs"][0]
        self.assertTrue(graph["dependency_decision_refs"][0]["escalation_signal"])
        self.assertEqual(graph["escalation_candidate"]["status"], "required")
        self.assertEqual(
            graph["escalation_candidate"]["evidence_dependency_refs"],
            [{"from_doc_id": 0, "to_doc_id": 1}],
        )

    def test_instruction_hardening_startup_applies_response_budget(self) -> None:
        payload = {
            "schema": "bears.instruction_hardening.graphs.v1",
            "source": {"scanner": "instruction_artifacts"},
            "counts": {"docs": 4, "graphs": 4},
            "docs": [{"id": index} for index in range(4)],
            "graphs": [{"target": index} for index in range(4)],
        }
        with patch.object(zones, "build_instruction_hardening_graphs", return_value=payload):
            packet = zones.build_instruction_hardening_startup(response_line_budget=3)

        self.assertEqual(packet["schema"], "bears.instruction_hardening.startup.v1")
        self.assertEqual(packet["response_line_budget"], 3)
        self.assertEqual(packet["response_lines"], 3)
        self.assertTrue(packet["truncated"])
        self.assertEqual(packet["next_calls"][0]["tool"], "instruction_hardening_graphs")

    def test_build_zones_uses_codex_config_parent_as_codex_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "workspace"
            codex_dir = Path(tmpdir) / "codex"
            codex_config = codex_dir / "config.toml"
            personal_agents = codex_dir / "AGENTS.md"
            root.mkdir()
            codex_dir.mkdir()
            codex_config.write_text("", encoding="utf-8")
            personal_agents.write_text("", encoding="utf-8")
            target = root / constants.AGENTS_NAME
            target.write_text("", encoding="utf-8")

            with (
                patch.object(zones.exporter, "parse_model_instructions_file", return_value=(None, [])),
                patch.object(zones.exporter, "discover_agents", return_value=([target], [])),
                patch.object(
                    zones.exporter,
                    "build_normalized_export",
                    return_value={"docs": [], "graphs": []},
                ) as build_normalized_export,
            ):
                result = zones.build_zones(
                    root=root,
                    codex_config=codex_config,
                    personal_agents=personal_agents,
                )

            self.assertEqual(result, {"docs": [], "graphs": []})
            self.assertEqual(
                build_normalized_export.call_args.kwargs["codex_root"],
                codex_dir.resolve(),
            )


if __name__ == "__main__":
    unittest.main()
