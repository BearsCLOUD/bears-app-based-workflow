# Workflow Refactor v5 Analysis

## Basis

This document records pre-binding correspondence notes for the workflow architecture refactor. The terminal semantic result remains a separate `app-semantic-analysis-result.v1` record bound to one exact compiled build and journal snapshot.

## Provisional correspondence

| Requirement | Current source correspondence | Remaining terminal check |
| --- | --- | --- |
| WF5-01 | `README.md`, `AGENTS.md`, and `contracts/app-workflow-definition.v3.json` assign each DIRECT stage to the DIRECT primary and keep `workflow-orchestrator` outside stage authority. | Traverse the exact build and confirm every stage record preserves that owner. |
| WF5-02 | `contracts/delegation-packets.v2.json`, `agents/README.md`, and the two orchestrator role definitions bind one persistent `repo-orchestrator` repo-L2 to each DELEGATED lane. | Confirm the exact process records retain one repo-L2 owner-session ref for the complete lane. |
| WF5-03 | L1 uses native collaboration with `repo-lane-dispatch.v1`; repo-L2 uses `$subagents`; completed-result provenance is durable in delegation events, with the app-analyze completion embedded atomically in its analysis event. | Confirm no record transfers authority to L3 and every represented delegation matches one completed result. |
| WF5-04 | The event contract and runtime restrict records to the stage owner, bind exact task-spec digests, enforce transition and dependency closure, require exact result and review commits, and place correction tasks in linked runs. | Confirm global result uniqueness, immutable terminal tasks, exact review range, single-successor acyclic lineage, and causal continuity. |
| WF5-05 | `skills/app-analyze/SKILL.md` defines agent-authored logical correspondence over one exact snapshot, including graph edges, task results, reviews, remediation tasks, and the incoming boundary. | Complete all bounded graph reads through the final opaque cursor and reconcile every canonical input-set digest. |
| WF5-06 | `contracts/app-semantic-analysis-result.v1.schema.json` defines categorized count-and-digest bindings, coverage, findings, unmapped refs, remediation task refs, completeness, and route. | Construct and validate the result against the exact predecessor build. |
| WF5-07 | The workflow, event, handoff, and analysis contracts restrict `audited` to complete semantic and process consistency. | Emit no terminal result until the immediate-predecessor build and journal delta satisfy that condition. |
| WF5-08 | The specification and functional map define all seven dimensions for each active requirement. | Reconcile every dimension entity, relation, and evidence ref in the exact build. |
| WF5-09 | `contracts/app-workflow-definition.v3.json` is the edge, route, reduction, and event registry consumed by compiler, query, stage, process, handoff, and analysis surfaces. | Confirm generic cycle rejection, deduplicated impact, traversable remediation lineage, complete immutable publication, and every outgoing `handoff_validate` result. |
| WF5-10 | `docs/plugin-effectiveness-metrics-and-agent-audit-methodology.md` keeps assessment observational, separates the public case from its sealed key, and remains outside workflow authority. | Confirm the final evidence set attributes no route, journal, or mutation act to the assessment agent and no expected answer is disclosed in the public packet. |

## Representation boundary

Treat lane, L3, result, and handoff packets as typed transient protocol inputs. Count represented delegation provenance only when it binds one completed result and authority identity; never infer a packet body from its record.

## Pending conclusion

Do not infer a terminal semantic result from these notes. Treat `docs/workflow-refactor-v5-source-map.md` only as a source map; bind `docs/workflow-refactor-v5-assessment.md` as independent frozen evidence and construct the structured app-analyze result only after source convergence, complete graph traversal, exact coverage reconciliation, and process-causality review.
