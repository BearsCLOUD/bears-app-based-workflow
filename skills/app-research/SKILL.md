---
name: app-research
description: Create, update, synchronize, and refine Bears app research waves. Use when Codex must turn app intent, sources, existing docs, or unknowns into wave research packets before specification or planning.
---

# App Research

## Delegation first

As the solo L2 analogue, decompose the stage payload below, then follow `$subagents` for each concrete L3 assignment before any data access.

## Stage payload

- User intent or feature area.
- App repo or path.
- Known wave refs.
- Known source refs, product notes, tickets, and user answers.
- Exact unknowns the research must close.

## L3 output

The selected L3 returns `wave-research.packet` and writes:

- `waves/index.md` with active waves and status;
- `waves/<wave-id>/research.md` for each touched wave.

Each research file contains `Wave ID`, `Scope`, `Known behavior`, `Unknowns`, `Sources`, `Decisions`, `Follow-up questions`, `Sync notes`, and `Next skill`.

## Stage rules

- Create a wave only for a distinct user value, dependency set, or implementation lane.
- Update an existing wave when evidence changes its scope, decisions, unknowns, or sources.
- Propagate a shared decision to every affected wave note.
- Keep unanswered product choices under `Follow-up questions`.
- Route decision gaps to `app-specify`; route graph or task gaps to `app-plan`.
