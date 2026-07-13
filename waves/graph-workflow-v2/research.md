# Graph Workflow v3 research

## Sources

- MCP lifecycle and stdio transport contracts for initialization, notifications, and JSON-RPC errors.
- MCP pagination contract for opaque cursors.
- Existing v2 workflow artifacts and seven process events.
- Existing promotion transaction, role publication, and durable receipt implementation.

## Findings

A persistent immutable journal is required to audit actual workflow history. Derived indexes need a versioned opt-in source manifest and a build receipt so queries and cursors bind to one snapshot. Semantic audits can verify refs, digests, causality, ownership, and trace completeness without executing tests or assuming product acceptance. Managed global instructions must participate in the existing promotion recovery transaction.
