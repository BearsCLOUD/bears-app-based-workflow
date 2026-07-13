# Bears App-Based Workflow Constitution

## Purpose

The plugin turns app intent into deterministic documentation, graph, plan, implementation orchestration, and semantic correspondence analysis while preserving repository and delegation authority.

## Source authority

- Keep source documents, structured semantic records, ledger records, implementation refs, review records, process events, and evidence authoritative.
- Treat traceability and process indexes as rebuildable projections.
- Bind every stage handoff to one build ref, source snapshot digest, journal digest, and explicit source refs.
- Use contracts/app-workflow-definition.v3.json as the only stage and finding route registry.
- Derive work order from typed graph dependencies and the topological ledger plan.

## Stage authority

- Let the DIRECT primary own every app-* stage for DIRECT work.
- Let one persistent repo-L2 own every app-* stage for DELEGATED work.
- Let the stage owner choose the next route and append native process records.
- Let the repo-L2 dispatch assignment-bounded L3 work only through $subagents.
- Let L3 workers return results to the repo-L2 without acquiring stage or journal authority.

## Stage flow

The ordered stages are app-constitution, app-research, app-specify, app-functional-graph, app-plan, app-dev, and app-analyze.

app-analyze compares the exact documentation, graph, ledger, implementation refs, review records, and process records for logical correspondence. Its structured result names covered refs, contradictions, unmapped decisions or requirements, open remediation, findings, completeness, and one canonical route.

## Seven dimensions

Every active requirement must map all seven dimensions or state a sourced not-applicable rationale.

| Dimension | Required meaning |
| --- | --- |
| behavior | Actor or system response and governing rule. |
| dependency | Prerequisites, ordering, constraints, and affected capabilities. |
| state | Modes, transitions, invariants, and persistence. |
| api | Interfaces, protocols, inputs, outputs, and compatibility. |
| data | Entities, fields, ownership, lifecycle, and protection. |
| integration | System boundaries, counterparties, and message flow. |
| error | Failure conditions, recovery behavior, and visible consequences. |

## Route vocabulary

| Status group | Deterministic target |
| --- | --- |
| constitution-ready, needs-research | app-research |
| research-ready, needs-spec | app-specify |
| spec-ready, needs-graph | app-functional-graph |
| graph-ready, waiting, needs-plan | app-plan |
| plan-ready, ready | app-dev |
| implemented, no-work | app-analyze |
| audited, blocked | none |

Route a missing source to needs-research, a product or decision conflict to needs-spec, a semantic or reference gap to needs-graph, a task or remediation gap to needs-plan, and an access, credential, or operator stop to blocked.

## Terminal meaning

audited means semantic and process consistency on one exact snapshot. It requires complete semantic analysis, zero logical contradictions, zero unmapped decisions, zero unmapped requirements, zero routable findings, and zero open remediation.

The plugin workflow owns only this documentation-and-process conclusion. Product outcome decisions remain outside its authority.
