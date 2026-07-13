# Workflow Refactor v5 Specification

## Functional requirements

| Ref | Requirement |
| --- | --- |
| WF5-01 | The DIRECT primary must own every app-* stage for a DIRECT workstream. |
| WF5-02 | One persistent repo-L2 must own every app-* stage for a DELEGATED workstream. |
| WF5-03 | The repo-L2 must dispatch every L3 assignment through $subagents and retain stage and route authority. |
| WF5-04 | Only the DIRECT primary or persistent repo-L2 may append native process records. |
| WF5-05 | app-analyze must compare documentation, graph, ledger, implementation refs, review records, and process records on one exact snapshot. |
| WF5-06 | app-analyze must return covered refs, findings, unmapped refs, open remediation refs, completeness, and one canonical route. |
| WF5-07 | audited must mean complete semantic and process consistency only. |
| WF5-08 | Every active requirement must map behavior, dependency, state, api, data, integration, and error or provide a sourced not-applicable rationale. |
| WF5-09 | Every stage status and finding must route through contracts/app-workflow-definition.v3.json. |
| WF5-10 | Effectiveness assessment must remain read-only and separate from workflow authority. |

## Dimension semantics

- behavior captures observable responses and their governing rules.
- dependency captures prerequisites, ordering, constraints, and impact.
- state captures modes, transitions, invariants, and persistence.
- api captures interfaces, protocols, inputs, outputs, and compatibility.
- data captures entities, fields, ownership, lifecycle, and protection.
- integration captures system boundaries, counterparties, and message flow.
- error captures failure conditions, recovery, and visible consequences.

## Route semantics

- constitution-ready and needs-research route to app-research.
- research-ready and needs-spec route to app-specify.
- spec-ready and needs-graph route to app-functional-graph.
- graph-ready, waiting, and needs-plan route to app-plan.
- plan-ready and ready route to app-dev.
- implemented and no-work route to app-analyze.
- audited and blocked are terminal.

## Documentation scope

This wave updates README.md, CHANGELOG.md, AGENTS.md, the managed instruction asset, runtime and runner guides, the constitution, the effectiveness methodology, the wave index, the four wave documents, and the evidence packet.
