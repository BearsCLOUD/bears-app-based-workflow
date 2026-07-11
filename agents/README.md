# Plugin Agent Profiles

This directory is the only source for the plugin's eleven active custom-agent TOML files:

- `worker.toml` — bounded workspace writes and a task-scoped local commit.
- `app-worker.toml` — one canonical app task at a time, reusable only within the same repo-wave session.
- `explorer.toml` — bounded read-only workspace inspection.
- `diagnostic-command-runner.toml` — one explicitly bounded read-only command.
- `primary-source-researcher.toml` — current primary-source evidence.
- `runtime-evidence-reader.toml` — bounded sanitized runtime observations.
- `wave-change-critic.toml` — one repository's immutable wave review and actionable remediation findings.
- `security-analysis-critic.toml` — trust-boundary findings on supplied changes.
- `workflow-orchestrator.toml` — fixed L1 app-development orchestration.
- `domain-lane-orchestrator.toml` — fixed L2 lane orchestration.
- `role-profile-architect.toml` — user-requested semantic role-taxonomy maintenance; each write assignment owns its task-scoped local commit.

The explicit `./install` entrypoint registers exactly these eleven profiles through `config_file` entries in `$CODEX_HOME/config.toml`. Removed names are not registered and have no compatibility aliases. Run the installer after profile changes and start a new task so Codex loads the current registrations.

`app-dev` keeps one persistent repo-L2 queue per repository. Each repo-wave session uses one `app-worker`, receives one current canonical task at a time, and closes with a fresh repo-local immutable review. Review findings enter the same repository as new remediation tasks rather than reopening terminal tasks.

- Do not copy these profiles into the global agent directory.
- Deterministic role choice and dispatch live in `skills/subagents/SKILL.md`.
- A role name is derived from one deliverable; removed names have no aliases.
- Agent TOML files use only the Codex custom-agent schema and supported `config.toml` keys; plugin role metadata belongs in `developer_instructions` or plugin-owned documentation, not in unsupported top-level fields.
- Role TOML files own triggers, specialist identity, required dependencies, permissions, decisions, acceptance criteria, result fields, and one declarative example.
- Skills own repeatable methods, acceptance lists, templates, scripts, references, and packet schemas.
- autoCI, outside this plugin payload, owns profile conformance and installation acceptance.
