# Workflow Refactor v5 Specification

## Functional requirements

| Ref | Requirement |
| --- | --- |
| WF5-01 | The DIRECT primary must own every app-* stage for a DIRECT workstream; workflow-orchestrator has no stage authority. |
| WF5-02 | One persistent repo-L2 with role kind repo-orchestrator must own every app-* stage for a DELEGATED workstream. |
| WF5-03 | The repo-L2 must dispatch every L3 assignment through $subagents, admit only a completed bound result, retain stage and route authority, and represent analysis delegation provenance atomically in its analysis event. |
| WF5-04 | Only the DIRECT primary or persistent repo-L2 may append native process records; every record must bind stable ownership, exact task specifications, a valid transition, completed dependencies, and exact Git provenance, while correction uses source-linked tasks in a new run. |
| WF5-05 | app-analyze must compare documentation, graph entities and edges, ledger, artifacts, evidence, task results, reviews, remediation tasks, process records, and the incoming boundary on one exact snapshot. |
| WF5-06 | app-analyze must return exact categorized input-set bindings, coverage counts, findings, unmapped refs, open remediation task refs, completeness, and one canonical route. |
| WF5-07 | audited must mean complete semantic and process correspondence against the constitution and specification only. |
| WF5-08 | Every active requirement must map behavior, dependency, state, api, data, integration, and error or provide a sourced not-applicable rationale. |
| WF5-09 | Every graph edge, stage status, event transition, finding, outgoing handoff, and build publication must resolve through contracts/app-workflow-definition.v3.json and the exact current build. |
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
| WF5-01 | The DIRECT primary performs each stage and chooses its route. | Each DIRECT stage consumes the preceding canonical handoff. | DIRECT ownership and `owner_session_ref=none` persist through the terminal handoff. | Stage skills exchange handoff v4 under DIRECT ownership. | Handoffs bind `DIRECT-primary`, `owner_session_ref=none`, repository, wave, and run. | The primary uses context and graph surfaces without transferring ownership; workflow-orchestrator only coordinates repo lanes. | DIRECT stage delegation, a non-none owner session, or L1 stage action is an ownership violation. |
| WF5-02 | One repo-L2 of kind `repo-orchestrator` performs every delegated stage and retains route authority; L1 owns neither. | The repo-L2 depends on one fixed L1 lane assignment. | One non-none owner session and repository-to-L2 binding persist across all stages. | L1 and L3 packets enter and leave through the same repo-L2. | Lane state binds repository, wave, run, and stable non-none repo-L2 owner session. | L1 of kind `workflow-orchestrator` coordinates lanes while repo-L2 integrates stages, graph MCP, and subagents. | A missing or replaced L2, L1 stage action, or owner-session drift blocks the lane. |
| WF5-03 | Repo-L2 invokes every L3 only through `$subagents`. | Selection depends on role kind, specialization, and a bounded packet. | Assignment state advances without transferring stage authority. | `dispatch-packet.v3` and `result-packet.v2` are the L3 boundaries; mutation work also carries `app-task-dispatch.v2`. | Completed records bind result, profile, model, checklist, assignment, and authority identity; app-analyze records its completion atomically with the analysis result. | `$subagents` connects repo-L2 to helpers, mutation workers, and critics. | Direct dispatch, an incomplete result, separate app-analyze delegation event, or packet identity drift is rejected. |
| WF5-04 | Only the stage owner records an event that occurred. | Pre-plan scope is empty; ordinary `plan-ready` establishes it; correction preserves it through terminal app-plan `needs-plan`; a linked run starts only its remediation tasks. | Records and terminal tasks are immutable; owner sessions are stable; correction lineage is acyclic and each source run has at most one successor. | `process_record_event` admits only `DIRECT-primary` with session `none` or `repo-L2` with one non-`none` session and enforces the event-kind transition matrix. | Event v3 binds run, owner, stage, status, exact task-spec digests, causes, trace, artifacts, payload digest, and Git-resolved result provenance; remediation tasks bind source events and findings. | Compilation enforces ledger and event parity; reviews cover exactly the in-scope result commits; `handoff_validate` reconstructs the current outgoing boundary. | L3 authorship, duplicate result, session mismatch, incomplete dependency, invalid or extra reviewed commit, scope drift, historical boundary, or dangling cause is rejected. |
| WF5-05 | app-analyze compares every declared correspondence surface. | Analysis starts from a clean implemented review boundary or canonical `no-work` on one exact build. | Sources and journal remain read-only; drift requires a new analysis. | One `explorer` reads named documentation and all graph pages with opaque cursor continuation and canonical set digests. | Inputs bind sources, decisions, requirements, functionalities, dimension entities and mappings, relations, graph edges, functional-map and ledger records, artifacts, evidence, tasks and results, reviews, remediation tasks, process records, and the incoming handoff. | Analysis correlates documentation, graph, ledger, and native events; transient handoffs and packets enter only through represented refs. | A stale basis, incomplete page set, or mismatched input digest cannot yield a complete result. |
| WF5-06 | One result records coverage, findings, and one route. | The result depends on its exact build, profile, model, checklist, and categorized input-set digests. | The result is immutable and bound to one analysis event. | `app-semantic-analysis-result.v1` defines the result boundary. | Required fields bind input counts and digests, coverage, findings, unmapped refs, remediation task refs, completeness, and route. | The result is embedded in the analysis event and feeds the outgoing transient handoff. | A malformed set binding, finding, or route reduction makes the result incomplete. |
| WF5-07 | `audited` is emitted only when every semantic and process condition is complete. | The terminal event analyzes the immediate predecessor build and is the only later journal delta. | `audited` is terminal only for the exact bound snapshot. | Event v3 carries the durable terminal status while handoff v4 carries the typed transient stage result. | Zero contradictions, unmapped refs, routable findings, and open remediation tasks are recorded. | Final compilation reconciles the structured analysis event. | Any remaining gap routes to its corrective stage instead of `audited`. |
| WF5-08 | Every active requirement maps all seven dimensions or a sourced not-applicable rationale. | Coverage entries depend on unique kind-compatible entities and evidence refs. | Activating a requirement activates its exact dimension set. | Functional map v4 defines dimension and coverage records. | Each record binds requirement, dimension, entity refs, status, rationale when needed, and evidence. | The compiler reconciles the dimension index and coverage list. | Missing, duplicated, reused, or wrong-kind dimension refs fail closed. |
| WF5-09 | Every edge, status, transition, finding, and outgoing handoff resolves through one registry and exact build. | Edge metadata defines direction, traversal, impact, and cycle policy; blocked otherwise dominates the frozen corrective route priority. | Build bundles are immutable and complete before atomic pointer publication; only `audited` and `blocked` are terminal. | Workflow v3 defines edge and process rules; `handoff_validate` derives identity and validates the current payload. | The registry binds edge semantics; findings and handoffs bind their exact subjects, conflicts, owner, refs, payload, route, and build. | Compiler, queries, stages, analysis, and handoff validation share the registry; impact is deduplicated and `remediates` lineage is traversable. | An unknown edge or transition, forbidden cycle, route mismatch, partial publication, stale build, historical boundary, or payload mismatch is rejected. |
| WF5-10 | The assessment agent observes exact records and reports without workflow mutation. | Comparative claims require a frozen cohort, baseline, primary metric, equivalence range, and available raw observations. | Assessment observations never change workflow state, and the assessed agent never sees the sealed scoring key. | The methodology defines public case, sealed key, metric, and report records. | Records bind snapshot, model profile, outcome, counts, and provenance. | Assessment consumes workflow outputs while remaining outside workflow authority. | A missing comparison prerequisite yields `inconclusive`, not a workflow transition. |

## Route semantics

- constitution-ready and needs-research route to app-research.
- research-ready and needs-spec route to app-specify.
- spec-ready and needs-graph route to app-functional-graph.
- graph-ready, waiting, and needs-plan route to app-plan.
- plan-ready and ready route to app-dev.
- implemented and no-work route to app-analyze.
- audited and blocked are terminal.

## Protocol persistence boundary

Native event v3 is the durable process source. Outgoing handoff v4 and delegation packets remain typed transient inputs; completed L3 provenance uses a delegation event except that app-analyze embeds its completion atomically in the analysis event. Every outgoing handoff follows its recorded source event and journal reconciliation, then passes read-only build-bound validation.

## Refactor scope

This wave updates the workflow contracts, graph runtime, stage skills, role profiles, structured graph sources, documentation, and delivery metadata as one cutover.
