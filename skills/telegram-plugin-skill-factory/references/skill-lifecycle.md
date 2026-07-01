# Telegram Plugin Skill Lifecycle

## Create

```bash
python3 /home/ai1/.codex/skills/.system/skill-creator/scripts/init_skill.py <skill-name> \
  --path /srv/bears/plugins/bears/skills/bears-telegram-workflow/skills \
  --resources references \
  --interface display_name="<Display Name>" \
  --interface short_description="<25-64 char description>" \
  --interface default_prompt="Use $<skill-name> to <task>."
```

Then replace all template text in `SKILL.md` and add only needed references.

## Update

- Read the current `SKILL.md` first.
- Route Telegram platform scope through the canonical gate first: `python3 /srv/bears/plugins/bears/scripts/platform_roles.py route <path-or-part>`.
- Preserve narrow scope and direct references.
- Keep `assets/catalog/telegram-plugin-skill-factory-policy.v1.json` aligned when workflow gates, packet shape, skill-bundle boundary, validators, or forward-test expectations change.
- Regenerate or edit `agents/openai.yaml` when the purpose changes.
- Update `.codex-plugin/plugin.json` only when the plugin should expose a real metadata-only skill-bundle discovery entry.
- Update `.codex-plugin/plugin.json` only when plugin discovery metadata changes.
- Use Telegram-specific validators only after canonical routing is confirmed.

## Validate

Local agents may run exact route/audit gates for the changed target and `git diff --check` for the changed scope.

```bash
python3 /srv/bears/plugins/bears/scripts/platform_roles.py route <path-or-part>
python3 /srv/bears/plugins/bears/scripts/platform_roles.py audit <path-or-part>
git diff --check -- /srv/bears/plugins/bears/skills/bears-telegram-workflow
```

Skill validation suites and test execution are local-commit-owned. A local agent may run them only after explicit operator approval for that exact command.

## Install/update note

When the local plugin is already installed in Codex and the operator needs the UI to refresh, use the plugin-creator update/cachebuster flow instead of hand-editing marketplace entries.
