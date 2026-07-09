# Bears App-Based Workflow

`bears-app-based-workflow` is a self-contained Codex plugin for sequential application workflow artifacts. It turns an app constitution into researched waves, sequential plan microtasks, a functional graph that models the future dev stage, hardened dispatch packets, implementation analysis, and role-aware handoffs.

## Lifecycle

1. `app-constitution` records the functional source of truth: capabilities, gaps, decisions, constraints, and evidence needs.
2. `app-research` explains constitution items through sources, decisions, unknowns, and wave scope.
3. `app-plan` decomposes research outcomes into ordered microtasks. Planning does not create graph nodes.
4. `app-functional-graph` builds the dev-stage model from approved plan microtasks. Every graph node traces to constitution, research, and plan references.
5. `subagents-roles` maps graph-backed work to owner, critic, and helper roles.
6. `bears-agents` confirms role coverage.
7. `subagents` creates bounded sequential dispatch packets.
8. `instruction-hardening` tightens plans or packets without changing functional truth.
9. `app-dev` executes only graph nodes with complete lineage.
10. `app-analyze` checks lineage and implementation convergence.

## Core artifacts

- `docs/app-constitution.md` — app functional source of truth.
- `waves/index.md` — wave registry.
- `waves/<wave-id>/research.md` — source-backed explanation of constitution items.
- `waves/<wave-id>/plan.md` — ordered microtasks derived from research.
- `waves/<wave-id>/analysis.md` — lineage and implementation comparison.
- `docs/app-functional-graph.v1.json` — dev-stage functional graph model.
- `docs/app-task-ledger.v1.json` — ordered plan microtask ledger.

## Plugin docs

- `SPEC.md` — workflow contract.
- `docs/workflow-stage-gates.md` — sequential stage gates and drift routing.
- `docs/functional-graph-ledger-contract.md` — graph and ledger lineage rules.
- `docs/artifact-contracts.md` — required artifact sections and fields.
- `docs/backtests/plugin-self-test.md` — plugin self-test backtest.
- `templates/` — copy-ready artifact templates.

## Plugin skills

App workflow skills: `app-constitution`, `app-research`, `app-plan`, `app-functional-graph`, `app-analyze`, `app-dev`.

Clarification helper skill: `app-specify`.

Subagent orchestration skills: `subagents`, `subagents-roles`, `bears-agents`.

Workflow hardening skill: `instruction-hardening`.

## Independence and script ownership

The plugin does not depend on a specific host workspace, host instruction file, runtime, MCP server, hook, or validation script. Host policies may constrain a live Codex session, but plugin artifacts remain portable and constitution-led.

Validation, test, audit, route, cache, cachebuster, quick-validate, and plugin-validate scripts are external automation responsibilities. Plugin skills do not ask agents to run those scripts manually.

This plugin must not add plugin-local `scripts/`, `hooks.json`, or `.mcp.json`.

## Repository target

Target GitHub repository: `BearsCLOUD/bears-app-based-workflow`.
