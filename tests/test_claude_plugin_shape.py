from __future__ import annotations

import json
from pathlib import Path
import re
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]
READ_TOOLS = {"project_list", "project_status", "graph_read", "graph_search", "graph_open", "dependency_slice", "impact_analysis", "graph_trace", "graph_diagnostics", "topological_plan", "workflow_state", "workflow_validate"}
WRITE_TOOLS = {"project_register", "project_rebind", "project_unregister", "project_migrate_json", "wave_initialize", "phase_record", "graph_apply", "plan_replace", "task_record_change", "review_record", "correction_record", "analysis_record", "workflow_mark_audited"}


def parse_frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        raise ValueError(f"{path} has no opening frontmatter delimiter")
    try:
        closing = lines.index("---", 1)
    except ValueError as error:
        raise ValueError(f"{path} has no closing frontmatter delimiter") from error
    frontmatter = {}
    for line in lines[1:closing]:
        key, separator, value = line.partition(":")
        if not separator:
            raise ValueError(f"{path} has invalid frontmatter line: {line}")
        frontmatter[key.strip()] = value.strip()
    return frontmatter


class ClaudePluginShapeTests(unittest.TestCase):
    def mcp_tool_names(self, tools: str) -> set[str]:
        tokens = {token.strip() for token in tools.split(",")}
        names = set()
        pattern = re.compile(r"mcp__plugin_bears-app-based-workflow_app-workflow__([a-z_]+)")
        for token in tokens:
            if token.startswith("mcp__"):
                matched = pattern.fullmatch(token)
                self.assertIsNotNone(matched, token)
                names.add(matched.group(1))
        return names

    def test_plugin_manifest_matches_codex_version_and_agent_paths(self) -> None:
        manifest = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
        codex_manifest = json.loads((ROOT / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
        agents = ["./claude/agents/app-worker.md", "./claude/agents/app-reviewer.md", "./claude/agents/app-analyst.md"]
        self.assertEqual(manifest["name"], "bears-app-based-workflow")
        self.assertEqual(manifest["version"], codex_manifest["version"])
        self.assertEqual(manifest["agents"], agents)
        self.assertTrue(all((ROOT / path).is_file() for path in agents))
        self.assertEqual(manifest["mcpServers"], "./claude/mcp.json")

    def test_marketplace_metadata_has_local_plugin_source(self) -> None:
        marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
        self.assertEqual(marketplace["name"], "bears-app-based-workflow")
        self.assertEqual(marketplace["plugins"][0]["name"], "bears-app-based-workflow")
        self.assertEqual(marketplace["plugins"][0]["source"], "./")

    def test_mcp_servers_have_claude_paths_and_split_modes(self) -> None:
        servers = json.loads((ROOT / "claude/mcp.json").read_text(encoding="utf-8"))["mcpServers"]
        self.assertEqual(set(servers), {"app-workflow", "app-workflow-maintainer"})
        for server in servers.values():
            self.assertEqual(server["command"], "python3")
            self.assertEqual(server["args"][0], "${CLAUDE_PLUGIN_ROOT}/scripts/app_workflow.py")
            self.assertNotIn("cwd", server)
        reader_args = servers["app-workflow"]["args"]
        maintainer_args = servers["app-workflow-maintainer"]["args"]
        self.assertEqual(reader_args[reader_args.index("--mode") + 1], "reader")
        self.assertEqual(maintainer_args[maintainer_args.index("--mode") + 1], "maintainer")

    def test_agent_frontmatter_enforces_role_tool_policies(self) -> None:
        frontmatters = {path.stem: parse_frontmatter(path) for path in (ROOT / "claude/agents").glob("*.md")}
        self.assertEqual(set(frontmatters), {"app-worker", "app-reviewer", "app-analyst"})
        for name, frontmatter in frontmatters.items():
            self.assertEqual(frontmatter["name"], name)
            self.assertTrue(frontmatter["description"])
            self.assertTrue(frontmatter["model"])
            self.assertNotIn("app-workflow-maintainer__", frontmatter["tools"])
            tokens = [token.strip() for token in frontmatter["tools"].split(",")]
            self.assertFalse(any(token.endswith(f"__{tool}") for token in tokens for tool in WRITE_TOOLS))

        worker_tokens = [token.strip() for token in frontmatters["app-worker"]["tools"].split(",")]
        self.assertNotIn("mcp__", frontmatters["app-worker"]["tools"])
        self.assertIn("Edit", worker_tokens)
        self.assertIn("Write", worker_tokens)

        reviewer_tokens = [token.strip() for token in frontmatters["app-reviewer"]["tools"].split(",")]
        self.assertEqual(self.mcp_tool_names(frontmatters["app-reviewer"]["tools"]), {"project_status", "graph_open", "dependency_slice", "impact_analysis", "workflow_state"})
        self.assertTrue(all(token not in {"Edit", "Write", "Bash"} for token in reviewer_tokens))

        analyst_tokens = [token.strip() for token in frontmatters["app-analyst"]["tools"].split(",")]
        self.assertEqual(self.mcp_tool_names(frontmatters["app-analyst"]["tools"]), READ_TOOLS - {"project_list"})
        self.assertTrue(all(token not in {"Edit", "Write", "Bash"} for token in analyst_tokens))

    def test_codex_and_claude_reader_tool_sets_match(self) -> None:
        namespace = "bears-app-based-workflow@bears-app-based-workflow"
        for name in ("app-reviewer", "app-analyst"):
            profile = tomllib.loads((ROOT / "agents" / f"{name}.toml").read_text(encoding="utf-8"))
            codex_tools = set(profile["plugins"][namespace]["mcp_servers"]["app-workflow"]["enabled_tools"])
            claude_tools = self.mcp_tool_names(parse_frontmatter(ROOT / "claude/agents" / f"{name}.md")["tools"])
            self.assertEqual(claude_tools, codex_tools)


if __name__ == "__main__":
    unittest.main()
