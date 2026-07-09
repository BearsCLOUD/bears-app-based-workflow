---
name: app-analyze
description: Analyze Bears app workflow artifacts against implemented code state. Use when Codex must compare wave docs, functional graph, task ledger, and current implementation, then return pass, needs-plan, needs-spec, or blocked status.
---

# App Analyze

## Purpose

Compare the documented wave, graph, ledger, and current implementation state.

## Output

Write `waves/<wave-id>/analysis.md` with one status:

- `pass`: docs, graph, ledger, and code state agree.
- `needs-plan`: functionality is specified but missing, partial, drifted, or not in ledger.
- `needs-spec`: decisions, flows, data, errors, or acceptance criteria are missing.
- `blocked`: progress requires access, credentials, unavailable source, or an explicit stop signal.

## Analysis sections

- Wave and target.
- Inputs reviewed.
- Requirement coverage.
- Functional graph coverage.
- Ledger coverage.
- Implemented-state comparison.
- Missing or drifted functionality.
- Parallel lane opportunities with disjoint repo, path, and target sets.
- Next skill and exact handoff.

## Rules

- Do not fix implementation during analysis.
- Use role-matched critic subagents for independent requirement, graph, ledger, or implementation slices.
- Send missing functionality to `app-plan`.
- Send missing requirement detail to `app-specify`.
- Send ready ledger work to `app-dev`.
- Use `blocked` only for access, credentials, unavailable source, or explicit stop signal.
- Validation, test, audit, route, cache, cachebuster, quick-validate, and plugin-validate scripts belong to pre-commit autoCI; agents do not run them manually.
