# Bears App-Based Workflow

Bears App-Based Workflow is a seven-phase Codex plugin whose canonical workflow state is a registered per-project SQLite database exposed through two stdio MCP servers.

## State Boundary

- `$CODEX_HOME/state/bears-app-based-workflow/registry.sqlite3` maps stable `project_ref` values to absolute Git roots.
- `<project>/.bears/app-workflow.sqlite3` stores normalized workflow state and never stores the absolute project path.
- `app-workflow` exposes twelve read-only tools.
- `app-workflow-maintainer` exposes thirteen registration and mutation tools.
- Markdown phase artifacts remain under `waves/<wave_id>/` in the target project.
- JSON workflow-state and functional-map fallbacks are forbidden.

`project_register` accepts only an absolute non-symlink Git root. It creates or attaches the project database, writes its stable identity, and adds these target-repository rules:

```gitattributes
.bears/app-workflow.sqlite3 binary
```

```gitignore
.bears/app-workflow.sqlite3-journal
.bears/app-workflow.sqlite3-wal
.bears/app-workflow.sqlite3-shm
.bears/app-workflow.sqlite3.lock
```

The database uses foreign keys, DELETE journaling, FULL synchronization, and a five-second busy timeout. WAL is rejected.

## MCP Surfaces

Read-only tools:

`project_list`, `project_status`, `graph_read`, `graph_search`, `graph_open`, `dependency_slice`, `impact_analysis`, `graph_trace`, `graph_diagnostics`, `topological_plan`, `workflow_state`, and `workflow_validate`.

Maintainer tools:

`project_register`, `project_rebind`, `project_unregister`, `project_migrate_json`, `wave_initialize`, `phase_record`, `graph_apply`, `plan_replace`, `task_record_change`, `review_record`, `correction_record`, `analysis_record`, and `workflow_mark_audited`.

Every mutation requires a unique `request_id`, expected revision, and expected logical digest. Wave mutations also require the stable owner-session ref. Batch graph and plan changes commit completely or roll back completely.

Responses contain text JSON and `structuredContent`. Pages default to 50 items and stop at 200. Traversal defaults to depth 4 and stops at 16. Cursors bind the project, revision, and normalized query. Requests stop at 1 MiB and responses stop at 512 KiB.

## Graph and Workflow

Entities, observations, and relations have stable refs, `active` or `retired` lifecycle state, optional replacement refs, and mandatory local-file provenance. The closed relation set is `depends_on`, `constrains`, `defines`, `decomposes_to`, `implemented_by`, `evidenced_by`, `replaces`, and `remediates`. No tool physically deletes graph records.

Each phase retains one current process record while superseded records remain in history. Review approval binds the current task change digest and completes a task only after every correction closes. Semantic findings reopen the earliest required phase. A clean analysis becomes `ready`.

`workflow_validate` reads canonical sorted logical database rows and exact SHA-256 file content. `workflow_mark_audited` repeats validation at the same revision inside its transaction and writes one audit attestation. Any later mutation stales that attestation.

## Seven Phases

1. `$app-constitution`
2. `$app-research`
3. `$app-specify`
4. `$app-functional-graph`
5. `$app-plan`
6. `$app-dev`
7. `$app-analyze`

Every phase carries `project_ref`, `wave_id`, revision, and logical digest. If either required MCP server is unavailable, the phase remains `pending`.

## Ownership

The `DIRECT` primary owns every direct phase and may use both servers. One persistent `repo-orchestrator` owns every delegated phase and both servers for its repository lane. `app-reviewer` and `app-analyst` receive limited read-only tools. `app-worker` and `workflow-orchestrator` receive neither server. Only the wave owner records mutations.

## Migration

`project_migrate_json` accepts `app-functional-map.v5` and `workflow-state.v1` only into an empty database. It verifies both declared SHA-256 values, checks imported parity, keeps source JSON files, and requires a new audit. A v4 map opens a new empty wave and remains snapshot evidence instead of receiving a lossy import. Source JSON deletion is a separate operator-reviewed change after parity succeeds.

## Validation

```bash
python3 skills/app-analyze/scripts/validate_workflow.py \
  --project-ref <project_ref> --wave-id <wave_id>

./install --codex-home /tmp/bears-app-workflow-codex --dry-run
```

The validator emits `ok`, `snapshot_digest`, and `findings` from read-only SQLite access. Database and MCP contracts are in `contracts/app-workflow-db-v1.sql` and `contracts/app-workflow-mcp-tools.v1.json`.

The runtime adapts entity, relation, observation, and MCP tool patterns from the pinned upstream memory server named in `THIRD_PARTY_NOTICES`. It does not copy JSONL rewrite storage, the fixed `memory://knowledge-graph` resource, or live subscriptions.

## Deployment

The existing main-branch CD topology remains separate from workflow execution. Push, promotion, merge, and deployment require separate authorization.
