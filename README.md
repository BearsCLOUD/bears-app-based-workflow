# Bears App-Based Workflow

`bears-app-based-workflow` is a Codex plugin for app constitutions, research waves, functional specifications, graph-linked plans, repo-scoped implementation queues, immutable review, remediation, and convergence analysis.

## Workflow

For work already classified `DELEGATED`, every `app-*` skill uses `subagents` before file, log, terminal, Git, MCP, runtime, or network access. A solo parent decomposes its stage work; app-dev instead uses fixed L1 orchestration and persistent repo-L2 queues without decomposing canonical tasks. Each caller follows the skill for every concrete L3 assignment. `DIRECT` work stays with the primary and never enters `subagents`.

1. `app-constitution` records the app baseline.
2. `app-research` creates and synchronizes research waves.
3. `app-specify` closes product decisions with the user.
4. `app-functional-graph` maps decision-complete requirements to the canonical functional graph.
5. `app-plan` creates graph-linked ledger tasks for unbuilt behavior.
6. `app-dev` runs dependency-ready work through persistent repo-L2 queues, one-task app-worker dispatch, immutable repo review, and remediation.
7. `app-analyze` determines convergence and routes gaps back to the owning stage.

Every inter-stage input and output uses the canonical `app-stage-handoff.v1` defined once in `app-functional-graph`. Its common fields are never omitted, unavailable early values use the schema's explicit empty semantics, and every status carries its canonical branch fields.

The normal success chain is `constitution-ready` -> `research-ready` -> `spec-ready` -> `graph-ready` -> `plan-ready` -> `implemented` -> `pass`. Feedback returns through named statuses: `needs-research` to `app-research`, `needs-spec` to `app-specify`, `needs-graph` to `app-functional-graph`, and `needs-plan` to `app-plan`. `app-analyze` may return `ready` only for already valid executable ledger tasks and then hands them to `app-dev`.

`<app-root>/docs/app-functional-graph.v1.json` in the consuming app repository is the source of truth for specified functionality ids, graph nodes, relationships, and functional coverage. Downstream plans, ledger tasks, implementation packets, and analyses carry its revision and refs; they never redefine graph meaning.

`worker` remains the generic bounded mutation profile and may apply `instruction-hardening` for instruction-policy edits. `app-worker` owns one canonical app task at a time and may be reused only inside the same repo-wave session. `wave-change-critic` owns one repo's immutable wave review; remediation is represented by new canonical tasks. `role-profile-architect` owns only concrete role-profile create, merge, split, or delete operations directly requested by the current user; `role-profile-maintenance` supplies its comparison and least-privilege method. Every write-capable L3 stages only its assigned files and creates its own task-scoped local commit; push requires separate current-task user authorization.

The active catalog contains exactly eleven profiles: `worker`, `app-worker`, `explorer`, `diagnostic-command-runner`, `primary-source-researcher`, `runtime-evidence-reader`, `wave-change-critic`, `security-analysis-critic`, `workflow-orchestrator`, `domain-lane-orchestrator`, and `role-profile-architect`. Removed names are not aliases. All L3 routing follows the canonical ordered rules in `subagents`; callers do not keep local routing summaries.

## Plugin skills

- Stage procedures: `app-constitution`, `app-research`, `app-specify`, `app-functional-graph`, `app-plan`, `app-analyze`, `app-dev`.
- Dispatch procedure: `subagents`.
- Instruction procedures: `instruction-hardening`, `role-profile-maintenance`.

In `app-dev`, the parent takes fixed `workflow-orchestrator` L1 and starts one persistent `domain-lane-orchestrator` L2 per repository. Each repo-L2 owns its canonical queue, reuses one `app-worker` session per repo wave, and sends exactly one current task at a time. A fresh `wave-change-critic` reviews each closed repo wave over an immutable commit range; repo-local findings become new remediation tasks through `app-plan`. `subagents` owns deterministic L3 selection and bounded dispatch. Outside app-dev, a solo parent acts as the L2 analogue. `subagents` is the only dispatch procedure; callers fail closed if it is unavailable.

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
- `app-plan` writes implementation or remediation wave plans and the planning fields of executable ledger tasks; it never writes the graph or graph anchors.
- `app-dev` writes implementation targets and only the ledger execution fields authorized by each task's `ledger_update_contract`.
- `app-analyze` writes wave analysis and treats the graph and ledger as read-only inputs.

