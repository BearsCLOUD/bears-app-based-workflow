import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import roadmap_backlog_ingest

GOOD = roadmap_backlog_ingest.PLUGIN_ROOT / "tests/fixtures/roadmap_backlog_ingest/good/propose-10-issues.json"
BAD = roadmap_backlog_ingest.PLUGIN_ROOT / "tests/fixtures/roadmap_backlog_ingest/bad/duplicate-node.invalid.json"


class RoadmapBacklogIngestTests(unittest.TestCase):
    def _roadmap(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "schema": "bears-workflow-roadmap.v1",
                    "version": "1",
                    "updated": "2026-06-25",
                    "delivery_id": "bears-governance-kernel-v1",
                    "owner_role": "bears-machine-first-execution-kernel-engineer",
                    "state_model": ["idea", "researched", "contracted", "decomposed", "queued", "running", "validated", "closed", "blocked", "manual_review"],
                    "node_type_model": ["research", "contract", "implementation", "validator", "migration", "cleanup", "closeout"],
                    "agent_roles": [
                        {"role_id": "roadmap_researcher", "authority": "Adds finding-backed candidate nodes only."},
                        {"role_id": "roadmap_curator", "authority": "Normalizes nodes."},
                        {"role_id": "roadmap_decomposer", "authority": "Adds child nodes."},
                        {"role_id": "roadmap_executor", "authority": "Executes eligible leaf nodes."},
                        {"role_id": "roadmap_reconciler", "authority": "Updates state from evidence."},
                    ],
                    "commands": [
                        "scripts/workflow_roadmap.py validate",
                        "scripts/workflow_roadmap.py add-node --packet <path>",
                        "scripts/workflow_roadmap.py decompose --node <id>",
                        "scripts/workflow_roadmap.py next --json",
                        "scripts/workflow_roadmap.py reconcile --json",
                    ],
                    "nodes": [
                        {"node_id": "issue-1-impl", "issue": "#1", "node_type": "implementation", "state": "queued", "owner_role": "roadmap_executor", "source_of_truth": ["github_issue"], "inputs": ["#1"], "outputs": ["docs/one.md"], "depends_on": [], "decomposes_to": [], "blocked_by": [], "autostart_policy": "eligible", "evidence_paths": ["https://github.com/example/repo/issues/1"]},
                        {"node_id": "issue-2-review", "issue": "#2", "node_type": "implementation", "state": "manual_review", "owner_role": "roadmap_executor", "source_of_truth": ["github_issue"], "inputs": ["#2"], "outputs": ["docs/two.md"], "depends_on": [], "decomposes_to": [], "blocked_by": [], "autostart_policy": "manual_review", "evidence_paths": ["https://github.com/example/repo/issues/2"]},
                        {"node_id": "issue-3-blocked", "issue": "#3", "node_type": "implementation", "state": "queued", "owner_role": "roadmap_executor", "source_of_truth": ["github_issue"], "inputs": ["#3"], "outputs": ["docs/three.md"], "depends_on": [], "decomposes_to": [], "blocked_by": ["issue-2-review"], "autostart_policy": "eligible", "evidence_paths": ["https://github.com/example/repo/issues/3"]},
                    ],
                }
            ),
            encoding="utf-8",
        )

    def test_validate_accepts_good_and_rejects_bad_fixture(self) -> None:
        self.assertEqual(roadmap_backlog_ingest.validate_ingestion_packet(json.loads(GOOD.read_text())), [])
        self.assertTrue(roadmap_backlog_ingest.validate_ingestion_packet(json.loads(BAD.read_text())))
        self.assertEqual(roadmap_backlog_ingest.validate_all(), [])

    def test_scan_normalizes_fixture_issues(self) -> None:
        packet = roadmap_backlog_ingest.scan(
            "owner/repo",
            issues=[{"number": 2, "title": "Two", "state": "OPEN", "url": "u", "labels": [{"name": "b"}, {"name": "a"}], "updatedAt": "now", "body": "scripts/two.py"}],
        )
        self.assertEqual(packet["status"], "pass")
        self.assertEqual(packet["source"], "fixture")
        self.assertEqual(packet["issues"][0]["labels"], ["a", "b"])
        self.assertIn("scripts/two.py", packet["issues"][0]["required_files"])

    def test_propose_emits_valid_nodes_without_mutation(self) -> None:
        issues = [{"number": 77, "title": "Bounded", "state": "OPEN", "url": "u", "labels": [], "body": "scripts/x.py\n## Acceptance\n- pass"}]
        with tempfile.TemporaryDirectory() as tmp:
            roadmap = Path(tmp) / "roadmap.json"
            self._roadmap(roadmap)
            before = roadmap.read_text()
            scan = roadmap_backlog_ingest.scan("owner/repo", issues=issues)
            proposal = roadmap_backlog_ingest.proposal_from_scan(scan, roadmap)
            self.assertEqual(roadmap.read_text(), before)
        self.assertEqual(proposal["fillability"]["needs_node"], 1)
        self.assertEqual(proposal["proposed_nodes"][0]["issue"], "#77")
        self.assertEqual(roadmap_backlog_ingest.validate_ingestion_packet(proposal), [])

    def test_apply_adds_nodes_only_from_valid_packet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            roadmap = Path(tmp) / "roadmap.json"
            packet = Path(tmp) / "packet.json"
            self._roadmap(roadmap)
            proposal = json.loads(GOOD.read_text())
            proposal["proposed_nodes"] = proposal["proposed_nodes"][:1]
            packet.write_text(json.dumps(proposal), encoding="utf-8")
            result = roadmap_backlog_ingest.apply_packet(packet, roadmap)
            self.assertEqual(result["status"], "pass")
            self.assertEqual(result["applied"], [proposal["proposed_nodes"][0]["node_id"]])

    def test_fillability_classifies_queued_missing_and_blocked(self) -> None:
        scan_packet = roadmap_backlog_ingest.scan(
            "owner/repo",
            issues=[
                {"number": 1, "title": "One", "state": "OPEN"},
                {"number": 2, "title": "Two", "state": "OPEN"},
                {"number": 3, "title": "Three", "state": "OPEN"},
                {"number": 4, "title": "Four", "state": "OPEN"},
            ],
        )
        with tempfile.TemporaryDirectory() as tmp:
            roadmap = Path(tmp) / "roadmap.json"
            self._roadmap(roadmap)
            missing = Path(tmp) / "missing-roadmap.json"
            with mock.patch.object(roadmap_backlog_ingest, "ROADMAP", missing):
                packet = roadmap_backlog_ingest.fillability(scan_packet, roadmap)
        rows = {row["number"]: row for row in packet["issues"]}
        self.assertTrue(rows[1]["fillable"])
        self.assertEqual(rows[2]["reason"], "roadmap_node_not_fillable")
        self.assertEqual(rows[3]["reason"], "blocked_by_dependency")
        self.assertEqual(rows[4]["reason"], "missing_roadmap_node")
        self.assertEqual(packet["counts"]["fillable"], 1)
        self.assertEqual(packet["schema"], "bears-roadmap-fillability-report.v1")

    def test_cli_validate_json_reports_pass(self) -> None:
        code = roadmap_backlog_ingest.main(["validate", "--json"])
        self.assertEqual(code, 0)

    def test_cli_scan_with_missing_fixture_returns_nonzero_json(self) -> None:
        code = roadmap_backlog_ingest.main(["scan", "--repo", "owner/repo", "--issues-json", "missing.json", "--json", "--no-write"])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
