from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import tomllib
import tarfile
import unittest
import hashlib


ROOT = Path(__file__).resolve().parents[1]
READ_TOOLS = {"project_list", "project_status", "graph_read", "graph_search", "graph_open", "dependency_slice", "impact_analysis", "graph_trace", "graph_diagnostics", "topological_plan", "workflow_state", "workflow_validate"}
WRITE_TOOLS = {"project_register", "project_rebind", "project_unregister", "project_migrate_json", "wave_initialize", "phase_record", "graph_apply", "plan_replace", "task_record_change", "review_record", "correction_record", "analysis_record", "workflow_mark_audited"}
PROFILES = {"app-analyst", "app-reviewer", "app-worker", "repo-orchestrator", "workflow-orchestrator"}
SKILLS = {"app-analyze", "app-constitution", "app-dev", "app-functional-graph", "app-plan", "app-research", "app-specify", "subagents"}


class PluginShapeTests(unittest.TestCase):
    def test_manifest_and_mcp_metadata_are_060(self) -> None:
        manifest = json.loads((ROOT / ".codex-plugin/plugin.json").read_text())
        self.assertEqual(manifest["version"], "0.6.0")
        self.assertEqual(manifest["mcpServers"], "./.mcp.json")
        servers = json.loads((ROOT / ".mcp.json").read_text())["mcpServers"]
        self.assertEqual(set(servers), {"app-workflow", "app-workflow-maintainer"})
        self.assertEqual({tuple(server["args"]) for server in servers.values()}, {("./scripts/app_workflow.py", "serve", "--mode", "reader"), ("./scripts/app_workflow.py", "serve", "--mode", "maintainer")})

    def test_exact_skill_contract_and_profile_surfaces(self) -> None:
        self.assertEqual({path.name for path in (ROOT / "skills").iterdir() if path.is_dir()}, SKILLS)
        self.assertEqual({path.name for path in (ROOT / "contracts").iterdir() if path.is_file()}, {"app-workflow-db-v1.sql", "app-workflow-mcp-tools.v1.json"})
        self.assertEqual({path.stem for path in (ROOT / "agents").glob("*.toml")}, PROFILES)
        for skill in SKILLS:
            size = sum(path.stat().st_size for path in (ROOT / "skills" / skill).rglob("*") if path.is_file() and "__pycache__" not in path.parts)
            self.assertLessEqual(size, 30 * 1024, skill)

    def test_profile_mcp_policy_matches_roles(self) -> None:
        profiles = {path.stem: tomllib.loads(path.read_text()) for path in (ROOT / "agents").glob("*.toml")}
        namespace = "bears-app-based-workflow@bears-app-based-workflow"
        for name, profile in profiles.items():
            servers = profile["plugins"][namespace]["mcp_servers"]
            reader = servers["app-workflow"]
            writer = servers["app-workflow-maintainer"]
            if name == "repo-orchestrator":
                self.assertEqual(set(reader["enabled_tools"]), READ_TOOLS)
                self.assertEqual(set(writer["enabled_tools"]), WRITE_TOOLS)
            elif name in {"app-reviewer", "app-analyst"}:
                self.assertTrue(reader["enabled"])
                self.assertFalse(writer["enabled"])
                self.assertTrue(set(reader["enabled_tools"]) < READ_TOOLS)
            else:
                self.assertFalse(reader["enabled"])
                self.assertFalse(writer["enabled"])

    def test_obsolete_json_runtime_and_role_sources_are_absent(self) -> None:
        self.assertFalse((ROOT / "role-definitions").exists())
        self.assertFalse((ROOT / "scripts/app_graph_mcp.py").exists())
        self.assertFalse((ROOT / "contracts/app-functional-map.v5.schema.json").exists())
        self.assertFalse((ROOT / "contracts/workflow-state.v1.schema.json").exists())
        self.assertFalse((ROOT / ".github/runner/bears_deploy/role_renderer.py").exists())

    def test_installer_dry_run_registers_five_without_writes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="bears-plugin-install-", dir="/tmp") as directory:
            home = Path(directory) / "codex"
            home.mkdir(mode=0o700)
            completed = subprocess.run([str(ROOT / "install"), "--codex-home", str(home), "--dry-run"], cwd=ROOT, text=True, capture_output=True, check=True)
            receipt = json.loads(completed.stdout)
            self.assertEqual((receipt["status"], receipt["role_count"], receipt["version"]), ("dry-run", 5, "0.6.0"))
            self.assertEqual(list(home.iterdir()), [])

    def test_repository_limits_and_artifact_language(self) -> None:
        files = [path for path in ROOT.rglob("*") if path.is_file() and ".git" not in path.parts and "__pycache__" not in path.parts and ".ruff_cache" not in path.parts]
        self.assertLessEqual(len(files), 80)
        self.assertLessEqual(sum(path.stat().st_size for path in files), 1024 * 1024)
        for path in [ROOT / "README.md", ROOT / "CHANGELOG.md", ROOT / "THIRD_PARTY_NOTICES"] + list((ROOT / "skills").glob("*/SKILL.md")):
            if path.exists():
                path.read_text(encoding="ascii")

    def test_release_bundle_is_060_and_matches_manifest(self) -> None:
        archive = ROOT / "dist/bears-app-based-workflow-0.6.0.tar.gz"
        manifest = json.loads((ROOT / "dist/bears-app-based-workflow-0.6.0.bundle.json").read_text())
        self.assertEqual(manifest["version"], "0.6.0")
        self.assertEqual(manifest["archive_sha256"], "sha256:" + hashlib.sha256(archive.read_bytes()).hexdigest())
        with tarfile.open(archive, "r:gz") as bundle:
            plugin = json.load(bundle.extractfile("bears-app-based-workflow-0.6.0/.codex-plugin/plugin.json"))
            marketplace = json.load(bundle.extractfile("bears-app-based-workflow-0.6.0/.agents/plugins/marketplace.json"))
        self.assertEqual(plugin["version"], "0.6.0")
        self.assertEqual(marketplace["plugins"][0]["version"], "0.6.0")


if __name__ == "__main__":
    unittest.main()
