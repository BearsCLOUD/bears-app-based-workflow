# App Graph Runtime Modules

## Module ownership

- app_graph_engine.py preserves public imports and dispatches supported tool calls.
- app_graph_store.py owns bounded source loading, digests, snapshot cursors, and drift-aware caches.
- app_graph_compiler.py owns deterministic compare-and-swap publication and immutable build receipts.
- app_graph_process.py owns native immutable event recording and exact repository-wave lifecycle rules.
- app_graph_query.py owns bounded dependency, bidirectional impact, trace, ordering, workflow-state, and diagnostic queries.
- app_graph_mcp.py exposes the read-only app-graph surface or the two-operation app-graph-maintainer surface through lifecycle-correct stdio MCP.
- role_profile_renderer.py renders deterministic role profiles from authoritative JSON definitions.

## Runtime boundary

The compiler reads structured meaning only from the workflow definition, functional map, task ledger, and native process journal. Tracked implementation and evidence artifacts contribute digests but never inferred semantics.

Duplicate refs, dangling refs, unknown edges, corrupt events, path escape, symlinks, stale compare-and-swap expectations, and resource-limit violations fail closed before publication.

The runtime supplies exact graph and process context. app-analyze remains agent-authored semantic analysis of documentation correspondence and is not a runtime product evaluator.

## Bounds

Requests are limited to 64 KiB and responses to 16 KiB. Page size is 50 by default and 200 at most. Traversal depth is 8 by default and 32 at most. Input is limited to 2,048 sources and 64 MiB, with at most 25,000 entities, 100,000 edges, 20,000 events, and 50,000 process links.
