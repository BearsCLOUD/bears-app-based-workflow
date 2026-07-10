# Bears App-Based Workflow

`bears-app-based-workflow` is a Codex plugin for app constitutions, research waves, functional specifications, graph-linked plans, delegated implementation, and convergence analysis.

## Workflow

For work already classified `DELEGATED`, every `app-*` skill uses `subagents` before file, log, terminal, Git, MCP, runtime, or network access. The solo parent or app-dev L2 first decomposes its task, then follows the skill for each concrete L3 assignment. `DIRECT` work stays with the primary and never enters `subagents`.

1. `app-constitution` records the app baseline.
2. `app-research` creates and synchronizes research waves.
3. `app-specify` closes product decisions with the user.
4. `app-functional-graph` maps decision-complete requirements to the canonical functional graph.
5. `app-plan` creates graph-linked ledger tasks for unbuilt behavior.
6. `app-dev` partitions dependency-ready work through fixed L1 and L2 orchestration, then dispatches concrete L3 assignments.
7. `app-analyze` checks convergence and routes gaps back to the owning stage.

Every inter-stage input and output uses the canonical `app-stage-handoff.v1` defined once in `app-functional-graph`. Its common fields are never omitted, unavailable early values use the schema's explicit empty semantics, and every status carries its canonical branch fields.

The normal success chain is `constitution-ready` -> `research-ready` -> `spec-ready` -> `graph-ready` -> `plan-ready` -> `implemented` -> `pass`. Feedback returns through named statuses: `needs-research` to `app-research`, `needs-spec` to `app-specify`, `needs-graph` to `app-functional-graph`, and `needs-plan` to `app-plan`. `app-analyze` may return `ready` only for already valid executable ledger tasks and then hands them to `app-dev`.

`docs/app-functional-graph.v1.json` is the source of truth for specified functionality ids, graph nodes, relationships, and functional coverage. Downstream plans, ledger tasks, implementation packets, and analyses carry its revision and refs; they never redefine graph meaning.

`instruction-editor` owns final instruction policy decisions and results; `instruction-hardening` supplies its repeatable editing method. `role-profile-architect` owns role-profile decisions and results; `role-profile-maintenance` supplies its comparison and least-privilege method.

The active catalog contains 50 deliverable-named profiles. Each profile defines its trigger, specialist, dependencies, permissions, conflict behavior, acceptance criteria, result contract, and one declarative example. Removed names are not aliases. `domain-lane-orchestrator` and `github-settings-editor` replace profiles that previously duplicated the same deliverable and permission boundary; `primary-source-researcher` owns evidence packets for decision-critical current claims.

## Plugin skills

- Stage procedures: `app-constitution`, `app-research`, `app-specify`, `app-functional-graph`, `app-plan`, `app-analyze`, `app-dev`.
- Dispatch procedure: `subagents`.
- Instruction procedures: `instruction-hardening`, `role-profile-maintenance`.

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

## Artifact ownership

- `app-constitution` writes only the app constitution.
- `app-research` writes the wave registry and research files.
- `app-specify` writes wave specifications.
- `app-functional-graph` is the sole semantic writer of the functional graph and writes only graph anchors in the ledger.
- `app-plan` writes wave plans and the planning fields of executable ledger tasks; it never writes the graph or graph anchors.
- `app-dev` writes implementation targets and only the ledger execution fields authorized by each task's `ledger_update_contract`.
- `app-analyze` writes wave analysis and treats the graph and ledger as read-only inputs.

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
- Plugin role TOML: result ownership, decisions, permissions, acceptance, and result fields.
- Plugin skills: repeatable methods, packet templates, references, and reusable procedures.
- External autoCI: tests, validators, audits, and cache checks.

Target repository: `BearsCLOUD/bears-app-based-workflow`.
