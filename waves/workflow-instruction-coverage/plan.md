# Wave Plan: workflow-instruction-coverage

## Wave ID

`workflow-instruction-coverage`

## Research basis

- `waves/workflow-instruction-coverage/research.md#constitution-mapping` explains all self-test constitution ids.

## Sequential microtasks

| Order | Task ID | Constitution refs | Research refs | Target paths | Definition of done | Proof requirement | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `task-docs-sequential-contract` | `cap-sequential-workflow`, `cap-constitution-truth`, `cap-self-contained-plugin` | `waves/workflow-instruction-coverage/research.md#constitution-mapping` | `README.md`, `SPEC.md`, `docs/workflow-stage-gates.md` | Docs state sequential workflow, constitution truth, self-contained plugin independence, and drift routing. | Targeted grep shows graph is modeled only after approved plan microtasks and no host-specific required dependency. | `graph_modeled` |
| 2 | `task-artifact-contracts-templates` | `cap-research-explains-truth`, `cap-plan-microtasks`, `cap-graph-dev-model` | `waves/workflow-instruction-coverage/research.md#plan-inputs` | `docs/functional-graph-ledger-contract.md`, `docs/artifact-contracts.md`, `templates/` | Contracts and templates require constitution, research, and plan refs. | JSON shape inspection confirms graph and ledger templates carry lineage fields. | `graph_modeled` |
| 3 | `task-skill-sequential-rules` | `cap-constitution-truth`, `cap-research-explains-truth`, `cap-plan-microtasks`, `cap-graph-dev-model`, `cap-lineage-analysis` | `waves/workflow-instruction-coverage/research.md#decisions` | `skills/*/SKILL.md` | Skills enforce constitution-led research, sequential planning, graph-after-plan modeling, and lineage analysis. | Targeted grep shows ordered microtasks are the default and no research-to-graph/dev shortcut exists. | `graph_modeled` |
| 4 | `task-self-test-lineage` | `cap-lineage-analysis`, `cap-self-contained-plugin` | `waves/workflow-instruction-coverage/research.md#drift-notes` | `docs/app-constitution.md`, `waves/`, `docs/app-task-ledger.v1.json`, `docs/app-functional-graph.v1.json` | Self-test artifacts form a complete constitution→research→plan→graph lineage. | Every graph node has constitution, research, and plan refs. | `graph_modeled` |
| 5 | `task-manifest-positioning` | `cap-sequential-workflow`, `cap-self-contained-plugin` | `waves/workflow-instruction-coverage/research.md#plan-inputs` | `.codex-plugin/plugin.json` | Manifest describes sequential workflow and removes non-sequential positioning. | JSON parses and capabilities match sequential model. | `graph_modeled` |

## Ledger updates

- `docs/app-task-ledger.v1.json` mirrors the sequential microtasks and graph backlinks.

## Graph modeling handoff

- `app-functional-graph` models each microtask as one or more dev-stage graph nodes and writes node refs back to the ledger.

## Drift notes

- No functional drift remains for this wave.

## Next skill

- `app-functional-graph`
