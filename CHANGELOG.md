# Changelog

All notable changes to this plugin are documented in this file.

## 0.7.0

- Made Claude Code the primary runtime and orchestrator. The plugin now ships a `hooks` entry point (`claude/hooks.json`) alongside its agents and MCP servers.
- Retired the Codex-host installer (`install`) and the self-hosted CD runner (`.github/runner`, `.github/workflows/plugin-marketplace-cd.yml`). Claude Code installs plugins natively, and the runner was pinned to an operator path that no longer exists.
- Removed the committed `dist/` release bundle; it was a Codex-marketplace artifact built by the retired CD.
- Hardened the substrate: `plan_replace` reorders tasks and reuses freed sequences, `project_status` reports an `audited` flag that on-disk file drift invalidates, `project_rebind` refuses to roll canonical state back from a stale clone, and the task, review, and correction backends reject a foreign `wave_id`.
- Versioned the project database `v1` -> `v2` with an idempotent in-place migration on writable open; `schema_version` is excluded from the logical digest so a migrating open cannot fail a caller's compare-and-swap.
- Stopped counting plugin runtime state (`.bears/`, `waves/`) against the repository budget so the workflow can be run against this repository itself.
- Added Claude Code as a second supported runtime alongside Codex: `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `claude/mcp.json` with `${CLAUDE_PLUGIN_ROOT}` server paths, and three Markdown L3 agents (`claude/agents/`).
- Added the `BEARS_APP_WORKFLOW_STATE_DIR` environment variable as the primary registry location override; the `$CODEX_HOME/state/...` path remains the default so both runtimes share one registry.
- Retired the delegated lane hierarchy. The `repo-orchestrator` and `workflow-orchestrator` profiles are gone; one orchestrator owns one repository, and a second repository is a separate session with its own wave. Three bounded roles remain: `app-worker`, `app-reviewer`, `app-analyst`.
- Generated roles from a single typed source: `roles/roles.json` plus `scripts/render_roles.py` render both `claude/agents/*.md` and `agents/*.toml`, with `--check` drift detection, replacing two hand-maintained representations that had drifted.
- Added enforcement hooks (`claude/hooks.json`): a PreToolUse guard denying maintainer mutations without a well-formed compare-and-swap triple, and Stop/SubagentStop guards refusing to end a turn on an inconsistent wave. Both fail open.
- Added the `/app-wave` command for starting and resuming a wave from live database state, and `claude/workflows/app-wave.js`, which encodes the seven phases as deterministic control flow with a dependency-ordered dev fan-out.
- Added `scripts/codex_exec_bridge.py`, a bounded executor bridge over `codex exec`: network off, sandbox overrides denylisted, and changed-file evidence taken from content digests at the git root.
- Demoted the phase skills from prose-as-algorithm to phase guidance; sequencing, gates, and retries now belong to the orchestrator.
- Added `docs/architecture.md` describing the layers, invariants, and the non-obvious sharp edges.

## 0.6.0

- Replaced JSON functional-map and workflow-state files with a registered per-project SQLite database.
- Added split `app-workflow` read-only and `app-workflow-maintainer` mutation MCP servers from one Python stdlib runtime.
- Added normalized graph, provenance, phase, process, plan, review, correction, analysis, snapshot, request, and audit storage.
- Added revision and logical-digest compare-and-swap writes, idempotent request IDs, bounded revision-bound cursors, and transactional batch changes.
- Added exact-file validation, atomic audit attestation, audit staleness after mutation, and a shared read-only CLI validator.
- Added guarded v5/state-v1 migration with source digest and parity checks plus non-lossy v4 evidence handling.
- Replaced JSON-rendered roles with five authoritative TOML profiles and explicit per-profile MCP access.
- Preserved seven Markdown-producing phases, existing main-branch CD topology, and deployment recovery compatibility.

## 0.5.0

- Resolved bundled graph MCP script paths from the plugin root so new and resumed Codex sessions can initialize both graph servers.
- Stopped plugin promotion and repair from injecting or refreshing instructions in `$CODEX_HOME/AGENTS.md`.
- Added a one-release, receipt-bound migration that removes only the exact legacy managed block and preserves all unmanaged bytes.
- Introduced graphless deployment receipt v5 while retaining read-only compatibility with v1-v4 receipts and interrupted legacy transactions.
- Gated CD on migration recovery tests and an explicit root-promoter bootstrap, then retained the v5-capable gateway across post-receipt process or commit interruption.

## 0.4.3

- Reframed the plugin as a workflow for deterministic documentation routing, graph planning, repository orchestration, and semantic correspondence analysis.
- Assigned every DIRECT stage to the DIRECT primary and every DELEGATED stage to one persistent `repo-orchestrator` repo-L2 with a stable owner session.
- Limited `workflow-orchestrator` L1 to native repository-lane coordination without stage, route, journal, or L3 authority.
- Restricted L3 use to assignment-bounded dispatch through $subagents.
- Defined app-analyze as agent-authored logical comparison of documentation, graph edges, ledger provenance, task results, immutable reviews, remediation tasks, and process records.
- Defined audited as exact-snapshot semantic and process correspondence against the constitution and specification.
- Added app-workflow-definition.v3, app-stage-handoff.v4, app-functional-map.v4, app-task-ledger.v3, app-process-event.v3, v4 indexes, and app-semantic-analysis-result.v1.
- Replaced legacy evaluation surfaces and proof metadata with native semantic-analysis and process records.
- Added exact task-result commit provenance, final-clean-review causality, canonical analysis input-set digests, and workflow-owned route reduction.
- Added completed-result delegation provenance, task-spec digests, exact review ranges, linked-run lineage, closed edge semantics, and atomic immutable build publication.
- Added the workflow-refactor-v5 wave, its source map, and a compact read-only effectiveness methodology with a sealed scoring key.
- Retained bounded graph queries, immutable build receipts, opaque snapshot-bound cursors, and compare-and-swap publication.

## 0.4.2

- Allowed every authoritative main promotion to rebuild and atomically activate the exact-revision root-owned deployment gateway before plugin promotion.
- Kept fetched gateway code outside the root execution path, ran it as ai1, and restored the prior gateway after interrupted activation.

## 0.4.1

- Rendered role-local MCP policy under the installed plugin namespace.
- Accepted standard MCP request metadata on tools/list while continuing to reject unsupported pagination cursors.

## 0.4.0

- Added seven-dimension functional maps and native exact-repository lifecycle records.
- Split the graph engine into compiler, store, query, process, and MCP modules.
- Added immutable build receipts with a separate current pointer and drift-aware caches.
- Replaced manual Sentry envelopes with the hash-locked official Python SDK and sanitized traceback capture.

## 0.3.5

- Kept the runner installer's one-time receipt migration compatible with current deployment receipts.

## 0.3.4

- Preserved the normalized activation failure cause after successful deployment rollback.

## 0.3.3

- Restored Codex-compatible Boolean web-search controls in generated role files.

## 0.3.2

- Made strict JSON role definitions and the capability catalog authoritative.
- Added exact per-role native tool, plugin skill, MCP, sandbox, web, app, and network boundaries.
- Hardened graph file access, artifact trace chains, run binding, MCP lifecycle handling, wire budgets, and deployment recovery.
- Made dynamic role discovery shared by the installer and production materializer.

## 0.3.0

- Introduced audited as the successful semantic workflow terminal.
- Added structured-source compilation, immutable process records, build receipts, compare-and-swap publication, and opaque snapshot-bound cursors.
- Split read-only graph access from the opted-in maintainer surface.
- Added transactional deployment ownership of one marked graph-behavior block in $CODEX_HOME/AGENTS.md.
