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
2. DELEGATED continuity requires one persistent repo-L2 of kind `repo-orchestrator` and one stable owner-session ref from constitution through analysis.
3. L1 of kind `workflow-orchestrator` must only open and continue each repository lane through native collaboration with `repo-lane-dispatch.v1`.
4. Repo-L2 must dispatch each L3 assignment only through `$subagents` with `dispatch-packet.v3`, `result-packet.v2`, and, for app-worker mutation, `app-task-dispatch.v2`.
5. Lane, dispatch, result, and handoff packets are typed transient inputs; completed L3 provenance becomes durable in a delegation event, or atomically inside the app-analyze event, only after binding result and identity fields.
6. Runtime graph operations establish structural correspondence, while app-analyze interprets logical correspondence across linked documentation, graph edges, result provenance, reviews, remediation ledger tasks, and records.
7. The implemented path requires complete task results, one final clean immutable review, one repo handoff, and then analysis; canonical `no-work` originates at app-plan.
8. Large exact input sets require canonical count-and-digest bindings rather than unbounded event payloads.
9. `audited` can represent only complete semantic and process consistency on one exact snapshot.
10. A compact effectiveness methodology must observe the workflow without gaining route, journal, or mutation authority and must hide its sealed scoring key from the assessed agent.
11. Human documentation must use the same seven dimensions and deterministic route vocabulary as the machine-readable workflow.
12. A typed handoff is insufficient unless a read-only runtime consumer proves its current build, source event, owner, route, refs, and payload digest; implemented and audited payloads also require exact reconstruction.
13. Commit-shaped strings are insufficient provenance; retained refs must resolve to Git commit objects, review ranges must preserve forward ancestry, and every reviewed commit must be represented by an in-scope task result.
14. New correction work cannot enter an immutable run scope; it must be a ledger remediation task in a single-successor acyclic linked run with an exact source basis.
15. Result pagination must remain within the response budget while preserving opaque continuation.
16. Pre-plan events have empty task scope; ordinary `plan-ready` establishes it; semantic correction preserves it until app-plan returns `no-work` or seals `needs-plan`; a linked run starts only its exact remediation tasks.
17. The compiler and graph queries must consume one closed edge registry, reject every forbidden cycle generically, deduplicate impact results, and project `remediates` lineage.
18. A build bundle must be complete and immutable under its build ref before one atomic compare-and-swap pointer publication; a failed publication must leave the current bundle intact.

## Decision

Refactor contracts, graph lifecycle, stage procedures, role authority, documentation, structured graph sources, and delivery metadata as one versioned architecture cutover. Preserve native L1-to-repo-L2 lane coordination, completed-result L3 provenance, stage-owner journal authority, phased immutable task scope, exact Git review provenance, validated exact-build handoffs, linked correction runs, closed edge semantics, atomic immutable build publication, exact-snapshot analysis, and sealed assessment keys.
