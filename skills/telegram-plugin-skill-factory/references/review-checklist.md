# Platform Plugin Skill and Role Review Checklist

## Trigger quality

- Description clearly says when to use the skill.
- Skill does not overlap another skill without a routing rule.
- Root router points to the skill when relevant.
- Telegram platform work references the canonical Bears role gate first.

## Workflow quality

- Starts with local project instructions.
- Selects the canonical Bears role gate before Telegram validators.
- Defines required input packet and output evidence.
- Protects secrets and production data.
- Handles live Telegram actions through read-only proof and explicit approval.
- Provides validation commands or test families.
- Updates and validates `telegram-plugin-skill-factory-policy.v1.json` when factory gates, packet fields, skill-bundle boundary, validators, or forward-tests change.

## Skill structure

- `SKILL.md` has only `name` and `description` frontmatter.
- No TODO placeholders remain.
- References are one level deep and directly linked from `SKILL.md`.
- No README/CHANGELOG/extra docs inside skill folder.
- `agents/openai.yaml` default prompt names `$skill-name`.

## Platform role structure

- Platform role TOMLs include name, description, model, reasoning effort, sandbox, and broad developer instructions.
- The canonical catalog in `/srv/bears/plugins/bears/assets/catalog/platform-role-catalog.v1.json` owns primary platform-role coverage.
- Telegram validators stay secondary and must not replace canonical routing.
- Missing role behavior is `ROLE_COVERAGE_BLOCKER`, not generic-agent fallback.
- Role handoff packets include role name, role file, platform part, write scope, forbidden actions, evidence, role-gate status, heartbeat/status packet, and closeout packet.

## Plugin structure

- `.codex-plugin/plugin.json` validates.
- `scripts/telegram_catalog.py validate` passes when Telegram catalog entries changed.
- `scripts/telegram_migration_backlog.py validate` passes when Aiogram migration backlog entries changed.
- `/srv/bears/plugins/bears/scripts/platform_roles.py validate` passes when canonical role routing assumptions changed.
- `scripts/platform_roles.py validate` passes when Telegram skill-bundle role catalog or agent files changed.
- `.codex-plugin/plugin.json` exposes only supported metadata-only claims.
- Marketplace entry exists only in the intended marketplace.
- `.gitignore` allows tracked plugin files when the root meta-repo owns the plugin.
