---
name: app-research
description: Create, update, synchronize, and refine Bears app research waves. Use when Codex must turn app intent, sources, existing docs, or unknowns into wave research packets before specification or planning.
---

# App Research

## Delegation first

For work already classified `DELEGATED`, act as the solo L2 analogue: decompose the stage payload below, then follow `$subagents` for each concrete L3 assignment before any data access. `DIRECT` work never enters `$subagents`.

## Stage payload

- Every stage-generated input uses canonical `app-stage-handoff.v3` from `contracts/app-stage-handoff.v3.schema.json` and carries a current `$app-context-index` result.
- `constitution-ready` from `app-constitution` additionally carries `app_repo_or_path`, `constitution_ref`, `constraint_refs`, `research_unknowns`, and `wave_creation_basis`.
- `needs-research` from `app-specify` additionally carries `source_handoff_ref`, `question_refs`, `source_refs`, and `research_unknowns`; its common `scope_delta`, artifact, decision, requirement, gap, and evidence fields carry the current affected context.
- User intent, feature area, constraint refs, and open-decision refs.
- Known wave ids or the exact wave-creation basis.
- Known source refs, product notes, tickets, and user answers.
- Exact unknowns the research must close.

## Stage output ownership

In `DIRECT`, the primary creates the stage artifacts and canonical handoff. In `DELEGATED`, the assigned L3 creates them and returns `wave-research.packet`.

The stage writes:

- `waves/index.md` with active waves and status;
- `waves/<wave-id>/research.md` for each touched wave.

Each research file contains `Wave ID`, `Scope`, `Known behavior`, `Unknowns`, `Sources`, `Decisions`, `Follow-up questions`, `Sync notes`, and `Next skill`. Refresh `$app-context-index`, then return canonical `app-stage-handoff.v3` status `research-ready` with current digest/index fields plus `constitution_ref`, `research_refs`, `question_refs`, and `source_refs`; target `app-specify`.

## Stage rules

- Create a wave only for a distinct user value, dependency set, or implementation lane.
- Update an existing wave when evidence changes its scope, decisions, unknowns, or sources.
- Propagate a shared decision to every affected wave note.
- Keep unanswered product choices under `Follow-up questions`.
- Route every researched wave to `app-specify`; that stage either closes or asks the remaining product decisions.
- Record graph or task observations as specification hints. Do not bypass `app-specify` or send research directly to `app-plan`.
