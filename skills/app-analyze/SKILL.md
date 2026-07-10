---
name: app-analyze
description: Analyze Bears app workflow artifacts against implemented code state. Use when Codex must compare wave docs, functional graph, task ledger, and current implementation, then return pass, ready, needs-plan, needs-spec, or blocked status.
---

# App Analyze

## Delegation first

For work already classified `DELEGATED`, act as the solo L2 analogue: decompose the stage payload below, then follow `$subagents` for each concrete L3 assignment before any data access. `DIRECT` work never enters `$subagents`.

## Stage payload

- `implemented`, `no-work`, or diagnostic handoff with target app id and wave id.
- Constitution, research, specification, graph, ledger, and plan refs.
- Exact graph revision and ledger task refs.
- Implemented-state target paths.
- Existing autoCI evidence refs.

## L3 output

The selected L3 writes `waves/<wave-id>/analysis.md` with inputs reviewed, requirement coverage, graph revision and coverage, ledger coverage, implemented-state comparison, `built|partial|missing|drifted` classification by requirement, and an exact handoff. The graph and ledger are read-only in this stage.

It sets one status:

- `pass`: documentation, graph, ledger, and implementation agree, and each required current autoCI check is `PASS`.
- `ready`: one or more existing canonical ledger tasks are `ready`, have current graph refs, and require execution.
- `needs-plan`: specified behavior is `partial`, `missing`, `drifted`, or absent from the ledger.
- `needs-spec`: flows, actors, data, errors, decisions, or acceptance criteria are incomplete.
- `blocked`: access, credentials, unavailable source, or an explicit operator decision prevents progress.

## Stage rules

- Do not fix implementation during analysis.
- Pending or missing required autoCI evidence is not `pass`.
- Return `app-stage-handoff.v1`. Send `ready` with complete canonical task records to `app-dev`; send `needs-plan` with per-requirement implementation state, graph revision, ledger coverage, gap refs, and evidence refs to `app-plan`; send `needs-spec` with exact decision and requirement refs to `app-specify`; close only on `pass`.
- If graph refs are missing or graph meaning drifted, report them inside `needs-plan`; `app-plan` returns the required `needs-graph` handoff without editing the graph.
- Do not use `blocked` for ordinary risk or incomplete work.
