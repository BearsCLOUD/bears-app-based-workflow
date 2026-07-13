# Workflow Refactor v5 Plan

## Dependency order

| Order | Work item | Targets | Depends on |
| --- | --- | --- | --- |
| 1 | Establish canonical semantics and terminology. | docs/app-constitution.md, waves/workflow-refactor-v5/research.md, waves/workflow-refactor-v5/spec.md | v3 workflow and linked schemas |
| 2 | Update operator and agent routing documentation. | AGENTS.md, assets/codex-home-graph-instructions.md, README.md | 1 |
| 3 | Align runtime and deployment boundary guides. | scripts/README.md, .github/runner/README.md | 1 |
| 4 | Replace the effectiveness framework with a compact read-only methodology. | docs/plugin-effectiveness-metrics-and-agent-audit-methodology.md | 1 |
| 5 | Record the refactor history and wave navigation. | CHANGELOG.md, waves/index.md | 2, 3, 4 |
| 6 | Perform semantic correspondence analysis and bind evidence. | waves/workflow-refactor-v5/analysis.md, docs/workflow-refactor-v5-evidence.md | 5 |

## Completion conditions

- Every designated artifact uses the same stage ownership model.
- Every designated artifact describes app-analyze as semantic documentation correspondence.
- The seven dimensions and deterministic route vocabulary are defined without contradiction.
- Effectiveness assessment has no workflow or execution authority.
- The evidence packet maps every requirement to its documentation refs.
