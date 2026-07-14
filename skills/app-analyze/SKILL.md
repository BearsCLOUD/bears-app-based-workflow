---
name: app-analyze
description: Perform exact-snapshot semantic agent analysis of app documentation, graph meaning, and recorded implementation correspondence.
---

# App Analyze

## Ownership

- Keep the `DIRECT` primary as the stage owner for semantic analysis, result creation, routing, protocol decisions, journal events, and the outgoing handoff.
- Keep one persistent repo-L2 with role `domain-lane-orchestrator` as the stage owner for `DELEGATED` work.
- Keep `owner_session_ref=none` for `DIRECT` and preserve one non-`none` repo-L2 `owner_session_ref` for `DELEGATED` work.
- Require the repo-L2 to invoke every read-only analyst and result-writer L3 through `$subagents` and consume only bounded result packets.
- Never let an L3 write the journal, select the workflow transition, or emit the stage handoff.

## Input

- Accept only `app-stage-handoff.v4` status `implemented` or `no-work` for one repo boundary.
- Require an implemented analysis event to have exactly one direct repo-handoff cause and a no-work analysis event to have exactly one direct app-plan no-work cause.
- Refresh `$app-context-index` and reject a handoff whose build, source snapshot, or journal digest is stale.
- Read the exact source, decision, requirement, functionality, dimension mapping, relation, graph edge, functional-map, ledger, artifact, evidence, task, result, review, remediation, process-index, and incoming-boundary refs named by that build.
- Follow every opaque cursor until no cursor remains and reject any truncated or incomplete page set.
- Keep all structured sources and the journal read-only during analysis.

## Semantic analysis

Perform agent reasoning over documentation and structured graph content rather than treating structural compilation as semantic proof.

Analyze all of these correspondence surfaces:

1. Compare source statements to decisions and compare each decision to its derived requirements.
2. Detect contradictory sources, decisions, requirements, terms, owners, statuses, routes, and stage targets.
3. Verify behavior, dependency, state, API, data, integration, and error coverage with kind-compatible refs or explicit not-applicable rationale.
4. Verify dependency direction, forbidden cycles, replacement chains, impact direction, and topological task order.
5. Verify every active requirement has complete task, implementation-artifact, and evidence coverage or an explicit no-work basis.
6. Compare task results, immutable reviews, and remediation records to ledger states and causal native process events.
7. Detect reopened terminal tasks, missing events, unmatched result refs, unplanned changes, open remediation, and owner violations.
8. Verify every status and target against workflow v3, every handoff against handoff v4, and every delegated identity against delegation v2.

## Result

Emit one immutable `app-semantic-analysis-result.v1` conforming to `contracts/app-semantic-analysis-result.v1.schema.json`.

Bind `analysis_ref`, profile, model, checklist, exact basis build, categorized input bindings, coverage counts, findings, unmapped refs, open remediation refs, completeness, and route.

Represent each input category as the exact count plus the `sha256` digest of its canonical sorted unique ref array.

Give every finding exact subject refs, conflict refs, one workflow-v3 finding kind, one canonical route, and a bounded summary.

Select the top-level route from the earliest required corrective stage in workflow v3 and use `blocked` only for its defined stop conditions.

## Delegated analysis

1. Require the repo-L2 to partition exact read-only surfaces without omitting any source, graph, ledger, or process page.
2. Dispatch each bounded analyst L3 through `$subagents` with the same basis build and checklist refs.
3. Reject overlapping conclusions that disagree without an explicit contradiction finding.
4. Combine only bounded result facts and dispatch a separate writer L3 through `$subagents` to persist the result artifact.
5. Preserve every consumed input and authority ref across the analyst and writer packets.

## Completion

1. Emit the canonical routed `app-stage-handoff.v4` when any contradiction, gap, unmapped ref, or open remediation remains.
2. Put the semantic result and finding refs in the handoff artifact and finding fields.
3. Emit `audited` only when exact-page coverage is complete, logical contradictions are zero, unmapped decisions are zero, unmapped requirements are zero, routable findings are zero, and open remediation tasks are zero.
4. Require the final source snapshot digest to equal the analyzed basis snapshot and repeat analysis after any semantic-source drift.
5. Treat `audited` only as documentation-and-graph logical consistency for the exact basis build.
6. Put `analysis_ref` and the exact semantic result in the audited handoff payload.
7. Bind the handoff owner mode, owner session, repo, wave, trace links, build, source snapshot, and journal digest to the analyzed run.
8. Validate the candidate handoff and transition against workflow v3 and handoff v4.
9. Record one actual native v3 analysis event with `analysis_ref` through the `DIRECT` primary or repo-L2.
10. Reconcile the resulting journal and emit the build-bound terminal or corrective handoff.
