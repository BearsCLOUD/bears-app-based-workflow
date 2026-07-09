# Bears App-Based Workflow Contract

## Purpose

Provide a compact Codex plugin that turns product-app intent into researched waves, detailed specs, functional graph nodes, graph-linked ledger tasks, hardened implementation dispatch packets, role-matched subagent orchestration, and convergence analysis.

## Terms

- `app constitution`: `docs/app-constitution.md`, the app-local functional baseline, functional gap register, open-decision list, and AGENTS alignment note. It is capped at 100 lines.
- `app-local AGENTS.md`: a short router for stable app-specific path, source, instruction, and evidence rules. It has instruction authority over the constitution inside its subtree.
- `wave`: one app workflow slice created by research, specified through source-backed decisions, planned through graph-linked ledger tasks, analyzed against code state, and dispatched when dependency-ready.
- `functional graph`: `docs/app-functional-graph.v1.json`, the app-local map of functionality, nodes, edges, state transitions, API calls, and evidence references.
- `task ledger`: `docs/app-task-ledger.v1.json`, the app-local source of executable tasks.
- `instruction hardening`: read-only compression of wave plans, dispatch packets, or workflow prose without changing product decisions, task scope, instruction authority, `AGENTS.md`, or contracts.
- `role-matched subagent`: a bounded worker whose profile matches the task role and whose packet names exact repo, paths, graph refs, target set, and completion criteria.
- `parallel lane`: an L2 partition whose repo, paths, target set, generated artifacts, and evidence outputs do not overlap another lane.
- `pre-commit autoCI`: the automatic commit-boundary system that owns validation, test, audit, route, cache, cachebuster, quick-validate, and plugin-validate scripts.
- `L1`: the parent app-dev coordinator.
- `L2`: one orchestrator lane for a ready wave or wave partition.
- `L3`: one worker or critic assigned a bounded ledger task.

## Workflow

```mermaid
flowchart LR
  C["app-constitution"] --> R["app-research"]
  R --> S["app-specify"]
  S --> G["app-functional-graph"]
  G --> P["app-plan"]
  P --> RA["subagents-roles"]
  RA --> BA["bears-agents"]
  BA --> SG["subagents"]
  SG --> H["instruction-hardening"]
  H --> A["app-analyze"]
  A -->|needs-spec| S
  A -->|needs-plan| P
  A -->|ready ledger work| D["app-dev"]
  D --> A
  A -->|pass| X["close wave"]
  A -->|blocked| B["record blocker"]
```

## Script ownership

Validation, test, audit, route, cache, cachebuster, quick-validate, and plugin-validate scripts are pre-commit autoCI responsibilities. Agents do not run them manually. Agents read generated autoCI or local-commit-validation evidence only after it exists, then fix known failures in owned files.

The plugin package must not add `scripts/`, `hooks.json`, `.mcp.json`, or manifest fields for those files.

## Stage contracts

### app-constitution

Input: app target, owner, product constraints, non-negotiable rules, existing docs, nearest parent `AGENTS.md`, and app-local `AGENTS.md` when present.

Output: `docs/app-constitution.md` with 100 lines or fewer, wave links when they already exist, functional gaps, open decisions, and an `AGENTS.md` alignment note. If a stable app-specific instruction rule is missing or stale, `app-constitution` creates or updates the app-local `AGENTS.md` as a short router.

Required constitution sections: `Functional summary`, `Core capabilities`, `Actors and runtime surfaces`, `Constraints and evidence`, `Functional gaps`, `Open decisions`, `AGENTS alignment note`, and `Next skill`.

Each functional gap records `gap`, `impact`, `evidence`, and `route`.

An app-local `AGENTS.md` router contains the app path, parent rule narrowed, constitution link, stable app rules, and evidence/source boundaries.

`app-constitution` does not write workspace-wide rules and does not override parent `AGENTS.md` files or contracts. Temporary, disputed, or functional details stay in the constitution.

### app-research

