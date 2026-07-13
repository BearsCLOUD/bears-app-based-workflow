---
name: app-functional-graph
description: Maintain decision-complete app semantics and typed dependency relations before planning.
---

# App Functional Graph

## Ownership

- Keep the `DIRECT` primary as the stage owner for target access, graph changes, protocol decisions, journal events, and the outgoing handoff.
- Keep one persistent repo-L2 with role `domain-lane-orchestrator` as the stage owner for `DELEGATED` work.
- Require the repo-L2 to invoke every L3 assignment through `$subagents` and consume only its bounded result packet.
- Never let an L3 write the journal, select a transition, or emit the stage handoff.

## Input

- Accept only `app-stage-handoff.v4` status `spec-ready` or `needs-graph` for the same repo boundary.
- Require a current `$app-context-index` result whose build and source snapshot match the handoff.
- Resolve graph kinds, edge direction, routes, and transitions only from `contracts/app-functional-map.v4.schema.json` and `contracts/app-workflow-definition.v3.json`.
- Follow every opaque cursor until no cursor remains before treating a graph result as complete.

## Semantic mapping

Create or update only `docs/app-functional-map.v4.json` as `app-functional-map.v4`.

Map every source decision to its requirements and map every active requirement to typed functionality or behavior.

Map each requirement across behavior, dependency, state, API, data, integration, and error dimensions.

Use kind-compatible entity refs for each dimension and use `not-applicable` only with empty refs and an explicit rationale.

Record typed relations with stable refs and direct `depends_on` from the dependent entity to its prerequisite.

Reject unknown edge kinds, dangling refs, duplicate refs, forbidden cycles, reversed dependency direction, and missing source provenance.

Record replacements instead of deleting any ref used by a task or process record.

Never create or mutate ledger tasks in this stage.

## Completion

1. Require the `DIRECT` primary to perform the bounded reads and writes itself.
2. Require the repo-L2 in `DELEGATED` mode to decompose each bounded read or write and dispatch each L3 through `$subagents`.
3. Return `needs-spec` for an unresolved decision or requirement meaning without inferring its resolution.
4. Reconcile the changed functional map through `$app-context-index` and reject any structural finding before handoff.
5. Select `graph-ready` only with complete seven-dimension coverage and current functional-map, entity, coverage, and replacement refs.
6. Validate the candidate `app-stage-handoff.v4`, record only the actual native v3 stage event, and reconcile the resulting journal.
7. Emit the build-bound handoff with target `app-plan` from workflow v3.
