# Bears App-Based Workflow

`bears-app-based-workflow` is a self-contained Codex plugin for sequential application workflow artifacts. It turns an app constitution into researched waves, ordered plan microtasks, a functional graph that models future development, bounded implementation packets, and `app-analyze` closeout.

## Lifecycle

1. `app-constitution` records one capability, constraint, gap, question, or inference per stable id, omits empty sections, and routes only to `app-research`.
2. `app-research` reads cited user-message evidence and verifies constitution items through sources, decisions, unknowns, and wave scope. `app-specify` is only a clarification helper inside this stage.
3. `app-plan` decomposes only research-confirmed `cap-*` and `gap-*` records into approved ordered microtasks. Planning does not accept inferences or create graph nodes.
4. `app-functional-graph` builds the dev-stage model from approved plan microtasks. Every graph node traces to constitution, research, and plan references.
5. `app-dev` executes only graph-backed ledger tasks with complete lineage. It may use support skills for role mapping, dispatch packets, and instruction hardening.
6. `app-analyze` checks lineage, implementation convergence, file-level instruction quality, reuse safety, and closes or reroutes the wave.

## Core artifacts

- `docs/app-constitution.md` — app register of exact typed records and their required sources.
- `docs/app-user-evidence.md` — optional user-message evidence with immutable quoted text.
- `waves/index.md` — wave registry.
- `waves/<wave-id>/research.md` — source-backed explanation of constitution items.
- `waves/<wave-id>/plan.md` — ordered microtasks derived from research.
- `waves/<wave-id>/analysis.md` — lineage, implementation, and reuse-quality comparison.
- `docs/app-functional-graph.v1.json` — dev-stage functional graph model.
- `docs/app-task-ledger.v1.json` — ordered plan microtask ledger.

## Plugin docs

- `SPEC.md` — workflow contract.
- `docs/workflow-stage-gates.md` — sequential stage gates and drift routing.
- `docs/functional-graph-ledger-contract.md` — graph and ledger lineage rules.
- `docs/handoff-packet-contracts.md` — packet fields passed between skills.
- `docs/role-catalog.md` — self-contained role names for handoff packets.
- `docs/artifact-contracts.md` — sole owner of artifact sections and fields.
- `docs/backtests/plugin-self-test.md` — structural self-test backtest.
- `templates/` — copy-ready artifact templates.

## Plugin skills

Core workflow skills: `app-constitution`, `app-research`, `app-plan`, `app-functional-graph`, `app-dev`, `app-analyze`.

Support skills: `app-specify`, `subagents-roles`, `subagents`, `instruction-hardening`.

## Independence and script ownership

The constitution has no line-count target or limit. It omits empty sections, placeholder rows, session execution constraints, and next-stage fields. `docs/app-user-evidence.md` is created only when a constitution record cites a safe, minimal verbatim excerpt.

The plugin does not depend on a specific host workspace, host instruction file, runtime, MCP server, hook, role inventory, or validation script. Session execution constraints may limit a live Codex session, but only their non-sensitive descriptions are returned in closeout; they are not stored in the constitution.

Validation, test, audit, route, cache, cachebuster, quick-validate, and plugin-validate scripts are external automation responsibilities. Plugin skills do not ask agents to run those scripts manually or create testing software just to test this workflow.

This plugin must not add plugin-local `scripts/`, `hooks.json`, or `.mcp.json`.

## Repository target

Target GitHub repository: `BearsCLOUD/bears-app-based-workflow`.
