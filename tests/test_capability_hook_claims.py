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

BASE_RUNTIME_CLAIM = {
    "event": "SubagentStop",
    "source_layer": "plugin",
    "hook_source_path": "skills/bears-plugin-update/SKILL.md",
    "enabled_config_layer": "plugin_manifest",
    "feature_key": "features.hooks",
    "effective_hooks_enabled": True,
    "trust_review_status": "pass",
    "handler_type": "command",
    "handler_async": False,
    "matcher_supported": False,
    "timeout_seconds": 10,
    "sanitized_output_schema": "status_only",
    "probe_command": "python3 scripts/capability_layout.py validate-hook-claims --json",
    "blocking_policy": "never",
    "fallback_when_disabled": "run_source_validator",
    "runtime_behavior_claimed": True,
}


def load_inventory():
    return json.loads(INVENTORY.read_text())


def write_inventory(data):
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    with handle:
        json.dump(data, handle)
    return Path(handle.name)


class CapabilityHookClaimTests(unittest.TestCase):
    def run_layout(self, inventory):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "validate-hook-claims", "--json", "--inventory", str(inventory)],
            cwd=PLUGIN_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        return result, json.loads(result.stdout)

    def mutate(self, mutation_id):
        data = load_inventory()
        claim = dict(BASE_RUNTIME_CLAIM)
        if mutation_id == "hook-project-runtime-disabled":
            claim["event"] = "UserPromptSubmit"
            claim["source_layer"] = "project"
            claim["enabled_config_layer"] = "/srv/bears/.codex/config.toml"
            claim["effective_hooks_enabled"] = False
        elif mutation_id == "hook-deprecated-feature-key":
            claim["feature_key"] = "features.codex_hooks"
        elif mutation_id == "hook-async-handler":
            claim["handler_async"] = True
        elif mutation_id == "hook-matcher-dependent":
            claim["event"] = "Stop"
            claim["matcher_dependent"] = True
        elif mutation_id == "hook-missing-probe":
            del claim["probe_command"]
        elif mutation_id == "hook-env-var-read":
            claim["reads_environment_variables"] = True
        elif mutation_id == "hook-raw-output":
            claim["captures_raw_stdout"] = True
        elif mutation_id == "hook-validator-replacement":
            claim["replaces_required_validator"] = True
        elif mutation_id == "hook-broad-tool-blocking":
            claim["blocks_broad_tool_use"] = True
        elif mutation_id == "source-only-hook-design":
            claim = {
                "event": "SubagentStop",
                "source_layer": "plugin",
                "hook_source_path": "skills/bears-plugin-update/SKILL.md",
                "runtime_behavior_claimed": False,
            }
        else:  # pragma: no cover - fixture guard
            raise AssertionError(mutation_id)
        for row in data["capabilities"]:
            if row["id"] == "validation-hooks":
                row["hook_claims"] = [claim]
                break
        return write_inventory(data)

    def test_current_inventory_passes(self):
        result, payload = self.run_layout(INVENTORY)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["restricted_data_status"], "clean")

    def test_source_only_hook_design_passes(self):
        mutated = self.mutate("source-only-hook-design")
        try:
            result, payload = self.run_layout(mutated)
        finally:
            mutated.unlink(missing_ok=True)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(payload["status"], "pass")

    def test_rejects_forbidden_hook_claims(self):
        fixture = json.loads(FIXTURE.read_text())
        rows = [row for row in fixture["mutations"] if row.get("command") == "validate-hook-claims"]
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
