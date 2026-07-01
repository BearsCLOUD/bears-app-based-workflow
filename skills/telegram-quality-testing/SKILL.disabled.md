---
name: telegram-quality-testing
description: "Telegram UI and quality testing standard for Bears bots. Use when Codex designs, reviews, implements, or tests Telegram messages, HTML or MarkdownV2 formatting, MessageEntity rendering, inline keyboards, reply keyboards, callback data, command menus, FSM conversations, bot approvals, Telegram feedback loops, or regression coverage for Telegram user-facing behavior."
---

# Telegram Quality Testing

Use this skill to make Telegram bot behavior safe, readable, and testable. If the global `$telegram-bot-ui` skill is available, use it for visible message and keyboard UX details, then apply this skill for Bears-specific evidence, safety, and regression gates.

## Quality workflow

1. Read the target project's local instructions and existing bot tests.
2. Inventory user-visible messages, parse mode, keyboards, callbacks, commands, and state transitions.
3. Choose a rendering policy: HTML, MarkdownV2, or explicit `MessageEntity`. Do not mix parse modes casually.
4. Define callback contracts: data schema, authorization, idempotency, acknowledgement, stale-action handling, and audit trail.
5. Build tests before changing high-risk flows:
   - message snapshot or normalized text tests;
   - keyboard layout and callback-data tests;
   - callback success, denial, stale, retry, and duplicate-click tests;
   - FSM transition tests;
   - webhook/polling startup checks without real tokens.
6. Validate escaping and no-secret logging. Redact private chats, raw tokens, and production payloads.
7. For live Telegram checks, use test bots/chats or read-only runtime evidence unless the operator explicitly approves a mutation.

## Message standards

- Keep messages short, actionable, and stateful: what happened, why it matters, what the user can do next.
- Treat one important message as one clear state or one clear ask; prefer editing existing messages for toggles, pagination, and refreshes when it avoids chat noise.
- Prefer buttons for bounded choices; free text only when the user must provide open input.
- Every destructive or production-affecting callback needs confirmation or equivalent explicit authorization.
- Every callback handler must acknowledge the callback, even on denial or stale state.
- Use stable callback data prefixes and version when old buttons may remain in chats.

## References

- Read `references/telegram-formatting-and-callbacks.md` for render/callback rules.
- Read `references/telegram-test-matrix.md` when writing or reviewing tests.
