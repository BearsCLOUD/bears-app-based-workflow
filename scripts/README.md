# App graph runtime modules

- `app_graph_engine.py` is the compatibility facade and preserves public imports and tool names.
- `app_graph_store.py` owns safe source loading, digests, cursors, and drift-aware caches.
- `app_graph_compiler.py` owns deterministic CAS publication and immutable build receipts.
- `app_graph_process.py` owns native v2 immutable event recording and exact repo-wave lifecycle checks.
- `app_graph_query.py` owns bounded dependency, bidirectional impact, trace, ordering, and workflow-state queries.
- `app_graph_audit.py` owns whole-branch trace and exact-run process audits.
- `app_graph_mcp.py` exposes either the read-only `app-graph` surface or the two-tool `app-graph-maintainer` surface through lifecycle-correct stdio MCP.

All modules consume the single store invariant set. The facade exposes the unchanged `execute_tool` dispatcher; callers do not import implementation modules.

The compiler reads structured semantics only from the workflow definition, functional map, task ledger, and event journal. Tracked code/test/evidence files contribute digests but never inferred meaning. Duplicate or dangling refs, unknown edges, corrupt events, path escape, symlinks, stale CAS, and resource limits fail closed before the build receipt is published.

Limits are 64 KiB request, 16 KiB response, 50 default/200 maximum page size, 8 default/32 maximum traversal depth, 2,048 sources/64 MiB aggregate input, 25,000 entities, 100,000 edges, 20,000 events, and 50,000 process links. Semantic audits never execute tests and never produce product acceptance.
