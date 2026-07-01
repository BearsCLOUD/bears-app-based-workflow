---
name: bears-telegram-workflow
description: "Central Bears platform and Telegram workflow router. Use when Codex works on any Bears platform part that may need a plugin-owned specialist role, any Telegram bot, Telegram-facing product flow, Telegram approval/status loop, Aiogram migration decision, bot UI formatting, callback/FSM behavior, Telegram testing plan, or when deciding which plugin skill or subagent should own a task. It coordinates local project rules, shared workspace-control / migration-reference rules, platform role governance, and plugin skills without overriding narrower AGENTS.md instructions."
---

# Bears Platform and Telegram Workflow

Use this as the entry point for Bears platform-role and Telegram work. It is a router, not a product-specific implementation contract.

## Start sequence

1. Read the nearest `AGENTS.md` for the target path plus `/srv/bears/dev/AGENTS.md` when available.
2. If the task touches auth, gateway, Telegram platform, WB integration, deploy, analytics, notifications, or product app-zone implementation, use `$platform-role-governance` before implementation. Missing role coverage is `ROLE_COVERAGE_BLOCKER`.
3. Classify the Telegram surface:
   - bot runtime or handler code;
   - formatting/keyboards/callback UX;
   - webhook, polling, deployment, or runtime evidence;
   - plugin/skill/workflow documentation;
   - non-bot Telegram client or operator bridge.
4. Route to the narrow skill:
   - Use `$platform-role-governance` for auth/gateway/platform-part routing, specialist role selection, and missing-role blocker decisions.
   - Use `$telegram-aiogram-migration` for framework rewrite, router/dispatcher design, FSM migration, webhook/polling migration, or behavior inventory.
   - Use `$telegram-quality-testing` for message rendering, parse mode, inline keyboard, callback, command menu, and Telegram test coverage.
   - Use `$telegram-plugin-skill-factory` for creating or changing skills inside this plugin.
5. For bot runtime work, check `assets/catalog/telegram-aiogram-migration-backlog.v1.json` and `assets/catalog/telegram-runtime-readiness.v1.json`; run `scripts/telegram_migration_backlog.py validate` and `scripts/telegram_runtime_readiness.py validate`. Missing or mismatched backlog, readiness, or role coverage blocks implementation until the plugin artifact is updated.
6. Keep product implementation inside the owning project. This central plugin supplies standards and handoff packets only.
7. For live Telegram or production actions, require runtime evidence, explicit approval for mutations, and no secret exposure.
8. For Infisical, Kubernetes, Telegram auth, TDLib, Bot API server, or session-location questions, read `references/telegram-infisical-kubernetes-map.md` before answering or editing.

## Non-negotiable rules

- A plugin-owned specialist role is mandatory before platform-part implementation. If no role covers the part, stop with `ROLE_COVERAGE_BLOCKER` and create the role gate before editing product/platform code.
- Bot runtimes must converge to an Aiogram 3-compatible platform pattern unless the migration backlog and readiness packet record a bounded exception or source-recovery deferral.
- Do not force non-bot Telegram clients, archival scripts, or read-only export tools into Aiogram without a product reason.
- Preserve current user-visible behavior before framework rewrites. Create characterization tests first when behavior is unclear.
- Keep Telegram as an operator feedback surface, not a secret transport. Do not print or store raw bot tokens, chat IDs tied to private users, or production payloads.
- While `workspace-map` is operator-disabled, use local docs, file search, and runtime evidence instead of workspace-map startup context.
- Apply the narrowest local project rule when this plugin conflicts with a repo-local `AGENTS.md`, `SPEC.md`, or `requirements.md`.

## Subagent routing

Use subagents for parallel, bounded work when the user authorized subagent work and write scopes are disjoint. For platform parts, select the registered role with `$platform-role-governance` first.

Recommended split:

- Explorer: inventory current Telegram surfaces and owner paths; read-only.
- Migration worker: draft Aiogram migration packet for one bot or package.
- Quality worker: build Telegram UI/test matrix for the same surface.
- Skill worker: update plugin skills or references only.
- Reviewer: check security, behavior preservation, and missing validation.

Each subagent must receive: role, objective, owning path, allowed writes, forbidden writes, expected evidence, and closeout format. See `references/subagent-start-packet.md` and the platform role start packet.

## References

- Read `references/workflow-router.md` for the decision matrix and handoff rules.
- Use `$platform-role-governance` and read `../platform-role-governance/references/role-start-packet.md` before platform-part delegation.
- Read `references/subagent-start-packet.md` before delegating Telegram work.
- Read `references/operator-tglib-auth.md` before changing the operator TDLib auth interface.
- Read `references/operator-auth-module-split-plan.md` before expanding operator auth helper scripts.
- Read `references/telegram-infisical-kubernetes-map.md` for Infisical paths, Kubernetes objects, Telegram auth helpers, session locations, and safe probes.
- Read `references/catalog-aggregation.md` when updating the plugin catalog.
- Read `../../assets/catalog/telegram-workflow-catalog.v1.json` for the current workflow and surface catalog.
- Read `../../assets/catalog/telegram-aiogram-migration-backlog.v1.json` for the current bot migration backlog and role gates.
- Read `../../assets/catalog/telegram-runtime-readiness.v1.json` for machine-validatable migration-readiness packets keyed by backlog surface.
- Read `../../assets/catalog/platform-role-catalog.v1.json` for platform roles and mandatory blocker policy.
- Run `../../scripts/telegram_catalog.py validate` after Telegram catalog edits.
- Run `../../scripts/telegram_migration_backlog.py validate` after Aiogram backlog edits.
- Run `../../scripts/telegram_runtime_readiness.py validate` after readiness-packet edits.
- Run `../../scripts/platform_roles.py validate` after role catalog or agent edits.
- Check `/srv/bears/dev/docs/reference/telegram-surface-map.md` when the workspace migration map exists.
- Check `/srv/bears/specs/005-telegram-workflow-plugin/spec.md` for feature acceptance scope.
