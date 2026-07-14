# Workflow Refactor v5 Research

## Objective

Define one workflow architecture across contracts, graph runtime, app stages, role profiles, documentation, structured sources, and delivery surfaces.

## Sources

- `contracts/app-workflow-definition.v3.json` defines stages, owners, routes, finding routes, terminal conditions, and delegation boundaries.
- `contracts/delegation-packets.v2.json` defines `repo-lane-dispatch.v1`, `dispatch-packet.v3`, `result-packet.v2`, and `app-task-dispatch.v2`.
- `contracts/app-stage-handoff.v4.schema.json` defines canonical handoff statuses and exact-snapshot fields.
- `contracts/app-functional-map.v4.schema.json` defines graph entities, relations, and seven-dimension coverage.
- `contracts/app-task-ledger.v3.schema.json` defines repository-owned work and evidence refs.
- `contracts/app-process-event.v3.schema.json` defines native process records and journal ownership.
- `contracts/app-semantic-analysis-result.v1.schema.json` defines app-analyze coverage, findings, completeness, and route.
- `role-definitions/workflow-orchestrator.json`, `role-definitions/domain-lane-orchestrator.json`, and `skills/subagents/SKILL.md` define the L1, repo-L2, and L3 authority boundaries.

## Findings

1. Stage authority must remain uniform across the complete app-* sequence instead of changing at development.
2. DELEGATED continuity requires one persistent repo-L2 from constitution through analysis.
3. L1 must open and continue each repository lane through native collaboration with `repo-lane-dispatch.v1`.
4. Repo-L2 must dispatch each L3 assignment only through `$subagents` with `dispatch-packet.v3`, `result-packet.v2`, and, for app-worker mutation, `app-task-dispatch.v2`.
5. Lane, dispatch, result, and handoff packets are typed transient protocol inputs; only the L3 identity fields represented by an immutable v3 event `delegation_record` become durable graph evidence.
6. Runtime graph operations establish structural correspondence, while app-analyze interprets logical correspondence across linked documentation and records.
7. `audited` can represent only complete semantic and process consistency on one exact snapshot.
8. A compact effectiveness methodology must observe the workflow without gaining route, journal, or mutation authority.
9. Human documentation must use the same seven dimensions and deterministic route vocabulary as the machine-readable workflow.

## Decision

Refactor contracts, graph lifecycle, stage procedures, role authority, documentation, structured graph sources, and delivery metadata as one versioned architecture cutover. Preserve native L1-to-repo-L2 lane coordination, L3-only `$subagents` dispatch, stage-owner journal authority, exact-snapshot analysis, and explicit representation boundaries for transient protocol inputs.
