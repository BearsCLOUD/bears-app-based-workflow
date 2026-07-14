# Workflow Refactor v5 Specification

## Functional requirements

| Ref | Requirement |
| --- | --- |
| WF5-01 | The DIRECT primary must own every app-* stage for a DIRECT workstream; workflow-orchestrator has no stage authority. |
| WF5-02 | One persistent repo-L2 with role kind repo-orchestrator must own every app-* stage for a DELEGATED workstream. |
| WF5-03 | The repo-L2 must dispatch every L3 assignment through $subagents and retain stage and route authority. |
| WF5-04 | Only the DIRECT primary or persistent repo-L2 may append native process records, and every record must bind the stable owner session. |
| WF5-05 | app-analyze must compare documentation, graph entities and edges, ledger, artifacts, evidence, task results, reviews, remediations, process records, and the incoming boundary on one exact snapshot. |
| WF5-06 | app-analyze must return exact categorized input-set bindings, coverage counts, findings, unmapped refs, open remediation refs, completeness, and one canonical route. |
| WF5-07 | audited must mean complete semantic and process consistency only. |
| WF5-08 | Every active requirement must map behavior, dependency, state, api, data, integration, and error or provide a sourced not-applicable rationale. |
| WF5-09 | Every stage status and finding must route and reduce through contracts/app-workflow-definition.v3.json. |
| WF5-10 | Effectiveness assessment must remain read-only, keep its scoring key sealed from the assessed agent, and remain separate from workflow authority. |

## Dimension semantics

- behavior captures observable responses and their governing rules.
- dependency captures prerequisites, ordering, constraints, and impact.
- state captures modes, transitions, invariants, and persistence.
- api captures interfaces, protocols, inputs, outputs, and compatibility.
- data captures entities, fields, ownership, lifecycle, and protection.
- integration captures system boundaries, counterparties, and message flow.
- error captures failure conditions, recovery, and visible consequences.

## Requirement dimension mapping

