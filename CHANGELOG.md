# Changelog

## 0.4.0

- Added the seven-dimension `app-functional-map.v3` and native `app-process-event.v2` exact repo-wave lifecycle while retaining v2/v1 read compatibility.
- Split the graph engine into compiler, store, query, audit, and process modules; fixed ledger dependency direction, superseded planning, whole-branch trace audit, and bidirectional impact traversal.
- Added immutable build receipts with a separate current pointer plus inode/metadata hash and build/argument query caches that fail closed on drift.
- Replaced manual Sentry envelopes with the hash-locked official Python SDK, sanitized real traceback capture, and root-owned gateway installation.
- Kept plugin CI absent and `automation_status=not_run`; live Sentry stack evidence remains `needs-evidence` pending an operator-bootstrapped real autoCD failure.

## 0.3.5

- Kept the runner installer's one-time receipt migration compatible with current v3/v4 deployment receipts.

## 0.3.4

- Preserved the normalized activation failure cause after successful CD rollback.

## 0.3.3

- Restored Codex-compatible boolean web-search controls in generated agent role files.

## 0.3.2

- Made strict JSON role definitions and the capability catalog authoritative; TOML is now a deterministic safe-subset projection.
- Added exact per-role native tool, plugin skill, MCP server/tool, sandbox, web, app, and network boundaries.
- Replaced `runtime-evidence-reader` with the source-specific `graph-evidence-reader` without an alias.
- Hardened graph file access, artifact trace chains, run-bound audits, MCP schemas/lifecycle/wire budgets, and CD recovery.
- Advanced the deploy receipt and promotion journal to v4/v5 while retaining v1-v3 receipt validation.
- Kept the exact `0.3.0` JSON-less role bundle recoverable without permitting new releases to bypass authoritative role definitions.

## 0.3.0

- Replaced the unreachable terminal status with `audited`, explicitly separate from product acceptance.
- Added deterministic structured-source compilation, immutable process events, build receipts, CAS publication, and opaque snapshot-bound cursors.
- Added read-only process and semantic/planning/convergence trace audits plus lower-level compiler/audit skills.
- Split read-only `app-graph` from the opted-in two-tool `app-graph-maintainer`.
- Added lifecycle-correct MCP 2025-11-25/2025-06-18 handling and bounded iterative graph operations.
- Added transactional CD ownership of one marked graph-behavior block in `$CODEX_HOME/AGENTS.md`.
- Continued `RUN-GRAPH-WORKFLOW-V2`, imported its seven legacy events, remediated findings, and cut over to v3/v2 active artifacts.

All notable changes to this plugin are documented in this file.

The format follows Keep a Changelog conventions.

## [Unreleased]

### Changed

- Refactored the 4,049-line deployment gateway into a stable launcher and cohesive root-owned modules without changing the external SHA-only CD command.
- Disconnected autoCI and removed its requirements binding; acceptance remains `not_run` unless exact external evidence is supplied.
- Restored CD independently of autoCI: every `main` push now updates the installed plugin through the fixed Git marketplace and durable deployment gateway without claiming acceptance.
- Adopted user-facing plain SemVer: patch for ordinary pushes, minor for substantial refactors, and major only by explicit user request; CD enforces monotonic versions after one-way legacy migration.
- Preserved exact historical receipt-fingerprint verification during the one-way SemVer migration.
- Added machine-readable workflow, handoff, functional-map, traceability-index, process-index, and context-index contracts.
- Added `app-context-index` as the source-digest entry gate and sole writer of rebuildable traceability and process indexes.
- Reframed `app-functional-graph` as the semantic-map owner while keeping documents, code, tests, ledger records, and evidence authoritative.
- Added the bundled read-only `app-graph` MCP for bounded dependency, impact, diagnostic, ordering, trace, and workflow queries.
- Made MCP reads fail closed on source-content drift, applied edge-level transitivity to impact propagation, expanded cycle detection to every forbidden edge type, and exposed planning blockers.
- Routed app stages through one workflow definition and canonical `app-stage-handoff.v2` instead of duplicated prose route tables.
- Added `app-solo-route` for sequential DIRECT stage resumption through the pre-development workflow, with canonical route validation and loop prevention.
- Made DIRECT primary and DELEGATED L3 stage-output ownership explicit across research, specification, functional graph, planning, and analysis.
- Made delegated entry fail closed on mixed DIRECT context and require a fresh task before overlapping target dispatch.
- Required explicit typed agent dispatch, exact authority-bound packet identity, and stable worker/critic lifecycle reuse.
- Added dynamically declared profile level and role-kind identity without reintroducing a fixed catalog.
- Replaced fixed role counts with exact-commit dynamic discovery shared by the installer and production materializer.
- Moved active delegation packet definitions into one portable plugin-local contract.
- Reduced the active role catalog and placed deterministic role routing solely with the caller and `subagents` procedure.
- Made write assignments own their task-scoped local commits.
- Added authenticated, crash-safe installer migration and configuration exchange.
- Made plugin promotion durable and fail-closed through a promotion-intent journal and convergence recovery.
