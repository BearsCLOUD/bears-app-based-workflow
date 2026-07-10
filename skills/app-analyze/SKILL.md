---
name: app-analyze
description: Analyze Bears app workflow artifacts against implemented code state. Use when Codex must compare wave docs, functional graph, task ledger, and current implementation, then return pass, needs-plan, needs-spec, or blocked status.
---

# App Analyze

## Delegation first

As the solo L2 analogue, decompose the stage payload below, then follow `$subagents` for each concrete L3 assignment before any data access.

## Stage payload

- Target app and wave id.
- Constitution, research, specification, graph, ledger, and plan refs.
- Implemented-state target paths.
- Existing autoCI evidence refs.

## L3 output

The selected L3 writes `waves/<wave-id>/analysis.md` with inputs reviewed, requirement coverage, graph coverage, ledger coverage, implemented-state comparison, missing or drifted behavior, and an exact handoff.

It sets one status:

- `pass`: documentation, graph, ledger, and implementation agree, and each required current autoCI check is `PASS`.
- `needs-plan`: specified behavior is missing, partial, drifted, or absent from the ledger.
- `needs-spec`: flows, actors, data, errors, decisions, or acceptance criteria are incomplete.
- `blocked`: access, credentials, unavailable source, or an explicit operator decision prevents progress.

## Stage rules

- Do not fix implementation during analysis.
- Pending or missing required autoCI evidence is not `pass`.
- Send `needs-plan` to `app-plan`, `needs-spec` to `app-specify`, and ready ledger work to `app-dev`.
- Do not use `blocked` for ordinary risk or incomplete work.
