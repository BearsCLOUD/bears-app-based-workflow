---
name: app-research
description: Create, update, synchronize, and refine Bears app research waves. Use when Codex must turn app intent, constitution gaps, sources, existing docs, or unknowns into wave research packets before specification or planning.
---

# App Research

## Purpose

Create or update the wave registry and one `waves/<wave-id>/research.md` file per research slice.

## Inputs

- User intent or feature area.
- App target path or repo.
- `docs/app-constitution.md` functional summary, constraints, and functional gaps.
- Nearest parent and app-local `AGENTS.md` rules.
- Existing wave registry and wave docs.
- Source docs, code observations, tickets, product notes, and user answers.

## Outputs

- `wave-research.packet` in the response or handoff.
- `waves/index.md` with all active waves and statuses.
- `waves/<wave-id>/research.md` for each touched wave.
- Candidate disjoint source slices for later role-matched subagents.
- `constitution_update_needed` note when research finds an important functional gap, drift, or decision that belongs in `docs/app-constitution.md`.

## Wave research file

Use these headings:

1. `Wave ID`
2. `Scope`
3. `Constitution context`
4. `Known behavior`
5. `Unknowns`
6. `Sources`
7. `Decisions`
8. `Follow-up questions`
9. `Parallel source slices`
10. `Sync notes`
11. `Next skill`

## Research steps

1. Read `docs/app-constitution.md` before creating or updating waves.
2. Read nearest parent and app-local `AGENTS.md` rules for source, path, and evidence boundaries.
3. Check `Functional summary` and `Functional gaps` against the requested wave scope.
4. Assign independent source, code, ticket, or product-note slices to role-matched subagents.
5. Record whether each touched wave covers, narrows, or discovers constitution gaps.
6. Route new important functional gaps or drift back to `app-constitution` instead of hiding them in wave prose.

## Wave lifecycle rules

- Create a new wave only when the scope has a distinct user value, dependency set, or implementation lane.
- Update existing waves when new information changes scope, unknowns, decisions, source links, or constitution gap coverage.
- Use role-matched research subagents for independent source, code, ticket, or product-note slices.
- Keep subagent source slices disjoint by repo, path, source set, or question set.
- Keep waves synchronized: if one wave changes a shared decision, update every affected wave note.
- Mark unanswered product choices as `Follow-up questions`; do not hide them in prose.
- If constitution and `AGENTS.md` disagree, treat `AGENTS.md` as authority and send a drift note to `app-constitution`.
- Route decision gaps to `app-specify`.
- Route graph or task gaps to `app-plan`.
- Validation, test, audit, route, cache, cachebuster, quick-validate, and plugin-validate scripts belong to pre-commit autoCI; agents do not run them manually.
