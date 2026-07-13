"""Validate authoritative JSON roles and the fixed safe TOML projection."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".github" / "runner"))
from bears_deploy.role_renderer import (  # noqa: E402
    RoleDefinitionError,
    render_directory,
    render_profile,
    validate_catalog,
    validate_definition,
)


class RoleProfileRendererTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = validate_catalog(json.loads((ROOT / "role-definitions/capability-catalog.v1.json").read_text()))
        cls.definitions = {
            path.stem: validate_definition(json.loads(path.read_text()), cls.catalog, expected_name=path.stem)
            for path in sorted((ROOT / "role-definitions").glob("*.json"))
            if path.name != "capability-catalog.v1.json"
        }

    def test_generated_profiles_are_current_and_deterministic(self) -> None:
        first = render_directory(ROOT, "0.3.2", check=True)
        second = render_directory(ROOT, "0.3.2", check=True)
        self.assertEqual(first, second)
        self.assertEqual(11, len(first["output_digests"]))
        self.assertNotIn("runtime-evidence-reader", self.definitions)
        self.assertIn("graph-evidence-reader", self.definitions)

    def test_safe_subset_has_no_raw_toml_or_network_escape(self) -> None:
        for name, definition in self.definitions.items():
            parsed = tomllib.loads(render_profile(definition, self.catalog, "0.3.2").decode())
            self.assertFalse(parsed["allow_login_shell"])
            self.assertEqual({"_default"}, set(parsed["apps"]))
            self.assertFalse(parsed["apps"]["_default"]["enabled"])
            if parsed["sandbox_mode"] == "workspace-write":
                self.assertFalse(parsed["sandbox_workspace_write"]["network_access"])
            plugin = parsed["plugins"]["bears-app-based-workflow@bears-app-based-workflow"]
            self.assertEqual({"app-graph", "app-graph-maintainer"}, set(plugin["mcp_servers"]))
            self.assertNotIn("mcp_servers", parsed)
            self.assertNotIn("config", parsed)
            self.assertNotIn("raw_toml", parsed)

    def test_exact_role_capability_matrix(self) -> None:
        def capabilities(name: str):
            value = self.definitions[name]["capability_requirements"]
            servers = {server["id"]: set(server["tools"]) for plugin in value["plugins"] for server in plugin["mcp_servers"]}
            skills = {skill for plugin in value["plugins"] for skill in plugin["skills"]}
            return set(value["native_tools"]), skills, servers
        native, skills, servers = capabilities("workflow-orchestrator")
        self.assertIn("request_user_input", native); self.assertEqual({"app-dev", "subagents"}, skills); self.assertEqual({}, servers)
        native, skills, servers = capabilities("domain-lane-orchestrator")
        self.assertEqual({"subagents", "app-context-index", "app-process-audit", "app-graph-compile"}, skills)
        self.assertEqual({"process_audit"}, servers["app-graph"])
        self.assertEqual({"process_record_event", "graph_compile"}, servers["app-graph-maintainer"])
        native, skills, servers = capabilities("graph-evidence-reader")
        self.assertEqual(set(), native); self.assertEqual(set(), skills); self.assertEqual(8, len(servers["app-graph"])); self.assertNotIn("app-graph-maintainer", servers)
        for name in ("app-worker", "worker"):
            self.assertEqual({"exec_command", "write_stdin", "apply_patch"}, capabilities(name)[0])
            self.assertEqual((set(), {}), capabilities(name)[1:])

    def test_unknown_fields_and_l3_maintainer_fail_closed(self) -> None:
        value = copy.deepcopy(self.definitions["worker"]); value["raw_toml"] = "network_access=true"
        with self.assertRaises(RoleDefinitionError): validate_definition(value, self.catalog)
        value = copy.deepcopy(self.definitions["worker"])
        value["capability_requirements"]["plugins"] = [{"id": "bears-app-based-workflow", "skills": [], "mcp_servers": [{"id": "app-graph-maintainer", "tools": ["graph_compile"]}]}]
        with self.assertRaises(RoleDefinitionError): validate_definition(value, self.catalog)


if __name__ == "__main__": unittest.main()
