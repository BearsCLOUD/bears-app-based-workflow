---
name: codex-telegram-operator-gate
description: "Request an operator decision, Telegram inline choice, bounded safe file exchange, or feedback wait through the configured codex-telegram MCP server. This is a skill-driven MCP workflow, not a PreToolUse hook."
---

# Codex Telegram Operator Gate

Required: activate this skill when an operator decision, bounded inline choice, feedback wait, or safe file exchange must go through the configured `codex-telegram` MCP server.

## Hard rules

- This is a skill-driven MCP workflow. Do not register, enable, or rely on a Telegram `PreToolUse` hook gate.
- Call the configured MCP server `codex-telegram`; do not call Telegram Bot API or userbot APIs directly.
- Do not store or print bot tokens, MCP tokens, chat IDs, private chats, raw Telegram payloads, kubeconfigs, `.env` values, secrets, raw logs, or production data.
- Keep the dependent step paused only while waiting for operator feedback; unrelated safe work may continue.
- If the current Codex surface does not expose `codex-telegram` MCP tools, return `CODEX_TELEGRAM_MCP_UNAVAILABLE` with the exact missing tool names and a manual operator fallback packet. Do not create a hook or local proof-file substitute.

## MCP tool flow

1. Build a concise operator packet with: request id, decision needed, safe choices, dependent action, timeout, and redacted context.
2. For choices, call `telegram_request_operator_input` with bounded inline options.
3. For status-only messages, call `telegram_send_message` when exposed by the MCP server.
4. For file delivery, call `telegram_send_file` only with a safe filename and a bounded safe file.
5. For uploaded files, call `telegram_get_attachment` only for the exact `request_id` and `attachment_id`.
6. For delayed replies, call `telegram_wait_for_feedback` with a bounded timeout.
7. Continue the dependent action only after the MCP result explicitly approves or supplies the required feedback.

## Validation packet

Return this packet after the operator-gate action:

```text
mcp_server=codex-telegram
request_id=<id>
tools_used=<comma-separated-tool-names>
dependent_action=<short-action>
operator_result=<approved|rejected|timeout|unavailable>
values_read=false
raw_payloads_read=false
hook_used=false
```

## Ownership

- Skill owner: `/srv/bears/plugins/bears/skills/codex-telegram-operator-gate`.
- MCP runtime source: `/srv/bears/dev/app/codex-telegram`.
- Kubernetes desired state: `/srv/bears/kubernetes/manifests/codex-telegram-prod`.
- Legacy migration source only: `/srv/bears/plugins/codex-telegram-operator`.
