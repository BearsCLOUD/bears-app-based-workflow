from __future__ import annotations

import argparse
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PLUGIN_ROOT / "scripts/local_commit_validation.py"

spec = importlib.util.spec_from_file_location("local_commit_validation", SCRIPT_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("cannot load scripts/local_commit_validation.py")
local_commit_validation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(local_commit_validation)


class LocalCommitValidationTests(unittest.TestCase):
    def test_clean_git_hook_env_removes_hook_specific_git_vars(self) -> None:
        original = os.environ.copy()
        try:
            for key in local_commit_validation.GIT_HOOK_ENV_KEYS:
                os.environ[key] = "hook-value"
            env = local_commit_validation.clean_git_hook_env()
        finally:
            os.environ.clear()
            os.environ.update(original)
        for key in local_commit_validation.GIT_HOOK_ENV_KEYS:
            self.assertNotIn(key, env)

    def test_install_hook_writes_post_commit_local_validation_runner(self) -> None:
        original_run_command = local_commit_validation.run_command
        original_plugin_root = local_commit_validation.PLUGIN_ROOT
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            hooks_dir = root / "hooks"

            def fake_run_command(command: list[str], *, timeout: int = 600) -> tuple[int, str, str]:
                self.assertEqual(command, ["git", "rev-parse", "--git-path", "hooks"])
                return 0, str(hooks_dir), ""

            local_commit_validation.run_command = fake_run_command
            local_commit_validation.PLUGIN_ROOT = root
            try:
                code = local_commit_validation.install_hook(argparse.Namespace(force=False))
            finally:
                local_commit_validation.run_command = original_run_command
                local_commit_validation.PLUGIN_ROOT = original_plugin_root
            pre_hook = hooks_dir / "pre-commit"
            post_hook = hooks_dir / "post-commit"
            self.assertEqual(code, 0)
            self.assertTrue(pre_hook.is_file())
            self.assertTrue(post_hook.is_file())
            pre_body = pre_hook.read_text(encoding="utf-8")
            post_body = post_hook.read_text(encoding="utf-8")
            self.assertIn("python3 scripts/bears_git_hook.py run --hook pre-commit", pre_body)
            self.assertIn("python3 scripts/bears_git_hook.py run --hook post-commit", post_body)
            self.assertIn(f"--workspace-root '{root.parent}'", pre_body)
            self.assertIn("unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_PREFIX GIT_COMMON_DIR", pre_body)
            self.assertIn("unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_PREFIX GIT_COMMON_DIR", post_body)
            self.assertTrue(pre_hook.stat().st_mode & 0o111)
            self.assertTrue(post_hook.stat().st_mode & 0o111)

    def test_validate_proof_requires_exact_pass_sha(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            proof = Path(tmpdir) / "proof.json"
            proof.write_text(
                json.dumps(
                    {
                        "schema": local_commit_validation.SCHEMA,
                        "status": "pass",
                        "commit_sha": "a" * 40,
                        "tests": [],
                    }
                ),
                encoding="utf-8",
            )
            code = local_commit_validation.validate_proof(
                argparse.Namespace(proof=str(proof), commit_sha="a" * 40)
            )
        self.assertEqual(code, 0)

    def test_select_autoci_zones_maps_app_paths_to_zone_names(self) -> None:
        packet = local_commit_validation.select_autoci_zones(
            ["src/lead.py", "docs/app-task-ledger.v1.json"],
            {
                "schema": "autoci-graph.v1",
                "zones": [
                    {"id": "app-source", "path_patterns": ["src/**"], "expected_statuses": ["app.autoCI.fast"]},
                    {"id": "app-functional-graph", "path_patterns": ["docs/app-task-ledger.v1.json"], "expected_statuses": ["app-functional-graph.validate"]},
                ],
            },
        )
        self.assertEqual(packet["status"], "pass")
        self.assertEqual(packet["zones"], ["app-functional-graph", "app-source"])
        self.assertEqual(packet["expected_statuses"], ["app-functional-graph.validate", "app.autoCI.fast"])

    def test_validation_plan_includes_autoci_zone_selection(self) -> None:
        plan = local_commit_validation.validation_plan(
            changed_files=["src/lead.py"],
            selection={"selector_confidence": "high", "tests": ["tests/test_app_functional_graph.py"], "unmatched": []},
            pants_impacted={"status": "pass", "tests": [], "unmatched": []},
            autoci_selection={"schema": "autoci-zone-selection.v1", "status": "pass", "zones": ["app-source"], "expected_statuses": ["app.autoCI.fast"], "matched": {"src/lead.py": ["app-source"]}, "unmatched": []},
        )
        self.assertEqual(plan["status"], "pass")
        self.assertEqual(plan["autoCI_zones"], ["app-source"])
        self.assertEqual(plan["autoCI_expected_statuses"], ["app.autoCI.fast"])


if __name__ == "__main__":
    unittest.main()
