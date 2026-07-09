from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts import mcp_agent_policy


class McpAgentPolicyTest(unittest.TestCase):
    def test_catalog_validates(self) -> None:
        self.assertEqual(mcp_agent_policy.validate_catalog(), [])

    def test_unknown_profile_denies_requested_tool(self) -> None:
        result = mcp_agent_policy.decide({
            "schema": "bears-mcp-agent-policy-decision-packet.v1",
            "profile_id": "missing",
            "requested_tools": ["mcp__context7__get-library-docs"],
            "allowed_mcp_tools": ["mcp__context7__get-library-docs"],
        })
        self.assertEqual(result["status"], "deny")
        self.assertEqual(result["decisions"][0]["reason"], "unknown_profile")

    def test_implementation_requires_decision_packet_allowlist(self) -> None:
        result = mcp_agent_policy.decide({
            "schema": "bears-mcp-agent-policy-decision-packet.v1",
            "profile_id": "bears_implementation_worker",
            "requested_tools": ["mcp__context7__get-library-docs"],
            "allowed_mcp_tools": [],
        })
        self.assertEqual(result["status"], "deny")
        self.assertEqual(result["decisions"][0]["reason"], "missing_decision_packet_allowlist")

    def test_implementation_allows_profile_and_decision_packet_match(self) -> None:
        result = mcp_agent_policy.decide({
            "schema": "bears-mcp-agent-policy-decision-packet.v1",
            "profile_id": "bears_implementation_worker",
            "requested_tools": ["mcp__context7__get-library-docs"],
            "allowed_mcp_tools": ["mcp__context7__get-library-docs"],
        })
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["allowed_tools"], ["mcp__context7__get-library-docs"])

    def test_github_mutation_denied_without_closeout_gate(self) -> None:
        result = mcp_agent_policy.decide({
            "schema": "bears-mcp-agent-policy-decision-packet.v1",
            "profile_id": "bears_implementation_worker",
            "requested_tools": ["mcp__github__create_issue"],
            "allowed_mcp_tools": ["mcp__github__create_issue"],
        })
        self.assertEqual(result["status"], "deny")
        self.assertEqual(result["decisions"][0]["reason"], "github_mutation_denied_except_closeout_gate")

    def test_github_mutation_allowed_only_for_closeout_gate(self) -> None:
        result = mcp_agent_policy.decide({
            "schema": "bears-mcp-agent-policy-decision-packet.v1",
            "profile_id": "bears_closeout_gate",
            "requested_tools": ["mcp__github__add_issue_comment"],
            "allowed_mcp_tools": ["mcp__github__add_issue_comment"],
            "closeout_gate": {
                "gate": "closeout",
                "status": "pass",
                "proof_ref": "runtime/local-commit-validation/HEAD.json",
            },
        })
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["decisions"][0]["reason"], "github_closeout_gate_passed")

    def test_research_shard_denies_without_explicit_read_only_allowlist(self) -> None:
        result = mcp_agent_policy.decide({
            "schema": "bears-mcp-agent-policy-decision-packet.v1",
            "profile_id": "oc_research_shard",
            "requested_tools": ["mcp__github__get_issue"],
            "allowed_mcp_tools": ["mcp__github__get_issue"],
        })
        self.assertEqual(result["status"], "deny")
        self.assertEqual(result["decisions"][0]["reason"], "missing_explicit_read_only_allowlist")

    def test_research_shard_allows_explicit_read_only_tool(self) -> None:
        result = mcp_agent_policy.decide({
            "schema": "bears-mcp-agent-policy-decision-packet.v1",
            "profile_id": "oc_research_shard",
            "requested_tools": ["mcp__github__get_issue"],
            "explicit_read_only_allowlist": ["mcp__github__get_issue"],
        })
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["allowed_tools"], ["mcp__github__get_issue"])

    def test_render_opencode_permissions_keeps_default_deny(self) -> None:
        result = mcp_agent_policy.render_opencode_permissions({
            "schema": "bears-mcp-agent-policy-decision-packet.v1",
            "profile_id": "bears_implementation_worker",
            "requested_tools": ["mcp__context7__get-library-docs", "mcp__github__create_issue"],
            "allowed_mcp_tools": ["mcp__context7__get-library-docs", "mcp__github__create_issue"],
        })
        self.assertEqual(result["permission"]["mcp_*"], "deny")
        self.assertEqual(result["permission"]["mcp__context7__get-library-docs"], "allow")
        self.assertNotIn("mcp__github__create_issue", result["permission"])

    def test_cli_outputs_json_for_decide(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            packet_path = Path(tmp) / "packet.json"
            packet_path.write_text(json.dumps({
                "schema": "bears-mcp-agent-policy-decision-packet.v1",
                "profile_id": "bears_implementation_worker",
                "requested_tools": ["mcp__context7__get-library-docs"],
                "allowed_mcp_tools": ["mcp__context7__get-library-docs"],
            }), encoding="utf-8")
            completed = subprocess.run(
                ["python3", "scripts/mcp_agent_policy.py", "decide", "--packet", str(packet_path)],
                cwd=Path(__file__).resolve().parents[1],
                check=True,
                text=True,
                stdout=subprocess.PIPE,
            )
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["schema"], "bears-mcp-agent-policy-decision-result.v1")
        self.assertEqual(payload["status"], "pass")


if __name__ == "__main__":
    unittest.main()
