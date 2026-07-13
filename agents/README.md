# Plugin Agent Profiles

`role-definitions/*.json` is the authoritative source for every active role. The fixed root-gateway renderer validates the capability catalog and produces this directory's TOML files from a closed safe subset; hand-authored TOML and raw configuration fragments are forbidden.

Each JSON definition owns one bounded behavior, capability requirements, and its result fact. The generated profile is an exact projection, not an independent source.

Every profile declares `Role identity: profile=<name>; level=<L1|L2|L3>; role_kind=<kind>` inside `developer_instructions`. Dispatch is valid when the packet identity matches, its instruction refs include the exact installed profile `config_file`, and the child starts with `fork_turns=none`. If the transport exposes `agent_type` or another documented role selector, it must also match; the selector's absence alone is not rejection. `task_name` is non-authoritative. Missing or mismatched profile binding fails closed instead of falling back to `default` or parent execution.

MCP capability policy is rendered under the installed plugin namespace. The plugin owns each server transport; role files only enable or disable its servers and tools, avoiding invalid standalone transport-less MCP definitions.

The explicit `./install` entrypoint registers the discovered profiles through `config_file` entries in `$CODEX_HOME/config.toml`. Removed names are not registered and have no compatibility aliases; prior receipt ownership is required before a managed registration can be retired. Run the installer after profile changes and start a new task so Codex loads the current registrations.

`app-dev` keeps one persistent repo-L2 queue per repository. Each repo-wave session uses one `app-worker`, receives one current canonical task at a time, and closes with a fresh repo-local immutable review. Review findings enter the same repository as new remediation tasks rather than reopening terminal tasks.

- Do not copy these profiles into the global agent directory.
- Deterministic role choice and dispatch live in `skills/subagents/SKILL.md`.
- A role name is derived from one deliverable; removed names have no aliases.
- Profile identity, role kind, and capabilities are validated from authoritative JSON; the current role count is derived from that exact catalog.
- Agent TOML files use only the Codex custom-agent schema and supported `config.toml` keys; plugin role metadata belongs in `developer_instructions` or plugin-owned documentation, not in unsupported top-level fields.
- Role TOML files own triggers, specialist identity, required dependencies, permissions, decisions, acceptance criteria, result fields, and one declarative example.
- Skills own repeatable methods, acceptance lists, templates, scripts, references, and packet schemas.
- autoCI, outside this plugin payload, owns profile conformance and installation acceptance.
