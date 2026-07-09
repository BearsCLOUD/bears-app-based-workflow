---
name: app-research
description: Create, update, synchronize, and refine Bears app research waves that explain constitution ids before planning. Use when Codex must turn app intent, constitution gaps, sources, existing docs, or unknowns into wave research files and wave-research.packet.v1 handoffs.
---

# App Research

## Purpose

Create or update `waves/index.md` and one `waves/<wave-id>/research.md` file per research slice. Research explains constitution truth; it does not create plan microtasks or graph nodes.

## Inputs

- User intent or feature area.
- App target path or repo.
- `docs/app-constitution.md` capabilities, constraints, gaps, decisions, and execution constraints.
- Existing wave registry and wave docs.
- Source docs, code observations, tickets, product notes, and user answers.

## Outputs

- `wave-research.packet.v1` using `docs/handoff-packet-contracts.md`.
- `waves/index.md` with all active waves and statuses.
- `waves/<wave-id>/research.md` for each touched wave.
- `constitution_update_needed` note when research finds functional truth, drift, or a decision that belongs in `docs/app-constitution.md`.

## Research file sections

1. `Wave ID`
2. `Scope`
3. `Constitution mapping`
4. `Known behavior`
5. `Sources`
6. `Decisions`
7. `Unknowns`
8. `Clarifications`
9. `Plan inputs`
10. `Drift notes`
11. `Next skill`

## Research steps

1. Read `docs/app-constitution.md` before creating or updating waves.
2. Map each wave to one or more constitution ids.
3. Record source-backed explanations for every mapped constitution id.
4. Record decisions and unknowns separately.
5. Use `app-specify` only when actors, flows, data, errors, or acceptance details cannot be resolved from sources.
6. Route new functional truth or functional drift back to `app-constitution`.
7. Route explained, decision-complete wave scope to `app-plan`.

## Rules

- Create a new wave only when the scope has a distinct functional value or dependency set.
- Update existing waves when new information changes scope, sources, decisions, unknowns, or constitution mapping.
- Do not create plan microtasks here.
- Do not create graph nodes here.
- Do not route directly to `app-functional-graph` or `app-dev`.
- Do not create validation tooling to prove research.
- Do not ask agents to run validation, test, audit, route, cache, cachebuster, quick-validate, or plugin-validate scripts manually.
