# MCP Agent Policy

## Purpose

`assets/catalog/mcp-agent-policy.v1.json` is the Bears default-deny policy for MCP tool access by agent profile.

## Hard rules

- All MCP tools are denied by default through `mcp_*: deny`.
- A tool can be allowed only when both the profile policy and a decision packet allow the exact tool.
- Missing decision packet, unknown profile, or unknown tool means deny.
- GitHub mutation tools are denied for every profile except the `bears_closeout_gate` profile with a passing closeout gate.
- `oc_research_shard` receives no MCP access unless the decision packet has an explicit read-only allowlist.
- Command output is JSON only.

## Commands

```bash
python3 scripts/mcp_agent_policy.py validate
python3 scripts/mcp_agent_policy.py decide --packet runtime/example-mcp-decision.json
python3 scripts/mcp_agent_policy.py render-opencode-permissions --packet runtime/example-mcp-decision.json
python3 scripts/mcp_agent_policy.py doctor
```

## Decision packet

```json
{
  "schema": "bears-mcp-agent-policy-decision-packet.v1",
  "profile_id": "bears_implementation_worker",
  "requested_tools": ["mcp__context7__get-library-docs"],
  "allowed_mcp_tools": ["mcp__context7__get-library-docs"]
}
```

Research packets must declare `explicit_read_only_allowlist` instead of a broad allow field.

```json
{
  "schema": "bears-mcp-agent-policy-decision-packet.v1",
  "profile_id": "oc_research_shard",
  "requested_tools": ["mcp__github__get_issue"],
  "explicit_read_only_allowlist": ["mcp__github__get_issue"]
}
```

Closeout packets must include a passing closeout gate before GitHub mutation tools can be allowed.

```json
{
  "schema": "bears-mcp-agent-policy-decision-packet.v1",
  "profile_id": "bears_closeout_gate",
  "requested_tools": ["mcp__github__add_issue_comment"],
  "allowed_mcp_tools": ["mcp__github__add_issue_comment"],
  "closeout_gate": {
    "gate": "closeout",
    "status": "pass",
    "proof_ref": "runtime/local-commit-validation/<sha>.json"
  }
}
```

## OpenCode permissions

`render-opencode-permissions` emits a permission fragment with `mcp_*: deny` plus exact allowed tool IDs. Denied tools are not rendered as allows.
