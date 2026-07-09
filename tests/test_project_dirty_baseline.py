from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PLUGIN_ROOT / "scripts" / "project_dirty_baseline.py"
spec = importlib.util.spec_from_file_location("project_dirty_baseline", SCRIPT_PATH)
baseline = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(baseline)  # type: ignore[arg-type]


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test User",
            "-c",
            "user.email=test@example.com",
            *args,
        ],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


class ProjectDirtyBaselineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy_catalog = baseline.load_json(PLUGIN_ROOT / "assets/catalog/project-dirty-baseline.v1.json")
        cls.role_catalog = baseline.load_json(PLUGIN_ROOT / "assets/catalog/platform-role-catalog.v1.json")

    def test_current_catalog_validates(self) -> None:
        self.assertEqual(
            baseline.validate_catalog(self.policy_catalog, role_catalog=self.role_catalog),
            [],
        )

    def test_rejects_write_handoff_in_policy(self) -> None:
        policy = json.loads(json.dumps(self.policy_catalog))
        policy["status_contract"]["dirty_confirmed"]["write_handoff_allowed"] = True
        errors = baseline.validate_catalog(policy, role_catalog=self.role_catalog, check_files=False)
        self.assertTrue(any("write_handoff_allowed must stay false" in error for error in errors))

    def test_rejects_projects_root_default_as_global_baseline(self) -> None:
        policy = json.loads(json.dumps(self.policy_catalog))
        policy["governance_scan"]["root_default"] = "/srv/bears/projects"
        errors = baseline.validate_catalog(policy, role_catalog=self.role_catalog, check_files=False)
        self.assertTrue(any("root_default is forbidden" in error for error in errors))

    def test_forbidden_git_verbs_match_catalog_exactly(self) -> None:
        policy_verbs = set(self.policy_catalog["read_only_policy"]["forbidden_git_verbs"])
        self.assertEqual(policy_verbs, baseline.REQUIRED_FORBIDDEN_GIT_VERBS)
        self.assertIn("am", policy_verbs)
        self.assertIn("apply", policy_verbs)
        self.assertIn("cherry-pick", policy_verbs)
        self.assertIn("restore", policy_verbs)
        self.assertIn("revert", policy_verbs)
        self.assertIn("switch", policy_verbs)

    def test_rejects_removed_catalog_forbidden_git_verb(self) -> None:
        policy = json.loads(json.dumps(self.policy_catalog))
        policy["read_only_policy"]["forbidden_git_verbs"].remove("switch")
        errors = baseline.validate_catalog(policy, role_catalog=self.role_catalog, check_files=False)
        self.assertTrue(any("forbidden_git_verbs must exactly match" in error for error in errors), errors)

    def test_capture_dirty_requires_operator_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "projects"
            repo = root / "team" / "repo-a"
            repo.mkdir(parents=True)
            git(repo, "init", "-b", "main")
            (root / "team" / "AGENTS.md").write_text("# group router\n", encoding="utf-8")
            (repo / "SPEC.md").write_text("# spec\n", encoding="utf-8")
            (repo / "requirements.md").write_text("# requirements\n", encoding="utf-8")
            (repo / "tracked.txt").write_text("before\n", encoding="utf-8")
            git(repo, "add", "tracked.txt", "SPEC.md", "requirements.md")
            git(repo, "commit", "-m", "init")
            (repo / "tracked.txt").write_text("after\n", encoding="utf-8")
            (repo / "notes.md").write_text("untracked file\n", encoding="utf-8")

            packet = baseline.capture_baseline(root)

            self.assertEqual(packet["schema"], "bears-project-dirty-baseline-capture.v1")
            self.assertEqual(packet["repo_count"], 1)
            self.assertEqual(packet["dirty_repo_count"], 1)
            self.assertEqual(packet["status"], "DIRTY_BASELINE_REQUIRES_OPERATOR_CONFIRMATION")
            self.assertFalse(packet["write_handoff_allowed"])
            repo_packet = packet["repositories"][0]
            self.assertEqual(repo_packet["branch"], "main")
            self.assertIn("main", repo_packet["status_short_branch"])
            self.assertEqual(repo_packet["tracked_diff_summary"], [{"status": "M", "path": "tracked.txt"}])
            self.assertEqual(repo_packet["untracked_files"], ["notes.md"])
            self.assertTrue(repo_packet["governance_files"]["AGENTS.md"]["present"])
            self.assertTrue(repo_packet["governance_files"]["SPEC.md"]["present"])
            self.assertTrue(repo_packet["governance_files"]["requirements.md"]["present"])
            self.assertTrue(repo_packet["governance_files"]["AGENTS.md"]["nearest_path"].endswith("/team/AGENTS.md"))
            serialized = json.dumps(packet)
            self.assertNotIn("after\\n", serialized)
            self.assertNotIn("untracked file", serialized)

    def test_container_inventory_mode_does_not_block_plugin_core_closeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "projects"
            repo = root / "team" / "repo-a"
            repo.mkdir(parents=True)
            git(repo, "init", "-b", "main")
            (repo / "tracked.txt").write_text("before\n", encoding="utf-8")
            git(repo, "add", "tracked.txt")
            git(repo, "commit", "-m", "init")
            (repo / "tracked.txt").write_text("after\n", encoding="utf-8")

            packet = baseline.capture_baseline(root, scope_mode=baseline.CONTAINER_INVENTORY_SCOPE)

            self.assertEqual(packet["status"], "CONTAINER_INVENTORY_ONLY")
            self.assertEqual(packet["scope_mode"], "container-inventory")
            self.assertTrue(packet["container_inventory_only"])
            self.assertEqual(packet["dirty_repo_count"], 1)
            self.assertFalse(packet["operator_confirmation_required"])
            self.assertFalse(packet["project_write_lane_allowed"])
            self.assertFalse(packet["project_write_lane_blocked_by_dirty_baseline"])
            self.assertTrue(packet["requires_exact_role_route"])
            self.assertFalse(packet["write_handoff_allowed"])
            self.assertTrue(any("not a baseline" in note for note in packet["notes"]))

    def test_cli_container_inventory_mode_exits_zero_for_dirty_projects_container(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "projects"
            repo = root / "repo-a"
            repo.mkdir(parents=True)
            git(repo, "init", "-b", "main")
            (repo / "tracked.txt").write_text("before\n", encoding="utf-8")
            git(repo, "add", "tracked.txt")
            git(repo, "commit", "-m", "init")
            (repo / "tracked.txt").write_text("after\n", encoding="utf-8")

            result = subprocess.run(
                [
                    "python3",
                    str(SCRIPT_PATH),
                    "capture",
                    "--root",
                    str(root),
                    "--scope-mode",
                    "container-inventory",
                    "--json",
                ],
                cwd=PLUGIN_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            packet = json.loads(result.stdout)

            self.assertEqual(packet["status"], "CONTAINER_INVENTORY_ONLY")
            self.assertEqual(packet["dirty_repo_count"], 1)
            self.assertFalse(packet["write_handoff_allowed"])

    def test_operator_confirmed_baseline_stays_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "projects"
            repo = root / "repo-b"
            repo.mkdir(parents=True)
            git(repo, "init", "-b", "main")
            (repo / "tracked.txt").write_text("before\n", encoding="utf-8")
            git(repo, "add", "tracked.txt")
            git(repo, "commit", "-m", "init")
            (repo / "tracked.txt").write_text("after\n", encoding="utf-8")

            packet = baseline.capture_baseline(root, operator_confirmed_baseline=True)

            self.assertEqual(packet["status"], "BASELINE_ACCEPTED_READ_ONLY")
            self.assertFalse(packet["write_handoff_allowed"])
            self.assertTrue(packet["operator_confirmed_baseline"])

    def test_bounded_capture_ignores_dirty_repositories_outside_target_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_root = Path(tmp_dir)
            target_root = temp_root / "projects" / "target"
            target_repo = target_root / "repo-clean"
            outside_repo = temp_root / "projects" / "other" / "repo-dirty"
            target_repo.mkdir(parents=True)
            outside_repo.mkdir(parents=True)

            git(target_repo, "init", "-b", "main")
            (target_repo / "file.txt").write_text("clean\n", encoding="utf-8")
            git(target_repo, "add", "file.txt")
            git(target_repo, "commit", "-m", "init")

            git(outside_repo, "init", "-b", "main")
            (outside_repo / "file.txt").write_text("before\n", encoding="utf-8")
            git(outside_repo, "add", "file.txt")
            git(outside_repo, "commit", "-m", "init")
            (outside_repo / "file.txt").write_text("after\n", encoding="utf-8")

            packet = baseline.capture_baseline(target_root)

            self.assertEqual(packet["repo_count"], 1)
            self.assertEqual(packet["dirty_repo_count"], 0)
            self.assertEqual(packet["status"], "CLEAN_READ_ONLY_BASELINE")
            self.assertTrue(packet["repositories"][0]["repo_root"].endswith("/repo-clean"))

    def test_capture_includes_upstream_when_present_and_counts_nested_repos(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_root = Path(tmp_dir)
            root = temp_root / "projects"
            remote = temp_root / "remote.git"
            repo_a = root / "group" / "repo-a"
            repo_b = root / "group" / "nested" / "repo-b"
            repo_a.mkdir(parents=True)
            repo_b.mkdir(parents=True)

            git(temp_root, "init", "--bare", str(remote))

            git(repo_a, "init", "-b", "main")
            (repo_a / "file.txt").write_text("one\n", encoding="utf-8")
            git(repo_a, "add", "file.txt")
            git(repo_a, "commit", "-m", "init")
            git(repo_a, "remote", "add", "origin", str(remote))
            git(repo_a, "push", "-u", "origin", "main")

            git(repo_b, "init", "-b", "main")
            (repo_b / "file.txt").write_text("two\n", encoding="utf-8")
            git(repo_b, "add", "file.txt")
            git(repo_b, "commit", "-m", "init")

            packet = baseline.capture_baseline(root)

            self.assertEqual(packet["repo_count"], 2)
            self.assertEqual(packet["dirty_repo_count"], 0)
            self.assertEqual(packet["status"], "CLEAN_READ_ONLY_BASELINE")
            repo_packets = {Path(repo["repo_root"]).name: repo for repo in packet["repositories"]}
            self.assertEqual(repo_packets["repo-a"]["upstream"], "origin/main")
            self.assertIsNone(repo_packets["repo-b"]["upstream"])


if __name__ == "__main__":
    unittest.main()
