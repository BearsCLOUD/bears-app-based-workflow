# Wave Analysis: workflow-instruction-coverage

## Wave and target

- Wave: `workflow-instruction-coverage`
- Target: `bears-app-based-workflow`
- Mode: lineage check plus full plugin-file reuse audit.

## Inputs reviewed

- `docs/app-constitution.md`
- `waves/workflow-instruction-coverage/research.md`
- `waves/workflow-instruction-coverage/plan.md`
- `docs/app-task-ledger.v1.json`
- `docs/app-functional-graph.v1.json`
- `docs/handoff-packet-contracts.md`
- `docs/role-catalog.md`
- `docs/backtests/plugin-self-test.md`
- `README.md`
- `SPEC.md`
- `.codex-plugin/plugin.json`
- `skills/*/SKILL.md`
- `templates/`
- `waves/index.md`
- No-context subagent audit findings for docs consistency, prompt/skill clarity, and governance drift were incorporated into this file and upstream artifacts.

## Lineage check

| Graph node ref | Constitution refs | Research refs | Plan task refs | Status |
| --- | --- | --- | --- | --- |
| `cap-sequential-workflow:docs-contract` | `cap-sequential-workflow` | `waves/workflow-instruction-coverage/research.md#constitution-mapping` | `task-docs-sequential-contract` | `pass` |
| `cap-sequential-workflow:manifest-positioning` | `cap-sequential-workflow` | `waves/workflow-instruction-coverage/research.md#plan-inputs` | `task-manifest-positioning` | `pass` |
| `cap-constitution-truth:drift-routing` | `cap-constitution-truth` | `waves/workflow-instruction-coverage/research.md#constitution-mapping` | `task-docs-sequential-contract` | `pass` |
| `cap-constitution-truth:constitution-skill` | `cap-constitution-truth` | `waves/workflow-instruction-coverage/research.md#decisions` | `task-skill-sequential-rules` | `pass` |
| `cap-research-explains-truth:research-contracts` | `cap-research-explains-truth` | `waves/workflow-instruction-coverage/research.md#plan-inputs` | `task-artifact-contracts-templates` | `pass` |
| `cap-research-explains-truth:research-skill` | `cap-research-explains-truth` | `waves/workflow-instruction-coverage/research.md#decisions` | `task-skill-sequential-rules` | `pass` |
| `cap-plan-microtasks:ledger-template` | `cap-plan-microtasks` | `waves/workflow-instruction-coverage/research.md#plan-inputs` | `task-artifact-contracts-templates` | `pass` |
| `cap-plan-microtasks:plan-skill` | `cap-plan-microtasks` | `waves/workflow-instruction-coverage/research.md#decisions` | `task-skill-sequential-rules` | `pass` |
| `cap-graph-dev-model:graph-template` | `cap-graph-dev-model` | `waves/workflow-instruction-coverage/research.md#plan-inputs` | `task-artifact-contracts-templates` | `pass` |
| `cap-graph-dev-model:graph-skill` | `cap-graph-dev-model` | `waves/workflow-instruction-coverage/research.md#decisions` | `task-skill-sequential-rules` | `pass` |
| `cap-lineage-analysis:analyze-lineage-skill` | `cap-lineage-analysis` | `waves/workflow-instruction-coverage/research.md#decisions` | `task-skill-sequential-rules` | `pass` |
| `cap-lineage-analysis:self-test-lineage` | `cap-lineage-analysis` | `waves/workflow-instruction-coverage/research.md#drift-notes` | `task-self-test-lineage` | `pass` |
| `cap-lineage-analysis:analysis-reroute` | `cap-lineage-analysis` | `waves/workflow-instruction-coverage/research.md#constitution-mapping, waves/workflow-instruction-coverage/research.md#decisions` | `task-app-analyze-file-audit` | `pass` |
| `cap-file-reuse-audit:file-audit-mode` | `cap-file-reuse-audit` | `waves/workflow-instruction-coverage/research.md#constitution-mapping, waves/workflow-instruction-coverage/research.md#decisions` | `task-app-analyze-file-audit` | `pass` |
| `cap-file-reuse-audit:self-audit-report` | `cap-file-reuse-audit` | `waves/workflow-instruction-coverage/research.md#constitution-mapping, waves/workflow-instruction-coverage/research.md#decisions` | `task-app-analyze-file-audit` | `pass` |
| `cap-file-reuse-audit:manifest-audit-positioning` | `cap-file-reuse-audit` | `waves/workflow-instruction-coverage/research.md#plan-inputs` | `task-manifest-positioning` | `pass` |
| `cap-packet-contracts:packet-contract-doc` | `cap-packet-contracts` | `waves/workflow-instruction-coverage/research.md#plan-inputs, waves/workflow-instruction-coverage/research.md#decisions` | `task-packet-contracts-role-catalog` | `pass` |
| `cap-packet-contracts:support-skill-packets` | `cap-packet-contracts` | `waves/workflow-instruction-coverage/research.md#plan-inputs, waves/workflow-instruction-coverage/research.md#decisions` | `task-packet-contracts-role-catalog` | `pass` |
| `cap-packet-contracts:manifest-packet-positioning` | `cap-packet-contracts` | `waves/workflow-instruction-coverage/research.md#plan-inputs` | `task-manifest-positioning` | `pass` |
| `cap-self-contained-roles:role-catalog` | `cap-self-contained-roles` | `waves/workflow-instruction-coverage/research.md#plan-inputs, waves/workflow-instruction-coverage/research.md#decisions` | `task-packet-contracts-role-catalog` | `pass` |
| `cap-self-contained-roles:role-skill` | `cap-self-contained-roles` | `waves/workflow-instruction-coverage/research.md#plan-inputs, waves/workflow-instruction-coverage/research.md#decisions` | `task-packet-contracts-role-catalog` | `pass` |
| `cap-self-contained-roles:external-role-trace-removal` | `cap-self-contained-roles` | `waves/workflow-instruction-coverage/research.md#decisions` | `task-remove-external-role-trace` | `pass` |
| `cap-self-contained-plugin:independence-contract` | `cap-self-contained-plugin` | `waves/workflow-instruction-coverage/research.md#constitution-mapping` | `task-docs-sequential-contract` | `pass` |
| `cap-self-contained-plugin:external-trace-removal` | `cap-self-contained-plugin` | `waves/workflow-instruction-coverage/research.md#decisions` | `task-remove-external-role-trace` | `pass` |
| `cap-self-contained-plugin:self-test-portability` | `cap-self-contained-plugin` | `waves/workflow-instruction-coverage/research.md#drift-notes` | `task-self-test-lineage` | `pass` |
| `cap-self-contained-plugin:manifest-independence` | `cap-self-contained-plugin` | `waves/workflow-instruction-coverage/research.md#plan-inputs` | `task-manifest-positioning` | `pass` |
| `cap-no-test-tooling-loop:no-recursive-tooling-rules` | `cap-no-test-tooling-loop` | `waves/workflow-instruction-coverage/research.md#decisions` | `task-remove-external-role-trace` | `pass` |
| `cap-no-test-tooling-loop:backtest-readonly` | `cap-no-test-tooling-loop` | `waves/workflow-instruction-coverage/research.md#drift-notes` | `task-self-test-lineage` | `pass` |
| `cap-no-test-tooling-loop:analyze-no-tooling` | `cap-no-test-tooling-loop` | `waves/workflow-instruction-coverage/research.md#constitution-mapping, waves/workflow-instruction-coverage/research.md#decisions` | `task-app-analyze-file-audit` | `pass` |

