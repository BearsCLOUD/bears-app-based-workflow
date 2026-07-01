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

BASE_PROFILE = {
    "source_agent_path": "agents/bears-workflow-overlay-platform-engineer.toml",
    "spawn_use": False,
}

SPAWN_PROFILE = {
    "source_agent_path": "agents/bears-workflow-overlay-platform-engineer.toml",
    "materialized_agent_path": "codex-agent-dir/bears-workflow-overlay-platform-engineer.toml",
    "model": "gpt-5.5",
    "model_reasoning_effort": "medium",
    "sandbox_mode": "workspace-write",
    "developer_instructions_hash": "sha256:source-only-test-hash",
    "catalog_role": "bears-workflow-overlay-platform-engineer",
    "route_audit_status": "pass",
    "spawn_use": True,
}


def load_inventory():
    return json.loads(INVENTORY.read_text())


def write_inventory(data):
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    with handle:
        json.dump(data, handle)
    return Path(handle.name)


class CapabilityAgentRegistrationTests(unittest.TestCase):
    def run_layout(self, inventory):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "validate-agent-registration", "--json", "--inventory", str(inventory)],
            cwd=PLUGIN_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        return result, json.loads(result.stdout)

    def mutate(self, mutation_id):
        data = load_inventory()
        row = next(item for item in data["capabilities"] if item["id"] == "development-workflow")
        if mutation_id == "agent-source-only-object":
            row["agent_profiles"] = [dict(BASE_PROFILE)]
        elif mutation_id == "agent-spawn-missing-fields":
            row["agent_profiles"] = [{"source_agent_path": BASE_PROFILE["source_agent_path"], "spawn_use": True}]
        elif mutation_id == "agent-spawn-route-audit-not-pass":
            profile = dict(SPAWN_PROFILE)
            profile["route_audit_status"] = "blocked"
            row["agent_profiles"] = [profile]
        else:  # pragma: no cover - fixture guard
            raise AssertionError(mutation_id)
        return write_inventory(data)

    def test_current_inventory_passes_as_source_only(self):
        result, payload = self.run_layout(INVENTORY)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["spawn_claim_count"], 0)
        self.assertEqual(payload["spawnability_status"], "source_only")

    def test_source_only_profile_object_passes(self):
        mutated = self.mutate("agent-source-only-object")
        try:
            result, payload = self.run_layout(mutated)
        finally:
            mutated.unlink(missing_ok=True)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(payload["status"], "pass")

    def test_rejects_spawn_claims_without_proof(self):
        fixture = json.loads(FIXTURE.read_text())
        rows = [
            row for row in fixture["mutations"]
            if row.get("command") == "validate-agent-registration" and row.get("expected_code")
        ]
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
