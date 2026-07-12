# Changelog

All notable changes to this plugin are documented in this file.

The format follows Keep a Changelog conventions.

## [Unreleased]

### Changed

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
- Consolidated plugin acceptance behind one requirements-driven reusable autoCI evaluator and one workflow invocation.
- Removed the unavailable private reusable-workflow hop while retaining the same immutable autoCI evaluator and evidence contract in the caller workflow.
- Moved active delegation packet definitions into one portable plugin-local contract.
- Reduced the active role catalog and placed deterministic role routing solely with the caller and `subagents` procedure.
- Made write assignments own their task-scoped local commits.
- Added authenticated, crash-safe installer migration and configuration exchange.
- Made plugin promotion durable and fail-closed through a promotion-intent journal and convergence recovery.
