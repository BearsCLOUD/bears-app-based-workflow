# Workflow Refactor v5 Plan

## Dependency order

| Order | Ledger task | Work item | Depends on |
| --- | --- | --- | --- |
| 1 | `TASK-WF5-CONTRACTS` | Replace the workflow, graph, process, handoff, analysis, ledger, catalog, and delegation contracts as one versioned model. | None |
| 2 | `TASK-WF5-GRAPH-RUNTIME` | Enforce the active model in compilation, event admission, queries, storage, and MCP surfaces. | `TASK-WF5-CONTRACTS` |
| 3 | `TASK-WF5-STAGES` | Align every app stage with mode-bound ownership, exact-snapshot handoffs, and semantic analysis. | `TASK-WF5-CONTRACTS` |
| 4 | `TASK-WF5-ROLES` | Align L1, persistent repo-L2, L3 role kinds, capabilities, and `$subagents` dispatch. | `TASK-WF5-STAGES` |
| 5 | `TASK-WF5-DOCS-GRAPH` | Reconcile human documentation, structured semantics, exact artifact coverage, and the observational assessment methodology. | `TASK-WF5-GRAPH-RUNTIME`, `TASK-WF5-ROLES` |
| 6 | `TASK-WF5-DELIVERY` | Align plugin metadata, installation, and machine-owned publication surfaces with the refactored model. | `TASK-WF5-DOCS-GRAPH` |

Use the exact target paths, implementation refs, evidence refs, and queue sequence from `docs/app-task-ledger.v3.json`; do not infer a second work order from this prose.

## Completion conditions

- Every ledger target is represented by one exact catalog ref and one owning task.
- Every app stage uses the same mode-bound owner and deterministic route vocabulary.
- Every active requirement maps all seven dimensions with kind-compatible evidence.
- Every native event preserves owner, causal, task, trace, and artifact correspondence.
- The exact-snapshot semantic result has no contradictions, gaps, unmapped refs, or open remediation.
- The effectiveness assessment remains read-only and outside workflow authority.
