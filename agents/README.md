# Plugin Agent Profiles

This directory is the only source for the plugin's active custom-agent TOML files. The installer and production gateway discover every regular non-symlink `*.toml`, require 1..64 valid profiles, and sort them by name.

Each profile owns one bounded behavior and its result fact. The profile body, rather than this README, is the source for its trigger, permissions, acceptance criteria, and result fields.

Every profile declares `Role identity: profile=<name>; level=<L1|L2|L3>; role_kind=<kind>` inside `developer_instructions`. Dispatch is valid only when the transport supplies the same explicit `agent_type`, the packet role and role kind match, and the child starts with `fork_turns=none`. `task_name` is non-authoritative. Missing typed transport fails closed: it stops instead of falling back to an untyped or parent execution path.

The explicit `./install` entrypoint registers the discovered profiles through `config_file` entries in `$CODEX_HOME/config.toml`. Removed names are not registered and have no compatibility aliases; prior receipt ownership is required before a managed registration can be retired. Run the installer after profile changes and start a new task so Codex loads the current registrations.

`app-dev` keeps one persistent repo-L2 queue per repository. Each repo-wave session uses one `app-worker`, receives one current canonical task at a time, and closes with a fresh repo-local immutable review. Review findings enter the same repository as new remediation tasks rather than reopening terminal tasks.

- Do not copy these profiles into the global agent directory.
- Deterministic role choice and dispatch live in `skills/subagents/SKILL.md`.
- A role name is derived from one deliverable; removed names have no aliases.
- Profile identity and role kind are discovered from each active TOML; there is no fixed current role count or duplicated role registry.
- Agent TOML files use only the Codex custom-agent schema and supported `config.toml` keys; plugin role metadata belongs in `developer_instructions` or plugin-owned documentation, not in unsupported top-level fields.
- Role TOML files own triggers, specialist identity, required dependencies, permissions, decisions, acceptance criteria, result fields, and one declarative example.
- Skills own repeatable methods, acceptance lists, templates, scripts, references, and packet schemas.
- autoCI, outside this plugin payload, owns profile conformance and installation acceptance.
