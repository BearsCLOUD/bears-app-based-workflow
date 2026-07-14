# Workflow Refactor v5 Analysis

## Basis

This document records pre-binding correspondence notes for the workflow architecture refactor. The terminal semantic result remains a separate `app-semantic-analysis-result.v1` record bound to one exact compiled build and journal snapshot.

## Provisional correspondence

| Requirement | Current source correspondence | Remaining terminal check |
| --- | --- | --- |
| WF5-01 | `README.md`, `AGENTS.md`, and `contracts/app-workflow-definition.v3.json` assign each DIRECT stage to the DIRECT primary and keep `workflow-orchestrator` outside stage authority. | Traverse the exact build and confirm every stage record preserves that owner. |
| WF5-02 | `contracts/delegation-packets.v2.json`, `agents/README.md`, and the two orchestrator role definitions bind one persistent `repo-orchestrator` repo-L2 to each DELEGATED lane. | Confirm the exact process records retain one repo-L2 owner-session ref for the complete lane. |
| WF5-03 | L1 uses native collaboration with `repo-lane-dispatch.v1`; repo-L2 uses `$subagents` with `dispatch-packet.v3`, `result-packet.v2`, and applicable `app-task-dispatch.v2`. | Confirm no represented record transfers stage or route authority to L3. |
| WF5-04 | `contracts/app-process-event.v3.schema.json` and graph runtime sources restrict native process records to the stage owner and bind one stable owner session. | Confirm actor, owner-session, task provenance, and causal continuity across every exact journal record. |
| WF5-05 | `skills/app-analyze/SKILL.md` defines agent-authored logical correspondence over one exact snapshot, including graph edges, task results, reviews, remediations, and the incoming boundary. | Complete all bounded graph reads through the final opaque cursor and reconcile every canonical input-set digest. |
| WF5-06 | `contracts/app-semantic-analysis-result.v1.schema.json` defines categorized count-and-digest bindings, coverage, findings, unmapped refs, remediation refs, completeness, and route. | Construct and validate the result against the exact predecessor build. |
| WF5-07 | The workflow, event, handoff, and analysis contracts restrict `audited` to complete semantic and process consistency. | Emit no terminal result until the immediate-predecessor build and journal delta satisfy that condition. |
| WF5-08 | The specification and functional map define all seven dimensions for each active requirement. | Reconcile every dimension entity, relation, and evidence ref in the exact build. |
| WF5-09 | `contracts/app-workflow-definition.v3.json` is the route and reduction registry consumed by stage and analysis surfaces. | Confirm every represented status and finding resolves through the registered blocked dominance and corrective priority. |
| WF5-10 | `docs/plugin-effectiveness-metrics-and-agent-audit-methodology.md` keeps assessment observational, separates the public case from its sealed key, and remains outside workflow authority. | Confirm the final evidence set attributes no route, journal, or mutation act to the evaluator and no expected answer is disclosed in the public packet. |

## Representation boundary

Treat lane, L3, result, and handoff packets as typed transient protocol inputs. Count only the L3 identity fields represented by an immutable v3 event `delegation_record` as durable graph evidence; never infer the full packet body from that record.

## Pending conclusion

Do not infer a terminal semantic result from these notes. Treat `docs/workflow-refactor-v5-source-map.md` only as a source map; bind independent evidence and the structured app-analyze result only after source convergence, complete graph traversal, exact coverage reconciliation, and process-causality review.
