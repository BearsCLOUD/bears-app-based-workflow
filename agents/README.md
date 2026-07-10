# Plugin Agent Profiles

This directory is the only source for the plugin's 50 active custom-agent TOML files.

- `./install` registers every profile through `config_file` entries in `$CODEX_HOME/config.toml`.
- Do not copy these profiles into the global agent directory.
- Role choice and dispatch procedure live in `skills/subagents/SKILL.md`.
- A role name is derived from one deliverable; removed names have no aliases.
- Agent TOML files use only the Codex custom-agent schema and supported `config.toml` keys; plugin role metadata belongs in `developer_instructions` or plugin-owned documentation, not in unsupported top-level fields.
- Role TOML files own triggers, specialist identity, required dependencies, permissions, decisions, acceptance criteria, result fields, and one declarative example.
- Skills own repeatable methods, checklists, templates, scripts, references, and packet schemas.
- autoCI, outside this plugin payload, owns profile checks and installation acceptance.
