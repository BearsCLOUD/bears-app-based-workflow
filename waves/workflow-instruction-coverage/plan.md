# Wave Plan: workflow-instruction-coverage

## Wave ID

`workflow-instruction-coverage`

## Research basis

- `waves/workflow-instruction-coverage/research.md#constitution-mapping` explains all self-test constitution ids.
- `waves/workflow-instruction-coverage/research.md#plan-inputs` lists the required documentation, skill, packet, role, graph, ledger, manifest, and analysis updates.

## Sequential microtasks

| Order | Task ID | Constitution refs | Research refs | Target paths | Depends on | Owner role | Critic role | Definition of done | Proof requirement | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `task-docs-sequential-contract` | `cap-sequential-workflow`, `cap-constitution-truth`, `cap-self-contained-plugin` | `waves/workflow-instruction-coverage/research.md#constitution-mapping` | `README.md`, `SPEC.md`, `docs/workflow-stage-gates.md` | none | `documentation-engineer` | `reviewer` | Docs state the sequential workflow, constitution truth, self-contained plugin independence, and drift routing. | Targeted grep shows graph is modeled only after approved plan microtasks and no host-specific required dependency remains. | `graph_modeled` |
| 2 | `task-artifact-contracts-templates` | `cap-research-explains-truth`, `cap-plan-microtasks`, `cap-graph-dev-model` | `waves/workflow-instruction-coverage/research.md#plan-inputs` | `docs/functional-graph-ledger-contract.md`, `docs/artifact-contracts.md`, `templates/` | `task-docs-sequential-contract` | `documentation-engineer` | `reviewer` | Contracts and templates require constitution, research, plan, dependencies, role, evidence, and graph refs. | JSON shape inspection confirms graph and ledger templates carry lineage fields. | `graph_modeled` |
| 3 | `task-skill-sequential-rules` | `cap-constitution-truth`, `cap-research-explains-truth`, `cap-plan-microtasks`, `cap-graph-dev-model`, `cap-lineage-analysis` | `waves/workflow-instruction-coverage/research.md#decisions` | `skills/app-constitution/SKILL.md`, `skills/app-research/SKILL.md`, `skills/app-plan/SKILL.md`, `skills/app-functional-graph/SKILL.md`, `skills/app-dev/SKILL.md`, `skills/app-specify/SKILL.md` | `task-artifact-contracts-templates` | `instruction-reviewer` | `reviewer` | Core skills enforce constitution-led research, sequential planning, graph-after-plan modeling, graph-backed dev, and lineage analysis. | Targeted grep shows ordered microtasks are the default and no research-to-graph or research-to-dev shortcut exists. | `graph_modeled` |
| 4 | `task-packet-contracts-role-catalog` | `cap-packet-contracts`, `cap-self-contained-roles`, `cap-self-contained-plugin` | `waves/workflow-instruction-coverage/research.md#plan-inputs`, `waves/workflow-instruction-coverage/research.md#decisions` | `docs/handoff-packet-contracts.md`, `docs/role-catalog.md`, `skills/subagents-roles/SKILL.md`, `skills/subagents/SKILL.md`, `skills/instruction-hardening/SKILL.md` | `task-skill-sequential-rules` | `documentation-engineer` | `instruction-reviewer` | Support packets and role mapping are versioned, self-contained, sequential, and compatible with `app-dev`. | Targeted reads confirm packet fields match support-skill inputs and no external role inventory is required. | `graph_modeled` |
| 5 | `task-remove-external-role-trace` | `cap-self-contained-plugin`, `cap-self-contained-roles`, `cap-no-test-tooling-loop` | `waves/workflow-instruction-coverage/research.md#decisions` | `skills/`, `README.md`, `SPEC.md`, `.codex-plugin/plugin.json` | `task-packet-contracts-role-catalog` | `instruction-reviewer` | `reviewer` | Obsolete external role-inventory artifacts and wording are removed or replaced by role-catalog and packet-contract references. | Targeted grep shows no legacy role-skill or external role-inventory dependency remains in plugin files. | `graph_modeled` |
| 6 | `task-self-test-lineage` | `cap-lineage-analysis`, `cap-self-contained-plugin`, `cap-no-test-tooling-loop` | `waves/workflow-instruction-coverage/research.md#drift-notes` | `docs/app-constitution.md`, `waves/`, `docs/app-task-ledger.v1.json`, `docs/app-functional-graph.v1.json`, `docs/backtests/plugin-self-test.md` | `task-remove-external-role-trace` | `documentation-engineer` | `reviewer` | Self-test artifacts form complete constitution to research to plan to graph lineage without creating workflow-test tooling. | Every graph node has constitution, research, and plan refs; every ledger task links back to graph nodes. | `graph_modeled` |
| 7 | `task-app-analyze-file-audit` | `cap-lineage-analysis`, `cap-file-reuse-audit`, `cap-no-test-tooling-loop` | `waves/workflow-instruction-coverage/research.md#constitution-mapping`, `waves/workflow-instruction-coverage/research.md#decisions` | `skills/app-analyze/SKILL.md`, `waves/workflow-instruction-coverage/analysis.md`, `docs/artifact-contracts.md`, `templates/waves/wave-id/analysis.md` | `task-self-test-lineage` | `instruction-reviewer` | `reviewer` | `app-analyze` covers every plugin file for reuse quality, portability, continuous-development readiness, and no-test-tooling risk. | The analysis file lists every plugin file with a pass or exact concern and does not require a new audit script. | `graph_modeled` |
| 8 | `task-manifest-positioning` | `cap-sequential-workflow`, `cap-self-contained-plugin`, `cap-packet-contracts`, `cap-file-reuse-audit` | `waves/workflow-instruction-coverage/research.md#plan-inputs` | `.codex-plugin/plugin.json`, `.agents/plugins/marketplace.json` | `task-app-analyze-file-audit` | `documentation-engineer` | `reviewer` | Manifest describes the sequential, self-contained workflow, packet contracts, role mapping, and reuse-quality audit. | JSON parses and manifest capabilities match the sequential model. | `graph_modeled` |

## Ledger updates

- `docs/app-task-ledger.v1.json` mirrors the sequential microtasks, dependencies, planned roles, proof requirements, and graph backlinks.

## Graph modeling handoff

- `app-functional-graph` models each approved microtask as one or more dev-stage graph nodes and writes node refs back to the ledger.

## Drift notes

- No functional drift remains for this wave.
- Any future artifact change must refresh this plan, ledger, graph, and analysis when the behavior changes.

## Next skill

- `app-functional-graph`
