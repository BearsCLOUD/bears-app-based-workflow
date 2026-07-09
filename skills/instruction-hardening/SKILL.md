---
name: instruction-hardening
description: Compress and harden Codex instructions, skills, prompts, wave plans, dispatch packets, and workflow prose without changing functional truth or execution constraints. Use inside Bears App-Based Workflow when Codex must remove duplication, make rules stricter, and return hardening-output.v1 plus drift notes.
---

# Instruction Hardening

## Goal

Turn an instruction or packet surface into a smaller, stricter version with the same required behavior.

## Process

1. Split the source into individual rules.
2. Delete restatements, commentary, stale traces, and environment-local noise.
3. Merge rules that share the same trigger, owner, and action.
4. Keep concrete triggers, required outputs, forbidden actions, and escalation points.
5. Replace vague wording with observable actions.
6. Return `hardening-output.v1`.

## Output

- `schema: hardening-output.v1`
- `wave_id`
- `input_refs`
- `compressed_text`
- `removed_content_summary`
- `behavior_equivalence_statement`
- `drift_notes`
- `next_skill`

## Keep

- Constitution refs and functional truth.
- Research refs and plan task refs.
- Path ownership stated in the packet.
- Trigger conditions.
- Required artifacts.
- Forbidden actions.
- Handoff and escalation rules.
- Secret and access boundaries.
- Sequential handoff order.

## Rules

- Never change functional truth from `docs/app-constitution.md`.
- Never change research decisions, plan task scope, graph ids, or execution constraints.
- Do not create implementation tasks or product decisions.
- Do not run scripts.
- Do not tell agents to run validation, test, audit, route, cache, cachebuster, quick-validate, or plugin-validate scripts manually.
- Keep script execution evidence sourced only from generated automation artifacts that already exist.
- Mark conflicts between source text and functional truth in the drift note.

## Remove

- Setup narration.
- Repeated definitions.
- Generic best practices.
- Manual validation, test, audit, route, cache, cachebuster, quick-validate, or plugin-validate commands.
- Environment-specific commands unless the target packet explicitly owns that command.
