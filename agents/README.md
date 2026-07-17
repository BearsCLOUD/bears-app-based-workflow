# Plugin Agent Profiles

The five TOML files in this directory are authoritative agent configurations. The installer validates and registers them directly without JSON role duplicates or a renderer.

| Profile | Level | Workflow MCP access |
| --- | --- | --- |
| `workflow-orchestrator` | L1 | None |
| `repo-orchestrator` | Persistent L2 | Full read-only and maintainer surfaces |
| `app-worker` | L3 | None |
| `app-reviewer` | L3 | Limited read-only review queries |
| `app-analyst` | L3 | Limited read-only analysis queries |

The `DIRECT` primary retains every app phase and may use both plugin servers. The persistent `repo-orchestrator` retains every `DELEGATED` app phase and all workflow writes. L3 profiles never call the maintainer server or own workflow state.

Run `./install --codex-home <path>` to register the five profiles through `config_file` entries. Use `--dry-run` to validate without writing.
