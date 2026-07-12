# Bears App-Based Workflow

`bears-app-based-workflow` is a Codex plugin for app constitutions, research waves, functional specifications, typed traceability and process indexes, graph-linked plans, repo-scoped implementation queues, immutable review, remediation, and convergence analysis.

`app-solo-route` keeps a `DIRECT` workstream with one primary and sequentially resumes `app-research`, `app-specify`, `app-functional-graph`, `app-plan`, and `app-analyze`. It stops at the external `app-constitution` or `app-dev` boundary, terminal `pass|blocked`, unchanged waiting state, or a required architecture decision; it never initializes delegated routing.

## Workflow

For work already classified `DELEGATED`, every `app-*` skill uses `subagents` before file, log, terminal, Git, MCP, runtime, or network access. A solo parent decomposes its stage work; app-dev instead uses fixed L1 orchestration and persistent repo-L2 queues without decomposing canonical tasks. Each caller follows the skill for every concrete L3 assignment. `DIRECT` work stays with the primary and never enters `subagents`.

1. `app-constitution` records the app baseline.
2. `app-research` creates and synchronizes research waves.
3. `app-specify` closes product decisions with the user.
4. `app-functional-graph` maps decision-complete requirements into the semantic functional map.
5. `app-context-index` rebuilds the derived traceability and process indexes at run/wave entry and source drift.
6. `app-plan` creates graph-linked ledger tasks for unbuilt behavior.
7. `app-dev` runs dependency-ready work through persistent repo-L2 queues, one-task app-worker dispatch, immutable repo review, and remediation.
8. `app-analyze` determines convergence and routes gaps back to the owning stage.

Every inter-stage input and output uses `contracts/app-stage-handoff.v2.schema.json`. `contracts/app-workflow-definition.v1.json` is the single route, ownership, entry-gate, app-dev process, and edge-semantics definition; skills do not keep local route tables.

The normal success chain is `constitution-ready` -> `research-ready` -> `spec-ready` -> `graph-ready` -> `plan-ready` -> `implemented` -> `pass`. Feedback returns through named statuses: `needs-research` to `app-research`, `needs-spec` to `app-specify`, `needs-graph` to `app-functional-graph`, and `needs-plan` to `app-plan`. `app-analyze` may return `ready` only for already valid executable ledger tasks and then hands them to `app-dev`.

Documents, code, tests, ledger records, results, reviews, commits, and existing evidence remain authoritative. `<app-root>/docs/app-functional-map.v2.json` records the specification-derived semantic mapping. `app-context-index` alone owns the rebuildable `<app-root>/docs/app-traceability-index.v2.json` and `<app-root>/docs/app-process-index.v1.json`; a mismatched source digest makes both unusable for routing, planning, or convergence.

The bundled read-only `app-graph` MCP exposes dependency closure, impact paths, cycle/reachability diagnostics, topological task layers, end-to-end trace paths, and process state. It reads only allowlisted tracked JSON under an explicit app root, performs no writes or network access, and never declares acceptance.

`worker` remains the generic bounded mutation profile and may apply `instruction-hardening` for instruction-policy edits. `app-worker` owns one canonical app task at a time and may be reused only inside the same repo-wave session. `wave-change-critic` owns one repo's immutable wave review; remediation is represented by new canonical tasks. `role-profile-architect` owns only concrete role-profile create, merge, split, or delete operations directly requested by the current user; `role-profile-maintenance` supplies its comparison and least-privilege method. Every write-capable L3 stages only its assigned files and creates its own task-scoped local commit; push requires separate current-task user authorization.

The active catalog is discovered from the regular, non-symlink `agents/*.toml` files at the exact plugin commit, sorted by profile name, and bounded to 1..64 entries. Removed names are not aliases. All L3 routing follows the canonical ordered rules in `subagents`; callers do not keep local routing summaries.

## Plugin skills

- Stage procedures: `app-constitution`, `app-research`, `app-specify`, `app-functional-graph`, `app-plan`, `app-analyze`, `app-dev`.
- Cross-cutting index procedure: `app-context-index`.
- DIRECT routing procedure: `app-solo-route`.
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
- `<app-root>/docs/app-functional-map.v2.json`
- `<app-root>/docs/app-traceability-index.v2.json`
- `<app-root>/docs/app-process-index.v1.json`
- `<app-root>/docs/app-task-ledger.v1.json`

## Artifact ownership

