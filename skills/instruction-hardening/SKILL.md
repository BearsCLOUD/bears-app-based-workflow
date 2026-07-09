---
name: instruction-hardening
description: Compress and harden Codex instructions, skills, prompts, and workflow prose. Use when Codex must remove duplication, merge overlapping rules, delete local-only noise, and preserve enforceable behavior in compact wording.
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
6. Return the compressed text plus a short removed-content summary.

## Keep

- Path ownership.
- Trigger conditions.
- Required artifacts.
- Forbidden actions.
- Handoff and escalation rules.
- Secret and access boundaries.

## Remove

- Setup narration.
- Repeated definitions.
- Generic best practices.
- Test, validation, or audit prose unless it is the explicit purpose of the artifact.
- Local machine commands unless the artifact owns that command.
