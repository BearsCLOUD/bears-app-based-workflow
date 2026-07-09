from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path
from scripts import gitops_degradation, gitops_workflow

ROOT = Path(__file__).resolve().parents[1]

class GitOpsWorkflowTest(unittest.TestCase):
    def test_catalog_validates(self) -> None:
        self.assertEqual([], gitops_workflow.validate_all())

    def test_missing_cache_or_hook_emits_degradation_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "runtime/deliveries/issue-421-fixture").mkdir(parents=True)
            (root / "runtime/deliveries/issue-421-fixture/delivery-manifest.v1.json").write_text("{}\n")
            packet = gitops_degradation.scan("issue-421-fixture", root=root)
        self.assertEqual("degraded", packet["status"])
        self.assertEqual({"cache_sync_missing", "hook_proof_missing"}, {row["signal"] for row in packet["events"]})
        self.assertTrue(all(row["delivery_manifest"].endswith("delivery-manifest.v1.json") for row in packet["events"]))
        self.assertTrue(all("commit-usage-ledger" in row["commit_usage_ledger"] for row in packet["events"]))

    def test_degraded_state_blocks_closeout(self) -> None:
        packet = json.loads((ROOT / "tests/fixtures/gitops_workflow/close-degraded.json").read_text())
        result = gitops_workflow.transition(packet)
        self.assertEqual("blocked", result["status"])
        self.assertTrue(any("degraded GitOps state blocks closeout" in err for err in result["errors"]))

    def test_rollback_required_cannot_close_without_rollback_policy(self) -> None:
        packet = json.loads((ROOT / "tests/fixtures/gitops_workflow/rollback-required-close.json").read_text())
        result = gitops_workflow.transition(packet)
        self.assertEqual("blocked", result["status"])
        self.assertTrue(any("rollback_required delivery cannot close" in err for err in result["errors"]))

    def test_doctor_passes(self) -> None:
        self.assertEqual("pass", gitops_workflow.doctor()["status"])
        self.assertEqual("pass", gitops_degradation.doctor()["status"])

if __name__ == "__main__":
    unittest.main()
