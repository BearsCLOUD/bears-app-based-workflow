---
name: instruction-hardening
description: Compress approved Codex instructions through the dedicated Sol Ultra editor without changing authority. Use for skills, prompts, plans, packets, role instructions, and workflow prose that must become short and exact.
---

# Instruction Hardening

## Delegation first

The caller is an app-dev L2 or a solo parent acting as L2. It decomposes the edit and follows `$subagents` before any data access. For each concrete assignment, it sends the persistent selector `work_kind: instruction-edit` and `required_role: bears-instruction-editor`. The selector must return that exact role or a fail-closed outcome. Parent, L1, and L2 do not read or edit the instruction surface.

## Role-change gate

For any new, renamed, merged, or behaviorally changed role:

1. Send a separate role request with `required_role: bears-role-editor-auditor` first.
2. Require a decision on role necessity, trigger, unique boundary, exclusions, overlap, model, reasoning effort, and sandbox.
3. Stop if the role is rejected or its semantics conflict.
4. Pass only the approved role semantics through a new request with `required_role: bears-instruction-editor` for final wording.

The role editor/auditor does not write general instruction text. The instruction editor does not change role boundaries, model, sandbox, or authority.

## Editor input

- Approved meaning and required behavior.
- Owning `AGENTS.md`, contract, skill, prompt, plan, packet, or role target refs.
- Exact block boundary.
- Required triggers, actions, outputs, prohibitions, and escalation points.
- Maximum 120 words per instruction block.

## Editor result

- Final compact text.
- Removed-content summary.
- Authority or drift note.
- Exact changed files when write scope was granted.

Every word must carry operational meaning. Remove narration, duplication, vague advice, generic definitions, and environment noise. Preserve concrete triggers, authority, scope, required output, forbidden action, and escalation.

If safe compression would change meaning, scope, or authority, return `INSTRUCTION_CONFLICT` with the conflicting rules. Do not provide a weakened rewrite.
