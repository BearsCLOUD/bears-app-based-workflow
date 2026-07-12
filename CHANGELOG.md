# Changelog

All notable changes to this plugin are documented in this file.

The format follows Keep a Changelog conventions.

## [Unreleased]

### Changed

- Made delegated entry fail closed on mixed DIRECT context and require a fresh task before overlapping target dispatch.
- Required explicit typed agent dispatch, exact authority-bound packet identity, and stable worker/critic lifecycle reuse.
- Added dynamically declared profile level and role-kind identity without reintroducing a fixed catalog.
- Replaced fixed role counts with exact-commit dynamic discovery shared by the installer and production materializer.
- Consolidated plugin acceptance behind one requirements-driven reusable autoCI evaluator and one workflow invocation.
- Moved active delegation packet definitions into one portable plugin-local contract.
- Reduced the active role catalog and placed deterministic role routing solely with the caller and `subagents` procedure.
- Made write assignments own their task-scoped local commits.
- Added authenticated, crash-safe installer migration and configuration exchange.
- Made plugin promotion durable and fail-closed through a promotion-intent journal and convergence recovery.
