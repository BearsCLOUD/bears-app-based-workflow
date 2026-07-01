from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PLUGIN_ROOT / "scripts" / "agentic_enterprise_workflow.py"
WORKFLOW_PATH = PLUGIN_ROOT / "assets" / "catalog" / "agentic-enterprise-workflow.v1.json"
WORKFLOW_SCHEMA_PATH = PLUGIN_ROOT / "assets" / "schemas" / "agentic-enterprise-workflow.v1.schema.json"
SUBAGENT_POLICY_PATH = PLUGIN_ROOT / "assets" / "catalog" / "subagent-orchestration-policy.v1.json"
SPEC = importlib.util.spec_from_file_location("agentic_enterprise_workflow", SCRIPT_PATH)
assert SPEC is not None
WORKFLOW_MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(WORKFLOW_MODULE)


def run_hook(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "hook-decision", *args],
        cwd=PLUGIN_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


class AgenticEnterpriseWorkflowHookTests(unittest.TestCase):
    def decision(self, *args: str) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        result = run_hook(*args)
        self.assertEqual(result.stderr, "")
        return result, json.loads(result.stdout)

    def test_over_five_minute_scope_denied(self) -> None:
        result, packet = self.decision("--event", "PreTask", "--agent-layer", "l1", "--duration-min", "6")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(packet["decision"], "deny")
        self.assertEqual(packet["control_reason"], "hard_split_threshold_exceeded")
        self.assertIn("hard_split_threshold_exceeded", packet["reason"])

    def test_token_over_budget_denied(self) -> None:
        result, packet = self.decision("--event", "PreTask", "--agent-layer", "l1", "--token-budget", "12001")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(packet["decision"], "deny")
        self.assertEqual(packet["control_reason"], "token_budget_over_policy")
        self.assertIn("token_budget_over_policy", packet["reason"])

    def test_pretool_over_five_minute_scope_denied(self) -> None:
        result, packet = self.decision(
            "--event",
            "PreToolUse",
            "--agent-layer",
            "l3",
            "--scope-id",
            "scope-a",
            "--tool-name",
            "implementation_tool",
            "--duration-min",
            "6",
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(packet["decision"], "deny")
        self.assertEqual(packet["control_reason"], "hard_split_threshold_exceeded")

    def test_over_five_minute_scope_allowed_only_after_split_started(self) -> None:
        result, packet = self.decision(
            "--event",
            "PreTask",
            "--agent-layer",
            "l1",
            "--duration-min",
            "6",
            "--split-state",
            "split_started",
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(packet["decision"], "allow")
        self.assertEqual(packet["control_status"], "armed")

    def test_pretool_token_spend_over_budget_denied(self) -> None:
        result, packet = self.decision(
            "--event",
            "PreToolUse",
            "--agent-layer",
            "l3",
            "--scope-id",
            "scope-a",
            "--tool-name",
            "implementation_tool",
            "--token-spend",
            "12001",
        )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(packet["decision"], "deny")
        self.assertEqual(packet["control_reason"], "token_budget_over_policy")

    def test_hooks_json_wires_required_scripts(self) -> None:
        self.assertEqual(WORKFLOW_MODULE.validate_hook_wiring(), [])

    def test_missing_pretool_hook_wiring_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hooks_path = Path(tmp) / "hooks.json"
            packet = json.loads((PLUGIN_ROOT / "hooks.json").read_text(encoding="utf-8"))
            packet["hooks"]["PreToolUse"][0]["hooks"][0]["command"] = "python3 wrong.py"
            hooks_path.write_text(json.dumps(packet), encoding="utf-8")
            errors = WORKFLOW_MODULE.validate_hook_wiring(hooks_path)
        self.assertIn("hooks.json.PreToolUse.hooks[0].command must call hooks/pre_tool_policy.py", errors)

    def test_missing_metadata_allows_only_for_unmanaged_layer(self) -> None:
        result, packet = self.decision("--event", "PreTask", "--agent-layer", "unknown")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(packet["decision"], "allow")
        self.assertEqual(packet["control_status"], "control_not_armed")
        self.assertEqual(packet["control_reason"], "missing_scope_time_token_metadata")
        self.assertEqual(packet["warnings"][0]["code"], "control_not_armed")

    def test_governed_l1_missing_metadata_is_denied(self) -> None:
        result, packet = self.decision("--event", "PreTask", "--agent-layer", "l1")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(packet["decision"], "deny")
        self.assertEqual(packet["control_status"], "enforced")
        self.assertEqual(packet["control_reason"], "missing_scope_time_token_metadata")

    def test_hook_wrapper_creates_runtime_state_without_global_duration_block(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            result = subprocess.run(
                [sys.executable, str(PLUGIN_ROOT / "hooks" / "pre_task_guard.py")],
                input=json.dumps({"state_path": str(state_path)}),
                cwd=PLUGIN_ROOT / "hooks",
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(result.stderr, "")
            packet = json.loads(result.stdout)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(set(packet), {"hookSpecificOutput"})
            self.assertEqual(packet["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")
            state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual(state["schema"], "bears-agentic-enterprise-runtime-state.v1")
        self.assertEqual(state["agent_layer"], "l1")
        self.assertEqual(state["split_state"], "none")

    def test_hook_wrapper_does_not_treat_stale_session_age_as_scope_time(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            state_path.write_text(
                json.dumps(
                    {
                        "schema": "bears-agentic-enterprise-runtime-state.v1",
                        "agent_layer": "l1",
                        "state_created_by_hook": True,
                        "started_at_epoch": 1,
                        "duration_min": 0,
                        "token_budget": 12000,
                        "split_state": "none",
                        "workflow_block": {"block_goal_run": False},
                        "scopes": [],
                    }
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(PLUGIN_ROOT / "hooks" / "pre_task_guard.py")],
                input=json.dumps({"state_path": str(state_path)}),
                cwd=PLUGIN_ROOT / "hooks",
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        packet = json.loads(result.stdout)
        self.assertEqual(packet["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")

    def test_session_start_hook_stdout_uses_current_codex_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            result = subprocess.run(
                [sys.executable, str(PLUGIN_ROOT / "hooks" / "session_start.py")],
                input=json.dumps({"state_path": str(state_path), "source": "startup"}),
                cwd=PLUGIN_ROOT / "hooks",
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stderr, "")
        packet = json.loads(result.stdout)
        self.assertEqual(set(packet), {"hookSpecificOutput"})
        self.assertEqual(packet["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.assertIsInstance(packet["hookSpecificOutput"].get("additionalContext"), str)

    def test_user_prompt_submit_block_has_non_empty_reason(self) -> None:
        result = subprocess.run(
            [sys.executable, str(PLUGIN_ROOT / "hooks" / "pre_task_guard.py")],
            input=json.dumps({"agent_layer": "l1", "token_budget": 12001}),
            cwd=PLUGIN_ROOT / "hooks",
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        packet = json.loads(result.stdout)
        self.assertEqual(packet["decision"], "block")
        self.assertTrue(packet["reason"])
        self.assertEqual(packet["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")
        self.assertIn(packet["reason"], result.stderr)

    def test_pretooluse_deny_has_reason_and_stderr_fallback(self) -> None:
        result = subprocess.run(
            [sys.executable, str(PLUGIN_ROOT / "hooks" / "pre_tool_policy.py")],
            input=json.dumps({"agent_layer": "l1", "tool_name": "mcp__unsafe__read_secret"}),
            cwd=PLUGIN_ROOT / "hooks",
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        packet = json.loads(result.stdout)
        self.assertEqual(set(packet), {"hookSpecificOutput"})
        hook_output = packet["hookSpecificOutput"]
        self.assertEqual(hook_output["hookEventName"], "PreToolUse")
        self.assertEqual(hook_output["permissionDecision"], "deny")
        self.assertTrue(hook_output["permissionDecisionReason"])
        self.assertIn(hook_output["permissionDecisionReason"], result.stderr)

    def test_l1_high_risk_tool_prefix_deny_still_works(self) -> None:
        result, packet = self.decision("--event", "PreToolUse", "--agent-layer", "l1", "--tool-name", "tool_search")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(packet["decision"], "deny")
        self.assertIn("L1 tool denied: tool_search", packet["reason"])

    def test_l1_normal_local_tool_is_allowed(self) -> None:
        result, packet = self.decision(
            "--event",
            "PreToolUse",
            "--agent-layer",
            "l1",
            "--tool-name",
            "Bash",
            "--duration-min",
            "1",
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(packet["decision"], "allow")

    def test_l2_l3_without_scope_id_denied(self) -> None:
        for layer in ("l2", "l3"):
            with self.subTest(layer=layer):
                result, packet = self.decision("--event", "PreTask", "--agent-layer", layer)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(packet["decision"], "deny")
                self.assertIn(f"{layer.upper()} requires scope_id", packet["reason"])

    def test_compact_state_over_five_minute_scope_denied(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            state_path.write_text(
                json.dumps({"active_scope": {"scope_id": "scope-a", "duration_min": 6}}),
                encoding="utf-8",
            )
            result, packet = self.decision(
                "--event",
                "PreTask",
                "--agent-layer",
                "l1",
                "--scope-id",
                "scope-a",
                "--state",
                str(state_path),
            )
        self.assertEqual(result.returncode, 2)
        self.assertEqual(packet["control_reason"], "hard_split_threshold_exceeded")


class AgenticEnterpriseWorkflowGoalModeTests(unittest.TestCase):
    def workflow(self) -> dict[str, object]:
        return json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))

    def workflow_schema(self) -> dict[str, object]:
        return json.loads(WORKFLOW_SCHEMA_PATH.read_text(encoding="utf-8"))

    def workflow_errors(self, workflow: dict[str, object]) -> list[str]:
        return WORKFLOW_MODULE.validate_workflow(workflow)

    def test_catalog_contains_required_goal_agent_modes(self) -> None:
        workflow = self.workflow()
        errors = self.workflow_errors(workflow)
        self.assertFalse([error for error in errors if error.startswith("goal_agent_modes")])

    def test_schema_contains_goal_agent_mode_contract(self) -> None:
        schema = self.workflow_schema()
        self.assertIn("goal_agent_modes", schema["required"])
        modes = schema["properties"]["goal_agent_modes"]
        self.assertFalse(modes["additionalProperties"])
        self.assertEqual(set(modes["required"]), {"goal_1_agent", "goal_parallel_l1"})
        self.assertEqual(
            modes["properties"]["goal_1_agent"]["properties"]["required_sequence"]["const"],
            WORKFLOW_MODULE.REQUIRED_GOAL_1_AGENT_SEQUENCE,
        )
        self.assertEqual(
            modes["properties"]["goal_parallel_l1"]["properties"]["required_sequence"]["const"],
            WORKFLOW_MODULE.REQUIRED_GOAL_PARALLEL_L1_SEQUENCE,
        )

    def test_missing_goal_mode_fails(self) -> None:
        workflow = self.workflow()
        modes = copy.deepcopy(workflow["goal_agent_modes"])
        del modes["goal_parallel_l1"]
        workflow["goal_agent_modes"] = modes
        errors = self.workflow_errors(workflow)
        self.assertEqual(errors, ["goal_agent_modes must contain exactly: goal_1_agent, goal_parallel_l1"])

    def test_extra_goal_mode_fails(self) -> None:
        workflow = self.workflow()
        workflow["goal_agent_modes"]["goal_extra"] = {}
        errors = self.workflow_errors(workflow)
        self.assertEqual(errors, ["goal_agent_modes must contain exactly: goal_1_agent, goal_parallel_l1"])

    def test_state_first_sequence_is_required(self) -> None:
        workflow = self.workflow()
        workflow["goal_agent_modes"]["goal_1_agent"]["required_sequence"] = [
            "research",
            "create_own_state_file",
        ]
        errors = self.workflow_errors(workflow)
        self.assertIn("goal_agent_modes.goal_1_agent.required_sequence must be exact and ordered", errors)
        self.assertIn(
            "goal_agent_modes.goal_1_agent.required_sequence must start with create_own_state_file",
            errors,
        )

    def test_subagent_spawn_requires_no_parent_context(self) -> None:
        workflow = self.workflow()
        workflow["goal_agent_modes"]["goal_1_agent"]["subagent_spawn_policy"]["fork_context"] = True
        workflow["goal_agent_modes"]["goal_parallel_l1"]["l2_spawn"]["parent_context"] = "parent"
        errors = self.workflow_errors(workflow)
        self.assertIn("goal_agent_modes.goal_1_agent.subagent_spawn_policy.fork_context must be false", errors)
        self.assertIn("goal_agent_modes.goal_parallel_l1.l2_spawn.parent_context must be none", errors)

    def test_helper_usage_is_required(self) -> None:
        workflow = self.workflow()
        workflow["goal_agent_modes"]["goal_1_agent"]["helper_agents"]["required"] = False
        workflow["goal_agent_modes"]["goal_parallel_l1"]["l2_helper_agents"]["purposes"] = []
        errors = self.workflow_errors(workflow)
        self.assertIn("goal_agent_modes.goal_1_agent.helper_agents.required must be true", errors)
        self.assertIn("goal_agent_modes.goal_parallel_l1.l2_helper_agents.purposes must be exact and ordered", errors)

    def test_parallel_l1_must_not_track_or_wait_for_l2_after_spawn(self) -> None:
        workflow = self.workflow()
        workflow["goal_agent_modes"]["goal_parallel_l1"]["l2_spawn"]["l1_tracks_l2_after_spawn"] = True
        workflow["goal_agent_modes"]["goal_parallel_l1"]["l2_spawn"]["l1_waits_for_l2_after_spawn"] = True
        workflow["goal_agent_modes"]["goal_parallel_l1"]["required_sequence"].append("wait_for_l2_completion")
        errors = self.workflow_errors(workflow)
        self.assertIn("goal_agent_modes.goal_parallel_l1.l2_spawn.l1_tracks_l2_after_spawn must be false", errors)
        self.assertIn("goal_agent_modes.goal_parallel_l1.l2_spawn.l1_waits_for_l2_after_spawn must be false", errors)
        self.assertIn(
            "goal_agent_modes.goal_parallel_l1.required_sequence must not include L1 L2 tracking or waiting after spawn",
            errors,
        )

    def test_repo_domain_l2_roles_have_agent_files(self) -> None:
        workflow = self.workflow()
        for domain in workflow["repo_domains"]:
            role = domain["primary_l2_role"]
            with self.subTest(domain=domain["id"]):
                self.assertTrue((PLUGIN_ROOT / "agents" / f"{role}.toml").is_file())

    def test_repo_domain_l2_roles_are_delegation_controllers(self) -> None:
        workflow = self.workflow()
        subagent_policy = json.loads(SUBAGENT_POLICY_PATH.read_text(encoding="utf-8"))
        controller_roles = {
            controller["role"]
            for controller in subagent_policy["orchestration_model"]["delegation_controller_roles"]
        }
        for domain in workflow["repo_domains"]:
            with self.subTest(domain=domain["id"]):
                self.assertIn(domain["primary_l2_role"], controller_roles)


if __name__ == "__main__":
    unittest.main()
