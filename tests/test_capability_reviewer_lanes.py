import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN_ROOT / "scripts/capability_layout.py"
INVENTORY = PLUGIN_ROOT / "capabilities/inventory.v1.json"
FIXTURE = PLUGIN_ROOT / "tests/fixtures/capability_layout/p1_06_08_mutations.v1.json"


def load_inventory():
    return json.loads(INVENTORY.read_text())


def write_inventory(data):
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    with handle:
        json.dump(data, handle)
    return Path(handle.name)


class CapabilityReviewerLaneTests(unittest.TestCase):
    def run_layout(self, inventory):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "validate-reviewer-lanes", "--json", "--inventory", str(inventory)],
            cwd=PLUGIN_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        return result, json.loads(result.stdout)

    def mutate(self, mutation_id):
        data = load_inventory()
        row = next(item for item in data["capabilities"] if item["id"] == "subagent-orchestration")
        policy = row["reviewer_lane_policy"]
        if mutation_id == "reviewer-advisory-blocks-parent":
            policy["advisory_async"]["parent_same_turn_wait_required"] = True
        elif mutation_id == "reviewer-advisory-write-authority":
            policy["advisory_async"]["write_authority"] = "write_files"
        elif mutation_id == "reviewer-blocking-missing-reason":
            policy["blocking_gate"]["hard_stop_reason"] = "opinion_only"
        elif mutation_id == "reviewer-blocking-missing-timeout":
            policy["blocking_gate"]["timeout_seconds"] = 0
        elif mutation_id == "reviewer-blocking-missing-fallback":
            policy["blocking_gate"]["fallback_action"] = ""
        elif mutation_id == "reviewer-blocking-missing-artifact":
            policy["blocking_gate"]["expected_closeout_artifact"] = ""
        elif mutation_id == "reviewer-blocking-no-stale-rejection":
            policy["blocking_gate"]["stale_result_rejection"] = False
        else:  # pragma: no cover - fixture guard
            raise AssertionError(mutation_id)
        return write_inventory(data)

    def test_current_inventory_passes(self):
        result, payload = self.run_layout(INVENTORY)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["mandatory_reviewer_lane_count"], 3)

    def test_rejects_invalid_reviewer_lanes(self):
        fixture = json.loads(FIXTURE.read_text())
        rows = [row for row in fixture["mutations"] if row.get("command") == "validate-reviewer-lanes"]
        self.assertGreater(len(rows), 0)
        for row in rows:
            with self.subTest(row=row["id"]):
                mutated = self.mutate(row["id"])
                try:
                    result, payload = self.run_layout(mutated)
                finally:
                    mutated.unlink(missing_ok=True)
                self.assertEqual(result.returncode, 1, result.stdout)
                self.assertEqual(payload["status"], "fail")
                self.assertIn(row["expected_code"], {item["code"] for item in payload["errors"]})


if __name__ == "__main__":
    unittest.main()
