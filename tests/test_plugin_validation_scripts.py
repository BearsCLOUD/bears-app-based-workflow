"""Tests for canonical Bears Telegram validation entrypoints."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest import TestCase, main


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATHS = [
    PLUGIN_ROOT / "scripts" / "platform_roles.py",
    PLUGIN_ROOT / "scripts" / "plugin_constitution.py",
    PLUGIN_ROOT / "scripts" / "role_gate_methodology.py",
    PLUGIN_ROOT / "scripts" / "project_registry_gate.py",
    PLUGIN_ROOT / "scripts" / "subagent_orchestration_policy.py",
    PLUGIN_ROOT / "scripts" / "roadmap_control.py",
    PLUGIN_ROOT / "scripts" / "git_discipline.py",
    PLUGIN_ROOT / "scripts" / "session_workers_runtime.py",
    PLUGIN_ROOT / "scripts" / "agent_github_dev_cd.py",
    PLUGIN_ROOT / "scripts" / "skill_catalog.py",
    PLUGIN_ROOT / "scripts" / "secret_factory.py",
    PLUGIN_ROOT / "scripts" / "telegram_migration_backlog.py",
    PLUGIN_ROOT / "scripts" / "telegram_runtime_readiness.py",
    PLUGIN_ROOT / "scripts" / "validate_overlay.py",
]


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module spec for {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ValidationEntrypointTests(TestCase):
    EXPECTED_HOOK_IDS = {
        "platform_roles_validate",
        "role_route",
        "role_audit",
        "project_registry_gate",
        "project_registry_validate",
        "subagent_policy_validate",
        "overlay_validate",
        "roadmap_validate",
        "git_discipline_validate",
        "plugin_constitution_validate",
        "role_gate_methodology_validate",
        "session_workers_runtime_validate",
        "agent_github_dev_cd_validate",
        "skill_catalog_generate_check",
        "secret_factory_validate",
        "full_tests_discover",
    }

    def test_required_validation_scripts_exist_and_have_main(self):
        for path in SCRIPT_PATHS:
            with self.subTest(path=path):
                self.assertTrue(path.is_file(), path)
                module = _load_module(path)
                self.assertTrue(hasattr(module, "main"), path)

    def test_removed_standalone_plugin_validators_are_not_required(self):
        self.assertFalse((PLUGIN_ROOT / "quick_validate.py").exists())
        self.assertFalse((PLUGIN_ROOT / "validate_plugin.py").exists())

    def test_telegram_scripts_are_under_canonical_plugin_root(self):
        for path in SCRIPT_PATHS:
            with self.subTest(path=path):
                self.assertTrue(str(path).startswith(str(PLUGIN_ROOT)))

    def test_validation_hook_allowlist_covers_plugin_validators(self):
        policy = json.loads(
            (PLUGIN_ROOT / "assets/catalog/subagent-orchestration-policy.v1.json").read_text()
        )
        hooks = policy["orchestration_model"]["validation_hook_runner"]["allowed_hooks"]
        self.assertEqual({hook["hook_id"] for hook in hooks}, self.EXPECTED_HOOK_IDS)
        for hook in hooks:
            with self.subTest(hook=hook["hook_id"]):
                if hook["script"] == "python3":
                    self.assertEqual(hook["args"], ["-m", "unittest", "discover", "-s", "tests"])
                else:
                    script = PLUGIN_ROOT / hook["script"]
                    self.assertTrue(script.is_file(), script)
                    self.assertTrue(str(script).startswith(str(PLUGIN_ROOT / "scripts")))
                self.assertNotIn("bash", hook["args"])
                self.assertNotIn("-c", hook["args"])

    def test_validation_hook_allowlist_blocks_restricted_output_fields(self):
        policy = json.loads(
            (PLUGIN_ROOT / "assets/catalog/subagent-orchestration-policy.v1.json").read_text()
        )
        runner = policy["orchestration_model"]["validation_hook_runner"]
        forbidden = set(runner["result_schema"]["forbidden_fields"])
        for field in ("raw_stdout", "raw_stderr", "env", "secret", "api_key"):
            with self.subTest(field=field):
                self.assertIn(field, forbidden)
        self.assertIn("credential_read", runner["forbidden_request_kinds"])
        self.assertIn("raw_log_read", runner["forbidden_request_kinds"])
        self.assertIn("production_data_read", runner["forbidden_request_kinds"])


if __name__ == "__main__":
    main()
