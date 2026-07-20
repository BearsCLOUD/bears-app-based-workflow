# Bears App-Based Workflow

Bears App-Based Workflow is a seven-phase plugin whose canonical workflow state is a
registered per-project SQLite database exposed through two stdio MCP servers. Both
servers start from the same stdlib-only Python 3.10+ runtime, `scripts/app_workflow.py`.
`git` must be on `PATH` for project registration.

Claude Code is the primary runtime and the sole orchestrator and sole writer. Codex
remains supported as an executor: Claude drives it either through a stateful `codex mcp`
session or through a headless `codex exec` one-shot, and the Codex plugin manifest keeps
the skills usable from a Codex session directly. Codex is no longer a host that installs
roles into a machine-level configuration.

## Runtimes

| | Claude Code | Codex |
|---|---|---|
| Manifest | `.claude-plugin/plugin.json` (plus `.claude-plugin/marketplace.json`) | `.codex-plugin/plugin.json` (plus `.agents/plugins/marketplace.json`) |
| MCP wiring | `claude/mcp.json`, resolved through `${CLAUDE_PLUGIN_ROOT}` | `.mcp.json`, resolved relative to the working directory |
| Hooks | `claude/hooks.json` | not applicable |
| Roles | agent definitions under `claude/agents/` | profile definitions under `agents/` |

The eight skills under `skills/` (one per phase, plus `subagents`) are shared by both
runtimes. Claude Code loads the plugin, both MCP servers, the skills, the agents, and the
hooks entry point from `.claude-plugin/plugin.json`.

```bash
claude plugin marketplace add /absolute/path/to/bears-app-based-workflow
claude plugin install bears-app-based-workflow@bears-app-based-workflow
```

For a single session, use `claude --plugin-dir /absolute/path/to/bears-app-based-workflow`.

There is no installer script, no machine-level role synchronization, and no deployment
pipeline in this repository. Installation is exactly the plugin load above.

## State Boundary

- The registry `registry.sqlite3` maps stable `project_ref` values to absolute Git roots.
  It lives in `$BEARS_APP_WORKFLOW_STATE_DIR` when that variable is set, otherwise in
  `$CODEX_HOME/state/bears-app-based-workflow/` (`$CODEX_HOME` defaults to `~/.codex`).
  Every runtime shares one registry by default.
- `<project>/.bears/app-workflow.sqlite3` stores normalized workflow state and never
  stores the absolute project path.
- `app-workflow` exposes twelve read-only tools.
- `app-workflow-maintainer` exposes thirteen registration and mutation tools.
- Markdown phase artifacts remain under `waves/<wave_id>/` in the target project.
- JSON workflow-state and functional-map fallbacks are forbidden.

`project_register` accepts only an absolute non-symlink Git root. It creates or attaches
the project database, writes its stable identity, and adds these target-repository rules:

```gitattributes
.bears/app-workflow.sqlite3 binary
```

```gitignore
.bears/app-workflow.sqlite3-journal
.bears/app-workflow.sqlite3-wal
.bears/app-workflow.sqlite3-shm
.bears/app-workflow.sqlite3.lock
```

The database uses foreign keys, DELETE journaling, FULL synchronization, and a
five-second busy timeout. WAL is rejected.

## Running the Servers

```bash
python3 scripts/app_workflow.py serve --mode reader      # app-workflow
python3 scripts/app_workflow.py serve --mode maintainer  # app-workflow-maintainer
```

The reader and maintainer boundary is enforced when a tool call is dispatched, so a
maintainer tool is unreachable from a reader server. Domain failures come back as
tool-level results carrying a stable code, not as protocol errors.

## MCP Surfaces

Read-only tools (twelve):

`project_list`, `project_status`, `graph_read`, `graph_search`, `graph_open`,
`dependency_slice`, `impact_analysis`, `graph_trace`, `graph_diagnostics`,
`topological_plan`, `workflow_state`, and `workflow_validate`.

Maintainer tools (thirteen):

`project_register`, `project_rebind`, `project_unregister`, `project_migrate_json`,
`wave_initialize`, `phase_record`, `graph_apply`, `plan_replace`, `task_record_change`,
`review_record`, `correction_record`, `analysis_record`, and `workflow_mark_audited`.

Every mutation requires a unique `request_id`, an expected revision, and an expected
logical digest. Wave mutations also require the stable owner-session ref. Batch graph and
plan changes commit completely or roll back completely. Replaying a `request_id` is
idempotent only for an identical payload digest.

Responses contain text JSON and `structuredContent`. Pages default to 50 items and stop
at 200. Traversal defaults to depth 4 and stops at 16. Cursors bind the project, the
revision, and the normalized query. Requests stop at 1 MiB and responses stop at 512 KiB.

