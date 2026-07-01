from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PLUGIN_ROOT / "scripts/pr_pipeline.py"

spec = importlib.util.spec_from_file_location("pr_pipeline", SCRIPT_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("cannot load scripts/pr_pipeline.py")
pr_pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pr_pipeline)


class PrPipelineTests(unittest.TestCase):
    def _ready_pr(self) -> dict[str, object]:
        return {
            "repo": "BearsCLOUD/bears_plugin",
            "number": 201,
            "issue": 201,
            "branch": "codex/issue-201-worker-pool-pr-pipeline",
            "head_sha": "a" * 40,
            "changed_files": ["scripts/pr_pipeline.py", "tests/test_pr_pipeline.py"],
            "ci_state": "pass",
            "review_state": "REVIEW_PASS",
            "mergeable": True,
            "validation_commands": [{"command": "python3 scripts/pr_pipeline.py validate", "exit_code": 0}],
            "route_audit_status": "pass",
        }

    def test_state_classifies_ready_to_merge(self) -> None:
        payload = pr_pipeline.classify_state(self._ready_pr())
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["state"], "ready_to_merge")
        self.assertEqual(payload["merge_gate"]["status"], "MERGE_ALLOWED")

    def test_state_classifies_review_failed(self) -> None:
        pr = self._ready_pr()
        pr["review_state"] = "REVIEW_FAIL"
        payload = pr_pipeline.classify_state(pr)
        self.assertEqual(payload["state"], "review_failed")

    def test_fix_packet_converts_review_fail_to_assignment(self) -> None:
        packet = pr_pipeline.build_fix_packet(
            self._ready_pr(),
            {
                "status": "REVIEW_FAIL",
                "owning_role": "bears-session-worker-runtime-engineer",
                "reviewer_role": "bears-platform-security-reviewer",
                "findings": [
                    {
                        "file": "scripts/pr_pipeline.py",
                        "summary": "Merge gate accepted missing validator evidence.",
                        "regression_test": "python3 -m unittest tests/test_pr_pipeline.py",
                    }
                ],
            },
        )
        self.assertEqual(packet["status"], "FIX_PACKET_READY")
        self.assertEqual(packet["owning_role"], "bears-session-worker-runtime-engineer")
        self.assertEqual(packet["allowed_write_files"], ["scripts/pr_pipeline.py"])
        self.assertEqual(packet["expected_final_status"], "FIX_PASS")

    def test_merge_refuses_without_review_pass_expected_sha_files_and_validators(self) -> None:
        pr = self._ready_pr()
        pr.pop("validation_commands")
        gate = pr_pipeline.merge_gate(pr)
        self.assertEqual(gate["status"], "MERGE_BLOCKED")
        self.assertIn("missing expected head SHA", gate["reasons"])
        self.assertIn("missing exact expected file list", gate["reasons"])
        self.assertIn("validation commands missing or failed", gate["reasons"])

    def test_merge_blocks_changed_file_set(self) -> None:
        pr = self._ready_pr()
        gate = pr_pipeline.merge_gate(pr, expected_head="a" * 40, expected_files=["scripts/pr_pipeline.py"])
        self.assertEqual(gate["status"], "MERGE_BLOCKED")
        self.assertIn("changed file set", gate["reasons"])

    def test_post_merge_reports_open_issue_and_root_ledger(self) -> None:
        payload = pr_pipeline.post_merge_report(
            {
                "number": 119,
                "merged": True,
                "merge_commit_sha": "b" * 40,
                "linked_issues": [{"number": 201, "state": "open"}],
                "ledger": {"root_status": "pending-access"},
            }
        )
        self.assertTrue(payload["merged"])
        self.assertTrue(payload["ledger_follow_up_required"])
        self.assertEqual({item["action"] for item in payload["ledger_followups"]}, {"issue_follow_up", "root_ledger_follow_up"})

    def test_cli_validate_passes(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "validate"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["status"], "ok")


if __name__ == "__main__":
    unittest.main()