## Role installation

Role TOML files live only in `agents/`. Plugin-root agent auto-discovery is undocumented, so explicit installer registration remains required after source updates:

```text
./install [--codex-home PATH] [--dry-run]
./install uninstall [--codex-home PATH] [--dry-run]
```

The installer registers the eleven exact profile names, updates only its marked config block, removes stale retired registrations, and archives known legacy profile files. It creates no aliases. Unrelated global `[agents.*]` registrations remain byte-for-byte outside that block; a canonical role name outside the block is an ownership collision and fails closed. Start a new Codex task after a changed install.

Live CD never executes or imports the cached `install` payload. The fixed root-owned gateway parses the exact pinned manifest and role blobs as data, materializes a content-addressed role generation under `/var/lib/bears-plugin-deploy/ai1`, and reconciles the shared marked config block and role receipt with Linux `renameat2` compare-and-swap publication. Before state work, the root installer stops each managed service cgroup (the kernel process group owned by one service), proves it has no remaining processes, and installs the runner unit with `KillMode=control-group`. The installer provisions the root-owned state ancestor and private `ai1` leaf, safely creates the gateway's exact private lock when absent, and acquires that lock plus the legacy lock exclusively without waiting. Its one-time importer refuses an old promotion intent or conflicting destination and durably copies only an exact private v1 deployment receipt through one fixed private staging file. A rerun resumes an exact complete stage or replaces only an exact incomplete prefix for the expected receipt or tombstone phase; unknown files, stage drift, and lock contention fail closed. The importer then publishes a no-clobber tombstone bound to the legacy source path, exact receipt identity, and SHA-256 digest. Reinstalls require that unchanged safe source and exact tombstone, but accept a valid private destination receipt in v1 or evolved v2 form; missing evidence, drift, and conflicts fail closed. Legacy evidence is never deleted. A durable `PREPARED` to `COMMITTED` journal retains displaced preimages until the combined config/receipt transition commits; installation, registration migration, and fallback removal recover from partial publication.

Role receipt v2 owns exactly the current eleven-role catalog. The one-shot registration migration accepts only the byte-exact live v1 receipt and managed block at `0.1.0+codex.20260711074119`. It authenticates the nine registered paths but never reads, moves, changes, archives, or deletes the referenced legacy TOML files. It replaces only the registration block and receipt, preserves prior archive metadata, and durably publishes a no-clobber tombstone before the v2 deployment receipt; drift, rollback, replay, or a conflicting tombstone fails closed.

The CD job executes only `/usr/local/sbin/deploy-bears-app-based-workflow` after proving it is a non-symlink, root-owned, non-group/world-writable file whose bytes and SHA-256 digest exactly match the CI-reviewed gateway source. Reinstall that gateway from reviewed exact source with `.github/runner/install-runner.sh` before relying on new enforcement. These same-user checks close cooperative races but cannot exclude a continuously malicious process with the same UID after verification; eliminating that residual risk requires a privileged broker or ownership separation.


## Ownership

- Nearest `AGENTS.md`: mandatory local rules.
- Workspace contracts: shared invariants.
- Plugin role TOML: result ownership, decisions, permissions, acceptance, and result fields.
- Plugin skills: repeatable methods, packet templates, references, and reusable procedures.
- External autoCI: machine-owned completion evidence and automation status; read runtime-backed evidence with `runtime-evidence-reader` and generated-file evidence with `explorer`.

Target repository: `BearsCLOUD/bears-app-based-workflow`.
