<!-- >>> bears-app-based-workflow graph behavior (managed by CD) -->
# Bears app graph behavior

- At app workflow start, verify the opted-in source manifest, current build receipt, source snapshot digest, journal digest, and graph state.
- Assign every DIRECT stage to the DIRECT primary and every DELEGATED stage to one persistent repo-L2.
- Dispatch L3 work only through $subagents and keep each assignment bounded to its declared result.
- Use graph dependencies, impact results, and the topological plan for work order.
- On structured-source or journal drift, invoke app-graph-compile with the current build as its compare-and-swap expectation.
- Record only events that occurred, and let only the DIRECT primary or persistent repo-L2 append them.
- At app-analyze, compare the exact documentation, graph, ledger, implementation refs, and process records for logical correspondence.
- Route every finding through the workflow registry and emit audited only for complete semantic and process consistency.
- Use app-graph-maintainer only when maintainer_enabled=true in the exact repository manifest.
- Treat cursors as opaque and continue pagination until no cursor remains.
<!-- <<< bears-app-based-workflow graph behavior (managed by CD) -->
