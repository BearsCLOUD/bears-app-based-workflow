# Plugin Agent Profiles

This directory is the only source for the plugin's 51 active custom-agent TOML files.

- `./install` registers every profile through `config_file` entries in `$CODEX_HOME/config.toml`.
- Do not copy these profiles into the global agent directory.
- Role choice and dispatch procedure live in `skills/subagents/SKILL.md`.
- A role name is derived from one deliverable; removed names have no aliases.
- Role TOML files own triggers, specialist identity, required dependencies, permissions, decisions, acceptance criteria, result fields, and one declarative example.
- Skills own repeatable methods, checklists, templates, scripts, references, and packet schemas.
- autoCI, outside this plugin payload, owns profile checks and installation acceptance.
