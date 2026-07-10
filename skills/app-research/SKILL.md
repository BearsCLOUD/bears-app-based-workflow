---
name: app-research
description: Create and update Bears app research waves that verify constitution records before planning. Use when Codex must check app intent, gaps, inferences, cited user messages, source documents, code observations, or unknowns and return wave-research.packet.v1.
---

# App Research

## Purpose

Create or update `waves/index.md` and one `waves/<wave-id>/research.md` file per research slice. Research explains constitution truth; it does not create plan microtasks or graph nodes.

## Inputs

- User intent or feature area.
- App target path or repo.
- `docs/app-constitution.md` records.
- `docs/app-user-evidence.md` only when a constitution record cites it.
- Existing wave registry and wave docs.
- Source docs, code observations, tickets, product notes, and user answers.
- Execution constraints supplied by the live session.

## Outputs

- `wave-research.packet.v1` using `docs/handoff-packet-contracts.md`.
- `waves/index.md` with all active waves and statuses.
- `waves/<wave-id>/research.md` for each touched wave.
- `constitution_update_needed` note when research finds functional truth, drift, or a decision that belongs in `docs/app-constitution.md`.

## Research packet

Return `wave-research.packet.v1` with:

- `schema: wave-research.packet.v1`
- `wave_id`
- `scope`
- `constitution_refs`
- `source_refs`
- `decisions`
- `unknowns`
- `clarifications_needed`
- `plan_inputs`
- `next_skill`

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
2. Open each exact source cited by the records in scope, including linked `docs/app-user-evidence.md#user-msg-*` entries.
3. Map each wave to one or more constitution ids.
4. Record source-backed explanations for every mapped `cap-*` or `gap-*` id.
5. Treat each `inference-*` as an unverified research target: check its stated facts and verification route, then return the confirmed result to `app-constitution` under the matching non-inference record type.
6. Record decisions and unknowns separately.
7. Use `app-specify` only when actors, flows, data, errors, or acceptance details cannot be resolved from sources.
8. Route new functional truth or functional drift back to `app-constitution`.
9. Route only explained, decision-complete `cap-*` and `gap-*` scope to `app-plan`.

## Rules

- Create a new wave only when the scope has a distinct functional value or dependency set.
- Update existing waves when new information changes scope, sources, decisions, unknowns, or constitution mapping.
- Copy exact source links into `source_refs`; do not replace a user-evidence link with a paraphrase or session reference.
- Never place an `inference-*`, `constraint-*`, or `decision-*` id in `plan_inputs`.
- Keep an unverified inference in `unknowns`; it cannot pass to `app-plan` or `app-functional-graph`.
- Do not create plan microtasks here.
- Do not create graph nodes here.
- Do not route directly to `app-functional-graph` or `app-dev`.
- Do not create validation tooling to prove research.
- Do not ask agents to run validation, test, audit, route, cache, cachebuster, quick-validate, or plugin-validate scripts manually.
