# App graph runtime modules

- `app_graph_engine.py` loads only tracked graph/process JSON under a supplied app root, rechecks every indexed source digest, and implements bounded read-only queries.
- `app_graph_mcp.py` exposes those queries through stdio MCP. It has no write, network, credential, acceptance, or validation surface.

Runtime risks are path escape, oversized artifacts, response amplification, and stale or incompatible snapshots. The modules fail closed through stable error codes, source re-hashing, trace/process/workflow digest agreement, and bounded files, depth, item count, and response size. Impact traversal honors each edge type's transitive flag; diagnostics inspect every forbidden-cycle edge type; planning reports structural and open-finding blockers. Product acceptance remains outside this runtime surface.

`app_graph_engine.py` remains slightly above 400 lines so loading, legacy normalization, edge-registry checks, traversal direction, cycle detection, and query bounds share one invariant surface. The repository's existing `plugin-ci-cd` autoCI pipeline remains the only acceptance pipeline; these modules add no agent-executable test or acceptance command.
