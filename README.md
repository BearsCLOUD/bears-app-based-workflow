# Bears App-Based Workflow

Bears App-Based Workflow is a Codex plugin for deterministic documentation-to-implementation routing, graph-bound planning, persistent repository orchestration, and semantic correspondence analysis.

## Workflow refactor v5

The workflow is defined by contracts/app-workflow-definition.v3.json and exchanges typed transient app-stage-handoff.v4 packets. Structured semantics use app-functional-map.v4, work queues use app-task-ledger.v3, durable process records use app-process-event.v3, and app-analyze results use app-semantic-analysis-result.v1.

app-context-index reconciles an opted-in repository from its source manifest. app-graph-compile publishes each complete immutable build bundle before atomically replacing one current-build pointer. Every stage uses the build, source snapshot digest, and journal digest in its handoff; pre-plan scope is empty, ordinary plan-ready establishes it, correction preserves it through terminal app-plan needs-plan, and only a linked run admits remediation tasks.

## Ownership

| Mode | Stage owner | Owner session | L3 use |
| --- | --- | --- | --- |
| DIRECT | The DIRECT primary owns every app-* stage. | `none` | Not used for stage ownership. |
| DELEGATED | One persistent repo-L2 of kind `repo-orchestrator` owns every app-* stage and the journal. | One stable non-`none` ref for the full run | The repo-L2 dispatches assignment-bounded work only through $subagents. |

L1 has kind `workflow-orchestrator`; it only opens and continues repository lanes and never owns a stage or dispatches L3. An L3 worker returns only its bounded result. It does not own a stage, choose the next workflow route, or append process records.

## Stage sequence

| Stage | Required outcome |
| --- | --- |
| app-constitution | Establish durable purpose, principles, and authority boundaries. |
| app-research | Resolve sources, facts, constraints, and open questions. |
| app-specify | Close product decisions and state decision-complete requirements. |
| app-functional-graph | Map requirements, seven dimensions, relations, and source refs. |
| app-plan | Produce dependency-ordered, repository-bounded ledger work. |
| app-dev | Orchestrate ready ledger work, immutable full-scope review, linked correction runs, and one clean repo handoff. |
| app-analyze | Compare documentation, graph entities and edges, ledger, artifacts, evidence, task results, reviews, remediation tasks, and process records for logical correspondence. |

app-analyze is semantic agent analysis of documentation and graph correspondence against the constitution and specification. In DELEGATED mode one `explorer` reads the named documentation and every bound graph page, returns the typed result, and leaves event persistence to repo-L2. The result binds each complete input category by count and canonical digest, produces structured findings, and resolves one route through the workflow registry.

## Seven dimensions

Every active requirement maps each dimension or records a sourced not-applicable rationale.

| Dimension | Meaning |
| --- | --- |
| behavior | Observable actor or system response and its governing rule. |
| dependency | Prerequisites, ordering, constraints, and affected capabilities. |
| state | Modes, transitions, invariants, and persistence boundaries. |
| api | Callable interfaces, protocols, inputs, outputs, and compatibility rules. |
| data | Entities, fields, ownership, lifecycle, and protection requirements. |
| integration | Boundaries and message flow between internal or external systems. |
| error | Failure conditions, recovery behavior, and user-visible consequences. |

## Deterministic routes

The workflow definition is the only route and reduction registry. Blocked dominates; otherwise findings reduce by the declared corrective priority.

| Status | Next stage |
| --- | --- |
| constitution-ready, needs-research | app-research |
| research-ready, needs-spec | app-specify |
| spec-ready, needs-graph | app-functional-graph |
| graph-ready, waiting, needs-plan | app-plan |
| plan-ready, ready | app-dev |
| implemented, no-work | app-analyze |
| audited, blocked | none |

Findings route as follows:

| Finding class | Route |
| --- | --- |
| Missing source | needs-research |
| Product or decision conflict | needs-spec |
| Semantic, reference, or cycle gap | needs-graph |
| Task, implementation, evidence, review, or remediation-task gap | needs-plan |
| Credential, access, or explicit operator stop | blocked |

audited is the only successful terminal workflow status. It means every analyzed documentation, graph, ledger, result, review, remediation, and process correspondence is consistent with the constitution and specification on the exact snapshot.

## Graph surfaces

The read-only app-graph MCP provides bounded dependency, impact, trace, ordering, workflow-state, diagnostic, and current-boundary handoff queries. The app-graph-maintainer MCP exposes only graph_compile and process_record_event, and only when maintainer_enabled=true in the exact repository manifest.

The closed workflow edge registry determines dependency direction, traversal, impact, cycle policy, and topological order. Pagination cursors are opaque and snapshot-bound; a decision query continues until no cursor remains.

## Managed deployment

assets/codex-home-graph-instructions.md is the exact managed instruction block promoted into $CODEX_HOME/AGENTS.md. Promotion preserves unmanaged bytes, records the desired revision, and fails closed on unsafe filesystem state or receipt drift.

The repository-owned deployment gateway activates one authoritative main revision at a time, runs repository gateway code as non-root ai1, and restores the prior gateway when activation cannot converge.

## Version

Workflow refactor v5 is represented by plugin source version 0.4.3. Publication remains a separately authorized action.
