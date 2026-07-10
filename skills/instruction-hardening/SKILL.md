---
name: instruction-hardening
description: Compress and harden Codex instructions, skills, prompts, wave plans, dispatch packets, and workflow prose without changing instruction authority. Use inside Bears App-Based Workflow when Codex must remove duplication, make rules stricter, and return compact text plus authority or drift notes.
---

# Instruction Hardening

## Goal

Turn an instruction surface into a smaller, stricter version with the same required behavior.

## Process

1. Split the source into individual rules.
2. Delete restatements, commentary, and environment-local noise.
3. Merge rules that share the same trigger, owner, and action.
4. Keep concrete triggers, required outputs, forbidden actions, and escalation points.
5. Replace vague wording with observable actions.
6. Return compressed text, removed-content summary, and authority or drift note.

## Output

- Compressed text.
- Removed-content summary.
- Authority or drift note.

## Keep

- Nearest `AGENTS.md` ownership and linked contracts.
- Path ownership.
- Trigger conditions.
- Required artifacts.
- Forbidden actions.
- Handoff and escalation rules.
- Secret and access boundaries.

## Rules

- Never change instruction authority.
- Never make plugin output override `AGENTS.md` or contracts.
- Follow the nearest `AGENTS.md` and referenced contracts for the target path.
- Do not create implementation tasks or product decisions.
- Mark conflicts between source text and owning instructions in the authority or drift note.

## Remove

- Setup narration.
- Repeated definitions.
- Generic best practices.
- Test, validation, or audit prose unless it is the explicit purpose of the artifact.
- Local machine commands unless the artifact owns that command.