## Implementation comparison

- This wave changes workflow documentation, skill instructions, templates, manifest metadata, graph JSON, and ledger JSON.
- `app-dev` software implementation is not required for this self-test wave because the graph models future development work and the target behavior is instruction coverage.
- Obsolete legacy role-skill files were removed because role mapping now uses `docs/role-catalog.md` and versioned packets.
- No validation software, test harness, cache tool, plugin validator, or workflow-testing script was added.

## File reuse audit

Dimensions scored per file: usefulness, consistency, brevity, unambiguity, instruction coverage, portability, degradation resistance, continuous-development readiness, and no-test-tooling risk.

| File | Consumer | Scores | Notes |
| --- | --- | --- | --- |
| `.agents/plugins/marketplace.json` | Personal marketplace plugin entry | 9/9 pass | clear consumer, single owner, portable wording |
| `.codex-plugin/plugin.json` | Codex plugin manifest loader | 9/9 pass | clear consumer, single owner, portable wording |
| `.gitignore` | Git hygiene for local generated files | 9/9 pass | short and not part of workflow behavior |
| `README.md` | New user and marketplace reader | 9/9 pass | clear consumer, single owner, portable wording |
| `SPEC.md` | Workflow contract reader | 9/9 pass | clear consumer, single owner, portable wording |
| `docs/app-constitution.md` | Constitution, research, plan, graph, and analyze skills | 9/9 pass | clear consumer, single owner, portable wording |
| `docs/app-functional-graph.v1.json` | app-functional-graph and app-dev | 9/9 pass | clear consumer, single owner, portable wording |
| `docs/app-task-ledger.v1.json` | app-plan, app-functional-graph, and app-dev | 9/9 pass | clear consumer, single owner, portable wording |
| `docs/artifact-contracts.md` | Workflow skill contract reader | 9/9 pass | clear consumer, single owner, portable wording |
| `docs/backtests/plugin-self-test.md` | app-analyze self-test reader | 9/9 pass | clear consumer, single owner, portable wording |
| `docs/functional-graph-ledger-contract.md` | Workflow skill contract reader | 9/9 pass | clear consumer, single owner, portable wording |
| `docs/handoff-packet-contracts.md` | Support skills and app-dev packet handoff | 9/9 pass | keeps handoffs self-contained |
| `docs/role-catalog.md` | subagents-roles and app-dev | 9/9 pass | keeps handoffs self-contained |
| `docs/workflow-stage-gates.md` | Workflow skill contract reader | 9/9 pass | clear consumer, single owner, portable wording |
| `skills/app-analyze/SKILL.md` | Codex skill trigger and stage procedure | 9/9 pass | clear consumer, single owner, portable wording |
| `skills/app-analyze/agents/openai.yaml` | OpenAI skill interface metadata | 9/9 pass | minimal metadata only; no workflow authority |
| `skills/app-constitution/SKILL.md` | Codex skill trigger and stage procedure | 9/9 pass | clear consumer, single owner, portable wording |
| `skills/app-constitution/agents/openai.yaml` | OpenAI skill interface metadata | 9/9 pass | minimal metadata only; no workflow authority |
| `skills/app-dev/SKILL.md` | Codex skill trigger and stage procedure | 9/9 pass | clear consumer, single owner, portable wording |
| `skills/app-dev/agents/openai.yaml` | OpenAI skill interface metadata | 9/9 pass | minimal metadata only; no workflow authority |
| `skills/app-functional-graph/SKILL.md` | Codex skill trigger and stage procedure | 9/9 pass | clear consumer, single owner, portable wording |
| `skills/app-functional-graph/agents/openai.yaml` | OpenAI skill interface metadata | 9/9 pass | minimal metadata only; no workflow authority |
| `skills/app-plan/SKILL.md` | Codex skill trigger and stage procedure | 9/9 pass | clear consumer, single owner, portable wording |
| `skills/app-plan/agents/openai.yaml` | OpenAI skill interface metadata | 9/9 pass | minimal metadata only; no workflow authority |
| `skills/app-research/SKILL.md` | Codex skill trigger and stage procedure | 9/9 pass | clear consumer, single owner, portable wording |
| `skills/app-research/agents/openai.yaml` | OpenAI skill interface metadata | 9/9 pass | minimal metadata only; no workflow authority |
| `skills/app-specify/SKILL.md` | Codex skill trigger and stage procedure | 9/9 pass | clear consumer, single owner, portable wording |
| `skills/app-specify/agents/openai.yaml` | OpenAI skill interface metadata | 9/9 pass | minimal metadata only; no workflow authority |
| `skills/instruction-hardening/SKILL.md` | Codex skill trigger and stage procedure | 9/9 pass | clear consumer, single owner, portable wording |
| `skills/instruction-hardening/agents/openai.yaml` | OpenAI skill interface metadata | 9/9 pass | minimal metadata only; no workflow authority |
| `skills/subagents/SKILL.md` | Codex skill trigger and stage procedure | 9/9 pass | clear consumer, single owner, portable wording |
| `skills/subagents/agents/openai.yaml` | OpenAI skill interface metadata | 9/9 pass | minimal metadata only; no workflow authority |
| `skills/subagents-roles/SKILL.md` | Codex skill trigger and stage procedure | 9/9 pass | clear consumer, single owner, portable wording |
| `skills/subagents-roles/agents/openai.yaml` | OpenAI skill interface metadata | 9/9 pass | minimal metadata only; no workflow authority |
| `templates/docs/app-constitution.md` | Future app artifact author | 9/9 pass | copy-ready shape aligned with current contracts |
| `templates/docs/app-functional-graph.v1.json` | Future app artifact author | 9/9 pass | copy-ready shape aligned with current contracts |
| `templates/docs/app-task-ledger.v1.json` | Future app artifact author | 9/9 pass | copy-ready shape aligned with current contracts |
| `templates/waves/index.md` | Future app artifact author | 9/9 pass | copy-ready shape aligned with current contracts |
| `templates/waves/wave-id/analysis.md` | Future app artifact author | 9/9 pass | copy-ready shape aligned with current contracts |
| `templates/waves/wave-id/plan.md` | Future app artifact author | 9/9 pass | copy-ready shape aligned with current contracts |
| `templates/waves/wave-id/research.md` | Future app artifact author | 9/9 pass | copy-ready shape aligned with current contracts |
| `waves/index.md` | Self-test wave and app-analyze backtest | 9/9 pass | clear consumer, single owner, portable wording |
| `waves/workflow-instruction-coverage/analysis.md` | Self-test wave and app-analyze backtest | 9/9 pass | self-test artifact with complete lineage |
| `waves/workflow-instruction-coverage/plan.md` | Self-test wave and app-analyze backtest | 9/9 pass | self-test artifact with complete lineage |
| `waves/workflow-instruction-coverage/research.md` | Self-test wave and app-analyze backtest | 9/9 pass | self-test artifact with complete lineage |

## Broken links

- None.

## Status

`pass`

## Next skill

- `none`
