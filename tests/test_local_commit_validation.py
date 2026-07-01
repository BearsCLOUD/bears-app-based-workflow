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
            self.assertIn("--workspace-root /srv/bears", pre_body)
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


if __name__ == "__main__":
    unittest.main()
