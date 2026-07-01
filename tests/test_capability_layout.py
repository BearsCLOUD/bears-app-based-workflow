import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN_ROOT / "scripts/capability_layout.py"
INVENTORY = PLUGIN_ROOT / "capabilities/inventory.v1.json"
SKILL_CATALOG = PLUGIN_ROOT / "assets/catalog/plugin-skill-catalog.v1.json"
MUTATIONS = PLUGIN_ROOT / "tests/fixtures/capability_layout/mutations.v1.json"


class CapabilityLayoutTests(unittest.TestCase):
    def run_layout(self, *args, cwd=None):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=cwd or PLUGIN_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:  # pragma: no cover - assertion aid
            self.fail(f"stdout is not JSON: {exc}: {result.stdout!r}; stderr={result.stderr!r}")
        return result, payload

    def write_mutated_inventory(self, mutation_id: str) -> Path:
        inventory = json.loads(INVENTORY.read_text())
        catalog = json.loads(SKILL_CATALOG.read_text())
        mutation_rows = json.loads(MUTATIONS.read_text())["mutations"]
        self.assertIn(mutation_id, {row["id"] for row in mutation_rows})
        first_active = catalog["active_skills"][0]["path"]
        first_disabled = catalog["disabled_skills"][0]["path"]

        if mutation_id == "duplicate-active-front-door":
            inventory["capabilities"][1]["active_skill_front_doors"].append(first_active)
        elif mutation_id == "unmapped-active-front-door":
            for row in inventory["capabilities"]:
                if first_active in row["active_skill_front_doors"]:
                    row["active_skill_front_doors"].remove(first_active)
                    break
        elif mutation_id == "disabled-skill-active-front-door":
            inventory["capabilities"][0]["active_skill_front_doors"].append(first_disabled)
        else:  # pragma: no cover - fixture guard
            raise AssertionError(mutation_id)

        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        with handle:
            json.dump(inventory, handle)
        return Path(handle.name)

    def assert_failure_code(self, mutation_id: str, expected_code: str):
        mutated = self.write_mutated_inventory(mutation_id)
        try:
            result, payload = self.run_layout("validate-inventory", "--json", "--inventory", str(mutated))
        finally:
            mutated.unlink(missing_ok=True)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertEqual(payload["status"], "fail")
        codes = {item["code"] for item in payload["errors"]}
        self.assertIn(expected_code, codes)

    def test_pass_inventory(self):
        result, payload = self.run_layout("validate-inventory", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["capability_count"], payload["target_capability_count"])
        self.assertEqual(payload["mapped_active_skill_count"], payload["active_skill_count"])

    def test_validate_checks_plugin_constitution_package(self):
        result, payload = self.run_layout("validate", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["status"], "pass")
        checks = {item["id"]: item for item in payload["checks"]}
        for check_id in [
            "hook_claims",
            "reviewer_lanes",
            "capability_packages",
            "agent_registration",
            "rule_coverage_ledger_validation",
            "automation_first_refactor_gate_validation",
        ]:
            self.assertIn(check_id, checks)
            self.assertEqual(checks[check_id]["status"], "pass")

    def test_duplicate_active_front_door_rejected(self):
        self.assert_failure_code("duplicate-active-front-door", "DUPLICATE_ACTIVE_SKILL_MAPPING")

    def test_unmapped_active_skill_rejected(self):
        self.assert_failure_code("unmapped-active-front-door", "UNMAPPED_ACTIVE_SKILL")

    def test_disabled_skill_exclusion(self):
        self.assert_failure_code("disabled-skill-active-front-door", "DISABLED_SKILL_ACTIVE_FRONT_DOOR")

    def test_runs_from_tmp(self):
        result, payload = self.run_layout("validate-inventory", "--json", cwd="/tmp")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(payload["plugin_root"], str(PLUGIN_ROOT))
        self.assertEqual(payload["status"], "pass")

    def test_status_json_fields_exist_now(self):
        result, payload = self.run_layout("status", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        for field in [
            "schema",
            "status",
            "plugin_root",
            "inventory_path",
            "schema_path",
            "target_capability_count",
            "capability_count",
            "active_skill_count",
            "disabled_skill_count",
            "mapped_active_skill_count",
            "checks",
            "cache_status",
            "validation_commands",
            "restricted_data_status",
            "errors",
        ]:
            self.assertIn(field, payload)
        self.assertEqual(payload["restricted_data_status"], "clean")
        for command in [
            "python3 scripts/capability_layout.py validate-hook-claims --json",
            "python3 scripts/capability_layout.py validate-reviewer-lanes --json",
            "python3 scripts/capability_layout.py validate-agent-registration --json",
            "python3 scripts/capability_layout.py validate-parity --json",
            "python3 scripts/capability_layout.py validate-restricted-data --json",
            "python3 scripts/capability_layout.py snapshot-environment --json",
            "python3 scripts/capability_layout.py plan-environment-operation --operation config_change_request --json",
            "python3 scripts/capability_layout.py validate-environment-packet --packet tests/fixtures/capability_layout/environment_packets/pass/config_change_request.valid.json --json",
            "python3 scripts/capability_layout.py validate-optimization-plan --packet tests/fixtures/capability_layout/optimization_lanes/pass/effective_config_resolution.valid.json --json",
            "python3 scripts/capability_layout.py resolve-effective-environment --json",
            "python3 scripts/capability_layout.py validate-effective-config --snapshot tests/fixtures/capability_layout/effective_config/pass/trusted_project_layer.valid.json --json",
            "python3 scripts/capability_layout.py validate-managed-requirements --snapshot tests/fixtures/capability_layout/effective_config/pass/trusted_project_layer.valid.json --json",
            "python3 scripts/capability_layout.py validate-performance-claims --packet tests/fixtures/capability_layout/performance_lanes/pass/all_surfaces.valid.json --snapshot tests/fixtures/capability_layout/effective_config/pass/trusted_project_layer.valid.json --json",
            "python3 scripts/capability_layout.py validate-offload-claims --packet tests/fixtures/capability_layout/offload_surfaces/pass/all_surfaces.valid.json --snapshot tests/fixtures/capability_layout/effective_config/pass/trusted_project_layer.valid.json --json",
            "python3 scripts/capability_layout.py validate-programmatic-surfaces --packet tests/fixtures/capability_layout/programmatic_surfaces/pass/all_surfaces.valid.json --snapshot tests/fixtures/capability_layout/effective_config/pass/trusted_project_layer.valid.json --json",
            "python3 scripts/capability_layout.py validate-rule-coverage --json",
            "python3 scripts/capability_layout.py validate-refactor-gate --json",
        ]:
            self.assertIn(command, payload["validation_commands"])
        self.assertEqual(payload["rule_coverage_status"], "pass")
        self.assertEqual(payload["instruction_only_rule_count"], 0)
        self.assertEqual(payload["uncovered_rule_ids"], [])
        self.assertEqual(payload["refactor_gate_status"], "pass")

    def test_cli_lists_p1_09_to_p1_15_commands(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            cwd=PLUGIN_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        for command in [
            "validate-parity",
            "validate-restricted-data",
            "snapshot-environment",
            "plan-environment-operation",
            "validate-environment-packet",
            "validate-optimization-plan",
            "resolve-effective-environment",
            "validate-effective-config",
            "validate-managed-requirements",
            "validate-performance-claims",
            "validate-offload-claims",
            "validate-programmatic-surfaces",
            "validate-rule-coverage",
            "validate-refactor-gate",
        ]:
            self.assertIn(command, result.stdout)


if __name__ == "__main__":
    unittest.main()
