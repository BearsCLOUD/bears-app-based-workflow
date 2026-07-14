<!-- >>> bears-app-based-workflow graph behavior (managed by CD) -->
# Bears app graph behavior

- At app workflow start, verify the opted-in source manifest, current build receipt, source snapshot digest, journal digest, and graph state.
- Assign every DIRECT stage to the DIRECT primary and every DELEGATED stage to one persistent `repo-orchestrator` repo-L2 with one stable owner-session ref.
- Keep `workflow-orchestrator` L1 limited to opening and continuing repository lanes.
- Dispatch L3 work only through $subagents and keep each assignment bounded to its declared result.
- Use graph dependencies, impact results, and the topological plan for work order.
- On structured-source or journal drift, invoke app-graph-compile with the current build as its compare-and-swap expectation.
- Keep task scope empty before app-plan; let ordinary plan-ready establish it; preserve source scope through terminal corrective needs-plan; then start one linked run with only its remediation tasks.
- For every outgoing boundary, prepare the payload, record only the event that occurred with its digest, reconcile the journal, then require app-graph.handoff_validate on the current candidate.
- Require complete task-result provenance and exactly one final clean full-scope review before an implemented repo handoff.
- At app-analyze, exhaust each opaque cursor and compare the exact documentation, graph edges, ledger, artifacts, evidence, task results, reviews, remediation tasks, and process records for logical correspondence.
- Bind each complete analysis input set by count and canonical digest; reduce every finding through the workflow registry and emit audited only for complete semantic and process consistency.
- Use app-graph-maintainer only when maintainer_enabled=true in the exact repository manifest.
<!-- <<< bears-app-based-workflow graph behavior (managed by CD) -->
