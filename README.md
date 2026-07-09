# Bears App-Based Workflow

`bears-app-based-workflow` is a Codex plugin for Bears application work. It follows a Spec Kit-style lifecycle and adds Bears-specific waves, functional graph planning, graph-linked ledger tasks, hardened dispatch packets, and parallel app-dev orchestration.

## Lifecycle

1. `app-constitution` records the app baseline and decision rules.
2. `app-research` creates or updates research waves and synchronizes the wave registry.
3. `app-specify` works with the user to expand wave docs into detailed functional specs.
4. `app-functional-graph` maps requirements to graph nodes and ledger references.
5. `app-plan` finds unbuilt functionality and writes graph-linked task plans.
6. `app-analyze` compares docs, graph, ledger, and implemented state.
7. `instruction-hardening` can tighten wave plans or dispatch packets without changing authority.
8. `app-dev` dispatches ready ledger tasks through L2 orchestrators and L3 workers.
9. `app-analyze` closes the convergence loop after implementation.

## Core artifacts

- `waves/index.md` — wave registry.
- `waves/<wave-id>/research.md` — wave research packet.
- `waves/<wave-id>/spec.md` — detailed functional specification.
- `waves/<wave-id>/plan.md` — task and dependency plan.
- `waves/<wave-id>/analysis.md` — implementation and documentation comparison.
- `docs/app-functional-graph.v1.json` — app-local functionality graph.
- `docs/app-task-ledger.v1.json` — app-local task ledger.

## Plugin skills

App workflow skills: `app-constitution`, `app-research`, `app-specify`, `app-functional-graph`, `app-plan`, `app-analyze`, `app-dev`.

Workflow hardening skill: `instruction-hardening`.

## Local Codex skill dependencies

General helper skills live outside this plugin under `/home/ai1/.codex/skills`:

- `bears-agents`
- `mcp-designer`
- `python-codeflow`
- `subagents`
- `subagents-roles`
- `yandex360-dns`

These local skills are optional helpers. They do not make this plugin an instruction authority and do not override `AGENTS.md` or contracts.

## Repository target

Target GitHub repository: `BearsCLOUD/bears-app-based-workflow`.

GitHub repository rename and push are operator steps. Local plugin identity and local remotes can point at the target name before the remote repository exists.