| Requirement | Behavior | Dependency | State | API | Data | Integration | Error |
| --- | --- | --- | --- | --- | --- | --- | --- |
| WF5-01 | The DIRECT primary performs each stage and chooses its route. | Each DIRECT stage consumes the preceding canonical handoff. | DIRECT ownership persists through the terminal handoff. | Stage skills exchange handoff v4 under DIRECT ownership. | Handoffs bind `DIRECT-primary`, repository, wave, run, and owner-session refs. | The primary uses context and graph surfaces without transferring ownership; workflow-orchestrator only coordinates repo lanes. | Any attempted DIRECT stage delegation or L1 stage action is an ownership violation. |
| WF5-02 | One repo-L2 of kind `repo-orchestrator` performs every delegated stage and retains route authority. | The repo-L2 depends on one fixed L1 lane assignment. | The repository and owner-session binding persists across all stages. | L1 and L3 packets enter and leave through the same repo-L2. | Lane state binds repository, wave, run, and stable L2 identity. | L1 of kind `workflow-orchestrator` coordinates lanes while repo-L2 integrates stages, graph MCP, and subagents. | A missing, replaced, or mismatched L2 binding blocks the lane. |
| WF5-03 | Repo-L2 invokes every L3 only through `$subagents`. | Selection depends on role kind, specialization, and a bounded packet. | Assignment state advances without transferring stage authority. | `dispatch-packet.v3` and `result-packet.v2` are the L3 boundaries; mutation work also carries `app-task-dispatch.v2`. | Packets bind assignment, profile, input, output, and authority refs; event v3 retains the consumed identity. | `$subagents` connects repo-L2 to helpers, mutation workers, and critics. | Direct L3 invocation or an invalid result packet is rejected. |
| WF5-04 | Only the stage owner records an event that occurred. | Each event depends on its declared run scope and causal refs. | Native records are immutable; the owner-session ref is stable; terminal task history is not reopened. | `process_record_event` admits only `DIRECT-primary` with session `none` or `repo-L2` with one non-`none` session. | Event v3 binds run, owner session, stage, status, tasks, causes, trace, artifacts, and applicable result provenance. | Graph compilation consumes the journal; an outgoing handoff binds the resulting build as a transient packet. | L3 authorship, session mismatch, scope mismatch, or a dangling cause is rejected. |
| WF5-05 | app-analyze compares every declared correspondence surface. | Analysis starts from a clean implemented review boundary or canonical `no-work` on one exact build. | Sources and journal remain read-only; drift requires a new analysis. | Analysts use bounded graph reads, opaque cursor continuation, and canonical set digests. | Inputs bind sources, decisions, requirements, functionality, dimensions, mappings, relations, graph edges, ledger, artifacts, evidence, task results, reviews, remediations, process records, and the incoming boundary. | Analysis correlates documentation, graph, ledger, and native events; transient handoffs and packets enter only through represented refs. | A stale basis, incomplete page set, or mismatched input digest cannot yield a complete result. |
| WF5-06 | One result records coverage, findings, and one route. | The result depends on its exact build, profile, model, checklist, and categorized input-set digests. | The result is immutable and bound to one analysis event. | `app-semantic-analysis-result.v1` defines the result boundary. | Required fields bind input counts and digests, coverage, findings, unmapped refs, remediation refs, completeness, and route. | The result is embedded in the analysis event and feeds the outgoing transient handoff. | A malformed set binding, finding, or route reduction makes the result incomplete. |
| WF5-07 | `audited` is emitted only when every semantic and process condition is complete. | The terminal event analyzes the immediate predecessor build and is the only later journal delta. | `audited` is terminal only for the exact bound snapshot. | Event v3 carries the durable terminal status while handoff v4 carries the typed transient stage result. | Zero contradictions, unmapped refs, routable findings, and open remediation are recorded. | Final compilation reconciles the structured analysis event. | Any remaining gap routes to its corrective stage instead of `audited`. |
| WF5-08 | Every active requirement maps all seven dimensions or a sourced not-applicable rationale. | Coverage entries depend on unique kind-compatible entities and evidence refs. | Activating a requirement activates its exact dimension set. | Functional map v4 defines dimension and coverage records. | Each record binds requirement, dimension, entity refs, status, rationale when needed, and evidence. | The compiler reconciles the dimension index and coverage list. | Missing, duplicated, reused, or wrong-kind dimension refs fail closed. |
| WF5-09 | Every status and finding resolves through one route registry. | Blocked dominates; otherwise the selected route follows the frozen corrective priority. | Only `audited` and `blocked` are terminal. | Workflow v3 defines routes and reduction; handoff v4 restricts emitted statuses. | Each finding binds kind, subjects, conflicts, summary, and canonical route. | Stage skills, analysis results, and native events consume the same vocabulary; transient handoffs do not establish graph state. | An unknown status or reduction mismatch is rejected. |
| WF5-10 | The evaluator observes exact records and reports without workflow mutation. | Comparative claims require a frozen cohort, baseline, primary metric, equivalence range, and available raw observations. | Assessment observations never change workflow state, and the assessed agent never sees the sealed scoring key. | The methodology defines public case, sealed key, metric, and report records. | Records bind snapshot, model profile, outcome, counts, and provenance. | Assessment consumes workflow outputs while remaining outside workflow authority. | A missing comparison prerequisite yields `inconclusive`, not a workflow transition. |

## Route semantics

- constitution-ready and needs-research route to app-research.
- research-ready and needs-spec route to app-specify.
- spec-ready and needs-graph route to app-functional-graph.
- graph-ready, waiting, and needs-plan route to app-plan.
- plan-ready and ready route to app-dev.
- implemented and no-work route to app-analyze.
- audited and blocked are terminal.

## Protocol persistence boundary

Native event v3 is the durable process source. Outgoing handoff v4 and delegation packets remain typed transient inputs; a delegation event retains the consumed L3 identity and packet schema names.

## Refactor scope

This wave updates the workflow contracts, graph runtime, stage skills, role profiles, structured graph sources, documentation, and delivery metadata as one cutover.
