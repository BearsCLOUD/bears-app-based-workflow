---
name: app-research
description: Create, update, synchronize, and refine Bears app research waves. Use when Codex must turn app intent, sources, existing docs, or unknowns into wave research packets before specification or planning.
---

# App Research

## Purpose

Create or update the wave registry and one `waves/<wave-id>/research.md` file per research slice.

## Inputs

- User intent or feature area.
- App target path or repo.
- Existing wave registry and wave docs.
- Source docs, code observations, tickets, product notes, and user answers.

## Outputs

- `wave-research.packet` in the response or handoff.
- `waves/index.md` with all active waves and statuses.
- `waves/<wave-id>/research.md` for each touched wave.
- Candidate disjoint source slices for later role-matched subagents.

## Wave research file

Use these headings:

1. `Wave ID`
2. `Scope`
3. `Known behavior`
4. `Unknowns`
5. `Sources`
6. `Decisions`
7. `Follow-up questions`
8. `Parallel source slices`
9. `Sync notes`
10. `Next skill`

## Wave lifecycle rules

- Create a new wave only when the scope has a distinct user value, dependency set, or implementation lane.
- Update existing waves when new information changes scope, unknowns, decisions, or source links.
- Use role-matched research subagents for independent source, code, ticket, or product-note slices.
- Keep subagent source slices disjoint by repo, path, source set, or question set.
- Keep waves synchronized: if one wave changes a shared decision, update every affected wave note.
- Mark unanswered product choices as `Follow-up questions`; do not hide them in prose.
- Route decision gaps to `app-specify`.
- Route graph or task gaps to `app-plan`.
- Validation, test, audit, route, cache, cachebuster, quick-validate, and plugin-validate scripts belong to pre-commit autoCI; agents do not run them manually.
