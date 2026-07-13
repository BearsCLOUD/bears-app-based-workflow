# App graph runtime modules

- `app_graph_engine.py` owns safe source loading, deterministic compilation, immutable event recording, build verification, opaque cursors, iterative traversal, and read-only process/trace audits.
- `app_graph_mcp.py` exposes either the read-only `app-graph` surface or the two-tool `app-graph-maintainer` surface through lifecycle-correct stdio MCP.

`app_graph_engine.py` intentionally exceeds the usual 400-line module target because compiler publication, journal integrity, cursor binding, and read-time digest verification share one fail-closed invariant set; splitting those checks would create multiple security-critical implementations of the same graph boundary. Its public entry point remains the single `execute_tool` dispatcher.

Bounded decomposition plan for the next runtime change: extract safe source/manifest loading into `app_graph_sources.py`, compiler and journal mutation into `app_graph_maintainer.py`, and read queries/audits into `app_graph_queries.py`; keep canonical serialization, digests, errors, and limits in the engine facade so each extracted module still uses one invariant implementation. This release does not mix that structural refactor with the v3 cutover.

The compiler reads structured semantics only from the workflow definition, functional map, task ledger, and event journal. Tracked code/test/evidence files contribute digests but never inferred meaning. Duplicate or dangling refs, unknown edges, corrupt events, path escape, symlinks, stale CAS, and resource limits fail closed before the build receipt is published.

Limits are 64 KiB request, 16 KiB response, 50 default/200 maximum page size, 8 default/32 maximum traversal depth, 2,048 sources/64 MiB aggregate input, 25,000 entities, 100,000 edges, 20,000 events, and 50,000 process links. Semantic audits never execute tests and never produce product acceptance.
