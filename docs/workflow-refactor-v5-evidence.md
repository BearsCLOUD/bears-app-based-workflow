# Workflow Refactor v5 Evidence

## Scope

This packet records documentation evidence for workflow-refactor-v5. It covers only the designated human-facing artifacts and does not modify contracts, runtime modules, skills, roles, or installation logic.

## Source basis

| Source | Authority used |
| --- | --- |
| contracts/app-workflow-definition.v3.json | Stage order, owner modes, route registry, finding routes, terminal meaning, and L3 boundary |
| contracts/app-stage-handoff.v4.schema.json | Canonical statuses and exact snapshot fields |
| contracts/app-functional-map.v4.schema.json | Entity kinds, relations, and seven-dimension coverage |
| contracts/app-task-ledger.v3.schema.json | Repository owner roles, task states, dependency order, and proof refs |
| contracts/app-process-event.v3.schema.json | Native event kinds and journal records |
| contracts/app-semantic-analysis-result.v1.schema.json | Analysis coverage, findings, completeness, and route |

## Requirement evidence

| Requirement | Evidence refs |
| --- | --- |
| Uniform DIRECT ownership | README.md; AGENTS.md; docs/app-constitution.md |
| Persistent repo-L2 ownership | README.md; AGENTS.md; assets/codex-home-graph-instructions.md |
| L3 dispatch through $subagents | README.md; AGENTS.md; docs/app-constitution.md |
| Stage-owner journal authority | README.md; AGENTS.md; assets/codex-home-graph-instructions.md |
| app-analyze semantic correspondence | README.md; scripts/README.md; docs/app-constitution.md; waves/workflow-refactor-v5/analysis.md |
| audited terminal meaning | README.md; docs/app-constitution.md; .github/runner/README.md |
| Seven-dimension definitions | README.md; docs/app-constitution.md; waves/workflow-refactor-v5/spec.md |
| Deterministic route vocabulary | README.md; docs/app-constitution.md; waves/workflow-refactor-v5/spec.md |
| Read-only effectiveness assessment | docs/plugin-effectiveness-metrics-and-agent-audit-methodology.md |
| Wave trace | waves/workflow-refactor-v5/research.md; waves/workflow-refactor-v5/spec.md; waves/workflow-refactor-v5/plan.md; waves/workflow-refactor-v5/analysis.md |

## Correspondence conclusion

The designated artifacts describe one coherent workflow: the primary owns DIRECT stages, one persistent repo-L2 owns DELEGATED stages, L3 work returns through $subagents, graph records determine dependency order, and app-analyze supplies semantic correspondence findings on an exact snapshot.

The seven dimensions and route vocabulary match the v3 workflow definition. audited is limited to complete semantic and process consistency. Effectiveness assessment remains observational and cannot change workflow state.

## Binding

The stage owner binds this packet and waves/workflow-refactor-v5/analysis.md to the exact build ref, source snapshot digest, and journal digest carried by the handoff.
