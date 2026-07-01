---
name: telegram-plugin-skill-factory
description: "Central hard factory for `/srv/bears/plugins/bears/skills/bears-telegram-workflow`. Use when Codex creates, updates, reviews, validates, or forward-tests Telegram workflow skills, role TOMLs, skill-bundle discovery metadata, catalog entries, plugin discovery metadata, references, or subagent workflow rules; also use when the skill bundle must reference the canonical Bears role gate first and keep Telegram validation second."
---

# Telegram Workflow Skill Factory

Use this skill to evolve the Bears Telegram workflow skill bundle without producing loose docs, fragile skills, stale aggregation claims, or ungoverned roles. Treat `assets/catalog/telegram-plugin-skill-factory-policy.v1.json` and `scripts/telegram_skill_factory_policy.py validate` as the machine-verifiable factory contract.

## Factory workflow

1. Confirm the requested workflow belongs in `bears-telegram-workflow`; otherwise route to the owning project.
2. Run the canonical Bears role gate first for Telegram platform scope: `python3 /srv/bears/plugins/bears/scripts/platform_roles.py route <path-or-part>`.
3. Keep Telegram-specific validators (`telegram_*` scripts and `validate_overlay.py`) secondary after the canonical role is selected.
4. Name skills in lowercase hyphen-case, under 64 characters.
5. Create new skill folders with `/home/ai1/.codex/skills/.system/skill-creator/scripts/init_skill.py`.
6. Keep each skill narrow: one trigger family, one workflow, direct references only.
7. Write `SKILL.md` with only `name` and `description` frontmatter. Put all trigger conditions in `description`.
8. Put detailed matrices/checklists in `references/`; no `README.md`, `CHANGELOG.md`, or extra narrative docs inside skill folders.
9. Update `agents/openai.yaml` so `default_prompt` mentions the skill as `$skill-name`.
10. For platform roles, create or update `agents/<role>.toml` with broad developer instructions, then update the owning role catalog.
11. For skill-bundle discovery, keep `.codex-plugin/plugin.json` conservative and metadata-only; do not add `.app.json`, connector, MCP, runtime, or live Telegram claims.
12. Update `.codex-plugin/plugin.json` only for plugin-wide discovery metadata.
13. Validate the factory policy with `python3 scripts/telegram_skill_factory_policy.py validate` before claiming a skill/app/role workflow change is accepted.
14. Validate changed Telegram skill/catalog/role surfaces with `/srv/bears/plugins/bears/scripts/platform_roles.py validate`, `scripts/telegram_skill_factory_policy.py validate`, the affected Telegram validators, `scripts/validate_overlay.py --json validate --strict-overlay-skills`, and targeted tests.
15. Forward-test central skills or role handoffs when safe; pass the artifact path and a realistic task, not the expected answer.

## Hard gates

- No TODO placeholders.
- No secrets, production data, raw tokens, private chat logs, or `.env` content.
- No broad workspace rewrites from a skill task.
- No duplicate skill or role that overlaps an existing trigger/scope without a routing rule.
- No unvalidated Telegram skill bundle, factory policy, or platform-role handoff.
- No claiming connector-backed, app-backed, MCP-backed, runtime-backed, or live Telegram behavior in this skill bundle.

## References

- Read `../../assets/catalog/telegram-plugin-skill-factory-policy.v1.json` for required packet fields, validator list, app boundary, and forward-test cases.
- Read `references/skill-lifecycle.md` for exact creation/update steps.
- Read `references/review-checklist.md` before accepting a skill change.
- Read `references/subagent-forward-test.md` before forward-testing.