- `app-constitution` writes only the app constitution.
- `app-research` writes the wave registry and research files.
- `app-specify` writes wave specifications.
- `app-functional-graph` is the sole semantic writer of the functional map.
- `app-context-index` is the sole writer of the two derived indexes and cannot change source meaning or acceptance.
- `app-plan` writes implementation or remediation wave plans and the planning fields of executable ledger tasks; it never writes the functional map or indexes.
- `app-dev` writes implementation targets and only the ledger execution fields authorized by each task's `ledger_update_contract`.
- `app-analyze` writes wave analysis and treats the functional map, indexes, and ledger as read-only inputs.

## Versioning

The plugin manifest uses plain `MAJOR.MINOR.PATCH` SemVer. Every new `main` push increments the version: use a patch increment for ordinary changes, a minor increment for a substantial refactor, and set `1.0.0` or any later major version only when the current user explicitly requests it. CD rejects a new commit whose plain SemVer is not strictly greater than the currently receipted version. Legacy `+codex.YYYYMMDDhhmmss` values remain readable only for one-way receipt and deployment migration; after the first plain SemVer deployment, CD cannot return to that format.

## Role installation

Role TOML files live only in `agents/`. Plugin-root agent auto-discovery is undocumented, so explicit installer registration remains required after source updates:

```text
./install [--codex-home PATH] [--dry-run]
./install uninstall [--codex-home PATH] [--dry-run]
```

The installer registers the dynamically discovered profile names, updates only its marked config block, removes stale retired registrations, and archives known legacy profile files. It creates no aliases. Unrelated global `[agents.*]` registrations remain byte-for-byte outside that block; an active role name outside the block is an ownership collision and fails closed. A removed or renamed registration is retired only from a managed block authenticated by its prior receipt. Start a new Codex task after a changed install.

Live CD never executes or imports the cached `install` payload. The fixed root-owned gateway parses the exact pinned manifest and role blobs as data, materializes a content-addressed role generation under `/var/lib/bears-plugin-deploy/ai1`, and reconciles the shared marked config block and role receipt with Linux `renameat2` compare-and-swap publication. Before state work, the root installer stops each managed service cgroup (the kernel process group owned by one service), proves it has no remaining processes, and installs the runner unit with `KillMode=control-group`. The installer provisions the root-owned state ancestor and private `ai1` leaf, safely creates the gateway's exact private lock when absent, and acquires that lock plus the legacy lock exclusively without waiting. Its one-time importer refuses an old promotion intent or conflicting destination and durably copies only an exact private v1 deployment receipt through one fixed private staging file. A rerun resumes an exact complete stage or replaces only an exact incomplete prefix for the expected receipt or tombstone phase; unknown files, stage drift, and lock contention fail closed. The importer then publishes a no-clobber tombstone bound to the legacy source path, exact receipt identity, and SHA-256 digest. Reinstalls require that unchanged safe source and exact tombstone, but accept a valid private destination receipt in v1 or evolved v2 form; missing evidence, drift, and conflicts fail closed. Legacy evidence is never deleted. When sourced, the installer only defines fixed constants and internal helpers: it does not change shell options, install traps, mutate files, or control services. Retained autoCI fixtures may call parameterized state-import and cgroup predicates only in disposable directories, while the production main passes fixed live paths and owners and accepts no environment path override. A durable `PREPARED` to `COMMITTED` journal retains displaced preimages until the combined config/receipt transition commits; installation, registration migration, and fallback removal recover from partial publication.

Role receipt v2 owns the exact dynamically discovered catalog and its ordered content digest. The one-shot registration migration accepts only the byte-exact live v1 receipt and managed block at `0.1.0+codex.20260711074119`. It authenticates the historical nine registered paths but never reads, moves, changes, archives, or deletes the referenced legacy TOML files. It replaces only the registration block and receipt, preserves prior archive metadata, and durably publishes a no-clobber tombstone before the v2 deployment receipt; drift, rollback, replay, or a conflicting tombstone fails closed.

On every push to `main`, `plugin-marketplace-cd.yml` invokes `/usr/local/sbin/deploy-bears-app-based-workflow` through the fixed runner-to-`ai1` sudo boundary. The gateway fetches the exact pushed revision, upgrades the fixed Git marketplace, reinstalls the plugin, reconciles roles, and advances the durable receipt only after exact SHA/version verification. CD does not declare acceptance.


## Ownership

- Nearest `AGENTS.md`: mandatory local rules.
- Workspace contracts: shared invariants.
- Plugin-local contract: portable delegation packet definitions installed with the runtime payload.
- Plugin role TOML: result ownership, decisions, permissions, acceptance, and result fields.
- Plugin skills: repeatable methods, active contract references, and reusable procedures.
- Repository automation: autoCI remains disconnected; CD updates the installed plugin from the fixed marketplace on every `main` push.

Target repository: `BearsCLOUD/bears-app-based-workflow`.
