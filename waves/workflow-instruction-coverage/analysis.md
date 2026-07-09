# Wave Analysis: workflow-instruction-coverage

## Wave and target

- Wave: `workflow-instruction-coverage`
- Target: `bears-app-based-workflow`

## Inputs reviewed

- `docs/app-constitution.md`
- `waves/workflow-instruction-coverage/research.md`
- `waves/workflow-instruction-coverage/plan.md`
- `docs/app-task-ledger.v1.json`
- `docs/app-functional-graph.v1.json`

## Lineage check

| Graph node ref | Constitution refs | Research refs | Plan task refs | Status |
| --- | --- | --- | --- | --- |
| `cap-sequential-workflow:docs-contract` | `cap-sequential-workflow` | `waves/workflow-instruction-coverage/research.md#constitution-mapping` | `task-docs-sequential-contract` | pass |
| `cap-constitution-truth:drift-routing` | `cap-constitution-truth` | `waves/workflow-instruction-coverage/research.md#constitution-mapping` | `task-docs-sequential-contract` | pass |
| `cap-research-explains-truth:research-template` | `cap-research-explains-truth` | `waves/workflow-instruction-coverage/research.md#plan-inputs` | `task-artifact-contracts-templates` | pass |
| `cap-plan-microtasks:ledger-template` | `cap-plan-microtasks` | `waves/workflow-instruction-coverage/research.md#plan-inputs` | `task-artifact-contracts-templates` | pass |
| `cap-graph-dev-model:graph-template` | `cap-graph-dev-model` | `waves/workflow-instruction-coverage/research.md#plan-inputs` | `task-artifact-contracts-templates` | pass |
| `cap-lineage-analysis:self-test-analysis` | `cap-lineage-analysis` | `waves/workflow-instruction-coverage/research.md#drift-notes` | `task-self-test-lineage` | pass |
| `cap-self-contained-plugin:host-independent-contract` | `cap-self-contained-plugin` | `waves/workflow-instruction-coverage/research.md#constitution-mapping` | `task-docs-sequential-contract` | pass |

## Implementation comparison

- Workflow artifacts model the requested implementation. Runtime execution is outside this documentation self-test.

## Broken links

- None recorded in the self-test artifacts.

## Status

`pass`

## Next skill

- `close-wave`
