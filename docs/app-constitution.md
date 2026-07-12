# Bears App-Based Workflow Constitution

## Purpose

The plugin provides a deterministic app lifecycle from research through implementation analysis while preserving repository and delegation authority boundaries.

## Invariants

- Documents, code, tests, task records, results, reviews, commits, and existing evidence are authoritative; graph indexes are rebuildable relationship caches.
- One machine-readable workflow definition owns stage routes, artifact ownership, process gates, and graph edge semantics.
- Every inter-stage handoff carries the current source snapshot digest and traceability/process index refs.
- MCP graph access is read-only, bounded, local, and unable to mutate workflow state or declare acceptance.
- `DIRECT` remains with the primary; `DELEGATED` continues through the existing subagent procedure and authority contracts.

## Wave

The active `graph-workflow-v2` wave introduces typed traceability and process indexes, the context-index preflight, and the bundled read-only graph query server.
