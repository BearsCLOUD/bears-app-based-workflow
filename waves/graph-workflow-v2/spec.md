# Graph Workflow v3 specification

Wave: `graph-workflow-v2`
Run: `RUN-GRAPH-WORKFLOW-V2`

## v3 cutover

Continue the existing run and preserve the seven v2 process refs as immutable `legacy-import` events. Replace active handoff/index/ledger generations rather than running two generations in parallel. The original v3 cutover was `0.3.0`; the reviewed role/runtime hardening cutover is `0.3.2`.

## v3 requirements

- `REQ-WORKFLOW-001`: the workflow definition owns routes and `audited`; semantic/process consistency is separate from autoCI acceptance.
- `REQ-INDEX-001`: identical structured inputs compile to byte-identical indexes and one stable build ref; CAS prevents stale publication.
- `REQ-PROCESS-001`: process events are immutable and idempotent, with conflicts and corrupt history rejected.
- `REQ-GRAPH-001`: queries are bounded, iterative, and paginated with opaque snapshot/query-bound cursors.
- `REQ-MCP-001`: read-only and maintainer MCP servers implement supported lifecycle and JSON-RPC behavior.
- `REQ-CYCLE-001`: semantic, planning, convergence, and terminal process audits route exact findings without executing tests.
- `REQ-CD-001`: CD transactionally reconciles one receipted managed block in `$CODEX_HOME/AGENTS.md` while preserving unmanaged bytes.
- `REQ-OWNERSHIP-001`: only a DIRECT primary or repo-L2 records events; L3 workers never modify the journal.

## Decision

`DEC-GRAPH-V3` selects structured sources, a persistent event journal, deterministic derived indexes, read-only audits, and a narrowly scoped opt-in maintainer. Markdown may be tracked by digest but is never interpreted as graph meaning.
