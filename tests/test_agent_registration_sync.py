from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PLUGIN_ROOT / "scripts/agent_registration_sync.py"

spec = importlib.util.spec_from_file_location("agent_registration_sync", SCRIPT_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("cannot load scripts/agent_registration_sync.py")
agent_sync = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = agent_sync
spec.loader.exec_module(agent_sync)


class AgentRegistrationSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "home"
        self.repo = Path(self.tmp.name) / "repo"
        self.home.mkdir()
        self.repo.mkdir()

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                "python3",
                str(SCRIPT_PATH),
                *args,
                "--home",
                str(self.home),
                "--repo-root",
                str(self.repo),
            ],
            cwd=PLUGIN_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def _json(self, *args: str) -> dict[str, object]:
        result = self._run(*args, "--json")
        self.assertEqual(result.stderr, "")
        return json.loads(result.stdout)

    def _valid_agent_text(self, *, extra: str = "", name: str = "broken") -> str:
        return (
            f'name = "{name}"\n'
            f'description = "{name} role description"\n'
            'role_kind = "helper"\n'
            'execution_class = "helper"\n'
            "primary_eligible = true\n"
            'model = "gpt-5.5"\n'
            'model_reasoning_effort = "medium"\n'
            'sandbox_mode = "workspace-write"\n'
            f"{extra}"
            'developer_instructions = """\n'
            "Working mode:\n"
            f"- Operate as `{name}` with `sandbox_mode = \"workspace-write\"`.\n"
            "Scope/focus:\n"
            f"- Role override: {name} role description\n"
            "Forbidden actions:\n"
            "Quality checks:\n"
            "Return shape:\n"
            "Validation expectations:\n"
            '"""\n'
        )

    def test_validate_passes_for_canonical_agents(self) -> None:
        result = subprocess.run(
            ["python3", str(SCRIPT_PATH), "validate"],
            cwd=PLUGIN_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("agent registration sync ok", result.stdout)

    def test_validate_checks_platform_role_catalog_agent_alignment(self) -> None:
        agents, errors = agent_sync.load_canonical_agents()
        self.assertEqual(errors, [])
        self.assertEqual(agent_sync.validate_role_agent_alignment(agents), [])

    def test_canonical_agents_keep_shared_instruction_markers(self) -> None:
        agents, errors = agent_sync.load_canonical_agents()
        self.assertEqual(errors, [])
        self.assertGreater(len(agent_sync.REQUIRED_DEVELOPER_INSTRUCTION_MARKERS), 0)
        for agent in agents:
            data = tomllib.loads(agent.body)
            marker_errors = agent_sync.validate_developer_instruction_markers(
                agent.source_path,
                data["developer_instructions"],
            )
            self.assertEqual(marker_errors, [])

    def test_canonical_agents_keep_role_specific_instruction_overrides(self) -> None:
        agents, errors = agent_sync.load_canonical_agents()
        self.assertEqual(errors, [])
        for agent in agents:
            data = tomllib.loads(agent.body)
            override_errors = agent_sync.validate_developer_instruction_role_override(agent.source_path, data)
            self.assertEqual(override_errors, [])
            self.assertIn(
                f"{agent_sync.ROLE_OVERRIDE_PREFIX}{data['description']}",
                {line.strip() for line in data["developer_instructions"].splitlines()},
            )

    def test_sequential_role_audit_packet_covers_every_agent(self) -> None:
        agents, errors = agent_sync.load_canonical_agents()
        packet = agent_sync.build_role_audit_packet(agents, errors)
        self.assertEqual(packet["status"], "pass")
        self.assertEqual(packet["canonical_agents"], len(agents))
        self.assertEqual(packet["failed_agents"], 0)
        self.assertEqual(
            [item["agent_file"] for item in packet["sequence"]],
            sorted(item["agent_file"] for item in packet["sequence"]),
        )

    def test_audit_roles_cli_outputs_json_packet(self) -> None:
        result = subprocess.run(
            ["python3", str(SCRIPT_PATH), "audit-roles", "--json"],
            cwd=PLUGIN_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        packet = json.loads(result.stdout)
        self.assertEqual(packet["schema"], "bears-agent-role-audit.v1")
        self.assertEqual(packet["status"], "pass")
        self.assertGreater(packet["canonical_agents"], 0)

    def test_schema_validation_reports_missing_shared_instruction_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            agent_dir = Path(tmpdir)
            (agent_dir / "broken.toml").write_text(
                'name = "broken"\n'
                'description = "broken"\n'
                'role_kind = "helper"\n'
                'execution_class = "helper"\n'
                "primary_eligible = true\n"
                'model = "gpt-5.5"\n'
                'model_reasoning_effort = "medium"\n'
                'sandbox_mode = "workspace-write"\n'
                'developer_instructions = """\n'
                "Working mode:\n"
                "- Operate as `broken` with `sandbox_mode = \"workspace-write\"`.\n"
                "Scope/focus:\n"
                "- Role override: broken\n"
                "Forbidden actions:\n"
                "Quality checks:\n"
                "Return shape:\n"
                '"""\n',
                encoding="utf-8",
            )
            agents, errors = agent_sync.load_canonical_agents(agent_dir)
        self.assertEqual(len(agents), 1)
        joined = "\n".join(errors)
        self.assertIn(
            "missing required developer_instructions marker: Validation expectations:",
            joined,
        )

    def test_schema_validation_reports_missing_role_specific_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            agent_dir = Path(tmpdir)
            text = self._valid_agent_text().replace("- Role override: broken role description\n", "")
            (agent_dir / "broken.toml").write_text(text, encoding="utf-8")
            agents, errors = agent_sync.load_canonical_agents(agent_dir)
        self.assertEqual(len(agents), 1)
        self.assertIn(
            "broken.toml developer_instructions must include exact role description override",
            "\n".join(errors),
        )

    def test_schema_validation_reports_missing_exact_role_override_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            agent_dir = Path(tmpdir)
            text = self._valid_agent_text().replace(
                "- Role override: broken role description\n",
                "- broken role description\n",
            )
            (agent_dir / "broken.toml").write_text(text, encoding="utf-8")
            agents, errors = agent_sync.load_canonical_agents(agent_dir)
        self.assertEqual(len(agents), 1)
        self.assertIn(
            "broken.toml developer_instructions must include exact role override line: "
            "- Role override: broken role description",
            "\n".join(errors),
        )

    def test_schema_validation_reports_missing_role_name_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            agent_dir = Path(tmpdir)
            text = self._valid_agent_text().replace("- Operate as `broken`", "- Operate as `other`")
            (agent_dir / "broken.toml").write_text(text, encoding="utf-8")
            agents, errors = agent_sync.load_canonical_agents(agent_dir)
        self.assertEqual(len(agents), 1)
        self.assertIn(
            "broken.toml developer_instructions must include exact role marker: Operate as `broken`",
            "\n".join(errors),
        )

    def test_schema_validation_reports_missing_role_classification(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            agent_dir = Path(tmpdir)
            text = self._valid_agent_text().replace('execution_class = "helper"\n', "")
            (agent_dir / "broken.toml").write_text(text, encoding="utf-8")
            agents, errors = agent_sync.load_canonical_agents(agent_dir)
        self.assertEqual(len(agents), 1)
        self.assertIn("agents", str(agent_sync.CANONICAL_AGENT_DIR))
        self.assertIn("broken.toml missing required role classification field: execution_class", "\n".join(errors))

    def test_schema_validation_reports_invalid_role_classification(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            agent_dir = Path(tmpdir)
            text = self._valid_agent_text().replace('execution_class = "helper"', 'execution_class = "runtime"')
            text = text.replace("primary_eligible = true", 'primary_eligible = "yes"')
            (agent_dir / "broken.toml").write_text(text, encoding="utf-8")
            agents, errors = agent_sync.load_canonical_agents(agent_dir)
        self.assertEqual(len(agents), 1)
        joined = "\n".join(errors)
        self.assertIn("execution_class must be one of", joined)
        self.assertIn("primary_eligible must be boolean", joined)

    def test_role_catalog_alignment_reports_missing_agent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            catalog_path = Path(tmpdir) / "platform-role-catalog.v1.json"
            catalog_path.write_text(
                json.dumps(
                    {
                        "roles": [{"name": "missing-platform-role"}],
                        "platform_parts": [{"required_role": "missing-platform-role"}],
                        "workflow_routes": [],
                        "route_regression_checks": [],
                    }
                ),
                encoding="utf-8",
            )
            errors = agent_sync.validate_role_agent_alignment([], catalog_path)

        joined = "\n".join(errors)
        self.assertIn("platform role missing-platform-role has no canonical agent TOML", joined)
        self.assertIn("platform role reference missing-platform-role has no canonical agent TOML", joined)

    def test_role_catalog_alignment_reports_undeclared_reference(self) -> None:
        agents, errors = agent_sync.load_canonical_agents()
        self.assertEqual(errors, [])
        with tempfile.TemporaryDirectory() as tmpdir:
            catalog_path = Path(tmpdir) / "platform-role-catalog.v1.json"
            catalog_path.write_text(
                json.dumps(
                    {
                        "roles": [],
                        "platform_parts": [{"required_role": agents[0].destination_name}],
                        "workflow_routes": [],
                        "route_regression_checks": [],
                    }
                ),
                encoding="utf-8",
            )
            errors = agent_sync.validate_role_agent_alignment(agents, catalog_path)

        self.assertIn(
            f"platform role reference {agents[0].destination_name} is not declared in catalog roles",
            errors,
        )

    def test_role_catalog_alignment_rejects_role_backed_classification_mismatch(self) -> None:
        agents, errors = agent_sync.load_canonical_agents()
        self.assertEqual(errors, [])
        catalog = json.loads((PLUGIN_ROOT / "assets/catalog/platform-role-catalog.v1.json").read_text(encoding="utf-8"))
        catalog = copy.deepcopy(catalog)
        for role in catalog["roles"]:
            if role["name"] == "bears-git-workflow-helper":
                role["execution_class"] = "specialist"
                break
        with tempfile.TemporaryDirectory() as tmpdir:
            catalog_path = Path(tmpdir) / "platform-role-catalog.v1.json"
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
            errors = agent_sync.validate_role_agent_alignment(agents, catalog_path)
        self.assertTrue(
            any(
                "agents/bears-git-workflow-helper.toml execution_class 'helper' must match" in error
                for error in errors
            )
        )

    def test_role_catalog_alignment_rejects_profile_mapping_classification_mismatch(self) -> None:
        agents, errors = agent_sync.load_canonical_agents()
        self.assertEqual(errors, [])
        catalog = json.loads((PLUGIN_ROOT / "assets/catalog/platform-role-catalog.v1.json").read_text(encoding="utf-8"))
        catalog = copy.deepcopy(catalog)
        target_file = catalog["agent_profile_mappings"][0]["agent_file"]
        catalog["agent_profile_mappings"][0]["execution_class"] = "specialist"
        with tempfile.TemporaryDirectory() as tmpdir:
            catalog_path = Path(tmpdir) / "platform-role-catalog.v1.json"
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
            errors = agent_sync.validate_role_agent_alignment(agents, catalog_path)
        self.assertTrue(
            any(f"{target_file} execution_class 'helper' must match" in error for error in errors)
        )

    def test_check_empty_user_target_reports_missing(self) -> None:
        packet = self._json("check", "--target", "user")
        self.assertEqual(packet["status"], "fail")
        self.assertEqual(packet["target"], "user")
        self.assertGreater(packet["canonical_agents"], 0)
        self.assertEqual(packet["registered_agents"], 0)
        self.assertGreater(len(packet["missing"]), 0)
        for key in ("missing", "stale", "extra", "local_edits", "schema_errors", "sync_command"):
            self.assertIn(key, packet)

    def test_tenant_registry_role_is_catalog_referenced_and_materialized(self) -> None:
        role_name = "bears-tenant-registry-platform-engineer"
        role_file = f"{role_name}.toml"
        agents, errors = agent_sync.load_canonical_agents()
        self.assertEqual(errors, [])
        agent_names = {agent.destination_name for agent in agents}
        self.assertIn(role_name, agent_names)

        declared_roles, referenced_roles, catalog_errors = agent_sync.load_platform_role_catalog_roles()
        self.assertEqual(catalog_errors, [])
        self.assertIn(role_name, declared_roles)
        self.assertIn(role_name, referenced_roles)

        missing_packet = self._json("check", "--target", "user")
        self.assertEqual(missing_packet["status"], "fail")
        self.assertIn(role_file, missing_packet["missing"])
        self.assertEqual(
            missing_packet["sync_command"],
            "python3 scripts/agent_registration_sync.py sync --target user",
        )

        sync_packet = self._json("sync", "--target", "user")
        self.assertEqual(sync_packet["status"], "pass")
        self.assertNotIn(role_file, sync_packet["missing"])
        target = self.home / ".codex" / "agents" / role_file
        self.assertTrue(target.is_file())
        self.assertIn(f'name = "{role_name}"', target.read_text(encoding="utf-8"))

    def test_sync_user_target_is_idempotent(self) -> None:
        sync_packet = self._json("sync", "--target", "user")
        self.assertEqual(sync_packet["status"], "pass")
        self.assertEqual(sync_packet["canonical_agents"], sync_packet["registered_agents"])
        checkpoint = sync_packet["runtime_tool_schema_checkpoint"]
        self.assertEqual(checkpoint["status"], agent_sync.TOOL_SCHEMA_REFRESH_REQUIRED_STATUS)
        self.assertTrue(checkpoint["disk_registration_only"])
        self.assertFalse(checkpoint["active_tool_schema_verified"])
        self.assertFalse(checkpoint["retry_direct_spawn_before_refresh_allowed"])
        self.assertTrue(checkpoint["unavailable_agent_type_cache_required"])
        self.assertIn("multi_agent tool schema", checkpoint["operator_message"])

        check_packet = self._json("check", "--target", "user")
        self.assertEqual(check_packet["status"], "pass")
        self.assertEqual(check_packet["missing"], [])
        self.assertEqual(check_packet["stale"], [])

    def test_text_output_names_runtime_tool_schema_checkpoint(self) -> None:
        result = self._run("check", "--target", "user")
        self.assertIn("runtime_tool_schema_checkpoint: runtime_tool_schema_refresh_required", result.stdout)
        self.assertIn("retry_direct_spawn_before_refresh_allowed: false", result.stdout)

    def test_repo_target_writes_repo_codex_agents(self) -> None:
        packet = self._json("sync", "--target", "repo")
        self.assertEqual(packet["status"], "pass")
        target_dir = self.repo / ".codex" / "agents"
        self.assertTrue(target_dir.is_dir())
        self.assertGreater(len(list(target_dir.glob("*.toml"))), 0)

    def test_stale_managed_file_is_reported_and_rewritten(self) -> None:
        self._json("sync", "--target", "user")
        agents, errors = agent_sync.load_canonical_agents()
        self.assertEqual(errors, [])
        target = self.home / ".codex" / "agents" / agents[0].destination_file
        target.write_text(target.read_text(encoding="utf-8") + "\n# stale\n", encoding="utf-8")

        check_packet = self._json("check", "--target", "user")
        self.assertEqual(check_packet["status"], "fail")
        self.assertIn(agents[0].destination_file, check_packet["stale"])

        sync_packet = self._json("sync", "--target", "user")
        self.assertEqual(sync_packet["status"], "pass")
        self.assertNotIn("# stale", target.read_text(encoding="utf-8"))

    def test_unmanaged_local_file_blocks_sync(self) -> None:
        agents, errors = agent_sync.load_canonical_agents()
        self.assertEqual(errors, [])
        target_dir = self.home / ".codex" / "agents"
        target_dir.mkdir(parents=True)
        target = target_dir / agents[0].destination_file
        target.write_text('name = "local"\ndescription = "local"\n', encoding="utf-8")

        check_packet = self._json("check", "--target", "user")
        self.assertEqual(check_packet["status"], "fail")
        self.assertIn(agents[0].destination_file, check_packet["local_edits"])

        result = self._run("sync", "--target", "user")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unmanaged target files block sync", result.stderr)
        self.assertEqual(target.read_text(encoding="utf-8"), 'name = "local"\ndescription = "local"\n')

    def test_managed_extra_with_existing_source_still_blocks_sync(self) -> None:
        self._json("sync", "--target", "user")
        agents, errors = agent_sync.load_canonical_agents()
        self.assertEqual(errors, [])
        rogue = self.home / ".codex" / "agents" / "rogue-extra.toml"
        rogue.write_text(
            "# Generated by Bears agent_registration_sync.py.\n"
            f"# Source-Path: agents/{agents[0].source_path.name}\n"
            f"# Source-Digest-SHA256: {agents[0].digest}\n"
            f"# Managed-Digest-SHA256: {agents[0].digest}\n\n"
            + agents[0].body,
            encoding="utf-8",
        )

        packet = self._json("check", "--target", "user")
        self.assertEqual(packet["status"], "fail")
        self.assertIn("rogue-extra.toml", packet["extra"])

        result = self._run("sync", "--target", "user")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stale managed target files block sync cleanup", result.stderr)

    def test_extra_managed_file_blocks_sync(self) -> None:
        target_dir = self.home / ".codex" / "agents"
        target_dir.mkdir(parents=True)
        extra = target_dir / "removed-bears-agent.toml"
        extra.write_text(
            "# Generated by Bears agent_registration_sync.py.\n"
            "# Source-Path: agents/removed-bears-agent.toml\n"
            "# Source-Digest-SHA256: 0\n"
            "# Managed-Digest-SHA256: 0\n\n"
            'name = "removed-bears-agent"\n'
            'description = "removed"\n'
            'developer_instructions = "removed"\n',
            encoding="utf-8",
        )

        packet = self._json("check", "--target", "user")
        self.assertEqual(packet["status"], "fail")
        self.assertIn("removed-bears-agent.toml", packet["extra"])

        result = self._run("sync", "--target", "user")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stale managed target files block sync cleanup", result.stderr)

    def test_schema_validation_reports_missing_codex_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            agent_dir = Path(tmpdir)
            (agent_dir / "broken.toml").write_text('name = "broken"\n', encoding="utf-8")
            agents, errors = agent_sync.load_canonical_agents(agent_dir)
        self.assertEqual(len(agents), 1)
        joined = "\n".join(errors)
        self.assertIn("missing required Codex custom-agent field: description", joined)
        self.assertIn("missing required Codex custom-agent field: developer_instructions", joined)


if __name__ == "__main__":
    unittest.main()
