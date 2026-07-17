# Changelog

All notable changes to this plugin are documented in this file.

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
