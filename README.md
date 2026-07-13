# Bears App-Based Workflow

A Codex plugin for structured app workflow stages, deterministic trace/process indexes, immutable process events, bounded graph queries, semantic audits, and repo-scoped implementation orchestration.

## Graph Workflow v3

`contracts/app-workflow-definition.v2.json` is the single route, ownership, audit, and edge registry. Every inter-stage transfer uses `app-stage-handoff.v3`; `audited` is the only successful terminal status and means semantic/process consistency, not product acceptance. `automation_status` remains independent and autoCI remains the acceptance owner.

`app-context-index` is a facade over the deterministic `app-graph-compile` operation. An opted-in repository declares exact structured sources and tracked paths in `docs/app-graph-source-manifest.v1.json`. The compiler reads semantics only from the functional map, task ledger, workflow definition, and immutable journal. It publishes:

- `docs/app-traceability-index.v3.json`;
- `docs/app-process-index.v2.json`;
- `docs/app-index-build.v1.json`;
- `docs/app-context-index-result.v1.json`.

Process events are immutable files at `docs/app-process-events/v1/<run-ref>/<event-ref>.json`. Re-recording identical content is a no-op; a different payload at the same key is an error.

## MCP servers

`.mcp.json` registers:

- `app-graph`: read-only dependency, impact, trace, topological-plan, workflow-state, process-audit, and trace-audit tools;
- `app-graph-maintainer`: only `graph_compile` and `process_record_event`.

Both servers implement the MCP `2025-11-25` and `2025-06-18` initialize/initialized lifecycle. Pagination uses opaque snapshot-bound cursors. The maintainer requires `maintainer_enabled=true` and has no arbitrary path, shell, network, Git, credential, source, or ledger mutation surface.

## Stage boundaries

- `app-functional-graph` runs the semantic trace profile.
- `app-plan` runs the planning trace profile.
- `app-analyze` runs convergence trace and terminal process profiles.
- Before every handoff, the owner validates the transition, records the event that actually occurred, and compiles the resulting build.
- Only a DIRECT primary or repo-L2 writes journal events; L3 workers do not.

Findings route to `needs-research`, `needs-spec`, `needs-graph`, `needs-plan`, or `blocked` according to the workflow definition.

## CD-managed global instructions

The exact pinned plugin payload contains `assets/codex-home-graph-instructions.md`. Promotion reconciles its marked block into `$CODEX_HOME/AGENTS.md` after marketplace and role publication but before the durable deployment receipt. Unmanaged bytes are preserved. Duplicate or malformed markers, symlinks, non-regular files, or receipted block drift fail closed. The promotion intent retains original and desired bytes for recovery; disable removes only the receipted block and its owned separator.

## Version

Graph Workflow v3 role/runtime hardening is released as `0.3.2`. A `1.0.0` release requires an explicit user request.
