from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
ACTION_PATH = PLUGIN_ROOT / "actions" / "subagents-roles-gate" / "action.yml"


class PlatformRoleGateActionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.action = yaml.safe_load(ACTION_PATH.read_text(encoding="utf-8"))
        cls.run_script = cls.action["runs"]["steps"][0]["run"]

    def run_action_script(
        self,
        *,
        github_workspace: Path,
        platform_repo_root: str = ".",
        role_targets: str = "tests/test_gateway_runtime_contracts.py\ndocs/ci/gateway-required-checks.md",
        require_target_files: str = "true",
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.update(
            {
                "BEARS_PLUGIN_ACTION_PATH": str(ACTION_PATH.parent),
                "BEARS_PLATFORM_REPO_ROOT": platform_repo_root,
                "BEARS_PLATFORM_ROUTE_ROOT": "/srv/bears/dev/platform",
                "BEARS_PLATFORM_ROLE_TARGETS": role_targets,
                "BEARS_REQUIRE_TARGET_FILES": require_target_files,
                "GITHUB_WORKSPACE": str(github_workspace),
            }
        )
        return subprocess.run(
            ["bash", "-c", self.run_script],
            cwd=PLUGIN_ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
        )

    def test_action_repository_has_no_recursive_plugin_symlink(self) -> None:
        tracked_symlinks = subprocess.check_output(
            ["git", "ls-files", "-s"],
            cwd=PLUGIN_ROOT,
            text=True,
        ).splitlines()
        has_recursive_plugin_symlink = any(
            line.endswith("\tplugins/bears") and line.startswith("120000 ")
            for line in tracked_symlinks
        )
        self.assertFalse(
            has_recursive_plugin_symlink,
            msg=(
                "plugins/bears must not be a tracked symlink because GitHub "
                "action setup archives the whole private action repository."
            ),
        )
        self.assertFalse((PLUGIN_ROOT / "plugins" / "bears").exists())

    def test_action_is_private_composite_without_checkout_or_secret_inputs(self) -> None:
        self.assertEqual(self.action["runs"]["using"], "composite")
        serialized = ACTION_PATH.read_text(encoding="utf-8")
        self.assertNotIn("actions/checkout", serialized)
        self.assertNotIn("${{ secrets.", serialized)
        self.assertNotIn("repository:", serialized)
        self.assertIn("${{ github.action_path }}", serialized)
        self.assertNotIn("github-token", serialized)
        self.assertNotIn("token:", serialized)
        self.assertNotIn("ref:", serialized)

    def test_action_inputs_cover_platform_root_and_pr143_targets(self) -> None:
        inputs = self.action["inputs"]
        self.assertEqual(inputs["platform-repo-root"]["default"], ".")
        self.assertEqual(
            inputs["platform-route-root"]["default"],
            "/srv/bears/dev/platform",
        )
        self.assertEqual(inputs["require-target-files"]["default"], "true")
        default_targets = inputs["role-targets"]["default"]
        self.assertIn("tests/test_gateway_runtime_contracts.py", default_targets)
        self.assertIn("docs/ci/gateway-required-checks.md", default_targets)

    def test_action_documents_private_action_permissions_and_no_secrets(self) -> None:
        serialized = ACTION_PATH.read_text(encoding="utf-8")
        self.assertIn("permissions: contents: read", serialized)
        self.assertIn("no secrets", serialized)

    def test_action_mirrors_pr143_role_gate_commands(self) -> None:
        script = self.run_script
        self.assertIn('python3 "${plugin_root}/scripts/subagents_roles.py" validate', script)
        self.assertIn('python3 "${plugin_root}/scripts/role_gate_methodology.py" validate', script)
        self.assertIn('python3 "${plugin_root}/scripts/subagents_roles.py" route "${route_target}"', script)
        self.assertIn('python3 "${plugin_root}/scripts/subagents_roles.py" audit "${route_target}"', script)
        self.assertIn('route_target="${platform_route_root}/${target}"', script)
        self.assertIn('platform_repo_root="${workspace_root}/${platform_repo_root}"', script)
        self.assertIn('plugin_root="$(cd "${action_root}/../.." && pwd -P)"', script)
        self.assertIn('role-targets entries must be relative paths without', script)
        self.assertIn('os.path.commonpath([workspace_root, platform_repo_root])', script)
        self.assertNotIn('route_target="${target}"', script)

    def test_simulated_composite_run_accepts_checkout_under_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            platform_root = workspace / "caller"
            (platform_root / "tests").mkdir(parents=True)
            (platform_root / "docs" / "ci").mkdir(parents=True)
            (platform_root / "tests" / "test_gateway_runtime_contracts.py").write_text("", encoding="utf-8")
            (platform_root / "docs" / "ci" / "gateway-required-checks.md").write_text("", encoding="utf-8")

            result = self.run_action_script(
                github_workspace=workspace,
                platform_repo_root="caller",
            )

        self.assertEqual(result.returncode, 0, msg=result.stderr + result.stdout)
        self.assertIn("status: matched", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_simulated_composite_run_rejects_relative_workspace_escape_before_file_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            result = self.run_action_script(
                github_workspace=workspace,
                platform_repo_root="../outside",
                role_targets="missing.txt",
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("platform-repo-root must stay under GITHUB_WORKSPACE", result.stderr)
        self.assertNotIn("Bears platform target is missing", result.stderr)

    def test_simulated_composite_run_rejects_absolute_workspace_escape_before_file_check(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            outside = Path(tmp) / "outside"
            workspace.mkdir()
            outside.mkdir()
            result = self.run_action_script(
                github_workspace=workspace,
                platform_repo_root=str(outside),
                role_targets="missing.txt",
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("platform-repo-root must stay under GITHUB_WORKSPACE", result.stderr)
        self.assertNotIn("Bears platform target is missing", result.stderr)


if __name__ == "__main__":
    unittest.main()
