# App graph runtime modules

- `app_graph_engine.py` loads only tracked graph/process JSON under a supplied app root and implements bounded read-only queries.
- `app_graph_mcp.py` exposes those queries through stdio MCP. It has no write, network, credential, acceptance, or validation surface.

Runtime risks are path escape, oversized artifacts, response amplification, and stale source snapshots. The modules fail closed through stable error codes and bounded files, depth, item count, and response size. Product acceptance remains outside this runtime surface.

`app_graph_engine.py` remains slightly above 400 lines so loading, legacy normalization, edge-registry checks, traversal direction, cycle detection, and query bounds share one invariant surface. The repository's existing `plugin-ci-cd` autoCI pipeline remains the only acceptance pipeline; these modules add no agent-executable test or acceptance command.
