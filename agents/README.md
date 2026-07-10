# Plugin Agent Profiles

This directory is the only source for Bears App-Based Workflow custom-agent TOML files.

- `./install` registers every profile through `config_file` entries in `$CODEX_HOME/config.toml`.
- Do not copy these profiles into the global agent directory.
- Role choice and dispatch procedure live in `skills/subagents/SKILL.md`.
- Role TOML files contain only behavior unique to that role.
- autoCI, outside this plugin payload, owns profile checks and installation acceptance.
