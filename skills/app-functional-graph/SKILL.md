---
name: app-functional-graph
description: Maintain a source-linked functional graph for the specified behavior through MCP. The orchestrator workflow decides when this phase runs.
---

# App Functional Graph

## Purpose

Represent the specified behavior as a durable, source-linked graph of entities,
observations, and relations. The graph is the shared model that planning,
development, and analysis read from.

## Done means

- The graph reflects the current specification and its records cite local source refs.
- The graph delta is described in `waves/<wave_id>/functional-graph.md`.
- The artifact explains the resulting model, its constraint-bearing relations, and the meaning of the change.

## How to think about this phase

- Model what the specification commits to, not what the code happens to look like today.
- Treat a record without a local source ref as unsupported graph content.
- Prefer stable refs that survive rewrites and make each delta's semantic effect clear.
- Use the closed relation set: `depends_on`, `constrains`, `defines`, `decomposes_to`, `implemented_by`, `evidenced_by`, `replaces`, and `remediates`.
- Make a good graph delta source-linked, internally coherent, and sufficient for a reader to reconstruct the affected model without querying.
- Explain which entities, observations, and relations carry the behavior or constraints, and identify any superseded meaning without silently changing it.

## Tools and artifact

- Read graph state and diagnostics through the workflow MCP tools.
- Record the resulting phase artifact at `waves/<wave_id>/functional-graph.md`.

The orchestrator workflow owns phase sequencing and execution decisions. The
maintainer server owns graph mutation mechanics, validation, concurrency,
atomicity, and lifecycle enforcement. This skill does not prescribe their order
or mechanics.
