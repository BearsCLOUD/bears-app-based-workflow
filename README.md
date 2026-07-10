# Bears App-Based Workflow

`bears-app-based-workflow` is a Codex plugin for app constitutions, research waves, functional specifications, graph-linked plans, delegated implementation, and convergence analysis.

## Workflow

Every `app-*` skill uses `subagents` before file, log, terminal, Git, MCP, runtime, or network access. The solo parent or app-dev L2 first decomposes its task, then follows the skill for each concrete L3 assignment. Selected L3 agents perform the work.

1. `app-constitution` records the app baseline.
2. `app-research` creates and synchronizes research waves.
3. `app-specify` closes product decisions with the user.
4. `app-functional-graph` maps requirements to stable graph nodes.
5. `app-plan` creates graph-linked ledger tasks for unbuilt behavior.
6. `app-analyze` compares documentation, graph, ledger, and implementation.
7. `app-dev` partitions dependency-ready work through fixed L1 and L2 orchestration, then dispatches concrete L3 assignments.
8. `app-analyze` checks convergence after implementation.

`instruction-hardening` routes approved semantics through the dedicated instruction editor. Role changes first go through the separate role editor/auditor.

## Plugin skills

- Stage procedures: `app-constitution`, `app-research`, `app-specify`, `app-functional-graph`, `app-plan`, `app-analyze`, `app-dev`.
- Dispatch procedure: `subagents`.
- Instruction procedure: `instruction-hardening`.

In `app-dev`, the parent takes the fixed L1 role and starts fixed L2 lanes; each L2 owns task decomposition. `subagents` owns the role-selection and helper-worker-critic dispatch procedure for each concrete L3 assignment, including the four packet schemas. It is not a task recipient. Outside app-dev, a solo parent acts as the L2 analogue. There is no `subagents-roles` skill.

## Core artifacts

- `docs/app-constitution.md`
- `waves/index.md`
- `waves/<wave-id>/research.md`
- `waves/<wave-id>/spec.md`
- `waves/<wave-id>/plan.md`
- `waves/<wave-id>/analysis.md`
- `docs/app-functional-graph.v1.json`
- `docs/app-task-ledger.v1.json`

## Role installation

Role TOML files live only in `agents/`. Register their `config_file` links after checkout updates:

```text
./install [--codex-home PATH] [--dry-run]
./install uninstall [--codex-home PATH] [--dry-run]
```

The installer updates only its marked config block and archives known legacy duplicates. Start a new Codex task after a changed install.


## Ownership

- Nearest `AGENTS.md`: mandatory local rules.
- Workspace contracts: shared invariants.
- Plugin skills: reusable procedures.
- Plugin role TOML: unique role behavior.
- External autoCI: tests, validators, audits, and cache checks.

Target repository: `BearsCLOUD/bears-app-based-workflow`.
