from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PLUGIN_ROOT / "scripts" / "git_discipline.py"
spec = importlib.util.spec_from_file_location("git_discipline", SCRIPT_PATH)
git_discipline = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(git_discipline)  # type: ignore[arg-type]


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return result.stdout.strip()


def make_child_commit(repo: Path, content: str) -> str:
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "codex-worker@bears.local")
    git(repo, "config", "user.name", "Bears Codex Worker")
    (repo / "file.txt").write_text(content, encoding="utf-8")
    git(repo, "add", "file.txt")
    git(repo, "commit", "-m", "Child commit")
    return git(repo, "rev-parse", "HEAD")


class GitDisciplineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = git_discipline.load_json(PLUGIN_ROOT / "assets/catalog/git-discipline.v1.json")
        cls.role_catalog = git_discipline.load_json(PLUGIN_ROOT / "assets/catalog/platform-role-catalog.v1.json")

    def test_catalog_validates_and_routes(self) -> None:
        self.assertEqual(
            git_discipline.validate_catalog(self.catalog, role_catalog=self.role_catalog),
            [],
        )

    def test_branch_cleanup_issue_mapping_is_required(self) -> None:
        catalog = json.loads(json.dumps(self.catalog))
        catalog["branch_cleanup_policy"]["issue_mapping"].pop(
            "BearsCLOUD/bears_plugin#133"
        )

        errors = git_discipline.validate_catalog(catalog, check_files=False)

        self.assertTrue(
            any("branch_cleanup_policy.issue_mapping" in error for error in errors),
            errors,
        )

    def test_dirty_triage_policy_outcomes_actions_are_required(self) -> None:
        catalog = json.loads(json.dumps(self.catalog))
        catalog["dirty_triage_policy"]["state_machine"]["actions"]["useful_abandoned_code"].remove(
            "block_auto_cherry_pick"
        )

        errors = git_discipline.validate_catalog(catalog, check_files=False)

        self.assertIn(
            "dirty_triage_policy.state_machine.actions.useful_abandoned_code is incomplete",
            errors,
        )

    def test_closeout_preflight_policy_is_required(self) -> None:
        catalog = json.loads(json.dumps(self.catalog))
        catalog["path_safety"].pop("closeout_preflight")

        errors = git_discipline.validate_catalog(catalog, check_files=False)

        self.assertTrue(
            any("path_safety.closeout_preflight" in error for error in errors),
            errors,
        )

    def test_closeout_preflight_command_requires_gitlink_proof_flag(self) -> None:
        catalog = json.loads(json.dumps(self.catalog))
        catalog["path_safety"]["closeout_preflight"]["command"] = (
            "python3 scripts/git_discipline.py closeout-preflight --repo <repo> "
            "--allowed-path <path> --expected-branch-prefix <branch-prefix> --json"
        )

        errors = git_discipline.validate_catalog(catalog, check_files=False)

        self.assertIn(
            "path_safety.closeout_preflight.command must require --gitlink-proof",
            errors,
        )

    def test_canonical_plugin_policy_requires_cwd_mismatch_blocker(self) -> None:
        catalog = json.loads(json.dumps(self.catalog))
        catalog["path_safety"]["canonical_plugin_checkout_policy"]["forbidden_closeout_states"].remove(
            "PLUGIN_CWD_MISMATCH"
        )

        errors = git_discipline.validate_catalog(catalog, check_files=False)

        self.assertIn(
            "path_safety.canonical_plugin_checkout_policy.forbidden_closeout_states is incomplete",
            errors,
        )

    def test_plugin_worktree_preflight_passes_from_canonical_root(self) -> None:
        packet = git_discipline.inspect_plugin_worktree_preflight(
            PLUGIN_ROOT,
            self.catalog,
            cwd=PLUGIN_ROOT,
        )

        self.assertEqual(packet["schema"], "bears-plugin-worktree-preflight.v1")
        self.assertEqual(packet["status"], "PLUGIN_WORKTREE_PASS")
        self.assertTrue(packet["work_allowed"])
        self.assertEqual(packet["canonical_root"], str(PLUGIN_ROOT))
        self.assertEqual(packet["block_reasons"], [])

    def test_plugin_worktree_preflight_blocks_wrong_cwd_and_repo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "not-plugin"
            repo.mkdir()
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.email", "codex-worker@bears.local")
            git(repo, "config", "user.name", "Bears Codex Worker")
            (repo / "file.txt").write_text("ok\n", encoding="utf-8")
            git(repo, "add", "file.txt")
            git(repo, "commit", "-m", "Initial commit")

            packet = git_discipline.inspect_plugin_worktree_preflight(
                repo,
                self.catalog,
                cwd=repo,
            )

        self.assertEqual(packet["status"], "PLUGIN_WORKTREE_BLOCKED")
        self.assertFalse(packet["work_allowed"])
        self.assertIn("PLUGIN_CWD_MISMATCH", packet["block_reasons"])
        self.assertIn("PLUGIN_TOPLEVEL_REDIRECTED", packet["block_reasons"])

    def test_safe_worker_git_identity_rule_is_required(self) -> None:
        catalog = json.loads(json.dumps(self.catalog))
        catalog["command_policy"].pop("safe_worker_git_identity")

        errors = git_discipline.validate_catalog(catalog, check_files=False)

        self.assertIn("command_policy.safe_worker_git_identity must be an object", errors)

    def test_safe_worker_git_identity_blocks_global_mutation_policy(self) -> None:
        catalog = json.loads(json.dumps(self.catalog))
        catalog["command_policy"]["safe_worker_git_identity"]["automatic_global_config_mutation_allowed"] = True
        catalog["command_policy"]["safe_worker_git_identity"]["allowed_config_sources"] = ["local", "global"]
        catalog["command_policy"]["forbidden_automatic_commands"].remove("git config --global")

        errors = git_discipline.validate_catalog(catalog, check_files=False)

        self.assertIn(
            "command_policy.safe_worker_git_identity.automatic_global_config_mutation_allowed must be false",
            errors,
        )
        self.assertIn(
            "command_policy.safe_worker_git_identity.allowed_config_sources must be exactly ['local']",
            errors,
        )
        self.assertIn(
            "command_policy.forbidden_automatic_commands is missing required Git commands",
            errors,
        )

    def test_safe_worker_git_identity_allows_commit_authority(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.email", "codex-worker@bears.local")
            git(repo, "config", "user.name", "Bears Codex Worker")
            (repo / "file.txt").write_text("ok\n", encoding="utf-8")
            git(repo, "add", "file.txt")
            git(repo, "commit", "-m", "Initial commit")
            (repo / "file.txt").write_text("changed\n", encoding="utf-8")

            packet = git_discipline.inspect_repo(repo, self.catalog)

        self.assertEqual(packet["status"], "GIT_DISCIPLINE_READY")
        self.assertTrue(packet["worker_git_identity_configured"])
        self.assertEqual(packet["worker_git_identity_label"], "Bears Codex Worker <codex-worker@bears.local>")
        self.assertTrue(packet["commit_allowed_after_validation"])

    def test_missing_worker_git_identity_fails_closed_before_commit_authority(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.email", "codex-worker@bears.local")
            git(repo, "config", "user.name", "Bears Codex Worker")
            (repo / "file.txt").write_text("ok\n", encoding="utf-8")
            git(repo, "add", "file.txt")
            git(repo, "commit", "-m", "Initial commit")
            git(repo, "config", "--unset", "user.email")
            git(repo, "config", "--unset", "user.name")
            (repo / "file.txt").write_text("changed\n", encoding="utf-8")

            packet = git_discipline.inspect_repo(repo, self.catalog)

        self.assertEqual(packet["status"], "GIT_DISCIPLINE_BLOCKED")
        self.assertFalse(packet["worker_git_identity_configured"])
        self.assertEqual(packet["worker_git_identity_label"], "Bears Codex Worker <codex-worker@bears.local>")
        self.assertFalse(packet["commit_allowed_after_validation"])
        self.assertFalse(packet["push_allowed"])

    def test_unsafe_worker_git_identity_fails_closed_before_commit_authority(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.email", "codex-worker@bears.local")
            git(repo, "config", "user.name", "Bears Codex Worker")
            (repo / "file.txt").write_text("ok\n", encoding="utf-8")
            git(repo, "add", "file.txt")
            git(repo, "commit", "-m", "Initial commit")
            git(repo, "config", "user.email", "unsafe@example.invalid")
            git(repo, "config", "user.name", "Unsafe User")
            (repo / "file.txt").write_text("changed\n", encoding="utf-8")

            packet = git_discipline.inspect_repo(repo, self.catalog)

        self.assertEqual(packet["status"], "GIT_DISCIPLINE_BLOCKED")
        self.assertFalse(packet["worker_git_identity_configured"])
        self.assertFalse(packet["commit_allowed_after_validation"])

    def test_cli_validate(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "validate"],
            cwd=PLUGIN_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("git discipline catalog ok", result.stdout)

    def test_inspect_clean_repo_reports_no_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.email", "codex-worker@bears.local")
            git(repo, "config", "user.name", "Bears Codex Worker")
            (repo / "file.txt").write_text("ok\n", encoding="utf-8")
            git(repo, "add", "file.txt")
            git(repo, "commit", "-m", "Initial commit")

            packet = git_discipline.inspect_repo(repo, self.catalog, require_changes=True)

        self.assertEqual(packet["schema"], "bears-git-discipline-inspection.v1")
        self.assertEqual(packet["status"], "GIT_DISCIPLINE_NO_CHANGES")
        self.assertFalse(packet["worktree_dirty"])
        self.assertTrue(packet["diff_check_passed"])
        self.assertFalse(packet["push_allowed"])

    def test_inspect_allowed_paths_blocks_unrelated_dirty_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.email", "codex-worker@bears.local")
            git(repo, "config", "user.name", "Bears Codex Worker")
            (repo / "allowed").mkdir()
            (repo / "allowed" / "file.txt").write_text("ok\n", encoding="utf-8")
            (repo / "unrelated.txt").write_text("old\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "Initial commit")
            (repo / "allowed" / "file.txt").write_text("changed\n", encoding="utf-8")
            (repo / "unrelated.txt").write_text("dirty\n", encoding="utf-8")

            packet = git_discipline.inspect_repo(
                repo,
                self.catalog,
                allowed_paths=["allowed"],
            )

        self.assertEqual(packet["status"], "DIRTY_WORKTREE_BLOCKER")
        self.assertEqual(packet["allowed_changed_paths"], ["allowed"])
        self.assertEqual(packet["disallowed_changed_paths"], ["unrelated.txt"])
        self.assertFalse(packet["commit_allowed_after_validation"])

    def test_inspect_allowed_paths_accepts_exact_assignment_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.email", "codex-worker@bears.local")
            git(repo, "config", "user.name", "Bears Codex Worker")
            (repo / "plans.md").write_text("old\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "Initial commit")
            (repo / "plans.md").write_text("new\n", encoding="utf-8")

            packet = git_discipline.inspect_repo(
                repo,
                self.catalog,
                allowed_paths=["plans.md"],
            )

        self.assertEqual(packet["status"], "GIT_DISCIPLINE_READY")
        self.assertEqual(packet["allowed_changed_paths"], ["plans.md"])
        self.assertEqual(packet["disallowed_changed_paths"], [])
        self.assertTrue(packet["commit_allowed_after_validation"])

    def test_inspect_dirty_repo_ready_when_no_sensitive_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.email", "codex-worker@bears.local")
            git(repo, "config", "user.name", "Bears Codex Worker")
            (repo / "file.txt").write_text("ok\n", encoding="utf-8")
            git(repo, "add", "file.txt")
            git(repo, "commit", "-m", "Initial commit")
            (repo / "file.txt").write_text("changed\n", encoding="utf-8")
            (repo / "new.txt").write_text("new\n", encoding="utf-8")

            packet = git_discipline.inspect_repo(repo, self.catalog)

        self.assertEqual(packet["status"], "GIT_DISCIPLINE_READY")
        self.assertTrue(packet["worktree_dirty"])
        self.assertEqual(packet["untracked_count"], 1)
        self.assertTrue(packet["commit_allowed_after_validation"])

    def test_closeout_preflight_blocks_unrelated_dirty_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.email", "codex-worker@bears.local")
            git(repo, "config", "user.name", "Bears Codex Worker")
            (repo / "specs").mkdir()
            (repo / "plans.md").write_text("old\n", encoding="utf-8")
            (repo / "specs" / "tasks.md").write_text("old\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "Initial commit")
            git(repo, "switch", "-c", "codex/closeout-ledger")
            (repo / "specs" / "tasks.md").write_text("new\n", encoding="utf-8")
            (repo / "plans.md").write_text("unrelated\n", encoding="utf-8")

            packet = git_discipline.inspect_closeout_preflight(
                repo,
                self.catalog,
                allowed_paths=["specs/tasks.md"],
                expected_branch_prefix="codex/closeout-",
            )

        self.assertEqual(packet["schema"], "bears-git-closeout-preflight.v1")
        self.assertEqual(packet["status"], "DIRTY_WORKTREE_BLOCKER")
        self.assertIn("plans.md", packet["disallowed_changed_paths"])
        self.assertFalse(packet["closeout_allowed"])
        self.assertFalse(packet["commit_allowed_after_validation"])

    def test_closeout_preflight_requires_allowed_paths_and_task_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.email", "codex-worker@bears.local")
            git(repo, "config", "user.name", "Bears Codex Worker")
            (repo / "tasks.md").write_text("old\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "Initial commit")
            (repo / "tasks.md").write_text("new\n", encoding="utf-8")

            packet = git_discipline.inspect_closeout_preflight(
                repo,
                self.catalog,
                allowed_paths=[],
            )

        self.assertEqual(packet["status"], "CLOSEOUT_PREFLIGHT_BLOCKED")
        self.assertIn("allowed_paths_required", packet["block_reasons"])
        self.assertIn("expected_branch_or_prefix_required", packet["block_reasons"])

    def test_closeout_preflight_blocks_unrelated_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.email", "codex-worker@bears.local")
            git(repo, "config", "user.name", "Bears Codex Worker")
            (repo / "tasks.md").write_text("old\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "Initial commit")
            git(repo, "switch", "-c", "codex/unrelated-task")
            (repo / "tasks.md").write_text("new\n", encoding="utf-8")

            packet = git_discipline.inspect_closeout_preflight(
                repo,
                self.catalog,
                allowed_paths=["tasks.md"],
                expected_branch_prefix="codex/closeout-",
            )

        self.assertEqual(packet["status"], "CLOSEOUT_PREFLIGHT_BLOCKED")
        self.assertIn("current_branch_prefix_mismatch", packet["block_reasons"])
        self.assertFalse(packet["closeout_allowed"])

    def test_closeout_preflight_accepts_gitlink_proof(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            child_one = root / "child-one"
            child_two = root / "child-two"
            old_object = make_child_commit(child_one, "old\n")
            target_object = make_child_commit(child_two, "new\n")
            repo.mkdir()
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.email", "codex-worker@bears.local")
            git(repo, "config", "user.name", "Bears Codex Worker")
            git(repo, "update-index", "--add", "--cacheinfo", f"160000,{old_object},kubernetes")
            git(repo, "commit", "-m", "Initial commit")
            git(repo, "switch", "-c", "codex/closeout-gitlink")
            git(repo, "update-index", "--cacheinfo", f"160000,{target_object},kubernetes")

            packet = git_discipline.inspect_closeout_preflight(
                repo,
                self.catalog,
                allowed_paths=["kubernetes"],
                expected_branch_prefix="codex/closeout-",
                gitlink_proofs=[
                    {
                        "path": "kubernetes",
                        "old_object": old_object,
                        "target_object": target_object,
                        "source_pr_merge_commit": "3333333333333333333333333333333333333333",
                    }
                ],
            )

        self.assertEqual(packet["status"], "CLOSEOUT_PREFLIGHT_PASS")
        self.assertTrue(packet["closeout_allowed"])
        self.assertEqual(packet["gitlink_proofs"][0]["path"], "kubernetes")

    def test_closeout_preflight_cli_accepts_gitlink_proof_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            child_one = root / "child-one"
            child_two = root / "child-two"
            old_object = make_child_commit(child_one, "old\n")
            target_object = make_child_commit(child_two, "new\n")
            source_pr_merge_commit = "3333333333333333333333333333333333333333"
            repo.mkdir()
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.email", "codex-worker@bears.local")
            git(repo, "config", "user.name", "Bears Codex Worker")
            git(repo, "update-index", "--add", "--cacheinfo", f"160000,{old_object},kubernetes")
            git(repo, "commit", "-m", "Initial commit")
            git(repo, "switch", "-c", "codex/closeout-gitlink")
            git(repo, "update-index", "--cacheinfo", f"160000,{target_object},kubernetes")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "closeout-preflight",
                    "--repo",
                    str(repo),
                    "--allowed-path",
                    "kubernetes",
                    "--expected-branch-prefix",
                    "codex/closeout-",
                    "--gitlink-proof",
                    f"kubernetes:{old_object}:{target_object}:{source_pr_merge_commit}",
                    "--json",
                ],
                cwd=PLUGIN_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        packet = json.loads(result.stdout)
        self.assertEqual(packet["schema"], "bears-git-closeout-preflight.v1")
        self.assertEqual(packet["status"], "CLOSEOUT_PREFLIGHT_PASS")
        self.assertTrue(packet["closeout_allowed"])
        self.assertEqual(packet["gitlink_proofs"][0]["path"], "kubernetes")

    def test_closeout_preflight_requires_gitlink_proof_for_changed_gitlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            child_one = root / "child-one"
            child_two = root / "child-two"
            old_object = make_child_commit(child_one, "old\n")
            target_object = make_child_commit(child_two, "new\n")
            repo.mkdir()
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.email", "codex-worker@bears.local")
            git(repo, "config", "user.name", "Bears Codex Worker")
            git(repo, "update-index", "--add", "--cacheinfo", f"160000,{old_object},kubernetes")
            git(repo, "commit", "-m", "Initial commit")
            git(repo, "switch", "-c", "codex/closeout-gitlink")
            git(repo, "update-index", "--cacheinfo", f"160000,{target_object},kubernetes")

            packet = git_discipline.inspect_closeout_preflight(
                repo,
                self.catalog,
                allowed_paths=["kubernetes"],
                expected_branch_prefix="codex/closeout-",
            )

        self.assertEqual(packet["status"], "CLOSEOUT_PREFLIGHT_BLOCKED")
        self.assertIn("kubernetes", packet["changed_gitlink_paths"])
        self.assertIn("gitlink_proof_required:kubernetes", packet["block_reasons"])
        self.assertFalse(packet["closeout_allowed"])

    def test_closeout_preflight_rejects_incomplete_gitlink_proof(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            child_one = root / "child-one"
            child_two = root / "child-two"
            old_object = make_child_commit(child_one, "old\n")
            target_object = make_child_commit(child_two, "new\n")
            repo.mkdir()
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.email", "codex-worker@bears.local")
            git(repo, "config", "user.name", "Bears Codex Worker")
            git(repo, "update-index", "--add", "--cacheinfo", f"160000,{old_object},kubernetes")
            git(repo, "commit", "-m", "Initial commit")
            git(repo, "switch", "-c", "codex/closeout-gitlink")
            git(repo, "update-index", "--cacheinfo", f"160000,{target_object},kubernetes")

            packet = git_discipline.inspect_closeout_preflight(
                repo,
                self.catalog,
                allowed_paths=["kubernetes"],
                expected_branch_prefix="codex/closeout-",
                gitlink_proofs=[
                    {
                        "path": "kubernetes",
                        "old_object": "1111111",
                        "target_object": target_object,
                        "source_pr_merge_commit": "3333333333333333333333333333333333333333",
                    }
                ],
            )

        self.assertEqual(packet["status"], "CLOSEOUT_PREFLIGHT_BLOCKED")
        self.assertIn(
            "gitlink_proof_old_object_must_be_full_object:kubernetes",
            packet["block_reasons"],
        )

    def test_closeout_preflight_rejects_mismatched_gitlink_old_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            child_one = root / "child-one"
            child_two = root / "child-two"
            old_object = make_child_commit(child_one, "old\n")
            target_object = make_child_commit(child_two, "new\n")
            repo.mkdir()
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.email", "codex-worker@bears.local")
            git(repo, "config", "user.name", "Bears Codex Worker")
            git(repo, "update-index", "--add", "--cacheinfo", f"160000,{old_object},kubernetes")
            git(repo, "commit", "-m", "Initial commit")
            git(repo, "switch", "-c", "codex/closeout-gitlink")
            git(repo, "update-index", "--cacheinfo", f"160000,{target_object},kubernetes")

            packet = git_discipline.inspect_closeout_preflight(
                repo,
                self.catalog,
                allowed_paths=["kubernetes"],
                expected_branch_prefix="codex/closeout-",
                gitlink_proofs=[
                    {
                        "path": "kubernetes",
                        "old_object": "4444444444444444444444444444444444444444",
                        "target_object": target_object,
                        "source_pr_merge_commit": "3333333333333333333333333333333333333333",
                    }
                ],
            )

        self.assertEqual(packet["status"], "CLOSEOUT_PREFLIGHT_BLOCKED")
        self.assertIn("gitlink_proof_old_object_mismatch:kubernetes", packet["block_reasons"])

    def test_closeout_preflight_rejects_mismatched_gitlink_target_object(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            child_one = root / "child-one"
            child_two = root / "child-two"
            old_object = make_child_commit(child_one, "old\n")
            target_object = make_child_commit(child_two, "new\n")
            repo.mkdir()
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.email", "codex-worker@bears.local")
            git(repo, "config", "user.name", "Bears Codex Worker")
            git(repo, "update-index", "--add", "--cacheinfo", f"160000,{old_object},kubernetes")
            git(repo, "commit", "-m", "Initial commit")
            git(repo, "switch", "-c", "codex/closeout-gitlink")
            git(repo, "update-index", "--cacheinfo", f"160000,{target_object},kubernetes")

            packet = git_discipline.inspect_closeout_preflight(
                repo,
                self.catalog,
                allowed_paths=["kubernetes"],
                expected_branch_prefix="codex/closeout-",
                gitlink_proofs=[
                    {
                        "path": "kubernetes",
                        "old_object": old_object,
                        "target_object": "5555555555555555555555555555555555555555",
                        "source_pr_merge_commit": "3333333333333333333333333333333333333333",
                    }
                ],
            )

        self.assertEqual(packet["status"], "CLOSEOUT_PREFLIGHT_BLOCKED")
        self.assertIn("gitlink_proof_target_object_mismatch:kubernetes", packet["block_reasons"])

    def test_secret_factory_governance_paths_are_not_value_bearing_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.email", "codex-worker@bears.local")
            git(repo, "config", "user.name", "Bears Codex Worker")
            (repo / "file.txt").write_text("ok\n", encoding="utf-8")
            git(repo, "add", "file.txt")
            git(repo, "commit", "-m", "Initial commit")
            target = repo / "assets" / "catalog" / "secret-factory.v1.json"
            target.parent.mkdir(parents=True)
            target.write_text("{}\n", encoding="utf-8")

            packet = git_discipline.inspect_repo(repo, self.catalog)

        self.assertEqual(packet["status"], "GIT_DISCIPLINE_READY")
        self.assertEqual(packet["secret_like_paths"], [])
        self.assertFalse(packet["operator_review_required"])

    def test_all_secret_path_exception_roots_allow_their_exact_paths(self) -> None:
        roots = self.catalog["path_safety"]["secret_path_exception_roots"]
        for root in roots:
            with self.subTest(root=root):
                with tempfile.TemporaryDirectory() as tmp:
                    repo = Path(tmp)
                    git(repo, "init", "-b", "main")
                    git(repo, "config", "user.email", "codex-worker@bears.local")
                    git(repo, "config", "user.name", "Bears Codex Worker")
                    (repo / "file.txt").write_text("ok\n", encoding="utf-8")
                    git(repo, "add", "file.txt")
                    git(repo, "commit", "-m", "Initial commit")

                    root_path = repo / root
                    root_path.parent.mkdir(parents=True, exist_ok=True)
                    root_path.write_text("allowed\n", encoding="utf-8")

                    allowed_packet = git_discipline.inspect_repo(repo, self.catalog)
                    self.assertEqual(allowed_packet["status"], "GIT_DISCIPLINE_READY")
                    self.assertEqual(allowed_packet["secret_like_paths"], [])
                    self.assertFalse(allowed_packet["operator_review_required"])

    def test_all_secret_path_exception_roots_do_not_allow_sibling_secret_like_paths(self) -> None:
        roots = self.catalog["path_safety"]["secret_path_exception_roots"]
        for root in roots:
            with self.subTest(root=root):
                with tempfile.TemporaryDirectory() as tmp:
                    repo = Path(tmp)
                    git(repo, "init", "-b", "main")
                    git(repo, "config", "user.email", "codex-worker@bears.local")
                    git(repo, "config", "user.name", "Bears Codex Worker")
                    (repo / "file.txt").write_text("ok\n", encoding="utf-8")
                    git(repo, "add", "file.txt")
                    git(repo, "commit", "-m", "Initial commit")

                    root_path = repo / root
                    root_path.parent.mkdir(parents=True, exist_ok=True)
                    root_path.write_text("allowed\n", encoding="utf-8")

                    blocked_path = root_path.with_name(f"{root_path.name}.notes")
                    blocked_path.write_text("blocked\n", encoding="utf-8")
                    blocked_packet = git_discipline.inspect_repo(repo, self.catalog)

                    self.assertEqual(blocked_packet["status"], "GIT_DISCIPLINE_REQUIRES_OPERATOR_REVIEW")
                    self.assertTrue(blocked_packet["operator_review_required"])
                    self.assertIn(str(blocked_path.relative_to(repo)), blocked_packet["secret_like_paths"])

    def test_secret_factory_skill_exception_is_exact_path_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.email", "codex-worker@bears.local")
            git(repo, "config", "user.name", "Bears Codex Worker")
            (repo / "file.txt").write_text("ok\n", encoding="utf-8")
            git(repo, "add", "file.txt")
            git(repo, "commit", "-m", "Initial commit")
            skill = repo / "skills" / "secret-factory" / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("# Skill\n", encoding="utf-8")

            allowed_packet = git_discipline.inspect_repo(repo, self.catalog)

            nested = repo / "skills" / "secret-factory" / "notes.txt"
            nested.write_text("governance note\n", encoding="utf-8")
            blocked_packet = git_discipline.inspect_repo(repo, self.catalog)

        self.assertEqual(allowed_packet["status"], "GIT_DISCIPLINE_READY")
        self.assertEqual(allowed_packet["secret_like_paths"], [])
        self.assertEqual(blocked_packet["status"], "GIT_DISCIPLINE_REQUIRES_OPERATOR_REVIEW")
        self.assertIn("skills/secret-factory/notes.txt", blocked_packet["secret_like_paths"])

    def test_sensitive_path_requires_operator_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.email", "codex-worker@bears.local")
            git(repo, "config", "user.name", "Bears Codex Worker")
            (repo / "file.txt").write_text("ok\n", encoding="utf-8")
            git(repo, "add", "file.txt")
            git(repo, "commit", "-m", "Initial commit")
            (repo / ".env").write_text("x=y\n", encoding="utf-8")

            packet = git_discipline.inspect_repo(repo, self.catalog)

        self.assertEqual(packet["status"], "GIT_DISCIPLINE_REQUIRES_OPERATOR_REVIEW")
        self.assertTrue(packet["operator_review_required"])
        self.assertFalse(packet["commit_allowed_after_validation"])
        self.assertIn(".env", packet["secret_like_paths"])

    def test_cli_inspect_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.email", "codex-worker@bears.local")
            git(repo, "config", "user.name", "Bears Codex Worker")
            (repo / "file.txt").write_text("ok\n", encoding="utf-8")
            git(repo, "add", "file.txt")
            git(repo, "commit", "-m", "Initial commit")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "inspect",
                    "--repo",
                    str(repo),
                    "--json",
                    "--require-changes",
                ],
                cwd=PLUGIN_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        packet = json.loads(result.stdout)
        self.assertEqual(packet["schema"], "bears-git-discipline-inspection.v1")
        self.assertEqual(packet["repo_root"], str(repo))
        self.assertEqual(packet["status"], "GIT_DISCIPLINE_NO_CHANGES")
        self.assertFalse(packet["operator_review_required"])
        self.assertFalse(packet["commit_allowed_after_validation"])
        self.assertFalse(packet["push_allowed"])

    def test_branch_inventory_classifies_github_squash_merged_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.email", "codex-worker@bears.local")
            git(repo, "config", "user.name", "Bears Codex Worker")
            (repo / "file.txt").write_text("ok\n", encoding="utf-8")
            git(repo, "add", "file.txt")
            git(repo, "commit", "-m", "Initial commit")
            git(repo, "switch", "-c", "codex/squash-merged")
            (repo / "feature.txt").write_text("feature\n", encoding="utf-8")
            git(repo, "add", "feature.txt")
            git(repo, "commit", "-m", "Feature commit")
            git(repo, "switch", "main")
            prs_path = repo / "prs.json"
            prs_path.write_text(json.dumps([{"number": 123, "headRefName": "codex/squash-merged", "state": "MERGED", "mergedAt": "2026-06-18T00:00:00Z"}]), encoding="utf-8")
            packet = git_discipline.inspect_branch_inventory(repo, self.catalog, base_ref="main", github_prs_json=prs_path)
            workflow_state = repo / "workflow-state.json"
            workflow_state.write_text(
                json.dumps(
                    {
                        "branches": {
                            "codex/squash-merged": {
                                "owner": "bears-platform-role-governor",
                                "cleanup_plan_proof": True,
                                "worker_state": "completed",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            not_ready_packet = git_discipline.inspect_branch_inventory(
                repo,
                self.catalog,
                base_ref="main",
                github_prs_json=prs_path,
                workflow_state_json=workflow_state,
            )
            workflow_state.write_text(
                json.dumps(
                    {
                        "branches": {
                            "codex/squash-merged": {
                                "owner": "bears-platform-role-governor",
                                "cleanup_plan_proof": True,
                                "cleanup_phase": "closeout",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            eligible_packet = git_discipline.inspect_branch_inventory(
                repo,
                self.catalog,
                base_ref="main",
                github_prs_json=prs_path,
                workflow_state_json=workflow_state,
            )
        branch = next(item for item in packet["branches"] if item["branch"] == "codex/squash-merged")
        self.assertFalse(branch["merged_into_base_by_ancestry"])
        self.assertEqual(branch["github_pr_numbers"], [123])
        self.assertEqual(branch["cleanup_class"], "github_merged_cleanup_candidate")
        self.assertFalse(branch["local_delete_eligible"])
        self.assertEqual(branch["dirty_triage_outcome"], "unsafe_dirty_blocker")
        self.assertIn("unknown_ownership", branch["dirty_triage_proofs"])
        not_ready_branch = next(item for item in not_ready_packet["branches"] if item["branch"] == "codex/squash-merged")
        self.assertFalse(not_ready_branch["local_delete_eligible"])
        self.assertEqual(not_ready_branch["dirty_triage_outcome"], "completed_needs_integration")
        eligible_branch = next(item for item in eligible_packet["branches"] if item["branch"] == "codex/squash-merged")
        self.assertTrue(eligible_branch["local_delete_eligible"])
        self.assertEqual(eligible_branch["dirty_triage_outcome"], "obsolete_cleanup_candidate")
        self.assertTrue(eligible_branch["cleanup_plan_proof"])

    def test_dirty_triage_protects_pr_363_open_draft_as_active_work(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.email", "codex-worker@bears.local")
            git(repo, "config", "user.name", "Bears Codex Worker")
            (repo / "file.txt").write_text("ok\n", encoding="utf-8")
            git(repo, "add", "file.txt")
            git(repo, "commit", "-m", "Initial commit")
            git(repo, "switch", "-c", "codex/pr-363-dirty-triage")
            (repo / "draft.txt").write_text("draft\n", encoding="utf-8")
            git(repo, "add", "draft.txt")
            git(repo, "commit", "-m", "Draft work")
            git(repo, "switch", "main")
            prs_path = repo / "prs.json"
            prs_path.write_text(
                json.dumps(
                    [
                        {
                            "number": 363,
                            "headRefName": "codex/pr-363-dirty-triage",
                            "state": "OPEN",
                            "isDraft": True,
                        }
                    ]
                ),
                encoding="utf-8",
            )

            packet = git_discipline.inspect_branch_inventory(
                repo,
                self.catalog,
                base_ref="main",
                github_prs_json=prs_path,
            )

        branch = next(item for item in packet["branches"] if item["branch"] == "codex/pr-363-dirty-triage")
        self.assertEqual(branch["cleanup_class"], "open_pr_review_required")
        self.assertEqual(branch["dirty_triage_outcome"], "active_parallel_agent")
        self.assertIn("open_pr", branch["dirty_triage_proofs"])
        self.assertFalse(branch["local_delete_eligible"])
        self.assertFalse(branch["auto_delete_allowed"])

    def test_dirty_triage_accepts_per_worker_state_active_proofs(self) -> None:
        proof_states = {
            "heartbeat": {"heartbeat": {"fresh": True}},
            "scope_lock": {"scope_lock": {"active": True}},
            "open_pr": {"pr": {"state": "OPEN", "number": 363}},
        }
        for proof, worker_payload in proof_states.items():
            with self.subTest(proof=proof):
                with tempfile.TemporaryDirectory() as tmp:
                    repo = Path(tmp)
                    git(repo, "init", "-b", "main")
                    git(repo, "config", "user.email", "codex-worker@bears.local")
                    git(repo, "config", "user.name", "Bears Codex Worker")
                    (repo / "file.txt").write_text("ok\n", encoding="utf-8")
                    git(repo, "add", "file.txt")
                    git(repo, "commit", "-m", "Initial commit")
                    branch_name = f"codex/worker-state-{proof}"
                    git(repo, "switch", "-c", branch_name)
                    (repo / f"{proof}.txt").write_text("active\n", encoding="utf-8")
                    git(repo, "add", f"{proof}.txt")
                    git(repo, "commit", "-m", "Active worker state")
                    git(repo, "switch", "main")
                    worker_state = repo / f"{proof}-worker-state.json"
                    payload = {
                        "branch": branch_name,
                        "worker_id": f"worker-{proof}",
                        "worker_state": "active",
                        **worker_payload,
                    }
                    worker_state.write_text(json.dumps(payload), encoding="utf-8")

                    packet = git_discipline.inspect_branch_inventory(
                        repo,
                        self.catalog,
                        base_ref="main",
                        worker_state_json=[worker_state],
                    )

                branch = next(item for item in packet["branches"] if item["branch"] == branch_name)
                self.assertEqual(branch["dirty_triage_outcome"], "active_parallel_agent")
                self.assertIn(proof, branch["dirty_triage_proofs"])
                self.assertFalse(branch["local_delete_eligible"])
                self.assertFalse(branch["auto_delete_allowed"])

    def test_dirty_triage_useful_abandoned_code_requires_assignment_no_cherry_pick(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.email", "codex-worker@bears.local")
            git(repo, "config", "user.name", "Bears Codex Worker")
            (repo / "file.txt").write_text("ok\n", encoding="utf-8")
            git(repo, "add", "file.txt")
            git(repo, "commit", "-m", "Initial commit")
            git(repo, "switch", "-c", "codex/useful-abandoned")
            (repo / "useful.txt").write_text("useful\n", encoding="utf-8")
            git(repo, "add", "useful.txt")
            git(repo, "commit", "-m", "Useful abandoned work")
            git(repo, "switch", "main")
            workflow_state = repo / "workflow-state.json"
            workflow_state.write_text(
                json.dumps(
                    {
                        "branches": {
                            "codex/useful-abandoned": {
                                "owner": "bears-platform-role-governor",
                                "worker_state": "abandoned",
                                "useful_abandoned_code": True,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            packet = git_discipline.inspect_branch_inventory(
                repo,
                self.catalog,
                base_ref="main",
                workflow_state_json=workflow_state,
            )

        branch = next(item for item in packet["branches"] if item["branch"] == "codex/useful-abandoned")
        self.assertEqual(branch["dirty_triage_outcome"], "useful_abandoned_code")
        self.assertIn("create_narrow_integration_assignment", branch["dirty_triage_actions"])
        self.assertIn("block_auto_cherry_pick", branch["dirty_triage_actions"])
        self.assertFalse(branch["local_delete_eligible"])
        self.assertFalse(branch["auto_delete_allowed"])

    def test_branch_inventory_blocks_backup_dirty_branch_delete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.email", "codex-worker@bears.local")
            git(repo, "config", "user.name", "Bears Codex Worker")
            (repo / "file.txt").write_text("ok\n", encoding="utf-8")
            git(repo, "add", "file.txt")
            git(repo, "commit", "-m", "Initial commit")
            git(repo, "branch", "backup/dirty-preserve")
            packet = git_discipline.inspect_branch_inventory(repo, self.catalog, base_ref="main")
        branch = next(item for item in packet["branches"] if item["branch"] == "backup/dirty-preserve")
        self.assertEqual(branch["cleanup_class"], "backup_dirty_preserve")
        self.assertFalse(branch["local_delete_eligible"])

    def test_branch_inventory_cli_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.email", "codex-worker@bears.local")
            git(repo, "config", "user.name", "Bears Codex Worker")
            (repo / "file.txt").write_text("ok\n", encoding="utf-8")
            git(repo, "add", "file.txt")
            git(repo, "commit", "-m", "Initial commit")
            result = subprocess.run([sys.executable, str(SCRIPT_PATH), "branch-inventory", "--repo", str(repo), "--base", "main", "--json"], cwd=PLUGIN_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        packet = json.loads(result.stdout)
        self.assertEqual(packet["schema"], "bears-git-branch-inventory.v1")
        self.assertTrue(packet["read_only"])

    def test_branch_inventory_classifies_remote_github_merged_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.email", "codex-worker@bears.local")
            git(repo, "config", "user.name", "Bears Codex Worker")
            (repo / "file.txt").write_text("ok\n", encoding="utf-8")
            git(repo, "add", "file.txt")
            git(repo, "commit", "-m", "Initial commit")
            git(repo, "switch", "-c", "codex/remote-merged")
            (repo / "remote.txt").write_text("remote\n", encoding="utf-8")
            git(repo, "add", "remote.txt")
            git(repo, "commit", "-m", "Remote commit")
            remote_head = git(repo, "rev-parse", "HEAD")
            git(repo, "switch", "main")
            git(repo, "branch", "-D", "codex/remote-merged")
            git(repo, "update-ref", "refs/remotes/origin/codex/remote-merged", remote_head)
            prs_path = repo / "prs.json"
            prs_path.write_text(
                json.dumps(
                    [
                        {
                            "number": 456,
                            "headRefName": "codex/remote-merged",
                            "state": "MERGED",
                            "mergedAt": "2026-06-18T00:00:00Z",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            packet = git_discipline.inspect_branch_inventory(
                repo,
                self.catalog,
                base_ref="main",
                github_prs_json=prs_path,
            )
            workflow_state = repo / "workflow-state.json"
            workflow_state.write_text(
                json.dumps(
                    {
                        "branches": {
                            "codex/remote-merged": {
                                "owner": "bears-platform-role-governor",
                                "cleanup_plan_proof": True,
                                "cleanup_phase": "merge_ready",
                                "cleanup_authority": {"remote_delete": True},
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            authorized_packet = git_discipline.inspect_branch_inventory(
                repo,
                self.catalog,
                base_ref="main",
                github_prs_json=prs_path,
                workflow_state_json=workflow_state,
            )

        branch = next(
            item
            for item in packet["remote_branches"]
            if item["branch"] == "codex/remote-merged"
        )
        self.assertEqual(packet["remote_branch_count"], 1)
        self.assertFalse(branch["local_branch_exists"])
        self.assertEqual(branch["github_pr_numbers"], [456])
        self.assertEqual(branch["cleanup_class"], "remote_github_merged_cleanup_candidate")
        self.assertFalse(branch["remote_delete_eligible"])
        self.assertIn("remote_cleanup_authority_missing", branch["dirty_triage_proofs"])
        authorized_branch = next(
            item
            for item in authorized_packet["remote_branches"]
            if item["branch"] == "codex/remote-merged"
        )
        self.assertTrue(authorized_branch["remote_delete_eligible"])
        self.assertEqual(authorized_branch["dirty_triage_outcome"], "obsolete_cleanup_candidate")
        self.assertTrue(authorized_branch["cleanup_authority"]["remote_delete"])

    def test_branch_inventory_skips_origin_head_symbolic_ref(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.email", "codex-worker@bears.local")
            git(repo, "config", "user.name", "Bears Codex Worker")
            (repo / "file.txt").write_text("ok\n", encoding="utf-8")
            git(repo, "add", "file.txt")
            git(repo, "commit", "-m", "Initial commit")
            main_head = git(repo, "rev-parse", "HEAD")
            git(repo, "update-ref", "refs/remotes/origin/main", main_head)
            git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")

            packet = git_discipline.inspect_branch_inventory(repo, self.catalog, base_ref="main")

        self.assertEqual(
            [item["branch"] for item in packet["remote_branches"]],
            ["main"],
        )
        self.assertNotIn("origin", [item["branch"] for item in packet["remote_branches"]])

    def test_branch_closeout_gate_blocks_merged_local_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.email", "codex-worker@bears.local")
            git(repo, "config", "user.name", "Bears Codex Worker")
            (repo / "file.txt").write_text("ok\n", encoding="utf-8")
            git(repo, "add", "file.txt")
            git(repo, "commit", "-m", "Initial commit")
            git(repo, "switch", "-c", "codex/merged-leftover")
            (repo / "leftover.txt").write_text("leftover\n", encoding="utf-8")
            git(repo, "add", "leftover.txt")
            git(repo, "commit", "-m", "Leftover branch")
            git(repo, "switch", "main")
            prs_path = repo / "prs.json"
            prs_path.write_text(
                json.dumps(
                    [
                        {
                            "number": 789,
                            "headRefName": "codex/merged-leftover",
                            "state": "MERGED",
                            "mergedAt": "2026-06-18T00:00:00Z",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            workflow_state = repo / "workflow-state.json"
            workflow_state.write_text(
                json.dumps(
                    {
                        "branches": {
                            "codex/merged-leftover": {
                                "owner": "bears-platform-role-governor",
                                "cleanup_plan_proof": True,
                                "cleanup_phase": "closeout",
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            packet = git_discipline.inspect_branch_closeout_gate(
                repo,
                self.catalog,
                base_ref="main",
                github_prs_json=prs_path,
                workflow_state_json=workflow_state,
            )

        self.assertEqual(packet["schema"], "bears-git-branch-closeout-gate.v1")
        self.assertEqual(packet["status"], "BRANCH_CLOSEOUT_REQUIRED")
        self.assertEqual(packet["local_delete_eligible_count"], 1)
        self.assertEqual(
            packet["local_delete_eligible_branches"][0]["branch"],
            "codex/merged-leftover",
        )

    def test_branch_closeout_gate_blocks_merged_worktree_attached_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "repo"
            linked = root / "linked"
            repo.mkdir()
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.email", "codex-worker@bears.local")
            git(repo, "config", "user.name", "Bears Codex Worker")
            (repo / "file.txt").write_text("ok\n", encoding="utf-8")
            git(repo, "add", "file.txt")
            git(repo, "commit", "-m", "Initial commit")
            git(repo, "branch", "codex/worktree-leftover")
            git(repo, "worktree", "add", str(linked), "codex/worktree-leftover")
            prs_path = repo / "prs.json"
            prs_path.write_text(
                json.dumps(
                    [
                        {
                            "number": 790,
                            "headRefName": "codex/worktree-leftover",
                            "state": "MERGED",
                            "mergedAt": "2026-06-18T00:00:00Z",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            packet = git_discipline.inspect_branch_closeout_gate(
                repo,
                self.catalog,
                base_ref="main",
                github_prs_json=prs_path,
            )

        self.assertEqual(packet["status"], "BRANCH_CLOSEOUT_REQUIRED")
        self.assertEqual(packet["local_delete_eligible_count"], 0)
        self.assertEqual(packet["merged_worktree_attached_count"], 1)
        self.assertEqual(
            packet["merged_worktree_attached_branches"][0]["branch"],
            "codex/worktree-leftover",
        )

    def test_branch_closeout_gate_passes_when_only_main_remains(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.email", "codex-worker@bears.local")
            git(repo, "config", "user.name", "Bears Codex Worker")
            (repo / "file.txt").write_text("ok\n", encoding="utf-8")
            git(repo, "add", "file.txt")
            git(repo, "commit", "-m", "Initial commit")

            packet = git_discipline.inspect_branch_closeout_gate(
                repo,
                self.catalog,
                base_ref="main",
            )

        self.assertEqual(packet["status"], "BRANCH_CLOSEOUT_READY")
        self.assertEqual(packet["local_delete_eligible_count"], 0)
        self.assertEqual(packet["remote_delete_eligible_count"], 0)
        self.assertEqual(packet["merged_worktree_attached_count"], 0)
    def test_branch_prefix_check_accepts_default_codex_prefix(self) -> None:
        packet = git_discipline.inspect_branch_prefix("codex/t110-static-hygiene")

        self.assertEqual(packet["schema"], "bears-branch-prefix-check.v1")
        self.assertEqual(packet["status"], "BRANCH_PREFIX_PASS")
        self.assertEqual(packet["branch_prefix_check"], "PASS")
        self.assertFalse(packet["override_used"])
        self.assertTrue(packet["read_only"])

    def test_branch_prefix_check_blocks_non_default_without_assignment_override(self) -> None:
        packet = git_discipline.inspect_branch_prefix("fix/t110-doc-literal")

        self.assertEqual(packet["status"], "BRANCH_PREFIX_BLOCKED")
        self.assertEqual(packet["branch_prefix_check"], "FAIL")
        self.assertIn("missing_assignment_prefix_override", packet["block_reasons"])

    def test_branch_prefix_check_accepts_explicit_assignment_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            packet_path = Path(tmp) / "assignment.json"
            packet_path.write_text(
                json.dumps(
                    {
                        "branch_prefix_override": {
                            "prefix": "agent/",
                            "reason": "registered goal branch model",
                            "approved_by": "operator",
                        }
                    }
                ),
                encoding="utf-8",
            )

            packet = git_discipline.inspect_branch_prefix(
                "agent/goal-173/role/slice",
                assignment_packet=packet_path,
            )

        self.assertEqual(packet["status"], "BRANCH_PREFIX_PASS")
        self.assertEqual(packet["branch_prefix_check"], "PASS")
        self.assertEqual(packet["override_prefix"], "agent/")
        self.assertTrue(packet["override_used"])

    def test_branch_prefix_check_cli_blocks_non_default_branch(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_PATH),
                "branch-prefix-check",
                "--branch",
                "ledger/008-backend-task-packets",
                "--json",
            ],
            cwd=PLUGIN_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 1)
        packet = json.loads(result.stdout)
        self.assertEqual(packet["status"], "BRANCH_PREFIX_BLOCKED")
        self.assertEqual(packet["branch_prefix_check"], "FAIL")


    def test_gitlink_audit_reports_parent_target_and_matching_local_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            child = root / "child"
            parent = root / "parent"
            child.mkdir()
            parent.mkdir()
            git(child, "init", "-b", "main")
            git(child, "config", "user.email", "codex-worker@bears.local")
            git(child, "config", "user.name", "Bears Codex Worker")
            (child / "target.txt").write_text("target\n", encoding="utf-8")
            git(child, "add", "target.txt")
            git(child, "commit", "-m", "Target commit")
            child_head = git(child, "rev-parse", "HEAD")
            git(parent, "init", "-b", "main")
            git(parent, "config", "user.email", "codex-worker@bears.local")
            git(parent, "config", "user.name", "Bears Codex Worker")
            git(parent, "update-index", "--add", "--cacheinfo", f"160000,{child_head},kubernetes")
            git(parent, "commit", "-m", "Pin gitlink")

            packet = git_discipline.inspect_gitlink_target(
                parent,
                tree_ref="HEAD",
                gitlink_path="kubernetes",
                expected_target=child_head,
                local_checkout=child,
                claim_source="local-checkout",
            )

        self.assertEqual(packet["schema"], "bears-gitlink-target-audit.v1")
        self.assertEqual(packet["status"], "GITLINK_AUDIT_PASS")
        self.assertEqual(packet["parent_gitlink_target"], child_head)
        self.assertEqual(packet["local_checkout_head"], child_head)
        self.assertEqual(packet["local_checkout_status"], "MATCHES_PARENT_TARGET")
        self.assertEqual(packet["claim_object_used"], child_head)
        self.assertTrue(packet["local_checkout_evidence_usable"])
        self.assertTrue(packet["read_only"])

    def test_gitlink_audit_blocks_stale_local_checkout_claims(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            child = root / "child"
            parent = root / "parent"
            child.mkdir()
            parent.mkdir()
            git(child, "init", "-b", "main")
            git(child, "config", "user.email", "codex-worker@bears.local")
            git(child, "config", "user.name", "Bears Codex Worker")
            (child / "target.txt").write_text("one\n", encoding="utf-8")
            git(child, "add", "target.txt")
            git(child, "commit", "-m", "First target")
            old_head = git(child, "rev-parse", "HEAD")
            (child / "target.txt").write_text("two\n", encoding="utf-8")
            git(child, "add", "target.txt")
            git(child, "commit", "-m", "Second target")
            new_head = git(child, "rev-parse", "HEAD")
            git(child, "checkout", old_head)
            git(parent, "init", "-b", "main")
            git(parent, "config", "user.email", "codex-worker@bears.local")
            git(parent, "config", "user.name", "Bears Codex Worker")
            git(parent, "update-index", "--add", "--cacheinfo", f"160000,{new_head},kubernetes")
            git(parent, "commit", "-m", "Pin gitlink")

            stale_packet = git_discipline.inspect_gitlink_target(
                parent,
                tree_ref="HEAD",
                gitlink_path="kubernetes",
                expected_target=new_head,
                local_checkout=child,
                claim_source="local-checkout",
            )
            parent_packet = git_discipline.inspect_gitlink_target(
                parent,
                tree_ref="HEAD",
                gitlink_path="kubernetes",
                expected_target=new_head,
                local_checkout=child,
                claim_source="parent-gitlink",
            )

        self.assertEqual(stale_packet["status"], "GITLINK_AUDIT_BLOCKED")
        self.assertEqual(stale_packet["parent_gitlink_target"], new_head)
        self.assertEqual(stale_packet["local_checkout_head"], old_head)
        self.assertEqual(stale_packet["local_checkout_status"], "STALE_LOCAL_CHECKOUT")
        self.assertFalse(stale_packet["local_checkout_evidence_usable"])
        self.assertIn("local_checkout_not_parent_target", stale_packet["block_reasons"])
        self.assertEqual(parent_packet["status"], "GITLINK_AUDIT_PASS")
        self.assertEqual(parent_packet["claim_object_used"], new_head)
        self.assertEqual(parent_packet["local_checkout_status"], "STALE_LOCAL_CHECKOUT")
        self.assertFalse(parent_packet["local_checkout_evidence_usable"])

    def test_gitlink_audit_cli_blocks_expected_target_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            child = root / "child"
            parent = root / "parent"
            child.mkdir()
            parent.mkdir()
            git(child, "init", "-b", "main")
            git(child, "config", "user.email", "codex-worker@bears.local")
            git(child, "config", "user.name", "Bears Codex Worker")
            (child / "target.txt").write_text("target\n", encoding="utf-8")
            git(child, "add", "target.txt")
            git(child, "commit", "-m", "Target commit")
            child_head = git(child, "rev-parse", "HEAD")
            wrong_head = "0" * 40
            git(parent, "init", "-b", "main")
            git(parent, "config", "user.email", "codex-worker@bears.local")
            git(parent, "config", "user.name", "Bears Codex Worker")
            git(parent, "update-index", "--add", "--cacheinfo", f"160000,{child_head},kubernetes")
            git(parent, "commit", "-m", "Pin gitlink")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "gitlink-audit",
                    "--repo",
                    str(parent),
                    "--tree-ref",
                    "HEAD",
                    "--path",
                    "kubernetes",
                    "--expected-target",
                    wrong_head,
                    "--json",
                ],
                cwd=PLUGIN_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        packet = json.loads(result.stdout)
        self.assertEqual(packet["status"], "GITLINK_AUDIT_BLOCKED")
        self.assertFalse(packet["expected_target_matches"])
        self.assertIn("expected_target_mismatch", packet["block_reasons"])

    def test_branch_base_preflight_blocks_detached_dirty_and_wrong_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.email", "codex-worker@bears.local")
            git(repo, "config", "user.name", "Bears Codex Worker")
            (repo / "file.txt").write_text("ok\n", encoding="utf-8")
            git(repo, "add", "file.txt")
            git(repo, "commit", "-m", "Initial commit")
            git(repo, "checkout", "--detach")
            (repo / "file.txt").write_text("changed\n", encoding="utf-8")

            packet = git_discipline.inspect_branch_base_preflight(
                repo,
                self.catalog,
                intended_base="HEAD",
                expected_branch_prefix="codex/",
                allowed_path=["docs/reference/git-discipline.md"],
            )

        self.assertEqual(packet["status"], "BRANCH_BASE_PREFLIGHT_BLOCKED")
        self.assertIn("detached_head", packet["block_reasons"])
        self.assertIn("dirty_worktree", packet["block_reasons"])
        self.assertIn("current_branch_prefix_mismatch", packet["block_reasons"])
        self.assertIn("assigned_file_diff_mismatch", packet["block_reasons"])

    def test_branch_base_preflight_blocks_merged_pr_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.email", "codex-worker@bears.local")
            git(repo, "config", "user.name", "Bears Codex Worker")
            (repo / "file.txt").write_text("ok\n", encoding="utf-8")
            git(repo, "add", "file.txt")
            git(repo, "commit", "-m", "Initial commit")
            git(repo, "switch", "-c", "codex/old-merged-branch")
            prs = Path(tmp) / "prs.json"
            prs.write_text(
                json.dumps([{"number": 127, "headRefName": "codex/old-merged-branch", "state": "MERGED"}]),
                encoding="utf-8",
            )

            packet = git_discipline.inspect_branch_base_preflight(
                repo,
                self.catalog,
                intended_base="HEAD",
                expected_branch_prefix="codex/",
                github_prs_json=prs,
            )

        self.assertEqual(packet["status"], "BRANCH_BASE_PREFLIGHT_BLOCKED")
        self.assertIn("branch_has_merged_pr", packet["block_reasons"])
        self.assertEqual(packet["merged_pr_numbers"], [127])

    def test_branch_base_preflight_allows_assigned_changes_before_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git(repo, "init", "-b", "main")
            git(repo, "config", "user.email", "codex-worker@bears.local")
            git(repo, "config", "user.name", "Bears Codex Worker")
            (repo / "scripts").mkdir()
            (repo / "scripts/git_discipline.py").write_text("ok\n", encoding="utf-8")
            git(repo, "add", "scripts/git_discipline.py")
            git(repo, "commit", "-m", "Initial commit")
            git(repo, "switch", "-c", "codex/git-discipline-guard")
            (repo / "scripts/git_discipline.py").write_text("changed\n", encoding="utf-8")

            packet = git_discipline.inspect_branch_base_preflight(
                repo,
                self.catalog,
                intended_base="HEAD",
                expected_branch_prefix="codex/",
                allowed_path=["scripts/git_discipline.py"],
                allow_assigned_changes=True,
            )

        self.assertEqual(packet["status"], "BRANCH_BASE_PREFLIGHT_PASS")
        self.assertTrue(packet["assigned_changes_allowed"])

    def test_clean_worktree_target_maps_physical_path_to_canonical_route(self) -> None:
        packet = git_discipline.map_clean_worktree_target(
            canonical_root="/srv/bears",
            worktree_root="/srv/bears/dev/workspace/bears-codex-workspace-t354",
            worktree_target="/srv/bears/dev/workspace/bears-codex-workspace-t354/specs/006-bears-platform-telegram/governance/live-telegram-approval-request.json",
            canonical_target="/srv/bears/specs/006-bears-platform-telegram/governance/live-telegram-approval-request.json",
        )

        self.assertEqual(packet["status"], "CLEAN_WORKTREE_TARGET_PASS")
        self.assertEqual(
            packet["route_target"],
            "/srv/bears/specs/006-bears-platform-telegram/governance/live-telegram-approval-request.json",
        )

    def test_ignored_staging_blocks_force_add_to_dev_surface(self) -> None:
        packet = git_discipline.evaluate_ignored_staging_command(
            "git add -f dev/PROJECTS.md dev/registry/projects.v1.json",
        )

        self.assertEqual(packet["status"], "IGNORED_STAGING_BLOCKED")
        self.assertTrue(packet["force_add_detected"])
        self.assertEqual(packet["blocked_paths"], ["dev/PROJECTS.md", "dev/registry/projects.v1.json"])
        self.assertIn("ignored_surface_force_add", packet["reasons"])

    def test_ignored_staging_allows_explicit_operator_allowlist(self) -> None:
        packet = git_discipline.evaluate_ignored_staging_command(
            "git add -f docs/reference/git-discipline.md",
            explicit_allowed_paths=["docs/reference/git-discipline.md"],
            operator_approval=True,
            owning_contract="/srv/bears/contracts/repo-boundary.md",
        )

        self.assertEqual(packet["status"], "IGNORED_STAGING_PASS")
        self.assertTrue(packet["force_add_detected"])


if __name__ == "__main__":
    unittest.main()
