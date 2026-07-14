# Workflow Refactor v5 Plan

## Dependency order

| Order | Ledger task | Work item | Depends on |
| --- | --- | --- | --- |
| 1 | `TASK-WF5-CONTRACTS` | Replace the workflow, graph, process, handoff, analysis, ledger, catalog, and delegation contracts as one versioned model. | None |
| 2 | `TASK-WF5-GRAPH-RUNTIME` | Enforce the active model in compilation, event admission, handoff validation, Git provenance, bounded queries, storage, and MCP surfaces. | `TASK-WF5-CONTRACTS` |
| 3 | `TASK-WF5-STAGES` | Align every app stage with mode-bound ownership, exact-snapshot handoffs, and semantic analysis. | `TASK-WF5-CONTRACTS` |
| 4 | `TASK-WF5-ROLES` | Align L1, persistent repo-L2, L3 role kinds, capabilities, and `$subagents` dispatch. | `TASK-WF5-STAGES` |
| 5 | `TASK-WF5-DOCS-GRAPH` | Reconcile human documentation, structured semantics, exact artifact coverage, and the observational assessment methodology. | `TASK-WF5-GRAPH-RUNTIME`, `TASK-WF5-ROLES` |
| 6 | `TASK-WF5-DELIVERY` | Align plugin metadata, installation, and machine-owned publication surfaces with the refactored model. | `TASK-WF5-DOCS-GRAPH` |

Use the exact target paths, implementation refs, evidence refs, and queue sequence from `docs/app-task-ledger.v3.json`; do not infer a second work order from this prose.

## Completion conditions

- Every ledger target is represented by one exact catalog ref and one owning task.
- Every app stage uses the same mode-bound owner and deterministic route vocabulary.
- Every active requirement maps all seven dimensions with kind-compatible evidence.
- Every native event preserves owner-session, exact task-spec, causal, trace, artifact, payload-digest, completed-result, commit, and exact-review correspondence.
- Corrective research, specification, and graph stages preserve source-run scope until app-plan returns `no-work` or seals `needs-plan`; only the linked run admits new remediation tasks.
- Every source run has at most one linked successor, and remediation lineage is acyclic and traversable.
- Compiler and queries share one closed edge registry with generic cycle rejection and deduplicated impact.
- Each immutable build bundle is complete before one atomic current-pointer publication.
- Every outgoing handoff proves the current source event, derived identity, exact build, and payload digest; implemented and audited payloads are reconstructed exactly.
- New correction work is represented only by remediation ledger tasks in a source-linked follow-up run.
- The exact-snapshot semantic result has no contradictions, gaps, unmapped refs, or open remediation tasks.
- The semantic result binds every categorized input set by an exact count and canonical digest.
- The effectiveness assessment remains read-only, keeps its scoring key sealed, and remains outside workflow authority.

## Linked correction run

Source run `RUN-WORKFLOW-REFACTOR-V5-SOURCE-001` routes finding `FIND-WF5-CORRECTION-SCOPE-UNREPRESENTED` to the exact remediation scope below. The historical tasks above remain immutable context and are not reopened.

| Order | Remediation task | Scope | Depends on |
| --- | --- | --- | --- |
| 1 | `TASK-WF5-REM-CONTRACTS` | Changed workflow contracts. | None |
| 2 | `TASK-WF5-REM-GRAPH-RUNTIME` | Changed graph runtime and its operator documentation. | `TASK-WF5-REM-CONTRACTS` |
| 3 | `TASK-WF5-REM-STAGES` | Changed app-stage and subagent instructions. | `TASK-WF5-REM-CONTRACTS` |
| 4 | `TASK-WF5-REM-ROLES` | Changed role definitions, profiles, catalog, and renderer. | `TASK-WF5-REM-STAGES` |
| 5 | `TASK-WF5-REM-DOCS-GRAPH` | Changed documentation, graph sources, frozen assessment, ledger, and wave packet. | `TASK-WF5-REM-GRAPH-RUNTIME`, `TASK-WF5-REM-ROLES` |
| 6 | `TASK-WF5-REM-DELIVERY` | Changed plugin metadata. | `TASK-WF5-REM-DOCS-GRAPH` |

The linked run ref is `RUN-WORKFLOW-REFACTOR-V5-CORRECTION-001`. Exact targets, catalog bindings, queue order, and remediation basis remain authoritative only in `docs/app-task-ledger.v3.json`.