## Graph and Workflow

Entities, observations, and relations have stable refs, `active` or `retired` lifecycle
state, optional replacement refs, and mandatory local-file provenance. The closed relation
set is `depends_on`, `constrains`, `defines`, `decomposes_to`, `implemented_by`,
`evidenced_by`, `replaces`, and `remediates`. No tool physically deletes graph records;
upserting a retired record is rejected.

Each phase retains one current process record while superseded records remain in history.
Review approval binds the current task change digest and completes a task only after
every correction closes. Semantic findings reopen the earliest required phase. A clean
analysis becomes `ready`.

`workflow_validate` reads canonical sorted logical database rows and exact SHA-256 file
content. The logical digest is a SHA-256 over those sorted canonical rows, excluding the
request log, the audit attestations, and the metadata revision row.
`workflow_mark_audited` repeats validation at the same revision inside its own
transaction and writes one audit attestation. Any later mutation stales that attestation.

## Seven Phases

1. `$app-constitution` writes `waves/<wave_id>/constitution.md`
2. `$app-research` writes `waves/<wave_id>/research.md`
3. `$app-specify` writes `waves/<wave_id>/spec.md`
4. `$app-functional-graph` writes `waves/<wave_id>/functional-graph.md`
5. `$app-plan` writes `waves/<wave_id>/plan.md`
6. `$app-dev` writes `waves/<wave_id>/dev.md`
7. `$app-analyze` writes `waves/<wave_id>/analysis.md`

Every phase carries `project_ref`, `wave_id`, revision, and logical digest. Phase order is
procedural discipline: `phase_record` validates the phase name and the single-active-record
rule, and does not verify that earlier phases completed. If either required MCP server is
unavailable, the phase remains `pending`.

## Ownership

One Claude session owns a repository, a wave, and both servers, and is the only writer.
It records every maintainer mutation itself. Executors, whether Claude subagents or Codex
through `codex mcp` or `codex exec`, stay bounded to an assigned result, receive at most a
read-only tool subset, and never reach the maintainer server. Only the wave owner records
mutations.

## Migration

The project database schema is `app-workflow-db.v2`. A `v1` database is migrated in place,
automatically, the first time it is opened writable; the migration runs in one transaction,
verifies foreign keys, and rolls back as a unit on failure. Any other schema version is
rejected with `PROJECT_SCHEMA_UNSUPPORTED`. Read-only opens never migrate.

`project_migrate_json` accepts `app-functional-map.v5` and `workflow-state.v1` only into
an empty database. It verifies both declared SHA-256 values, checks imported parity, keeps
the source JSON files, and requires a new audit. A v4 map opens a new empty wave and
remains snapshot evidence instead of receiving a lossy import. Source JSON deletion is a
separate operator-reviewed change after parity succeeds.

## Validation

```bash
python3 scripts/app_workflow.py validate --project-ref <project_ref> --wave-id <wave_id>

python3 skills/app-analyze/scripts/validate_workflow.py \
  --project-ref <project_ref> --wave-id <wave_id>
```

The second command is a thin wrapper over the first. The validator emits `ok`,
`snapshot_digest`, and `findings` from read-only SQLite access. The `validate` CLI, the
`workflow_validate` tool, and the recheck inside `workflow_mark_audited` share one
validation core.

Database and MCP contracts are in `contracts/app-workflow-db-v1.sql` and
`contracts/app-workflow-mcp-tools.v1.json`. The schema is not embedded in the runtime: it
is read from the contract file and executed only when a project database is first created.

Tests use the standard library `unittest` runner:

```bash
python3 -m unittest discover -s tests
```

## What Changed in 0.7.0

- Claude Code is the primary runtime and the sole orchestrator. One session per repository
  owns the wave and is the single writer; everything else is an executor with read-only
  access at most.
- Codex is an executor reached through `codex mcp` or `codex exec`, and is still supported
  as a direct runtime through its own plugin manifest, but it no longer hosts or installs
  roles.
- The installer script, the machine-level role synchronization receipts, the continuous
  deployment workflow and its self-hosted runner, and the committed release bundle are all
  removed. The plugin is installed by loading it from this repository.
- The project database schema moved from `app-workflow-db.v1` to `app-workflow-db.v2`. The
  upgrade is automatic and in place on the first writable open, so no operator step is
  required.

The runtime adapts entity, relation, observation, and MCP tool patterns from the pinned
upstream memory server named in `THIRD_PARTY_NOTICES`. It does not copy JSONL rewrite
storage, the fixed `memory://knowledge-graph` resource, or live subscriptions.
