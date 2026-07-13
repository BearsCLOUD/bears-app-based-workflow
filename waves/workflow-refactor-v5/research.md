# Workflow Refactor v5 Research

## Objective

Establish one human-readable workflow model that matches the v3 route registry, persistent stage ownership, graph semantics, and agent-authored correspondence analysis.

## Sources

- contracts/app-workflow-definition.v3.json defines stages, owners, routes, finding routes, terminal conditions, and delegation boundaries.
- contracts/app-stage-handoff.v4.schema.json defines canonical handoff statuses and exact snapshot bindings.
- contracts/app-functional-map.v4.schema.json defines graph entities, relations, and seven-dimension coverage.
- contracts/app-task-ledger.v3.schema.json defines repository-owned work and proof refs.
- contracts/app-process-event.v3.schema.json defines native process records and journal ownership.
- contracts/app-semantic-analysis-result.v1.schema.json defines app-analyze coverage, findings, completeness, and route.

## Findings

1. Stage authority must be uniform across the complete app-* sequence rather than changing at development.
2. DELEGATED continuity requires one persistent repo-L2 from constitution through analysis.
3. L3 work is useful only as an assignment-bounded result returned through $subagents.
4. Runtime graph operations can prove structural facts, but documentation correspondence requires an agent to interpret meaning across linked sources.
5. audited can represent only complete semantic and process consistency on one exact snapshot.
6. A compact effectiveness methodology must observe the workflow without gaining route, journal, or execution authority.
7. Human documentation must use the same seven dimensions and deterministic route vocabulary as the machine-readable workflow.

## Decision

Refactor the designated human documentation around ownership, exact-snapshot semantics, seven dimensions, canonical routes, and app-analyze correspondence. Keep runtime, contract, skill, role, installer, and deployment implementation changes outside this documentation assignment.
