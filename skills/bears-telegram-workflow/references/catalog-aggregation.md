# Telegram Workflow Catalog Aggregation

The plugin catalog is the durable index of Telegram workflow knowledge.

## Update targets

- Plugin manifest: `.codex-plugin/plugin.json` for discoverability metadata.
- Root router skill: `skills/bears-telegram-workflow/SKILL.md` for entry routing.
- Narrow skills: one skill per repeatable workflow.
- References: detailed matrices, packets, and checklists loaded only when needed.
- Migration backlog: `assets/catalog/telegram-aiogram-migration-backlog.v1.json` for bot/runtime convergence, role-gate status, artifact gates, and next actions.
- Readiness registry: `assets/catalog/telegram-runtime-readiness.v1.json` for machine-validatable migration-readiness packets keyed by backlog surface.
- Feature spec: `/srv/bears/specs/005-telegram-workflow-plugin/spec.md` for acceptance scope.
- Dev-core references: `/srv/bears/dev/docs/reference/telegram-surface-map.md` for workspace-level surfaces.
- Governance route: `telegram-workflow-governance` in `platform-role-catalog.v1.json` covers this plugin tree, the feature spec, and the dev-core surface map under `bears-platform-role-governor`.

## Catalog entry contract

Every new Telegram surface must define:

```yaml
name: <surface name>
path: <repo path or null>
owner_group: <platform/products/ops/etc>
surface_type: <bot/bridge/client/collector/custom>
current_framework_status: <verified status or unknown>
target_state: <shared core/adaptor/exception/deferred>
migration_status: <already-aiogram/target/adapter-first/not-applicable/deferred>
test_status: <verified/static/missing>
exception_status: <none/reason/pending verification>
trust_status: trusted | candidate | deferred | blocked | exception
last_verified: <YYYY-MM-DD>
evidence_source:
  - <non-secret source paths>
next_action: <safe next step>
```

Every new Telegram workflow must define:

```yaml
name: <workflow name>
trigger: <when agents should use it>
owning_skill: <skill folder>
reference: <direct reference path>
input_packet: <required context>
output_packet: <required closeout>
validation: <checks>
security_rules: <secret/runtime/approval constraints>
reuse_targets: <where this can be reused>
```

Reject workflow entries that lack triggers, owner, direct reference, input packet, output packet, validation, security rules, or reuse targets. Reject surface entries that lack owner, status, evidence source, trust status, or next action.
Run `scripts/telegram_catalog.py validate` from the plugin root after catalog edits.

## Migration backlog entry contract

Every bot or Telegram-adjacent surface in the migration backlog must define:

```yaml
surface: <stable id>
path: <repo path or null>
role_route_target: <path/name used by platform_roles.py route>
surface_class: <bot/runtime/client/service/source state>
current_framework: <aiogram/telethon/custom/fastapi-aiohttp/unknown>
current_framework_version: <version or reason>
migration_status: already-aiogram3-core-seed | already-aiogram3-hardening | target-aiogram3-upgrade | target-aiogram3-rewrite | not-applicable-non-bot | deferred-missing-source
aiogram_target: platform-core-seed | platform-core-consumer | aiogram3-upgrade-required | aiogram3-rewrite-required | no-aiogram-non-bot | deferred-source-required
primary_role: <registered role>
supporting_roles:
  - <registered role>
artifact_gate:
  status: open | blocked-before-code | not-applicable | deferred-source-required
  present: []
  missing: []
evidence_source:
  - <non-secret source paths>
next_actions:
  - <safe next step>
validation_before_code:
  - <checks before implementation>
```

Run `scripts/telegram_migration_backlog.py validate` after backlog edits. A missing or role-mismatched backlog item blocks product/platform implementation until the plugin artifact validates.

## Runtime readiness packet contract

Every readiness packet must be keyed by the backlog `surface` and define:

```yaml
surface: <stable backlog surface id>
backlog_item: <same surface id>
backlog_link:
  catalog: assets/catalog/telegram-aiogram-migration-backlog.v1.json
  surface: <same surface id>
path: <repo path from backlog>
backlog_status: <migration_status from backlog>
role_route_target: <path/name routed by platform_roles.py>
primary_role: <registered role that matches backlog and route>
readiness_status: blocked | ready | exception | deferred-source-required
implementation_gate: open | blocked | not-applicable | deferred-source-required
behavior_inventory: <commands/message/fsm/jobs/side-effects status block>
callback_governance: <schema/privilege/integrity/replay/audit status block>
security_controls: <trust-boundary/RBAC/idempotency/redaction/external-side-effect status block>
secret_governance: <classification-only secret source and chat-id fields>
approval_status: not-requested | pending | approved | blocked
security_signoff: required | not-required | approved | blocked
validation_plan:
  - <safe checks>
rollback_plan:
  - <rollback path>
missing_evidence:
  - <explicit missing evidence>
last_verified: <YYYY-MM-DD>
```

Run `scripts/telegram_runtime_readiness.py validate` after readiness registry edits. Every `already-aiogram3-core-seed`, `already-aiogram3-hardening`, `target-aiogram3-upgrade`, and `target-aiogram3-rewrite` surface must have a readiness packet. For any readiness packet, `implementation_gate=open` is invalid until approval, behavior, callback, security, validation, rollback, and route evidence are complete.
