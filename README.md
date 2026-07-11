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
7. `app-analyze` determines convergence and routes gaps back to the owning stage.

Every inter-stage input and output uses the canonical `app-stage-handoff.v1` defined once in `app-functional-graph`. Its common fields are never omitted, unavailable early values use the schema's explicit empty semantics, and every status carries its canonical branch fields.

The normal success chain is `constitution-ready` -> `research-ready` -> `spec-ready` -> `graph-ready` -> `plan-ready` -> `implemented` -> `pass`. Feedback returns through named statuses: `needs-research` to `app-research`, `needs-spec` to `app-specify`, `needs-graph` to `app-functional-graph`, and `needs-plan` to `app-plan`. `app-analyze` may return `ready` only for already valid executable ledger tasks and then hands them to `app-dev`.

`<app-root>/docs/app-functional-graph.v1.json` in the consuming app repository is the source of truth for specified functionality ids, graph nodes, relationships, and functional coverage. Downstream plans, ledger tasks, implementation packets, and analyses carry its revision and refs; they never redefine graph meaning.

`worker` owns bounded instruction-policy edits and may apply `instruction-hardening` as the editing method. `role-profile-architect` owns only concrete role-profile create, merge, split, or delete operations directly requested by the current user; `role-profile-maintenance` supplies its comparison and least-privilege method. Every write-capable L3 stages only its assigned files and creates its own task-scoped local commit; push requires separate current-task user authorization.

The active catalog contains exactly nine profiles: `worker`, `explorer`, `diagnostic-command-runner`, `primary-source-researcher`, `runtime-evidence-reader`, `security-analysis-critic`, `workflow-orchestrator`, `domain-lane-orchestrator`, and `role-profile-architect`. Removed names are not aliases. All L3 routing follows the canonical ordered rules in `subagents`; callers do not keep local routing summaries.

## Plugin skills

- Stage procedures: `app-constitution`, `app-research`, `app-specify`, `app-functional-graph`, `app-plan`, `app-analyze`, `app-dev`.
- Dispatch procedure: `subagents`.
- Instruction procedures: `instruction-hardening`, `role-profile-maintenance`.

In `app-dev`, the parent takes fixed `workflow-orchestrator` L1 and starts fixed `domain-lane-orchestrator` L2 lanes; each L2 owns task decomposition. `subagents` deterministically selects one eligible L3 for each concrete assignment, emits `dispatch-packet.v2`, and accepts `result-packet.v1`. Each L3 reference ends with its assignment. Outside app-dev, a solo parent acts as the L2 analogue. `subagents` is the only dispatch procedure; callers fail closed if it is unavailable.

## Core artifacts

These paths are relative to the consuming app repository root, not this plugin repository:

- `<app-root>/docs/app-constitution.md`
- `<app-root>/waves/index.md`
- `<app-root>/waves/<wave-id>/research.md`
- `<app-root>/waves/<wave-id>/spec.md`
- `<app-root>/waves/<wave-id>/plan.md`
- `<app-root>/waves/<wave-id>/analysis.md`
- `<app-root>/docs/app-functional-graph.v1.json`
- `<app-root>/docs/app-task-ledger.v1.json`

## Artifact ownership

- `app-constitution` writes only the app constitution.
- `app-research` writes the wave registry and research files.
- `app-specify` writes wave specifications.
- `app-functional-graph` is the sole semantic writer of the functional graph and writes only graph anchors in the ledger.
- `app-plan` writes wave plans and the planning fields of executable ledger tasks; it never writes the graph or graph anchors.
- `app-dev` writes implementation targets and only the ledger execution fields authorized by each task's `ledger_update_contract`.
- `app-analyze` writes wave analysis and treats the graph and ledger as read-only inputs.

## Role installation

Role TOML files live only in `agents/`. Plugin-root agent auto-discovery is undocumented, so explicit installer registration remains required after source updates:

```text
./install [--codex-home PATH] [--dry-run]
./install uninstall [--codex-home PATH] [--dry-run]
```

The installer registers the nine exact profile names, updates only its marked config block, removes stale retired registrations, and archives known legacy profile files. It creates no aliases. Start a new Codex task after a changed install.


## Ownership

- Nearest `AGENTS.md`: mandatory local rules.
- Workspace contracts: shared invariants.
- Plugin role TOML: result ownership, decisions, permissions, acceptance, and result fields.
- Plugin skills: repeatable methods, packet templates, references, and reusable procedures.
- External autoCI: machine-owned completion evidence and automation status; read runtime-backed evidence with `runtime-evidence-reader` and generated-file evidence with `explorer`.

Target repository: `BearsCLOUD/bears-app-based-workflow`.
