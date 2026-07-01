---
name: telegram-aiogram-migration
description: "Bears Aiogram migration governance. Use when Codex rewrites, designs, reviews, or plans any Bears Telegram bot runtime around Aiogram; when moving handlers from another framework to Aiogram; when defining Dispatcher, Router, filters, middleware, FSM, webhook, polling, dependency-injection, or callback-query architecture; or when recording a justified exception for non-Aiogram Telegram surfaces."
---

# Telegram Aiogram Migration

Use this skill to migrate bot surfaces to Aiogram without losing behavior.

## Migration workflow

1. Identify the surface and owner. Read local `AGENTS.md`, `SPEC.md`, and tests before changing code.
2. Check `../../assets/catalog/telegram-aiogram-migration-backlog.v1.json` and `../../assets/catalog/telegram-runtime-readiness.v1.json`; run `../../scripts/telegram_migration_backlog.py validate` and `../../scripts/telegram_runtime_readiness.py validate`. If the surface is missing from the backlog or readiness registry, add the plugin artifact before implementation.
3. Build a behavior inventory: commands, messages, callbacks, keyboards, FSM states, background jobs, auth/RBAC checks, webhook/polling entrypoint, side effects, and error paths.
4. Create or preserve characterization tests before framework replacement when behavior is not already covered.
5. Decide migration status:
   - `already-aiogram3-core-seed`: seed for reusable platform primitives;
   - `already-aiogram3-hardening`: Aiogram 3 runtime that needs tests/adapters;
   - `target-aiogram3-upgrade`: Aiogram 2 or beta runtime that must upgrade to stable Aiogram 3;
   - `target-aiogram3-rewrite`: bot runtime that must rewrite to Aiogram 3 after adapter seam and tests;
   - `not-applicable-non-bot`: collector, delivery service, or non-bot Telegram surface;
   - `deferred-missing-source`: source or owner is missing.
6. Design the Aiogram boundary: one dispatcher composition root, routers by domain, typed callback data, explicit middlewares, FSM storage policy, dependency injection, and webhook or polling entrypoint.
7. Migrate incrementally with adapter seams when possible. Do not mix old and new frameworks without a cleanup plan.
8. Validate with unit tests, handler tests, callback tests, and one runtime-safe startup/import check. Live webhook or production mutation requires explicit approval.

## Aiogram platform baseline

Current Aiogram 3 docs describe an async Telegram Bot API framework where `Dispatcher` is the root router, handlers attach to `Router` or `Dispatcher`, routers can be included into the dispatcher, filters select events, middlewares modify event data, FSM supports stateful flows, webhook setup uses aiohttp helpers with secret-token support, and dependencies can be injected through dispatcher/startup context.

Read `references/aiogram-platform-baseline.md` before making framework-shape decisions.

## Required migration packet

Before implementation, write or update the central readiness packet in `../../assets/catalog/telegram-runtime-readiness.v1.json`, then mirror any extra working detail in the owning issue, plan, or local docs. Use `references/migration-readiness-packet.md`.

The migration packet must cite the matching backlog item and selected specialist role. Missing backlog coverage, missing readiness coverage, or role mismatch blocks product/platform implementation until the plugin catalog validates.

## Architecture rules

- Keep bot construction and runtime startup separate from business logic.
- Keep handlers thin: parse update, call service/application logic, render response.
- Share reusable business flows outside Telegram adapters so future non-seller services can reuse them.
- Centralize callback-data schema and version it when callbacks can outlive deployments.
- Make middlewares explicit for auth, tenant, tracing, localization, and idempotency.
- Never embed tokens, private chat IDs, or production payloads in examples, tests, docs, or logs.
