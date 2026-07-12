# Graph Workflow v2 Specification

## Requirements

- `REQ-WORKFLOW-001`: one contract defines stage routes, ownership, entry gates, app-dev lifecycle, and edge semantics.
- `REQ-INDEX-001`: a source digest gates a rebuildable product traceability index.
- `REQ-PROCESS-001`: a process index records actual stage, handoff, task, review, remediation, and commit relationships.
- `REQ-GRAPH-001`: dependency closure, impact, cycle, reachability, ordering, and end-to-end trace queries are deterministic and bounded.
- `REQ-MCP-001`: agents receive those queries through a read-only local MCP surface with stable errors and pagination.
- `REQ-CYCLE-001`: every app stage consumes `app-stage-handoff.v2` and refreshes context only at entry, digest drift, or `needs-index`.

## Decisions

- `DEC-TRUTH-001`: indexes never override source artifacts.
- `DEC-LAYERS-001`: semantic functional mapping and actual development process are separate graph layers.
- `DEC-MIGRATION-001`: touched v1 consumers are read once, migrated to v2 refs with aliases/replacements, and do not retain dual active indexes.
- `DEC-CODE-001`: code entities require a relative file path and may add a symbol/API/test anchor; no full AST is stored.
- `DEC-MCP-001`: MCP has no write, network, credential, validation, or acceptance capability.
