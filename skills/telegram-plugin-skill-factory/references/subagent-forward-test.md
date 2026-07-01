# Subagent Forward Test Protocol

Use forward tests for complex or central skills.

## Prompt shape

Good:

```markdown
Use $telegram-plugin-skill-factory at /srv/bears/plugins/bears/skills/telegram-plugin-skill-factory to review whether a proposed Telegram workflow skill update correctly references the canonical Bears role gate first, keeps `.codex-plugin/plugin.json` metadata-only, and lists the required validation commands. Read only local docs and do not edit files.
```

Avoid:

```markdown
Review this skill and confirm it says X.
```

## Rules

- Use fresh agents when possible.
- Pass only the skill path and realistic task.
- Keep tests read-only unless validating a bounded write workflow.
- Ask for concrete output: packet, test matrix, missing-rule list, changed-file list, aggregation-gap list, or factory-policy regression list.
- Review whether the subagent used the skill naturally, missed a trigger, or needed hidden context.
- Tighten `SKILL.md`, `references/`, or `assets/catalog/telegram-plugin-skill-factory-policy.v1.json` after failures.

## Required regression prompts

- New Telegram workflow skill request must route through the canonical Bears role gate before Telegram skill-bundle validation.
- Subagent delegation request must produce role, lane, bounded paths, allowed/forbidden scope, current Spec Kit snapshot, heartbeat/status packet, validation target, and closeout packet.
- Skill-bundle discovery request must stay metadata-only and reject connector-backed, runtime-backed, or live Telegram mutation claims.
- Broad or duplicate skill request must be blocked until decomposed or explicitly routed.
