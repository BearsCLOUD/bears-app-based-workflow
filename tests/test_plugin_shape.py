from __future__ import annotations

import json
from pathlib import Path
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.7.0"
READ_TOOLS = {"project_list", "project_status", "graph_read", "graph_search", "graph_open", "dependency_slice", "impact_analysis", "graph_trace", "graph_diagnostics", "topological_plan", "workflow_state", "workflow_validate"}
WRITE_TOOLS = {"project_register", "project_rebind", "project_unregister", "project_migrate_json", "wave_initialize", "phase_record", "graph_apply", "plan_replace", "task_record_change", "review_record", "correction_record", "analysis_record", "workflow_mark_audited"}
# Role and skill sets are read from disk on purpose: the Claude-native rework adds and retires
# both, and hard-coding them here made this file a merge hub for every unrelated change.
ORCHESTRATOR_PROFILES = {"repo-orchestrator"}
READER_PROFILES = {"app-reviewer", "app-analyst"}
# Working-tree paths that are local state rather than shipped artifacts, so they must not count
# against the repository budget: `.bears`/`waves` appear when the plugin is run against its own
# repository, and `.claude` holds Claude Code's local settings and worktrees. `.claude-plugin` is a
# different path component and still counts.
LOCAL_STATE_DIRS = {".bears", "waves", ".claude"}


def skill_dirs() -> list[Path]:
    return sorted(path for path in (ROOT / "skills").iterdir() if path.is_dir())


def profile_paths() -> list[Path]:
    return sorted((ROOT / "agents").glob("*.toml"))


class PluginShapeTests(unittest.TestCase):
    def test_manifest_and_mcp_metadata_match_version(self) -> None:
        manifest = json.loads((ROOT / ".codex-plugin/plugin.json").read_text())
        self.assertEqual(manifest["version"], VERSION)
        self.assertEqual(manifest["mcpServers"], "./.mcp.json")
        servers = json.loads((ROOT / ".mcp.json").read_text())["mcpServers"]
        self.assertEqual(set(servers), {"app-workflow", "app-workflow-maintainer"})
        self.assertEqual({tuple(server["args"]) for server in servers.values()}, {("./scripts/app_workflow.py", "serve", "--mode", "reader"), ("./scripts/app_workflow.py", "serve", "--mode", "maintainer")})

    def test_every_skill_has_a_bounded_skill_document(self) -> None:
        skills = skill_dirs()
        self.assertTrue(skills)
        self.assertEqual({path.name for path in (ROOT / "contracts").iterdir() if path.is_file()}, {"app-workflow-db-v1.sql", "app-workflow-mcp-tools.v1.json"})
        for skill in skills:
            self.assertTrue((skill / "SKILL.md").is_file(), skill.name)
            size = sum(path.stat().st_size for path in skill.rglob("*") if path.is_file() and "__pycache__" not in path.parts)
            self.assertLessEqual(size, 30 * 1024, skill.name)

    def test_profile_mcp_policy_matches_roles(self) -> None:
        profiles = {path.stem: tomllib.loads(path.read_text()) for path in profile_paths()}
        self.assertTrue(profiles)
        namespace = "bears-app-based-workflow@bears-app-based-workflow"
        for name, profile in profiles.items():
            servers = profile["plugins"][namespace]["mcp_servers"]
            reader = servers["app-workflow"]
            writer = servers["app-workflow-maintainer"]
            if name in ORCHESTRATOR_PROFILES:
                self.assertEqual(set(reader["enabled_tools"]), READ_TOOLS)
                self.assertEqual(set(writer["enabled_tools"]), WRITE_TOOLS)
            elif name in READER_PROFILES:
                self.assertTrue(reader["enabled"])
                self.assertFalse(writer["enabled"])
                self.assertTrue(set(reader["enabled_tools"]) < READ_TOOLS)
            else:
                self.assertFalse(reader["enabled"])
                self.assertFalse(writer["enabled"])

    def test_obsolete_json_runtime_and_codex_host_sources_are_absent(self) -> None:
        self.assertFalse((ROOT / "role-definitions").exists())
        self.assertFalse((ROOT / "scripts/app_graph_mcp.py").exists())
        self.assertFalse((ROOT / "contracts/app-functional-map.v5.schema.json").exists())
        self.assertFalse((ROOT / "contracts/workflow-state.v1.schema.json").exists())
        # Retired with the Claude-native rework: the Codex installer and the self-hosted CD runner.
        self.assertFalse((ROOT / "install").exists())
        self.assertFalse((ROOT / ".github/runner").exists())
        self.assertFalse((ROOT / "dist").exists())

    def test_repository_limits_and_artifact_language(self) -> None:
        skipped = {".git", "__pycache__", ".ruff_cache", *LOCAL_STATE_DIRS}
        files = [path for path in ROOT.rglob("*") if path.is_file() and skipped.isdisjoint(path.parts)]
        self.assertLessEqual(len(files), 80)
        self.assertLessEqual(sum(path.stat().st_size for path in files), 1024 * 1024)
        for path in [ROOT / "README.md", ROOT / "CHANGELOG.md", ROOT / "THIRD_PARTY_NOTICES"] + list((ROOT / "skills").glob("*/SKILL.md")):
            if path.exists():
                path.read_text(encoding="ascii")


if __name__ == "__main__":
    unittest.main()
