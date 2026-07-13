# Plugin Effectiveness Metrics and Agent Assessment Methodology

## Purpose and authority

This methodology measures whether the plugin improves documentation convergence, routing precision, trace completeness, and authority discipline. It is an observational framework, not a workflow stage or instruction source.

An assessment agent has read-only analytical authority over the frozen reference packet. It cannot mutate repository state, dispatch work, append process records, choose a workflow handoff, or emit audited.

Effectiveness verdicts remain separate from workflow authority. improved, neutral, regressed, and inconclusive describe measured change only; they never become workflow statuses.

## Definitions

| Term | Definition |
| --- | --- |
| eligible run | A native run with one repository, wave, owner mode, exact start snapshot, and complete observed record set. |
| exact snapshot | One build ref bound to its source snapshot digest and journal digest. |
| semantic convergence | The exact snapshot has complete app-analyze coverage with no contradiction, unmapped decision, unmapped requirement, routable finding, or open remediation. |
| first-pass convergence | Semantic convergence without a remediation cycle. |
| late reroute | A needs-research, needs-spec, needs-graph, or needs-plan route first emitted after its owning stage. |
| seven-dimension coverage | The share of required behavior, dependency, state, api, data, integration, and error mappings that are sourced or explicitly not applicable. |
| trace completeness | The share of active branches connected from specification through decision, requirement, functionality or behavior, task, implementation artifact, and evidence. |
| reference case | A frozen documentation packet with expected dimensions, graph links, findings, owner, and route. |
| assessment agent | A named model and profile that analyzes a reference case without repository mutation or workflow authority. |

## Seven-dimension rubric

| Dimension | Assessment question |
| --- | --- |
| behavior | Is every observable response and governing rule represented? |
| dependency | Are prerequisites, ordering, constraints, and impacts represented? |
| state | Are modes, transitions, invariants, and persistence represented? |
| api | Are interfaces, protocols, inputs, outputs, and compatibility represented? |
| data | Are entities, fields, ownership, lifecycle, and protection represented? |
| integration | Are system boundaries, counterparties, and message flow represented? |
| error | Are failure conditions, recovery behavior, and visible consequences represented? |

A not-applicable result counts only when it carries a source-backed rationale.

## Route rubric

| Finding class | Required route |
| --- | --- |
| Missing source | needs-research |
| Product or decision conflict | needs-spec |
| Semantic, reference, or cycle gap | needs-graph |
| Task, implementation, evidence, review, or remediation gap | needs-plan |
| Credential, access, or explicit operator stop | blocked |

The stage status mapping remains defined only by contracts/app-workflow-definition.v3.json. The assessment report records observed route correspondence but cannot create or change a route.

## Metric record

Each result records metric id, frozen definition, cohort ref, baseline ref, numerator, denominator, exclusions, value, confidence, and source refs. Missing source material produces inconclusive rather than a numeric substitute.

Aggregate only comparable repository, wave, owner-mode, complexity, and model-profile strata. Preserve raw counts beside rates.

## Effectiveness metrics

| ID | Metric | Formula or rule |
| --- | --- | --- |
| EFF-01 | Semantic convergence rate | semantically converged eligible runs / eligible runs |
| EFF-02 | First-pass convergence rate | first-pass converged runs / semantically converged runs |
| EFF-03 | Late reroute rate | runs with a late reroute / runs reaching the affected later stage |
| EFF-04 | Remediation load | median and p90 remediation tasks per implemented run |
| EFF-05 | Blocker rate | blocked eligible runs / eligible runs, split by blocker class |
| SEM-01 | Seven-dimension coverage | sourced or justified dimension mappings / required dimension mappings |
| SEM-02 | End-to-end trace completeness | complete active trace branches / active trace branches |
| SEM-03 | Logical contradiction count | unresolved contradictions on the exact snapshot |
| SEM-04 | Unmapped source count | unmapped decisions plus unmapped requirements |
| RTE-01 | Finding route accuracy | findings with the registry route / findings |
| AUT-01 | Stage-owner correctness | stages owned by the required DIRECT primary or persistent repo-L2 / stages |
| AUT-02 | L3 boundary correctness | bounded L3 results returned through $subagents / L3 assignments |
| AUT-03 | Journal-owner correctness | native records appended by the DIRECT primary or persistent repo-L2 / native records |
| DET-01 | Build reproducibility | repeated equal-source compilations with equal build refs and bytes / observed repeats |
| DET-02 | Pagination completeness | decision queries continued to no cursor / decision queries |
| OPS-01 | Bounded response compliance | observed responses within declared wire and page bounds / observed responses |

SEM-01, SEM-02, RTE-01, AUT-01, AUT-02, AUT-03, DET-01, DET-02, and OPS-01 require exact correspondence for a conformant observation. Outcome rates are comparative and require a frozen baseline before an improvement claim.

## Reference-case agent assessment

1. Freeze a packet containing the exact source refs, expected owner mode, seven-dimension labels, graph links, finding set, route, and scoring rubric.
2. Give every assessment agent the same packet, context budget, response schema, and model-profile identity.
3. Collect one read-only analysis result per agent with cited source refs.
4. Score route selection, dimension classification, contradiction discovery, trace mapping, and authority-boundary adherence against the reference.
5. Report exact-match counts, precision, recall, omissions, unsupported claims, latency, and token use when those observations are already available.
6. Compare candidate and baseline agents only within the same frozen case set and configuration stratum.
7. Publish an assessment report with limitations and suggested follow-up; let the workflow owner decide whether any suggestion becomes a source change or ledger task.

A useful reference set covers each route class, every dimension, DIRECT and DELEGATED ownership, an L3 boundary case, a source conflict, a graph gap, a remediation gap, and a blocker.

## Verdict policy

| Verdict | Meaning |
| --- | --- |
| improved | The frozen primary metric improves and no exact-correspondence metric regresses. |
| neutral | Differences stay within the frozen equivalence range and exact-correspondence metrics remain complete. |
| regressed | A primary metric worsens or an exact-correspondence metric loses completeness. |
| inconclusive | The packet, cohort, baseline, or observation set is insufficient. |

The report states its metric verdict and source limitations. It does not write a handoff, process event, task, or terminal workflow status.