Input: user intent, app target, `docs/app-constitution.md`, nearest/app-local `AGENTS.md`, existing waves, and relevant sources.

Output:

- `wave-research.packet`
- `waves/index.md`
- `waves/<wave-id>/research.md`

Each wave records scope, constitution context, unknowns, sources, decisions, follow-up questions, sync status, and candidate parallel lanes. New important functional gaps return to `app-constitution`.

### app-specify

Input: one or more research waves and open questions.

Output: `waves/<wave-id>/spec.md` with actors, flows, data, errors, acceptance criteria, unresolved decisions, and graph hints.

### app-functional-graph

Input: specified waves and existing graph or ledger files.

Output:

- `docs/app-functional-graph.v1.json`
- graph references for `docs/app-task-ledger.v1.json`

Every executable task must reference at least one functionality id and one graph node ref.

### app-plan

Input: `docs/app-constitution.md`, nearest/app-local `AGENTS.md`, wave specs, graph, ledger, and implemented-state notes.

Output:

- `waves/<wave-id>/plan.md`
- updated `docs/app-functional-graph.v1.json`
- updated `docs/app-task-ledger.v1.json`
- L2/L3 lane plan with disjoint repo, path, and target sets

`app-plan` creates only decision-complete tasks that match constitution gaps, graph refs, and `AGENTS.md` constraints. Missing decisions return to `app-specify`. New important functional gaps return to `app-constitution`. It applies read-only `instruction-hardening` to the wave plan and candidate dispatch packets before app-dev handoff. It maximizes parallel lanes when write scopes and evidence outputs do not overlap.

If `docs/app-constitution.md` and `AGENTS.md` disagree, `AGENTS.md` is authority. The constitution receives a drift note and a route to the owning `AGENTS.md` or contract.

### subagents-roles

Input: graph-linked tasks, target paths, proof requirements, and dependency edges.

Output: role packet with owner role, critic role, lane, path scope, parallel safety, and role gaps.

### bears-agents

Input: role packet, task ledger, wave plan, and Bears role inventory.

Output: role coverage packet for every lane and L3 task.

### subagents

Input: role coverage packet, ready ledger tasks, target paths, and completion criteria.

Output: bounded L2/L3 delegation packets for role-matched subagents.

### instruction-hardening

Input: wave plan, candidate dispatch packets, and target `AGENTS.md` or linked contracts.

Output: compressed text, removed-content summary, and authority or drift note.

`instruction-hardening` is read-only. It never creates tasks, changes product decisions, runs scripts, or overrides `AGENTS.md` and contracts.

### app-analyze

Input: docs, graph, ledger, and implemented code state.

Output: `waves/<wave-id>/analysis.md` with status `pass`, `needs-plan`, `needs-spec`, or `blocked`.

Missing functionality returns to `app-plan`. Missing requirements return to `app-specify`. Ready ledger work goes to `app-dev`. `pass` closes the wave.

### app-dev

Input: ledger tasks with valid graph refs, ready dependencies, role coverage, hardened packets, and disjoint lane plan.

Output: L2 dispatch packets, L3 task packets, ledger status updates, changed-file lists, generated evidence refs when present, and wave closeout notes.

`app-dev` never invents implementation tasks outside the ledger. L1 starts L2 lanes. L2 starts L3 workers and critics. Every specific implementation, review, or integration task goes to a role-matched subagent. Planning and development maximize parallelism across disjoint repo, path, and target sets.

## Scenario prompts

- “research app feature” uses `app-research` and creates or updates waves.
- “specify this wave” uses `app-specify` and expands wave docs.
- “plan unbuilt functionality” uses `app-plan`, `subagents-roles`, `bears-agents`, and `subagents` to write graph-linked ledger tasks and lane packets.
- “analyze implemented state” uses `app-analyze` and reports missing or drifted functionality.
- “harden this wave” uses `instruction-hardening` and tightens wave prose without changing authority.
- “dev ready wave” uses `app-dev` with role-matched L2/L3 subagents.
