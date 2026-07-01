from __future__ import annotations

import argparse
import json
import unittest
from unittest import mock

from scripts import bears_commit


class BearsCommitTest(unittest.TestCase):
    def test_commit_runs_plugin_cache_sync_after_exact_lcv(self) -> None:
        commands: list[list[str]] = []

        def fake_run(command: list[str]):
            commands.append(list(command))
            if command[:2] == [bears_commit.sys.executable, "scripts/local_commit_validation.py"] and "--staged" in command:
                return 0, json.dumps({"status": "pass", "proof_path": "runtime/local-commit-validation/staged.json"}), ""
            if command[:2] == ["git", "commit"]:
                return 0, "committed", ""
            if command[:3] == ["git", "rev-parse", "--verify"]:
                return 0, "abc123\n", ""
            if command[:2] == [bears_commit.sys.executable, "scripts/local_commit_validation.py"] and "--commit-sha" in command:
                return 0, json.dumps({"status": "pass", "proof_path": "runtime/local-commit-validation/abc123.json"}), ""
            if command[:2] == [bears_commit.sys.executable, "scripts/plugin_cache_sync.py"]:
                return 0, json.dumps({"cache_sync": {"status": "success"}, "delivery_complete": True}), ""
            return 1, "", f"unexpected command {command}"

        args = argparse.Namespace(git_args=["--", "-m", "test"])
        with mock.patch.object(bears_commit, "run", side_effect=fake_run), mock.patch("builtins.print"):
            code = bears_commit.commit(args)
        self.assertEqual(code, 0)
        self.assertTrue(any(command[:2] == [bears_commit.sys.executable, "scripts/plugin_cache_sync.py"] for command in commands))

    def test_commit_blocks_when_plugin_cache_sync_fails(self) -> None:
        def fake_run(command: list[str]):
            if command[:2] == [bears_commit.sys.executable, "scripts/local_commit_validation.py"] and "--staged" in command:
                return 0, json.dumps({"status": "pass", "proof_path": "runtime/local-commit-validation/staged.json"}), ""
            if command[:2] == ["git", "commit"]:
                return 0, "committed", ""
            if command[:3] == ["git", "rev-parse", "--verify"]:
                return 0, "abc123\n", ""
            if command[:2] == [bears_commit.sys.executable, "scripts/local_commit_validation.py"] and "--commit-sha" in command:
                return 0, json.dumps({"status": "pass", "proof_path": "runtime/local-commit-validation/abc123.json"}), ""
            if command[:2] == [bears_commit.sys.executable, "scripts/plugin_cache_sync.py"]:
                return 5, json.dumps({"cache_sync": {"status": "fail"}, "delivery_complete": False, "workflow_defect": {"reason": "cache mismatch"}}), ""
            return 1, "", f"unexpected command {command}"

        args = argparse.Namespace(git_args=["--", "-m", "test"])
        with mock.patch.object(bears_commit, "run", side_effect=fake_run), mock.patch("builtins.print"):
            code = bears_commit.commit(args)
        self.assertEqual(code, 5)


if __name__ == "__main__":
    unittest.main()
