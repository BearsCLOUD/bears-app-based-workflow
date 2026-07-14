---
name: app-analyze
description: Perform exact-snapshot semantic agent analysis of app documentation, graph meaning, and recorded implementation correspondence.
---

# App Analyze

## Ownership

- Keep the `DIRECT` primary as the stage owner for semantic analysis, result creation, routing, protocol decisions, journal events, and the outgoing handoff.
- Keep one persistent repo-L2 with role `domain-lane-orchestrator` as the stage owner for `DELEGATED` work.
- Keep `owner_session_ref=none` for `DIRECT` and preserve one non-`none` repo-L2 `owner_session_ref` for `DELEGATED` work.
- Require the repo-L2 to invoke one `explorer` analyst through `$subagents` and consume only its bounded semantic result packet.
- Never let an L3 write the journal, select the workflow transition, or emit the stage handoff.

## Input

- Accept only `app-stage-handoff.v4` status `implemented` or `no-work` for one repo boundary.
- Require the analysis event to have exactly one direct cause: a repo-handoff with status `implemented` or an app-plan stage event with status `no-work`.
- Refresh `$app-context-index` and reject a handoff whose build, source snapshot, or journal digest is stale.
- Read the exact source, decision, requirement, functionality, dimension mapping, relation, graph edge, functional-map, ledger, artifact, evidence, task, result, review, remediation-task, process-index, and incoming-boundary refs named by that build.
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
6. Compare task results, immutable reviews, and remediation tasks to ledger states and causal native process events.
7. Detect reopened terminal tasks, missing events, unmatched result refs, unplanned changes, open remediation tasks, and owner violations.
8. Verify every status and target against workflow v3 and every delegated identity against delegation v2.

## Result

Emit one immutable `app-semantic-analysis-result.v1` conforming to `contracts/app-semantic-analysis-result.v1.schema.json`.

Bind `analysis_ref`, profile, model, checklist, exact basis build, categorized input bindings, coverage counts, findings, unmapped refs, open remediation task refs, completeness, and route.

Represent each input category as the exact count plus the `sha256` digest of its canonical sorted unique ref array.

Give every finding exact subject refs, conflict refs, one workflow-v3 finding kind, one canonical route, and a bounded summary.

Select the top-level route from the earliest required corrective stage in workflow v3 and use `blocked` only for its defined stop conditions.

## Delegated analysis

1. Require the repo-L2 to bind every named documentation path and every graph page to one exact read-only assignment.
2. Dispatch one `explorer` L3 through `$subagents` with the basis build and checklist refs.
3. Accept only one complete `app-semantic-analysis-result.v1` fact from that assignment.
4. Preserve every consumed input and authority ref and bind the completed analyst record inside the single analysis event.

## Completion

1. Emit the canonical routed `app-stage-handoff.v4` when any contradiction, gap, unmapped ref, or open remediation task remains.
2. Put the semantic result and finding refs in the handoff artifact and finding fields.
3. Emit `audited` only when exact-page coverage is complete, logical contradictions are zero, unmapped decisions are zero, unmapped requirements are zero, routable findings are zero, and open remediation tasks are zero.
4. Require the final source snapshot digest to equal the analyzed basis snapshot and repeat analysis after any semantic-source drift.
5. Treat `audited` only as semantic and process consistency of every analyzed documentation, graph, ledger, result, review, remediation, and process correspondence against the constitution and specification.
6. Put `analysis_ref` and the exact semantic result in the audited handoff payload.
7. Bind the handoff owner mode, owner session, repo, wave, trace links, build, source snapshot, and journal digest to the analyzed run.
8. Preserve the run's exact task scope and record one actual native v3 analysis event with `analysis_ref` plus `handoff_payload_digest` over canonical outgoing `stage_payload` through the `DIRECT` primary or repo-L2.
9. Reconcile the resulting journal and build the complete terminal or corrective candidate.
10. Call `app-graph.handoff_validate` and emit only its validated handoff.
