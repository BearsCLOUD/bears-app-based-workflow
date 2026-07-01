# Bears Platform and Telegram Workflow Router

## Decision matrix

| Task signal | Primary skill | Required output |
| --- | --- | --- |
| "auth", "auth_core", "session", "MFA", "RBAC", "agreement", "gateway", "route", "platform part" | `$platform-role-governance` | Selected specialist role or `ROLE_COVERAGE_BLOCKER` |
| "rewrite bot", "aiogram", "dispatcher", "router", "FSM", "webhook" | `$telegram-aiogram-migration` | Migration backlog item, readiness packet, and test plan |
| "format message", "MarkdownV2", "HTML", "keyboard", "callback", "command menu" | `$telegram-quality-testing` | Rendering policy, callback contract, and test matrix |
| "create skill", "plugin skill", "workflow in plugin", "agents should know when" | `$telegram-plugin-skill-factory` | Skill lifecycle packet, updated skill, validation logs |
| "which Telegram surface owns this?" | `$bears-telegram-workflow` | Surface classification and owner handoff |
| "Infisical", "Kubernetes Secret", "tdlib-runtime", "Bot API server", "Telegram user auth", "QR login", "session file" | `$bears-telegram-workflow` plus `references/telegram-infisical-kubernetes-map.md` | Safe location map, presence probes, and operator-gated auth helper command |
| Live bot action, webhook, production runtime | Local project rules plus runtime evidence | Read-only proof first; mutation only after explicit approval |

## Handoff packet

For every platform or Telegram task, produce this packet before broad edits:

```yaml
surface: <service/bot/package/path>
owning_project: <repo or project group>
operator_goal: <short outcome>
platform_part: <catalog platform_parts.name or unknown>
required_role: <registered role or ROLE_COVERAGE_BLOCKER>
telegram_type: bot | bridge | client | archive | unknown | not-applicable
aiogram_status: target | already-aiogram | exception-needed | not-applicable
migration_backlog_item: <surface id or missing>
behavior_baseline: tests | snapshots | runtime evidence | missing
risk_level: low | medium | high
allowed_writes:
  - <paths>
forbidden_writes:
  - secrets
  - production data
  - unrelated project files
validation:
  - <commands or read-only probes>
next_skill: <skill name>
role_gate_status: matched | ROLE_COVERAGE_BLOCKER | not-applicable
```

## Mandatory role gate

- Use `platform-role-catalog.v1.json` before implementation on auth, gateway, Telegram platform, WB integration, deploy, analytics, notifications, or product app-zone work.
- If no registered role covers the platform part, return `ROLE_COVERAGE_BLOCKER`; do not use a generic worker as a substitute.
- The only allowed pre-resolution write is the missing role/catalog artifact inside this plugin.
- For bot runtime work, the route role must also match `telegram-aiogram-migration-backlog.v1.json`; missing or mismatched backlog coverage blocks implementation until the plugin catalog validates.

## Long-distance defaults

- Centralize cross-cutting Telegram and platform-role guidance in this plugin; keep product code in owning projects.
- Make shared behavior reusable through adapters, typed callback data, rendering helpers, and test fixtures.
- Keep migration incremental: backlog coverage, inventory, project artifacts, tests, adapter boundary, Aiogram router split, runtime rollout, cleanup.
- Prefer documented exceptions over silent drift.
