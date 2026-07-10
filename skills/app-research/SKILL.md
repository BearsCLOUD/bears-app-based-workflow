---
name: app-research
description: Create, update, synchronize, and refine Bears app research waves. Use when Codex must turn app intent, sources, existing docs, or unknowns into wave research packets before specification or planning.
---

# App Research

## Delegation first

For work already classified `DELEGATED`, act as the solo L2 analogue: decompose the stage payload below, then follow `$subagents` for each concrete L3 assignment before any data access. `DIRECT` work never enters `$subagents`.

## Stage payload

- App id, app repo or path, and constitution ref.
- User intent, feature area, constraint refs, and open-decision refs.
- Known wave ids or the exact wave-creation basis.
- Known source refs, product notes, tickets, and user answers.
- Exact unknowns the research must close.

## L3 output

The selected L3 returns `wave-research.packet` and writes:

- `waves/index.md` with active waves and status;
- `waves/<wave-id>/research.md` for each touched wave.

Each research file contains `Wave ID`, `Scope`, `Known behavior`, `Unknowns`, `Sources`, `Decisions`, `Follow-up questions`, `Sync notes`, and `Next skill`. Return `app-stage-handoff.v1` with status `research-ready`, the constitution and research refs, wave id, decision and question refs, source refs, and `next_stage: app-specify`.

## Stage rules

- Create a wave only for a distinct user value, dependency set, or implementation lane.
- Update an existing wave when evidence changes its scope, decisions, unknowns, or sources.
- Propagate a shared decision to every affected wave note.
- Keep unanswered product choices under `Follow-up questions`.
- Route every researched wave to `app-specify`; that stage either closes or asks the remaining product decisions.
- Record graph or task observations as specification hints. Do not bypass `app-specify` or send research directly to `app-plan`.
