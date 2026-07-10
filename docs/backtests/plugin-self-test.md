# Plugin Self-Test Backtest

## Target

Use this plugin checkout as the app target for backtesting the sequential workflow.

Wave id: `workflow-instruction-coverage`.

## Goal

Prove that the constitution retains only exact records, cited user-message evidence stays safe and unchanged, and every graph node resolves through research and a concrete plan microtask without workflow-testing software.

## Backtest sequence

1. Read `docs/artifact-contracts.md` for the constitution and user-evidence shapes.
2. Read `docs/app-constitution.md` and confirm each present section contains exact records.
3. Follow its user-message citations to `docs/app-user-evidence.md` and compare the excerpts byte for byte with the captured inputs.
4. Read `waves/workflow-instruction-coverage/research.md` and confirm every constitution id is explained.
5. Read `waves/workflow-instruction-coverage/plan.md` and confirm every microtask cites confirmed constitution and research refs.
6. Read `docs/app-task-ledger.v1.json` and confirm every task matches the plan.
7. Read `docs/app-functional-graph.v1.json` and confirm every graph node cites constitution, research, and plan refs.
8. Read `docs/handoff-packet-contracts.md` and confirm support-skill packet fields are aligned.
9. Read `docs/role-catalog.md` and confirm role mapping is self-contained.
10. Read `waves/workflow-instruction-coverage/analysis.md` and confirm the wave status names any broken link or passes.

## Constitution precision cases

| Case | Input | Required result |
| --- | --- | --- |
| Minimal constitution | Exact app target and one exact capability | Title, app target, and one populated `Capabilities` record; no other section |
| Necessary document over 100 lines | Enough independently changeable exact records to exceed 100 lines | Every necessary record remains; no padding or truncation |
| No exact record | Exact app target but no exact capability, constraint, gap, decision, or inference | No constitution file; one concrete question |
| Empty record type | No record for one optional section | The section is absent; no table or placeholder value is emitted |
| Inference | Source facts support only an unverified conclusion | Labeled `inference-*` with `app-research` route; no plan, ledger, or graph reference |
| Exact user excerpt | A safe session message supports a constitution ID | One cited `user-msg-*` entry contains the shortest unchanged continuous excerpt |
| Corrected user excerpt | A committed quote is corrected | A new entry is appended; the old quote is unchanged and its status becomes `superseded` or `withdrawn` |
| Conflicting user excerpts | Two active messages require incompatible results | A `decision-*` names one question, the blocked IDs, and the decision authority |
| Sensitive user text | The only self-contained excerpt contains a secret, credential, or production datum | No evidence entry; ask for a sanitized statement |
| Complete lineage | Research confirms a `cap-*` or `gap-*` | The ID resolves through research, plan, ledger, and graph references |

## Pass rules

- Every workflow text positions graph modeling after approved plan microtasks.
- Every planning instruction uses ordered microtasks as the default.
- Every graph node has `functionality_id`, `constitution_refs`, `research_refs`, and `plan_task_refs`.
- Every graph node has concrete `evidence_refs`; directory-only and wildcard refs are not sufficient proof.
- Every plan microtask has `constitution_refs`, `research_refs`, dependencies, owner role, critic role, done, proof, and status.
- Every research wave explains constitution ids.
- Every plan, ledger, and graph constitution reference is a research-confirmed `cap-*` or `gap-*`; no `inference-*` crosses that boundary.
- Every constitution section is populated, and its records use the exact fields in `docs/artifact-contracts.md`.
- Every cited `user-msg-*` entry has a valid status, UTC capture date, related constitution IDs, and an unchanged safe excerpt.
- Packet contracts do not require downstream fields that upstream packets omit.
- Role mapping uses `docs/role-catalog.md` and does not require an external role inventory.
- Functional drift routes to constitution; execution-constraint drift is reported separately and does not rewrite functional truth.
- `app-analyze` file-audit mode covers plugin file reuse quality without requiring a new audit script, validator, harness, or workflow-testing tool.

## Local inspection commands

Agents may use targeted reads, targeted grep, `git diff --check`, `git status --short`, and JSON shape inspection. External automation owns validation, test, audit, route, cache, cachebuster, quick-validate, and plugin-validate scripts.
