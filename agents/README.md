# Plugin Agent Profiles

The TOML files in this directory are **generated**. Do not edit them by hand.

The single source of truth is the typed role IR in `roles/roles.json`. `scripts/render_roles.py`
renders it into both runtime representations:

- `agents/<name>.toml` - Codex profile (model, reasoning effort, sandbox, developer instructions, per-server MCP policy).
- `claude/agents/<name>.md` - Claude Code subagent (frontmatter `name`, `description`, `model`, `tools`, plus role prose).

```bash
python3 scripts/render_roles.py           # write both artifact sets
python3 scripts/render_roles.py --check   # drift detection; non-zero exit if artifacts are stale
```

| Role | Kind | Authority | Workflow MCP access |
| --- | --- | --- | --- |
| `app-worker` | worker | mutation (Edit/Write/Bash) | None |
| `app-reviewer` | critic | read-only | Bounded read-only review queries |
| `app-analyst` | reader | read-only | Bounded read-only analysis queries |

Claude Code is the sole orchestrator and the sole writer: the main session owns the wave and both
MCP servers, and dispatches these three bounded roles as subagents. The former Codex-only
`workflow-orchestrator` and `repo-orchestrator` lane profiles are retired; parallel work uses
native subagents and separate sessions instead.

Authority derives from role kind, not from specialization. Specialization arrives through the
assignment, so per-technology micro-profiles are not added here, and security and performance are
mandatory sections of the reviewer's single acceptance surface rather than separate roles.
