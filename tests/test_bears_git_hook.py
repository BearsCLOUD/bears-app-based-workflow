import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import bears_git_hook
from scripts.local_json_schema import validate_json_schema


GOOD = bears_git_hook.PLUGIN_ROOT / "tests/fixtures/git_hook_bootstrap/good/effective-hooks-proof.json"
BAD = bears_git_hook.PLUGIN_ROOT / "tests/fixtures/git_hook_bootstrap/bad/missing-bears-reference.json"


class BearsGitHookTests(unittest.TestCase):
    def make_repo(self) -> Path:
        root = Path(tempfile.mkdtemp())
        subprocess.run(["git", "init"], cwd=root, check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["git", "config", "user.email", "bears@example.invalid"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "Bears Test"], cwd=root, check=True)
        return root

    def test_fixture_proof_schema_accepts_good_and_rejects_bad(self) -> None:
        good = json.loads(GOOD.read_text(encoding="utf-8"))
        bad = json.loads(BAD.read_text(encoding="utf-8"))
        self.assertEqual(validate_json_schema(good, bears_git_hook.PROOF_SCHEMA, "good"), [])
        self.assertTrue(validate_json_schema(bad, bears_git_hook.PROOF_SCHEMA, "bad"))

    def test_install_writes_thin_bears_entrypoints_and_effective_proof(self) -> None:
        repo = self.make_repo()
        packet = bears_git_hook.install_hooks(repo, repo, force=True)
        self.assertEqual(packet["decision"], "allow")
        for name in bears_git_hook.HOOKS:
            text = (repo / ".git" / "hooks" / name).read_text(encoding="utf-8")
            self.assertIn("@bears", text)
            self.assertIn("scripts/bears_git_hook.py", text)
        errors = bears_git_hook.validate_proof_file(Path(packet["proof_path"]))
        self.assertEqual(errors, [])

    def test_pre_commit_outputs_single_json_event(self) -> None:
        repo = self.make_repo()
        bears_git_hook.install_hooks(repo, repo, force=True)
        code, packet = bears_git_hook.run_hook("pre-commit", repo, repo)
        self.assertEqual(code, 0)
        self.assertEqual(packet["schema"], "bears-git-hook-event.v1")
        self.assertEqual(packet["hook"], "pre-commit")
        self.assertEqual(packet["decision"], "allow")
        self.assertNotIn("stderr", json.dumps(packet).lower())

    def test_post_commit_enqueues_validation_without_worker_execution(self) -> None:
        repo = self.make_repo()
        subprocess.run(["git", "commit", "--allow-empty", "-m", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL)
        bears_git_hook.install_hooks(repo, repo, force=True)
        code, packet = bears_git_hook.run_hook("post-commit", repo, repo)
        self.assertEqual(code, 0)
        self.assertEqual(packet["decision"], "allow")
        self.assertEqual(packet["worker_spawn"], "not_started")
        self.assertIn("outside hook hot paths", packet["worker_spawn_reason"])
        self.assertTrue(Path(packet["job_path"]).exists())
        self.assertTrue(Path(packet["state_path"]).exists())

    def test_invalid_hook_is_denied_as_json_event(self) -> None:
        repo = self.make_repo()
        code, packet = bears_git_hook.run_hook("stop", repo, repo)
        self.assertEqual(code, 2)
        self.assertEqual(packet["decision"], "deny")
        self.assertEqual(packet["schema"], "bears-git-hook-event.v1")

    def test_cli_unsupported_stop_hook_outputs_json_event(self) -> None:
        repo = self.make_repo()
        proc = subprocess.run(
            [
                "python3",
                str(bears_git_hook.PLUGIN_ROOT / "scripts/bears_git_hook.py"),
                "run",
                "--hook",
                "stop",
                "--repo-path",
                str(repo),
            ],
            cwd=bears_git_hook.PLUGIN_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stderr, "")
        packet = json.loads(proc.stdout)
        self.assertEqual(packet["schema"], "bears-git-hook-event.v1")
        self.assertEqual(packet["decision"], "deny")
        self.assertEqual(packet["hook"], "stop")

    def test_catalog_validate_passes(self) -> None:
        self.assertEqual(bears_git_hook.validate_catalog(), [])


if __name__ == "__main__":
    unittest.main()
