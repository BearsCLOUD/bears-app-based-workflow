# Bears App-Based Workflow

`bears-app-based-workflow` is a Codex plugin for Bears application work. It follows a Spec Kit-style lifecycle and adds Bears-specific waves, functional graph planning, graph-linked ledger tasks, instruction hardening, role-matched subagents, and parallel app-dev orchestration.

## Lifecycle

1. `app-constitution` records the app baseline and decision rules.
2. `app-research` creates or updates research waves and synchronizes the wave registry.
3. `app-specify` expands wave docs into detailed functional specs.
4. `app-functional-graph` maps requirements to graph nodes and ledger references.
5. `app-plan` finds unbuilt functionality, writes graph-linked task plans, and maximizes disjoint parallel lanes.
6. `subagents-roles` maps tasks to owner and critic roles.
7. `bears-agents` confirms Bears role coverage for every lane.
8. `subagents` creates bounded L2/L3 delegation packets.
9. `instruction-hardening` tightens wave plans or dispatch packets without changing authority.
10. `app-dev` dispatches ready ledger tasks through L2 orchestrators, L3 workers, and critics.
11. `app-analyze` closes the convergence loop after implementation.

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

Subagent orchestration skills: `subagents`, `subagents-roles`, `bears-agents`.

Workflow hardening skill: `instruction-hardening`.

## Local Codex skill dependencies

General helper skills that stay outside this plugin under `/home/ai1/.codex/skills`:

- `mcp-designer`
- `python-codeflow`
- `yandex360-dns`

These local skills are external dependencies. They do not make this plugin an instruction authority and do not override `AGENTS.md` or contracts.

## Script ownership

Validation, test, audit, route, cache, cachebuster, quick-validate, and plugin-validate scripts are pre-commit autoCI responsibilities. Agents do not run them manually. Agents read generated autoCI or local-commit-validation evidence only after it exists, then fix known failures in owned files.

This plugin must not add plugin-local `scripts/`, `hooks.json`, or `.mcp.json`.

## Repository target

Target GitHub repository: `BearsCLOUD/bears-app-based-workflow`.

Repository rename and push are repository-publishing steps. Local plugin identity and local remotes can point at the target name before the remote repository exists.
