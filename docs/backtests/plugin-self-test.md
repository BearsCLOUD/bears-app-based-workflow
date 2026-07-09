# Plugin Self-Test Backtest

## Target

Use this plugin checkout as the app target for backtesting the sequential workflow.

Wave id: `workflow-instruction-coverage`.

## Goal

Prove that every functional graph node is explainable through constitution truth, research explanation, and a concrete plan microtask, without relying on environment instructions or creating workflow-testing software.

## Backtest sequence

1. Read `docs/app-constitution.md` as functional source of truth.
2. Read `waves/workflow-instruction-coverage/research.md` and confirm every constitution id is explained.
3. Read `waves/workflow-instruction-coverage/plan.md` and confirm every microtask cites constitution and research refs.
4. Read `docs/app-task-ledger.v1.json` and confirm every task matches the plan.
5. Read `docs/app-functional-graph.v1.json` and confirm every graph node cites constitution, research, and plan refs.
6. Read `docs/handoff-packet-contracts.md` and confirm support-skill packet fields are aligned.
7. Read `docs/role-catalog.md` and confirm role mapping is self-contained.
8. Read `waves/workflow-instruction-coverage/analysis.md` and confirm the wave status names any broken link or passes.

## Pass rules

- Every workflow text positions graph modeling after approved plan microtasks.
- Every planning instruction uses ordered microtasks as the default.
- Every graph node has `functionality_id`, `constitution_refs`, `research_refs`, and `plan_task_refs`.
- Every plan microtask has `constitution_refs`, `research_refs`, dependencies, owner role, critic role, done, proof, and status.
- Every research wave explains constitution ids.
- Packet contracts do not require downstream fields that upstream packets omit.
- Role mapping uses `docs/role-catalog.md` and does not require an external role inventory.
- Functional drift routes to constitution; execution-constraint drift is reported separately and does not rewrite functional truth.
- `app-analyze` file-audit mode covers plugin file reuse quality without requiring a new audit script, validator, harness, or workflow-testing tool.

## Local inspection commands

Agents may use targeted reads, targeted grep, `git diff --check`, `git status --short`, and JSON shape inspection. External automation owns validation, test, audit, route, cache, cachebuster, quick-validate, and plugin-validate scripts.
