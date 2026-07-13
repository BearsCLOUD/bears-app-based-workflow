<!-- >>> bears-app-based-workflow graph behavior (managed by CD) -->
## Bears app graph behavior

- At the start of app workflow work, verify the opted-in source manifest, current build receipt, source snapshot digest, journal digest, and graph state.
- Use graph dependencies, impact results, and the topological task plan; do not infer dependency order from prose.
- On structured-source or journal drift, invoke `app-graph-compile` with the current build as its compare-and-swap expectation.
- Record only stage, task, review, and remediation events that actually occurred. Before every handoff run the process audit; at functional-graph, plan, and analyze boundaries also run the semantic, planning, or convergence trace audit.
- Route findings through canonical `needs-*` statuses. `audited` is the only successful terminal status and means semantic/process consistency, not product acceptance; autoCI remains the acceptance owner.
- Respect ownership: the DIRECT primary or repo-L2 may append journal events; an L3 worker never writes the journal.
- Use `app-graph-maintainer` only when `maintainer_enabled=true` in the exact repository manifest.
- Treat cursors as opaque. Continue pagination until no cursor remains, and never treat a truncated result as complete.
<!-- <<< bears-app-based-workflow graph behavior (managed by CD) -->
