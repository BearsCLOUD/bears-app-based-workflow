---
name: instruction-hardening
description: Convert approved meaning into compact scoped policy while preserving authority and unresolved conflicts.
---

# Instruction Hardening

## Boundary

Use this skill only as an editing method.

Keep final wording, policy choices, permissions, completion conditions, and result ownership with the invoking role.

Never invent authority, approved meaning, or a conflict resolution that the input does not supply.

## Security Terms

Define a term only when its ambiguity changes a permission or safety decision.

- Define `execute` as starting code or a command through any direct or wrapped entrypoint.
- Define `external write` as creating, changing, or deleting state outside the declared local workspace.
- Define `destructive action` as removing or overwriting state without a declared recovery path.
- Define `material scope expansion` as adding targets, permissions, systems, or deliverables beyond the approved request.

Preserve behaviorally distinct verbs and normalize two terms only when they select the same action in the same scope.

## Input

Require approved meaning, audience, ordered authority refs, exact object scope, triggers, actions, permissions, constraints, completion conditions, outputs, and escalation targets.

Keep an unresolved equal-authority conflict unresolved unless the input supplies an applicable conflict rule.

## Method

1. Convert prose into rules that can change one agent decision.
2. Bind every rule to an exact trigger, action, object, scope, condition, authority, and outcome.
3. Normalize only true synonyms within that bound scope.
4. Replace informal objects with exact paths, object classes, entrypoints, tools, plugins, or external systems.
5. State the real operation without mapping it to an unrelated canonical verb.
6. Label a rule `Allowed`, `Forbidden`, `Required`, `Ask`, or `Escalate` when the result format uses modes.
7. Apply authority order and preserve `INSTRUCTION_CONFLICT` for an unresolved equal-authority conflict.
8. Identify direct and transitive paths to every forbidden security-critical action.
9. Close wrapper, module, import, task-runner, container, remote-command, plugin, tool, and nested-command bypasses.
10. Combine rules only when trigger, action, object, scope, condition, authority, and outcome match.
11. Remove narration, repeated qualifiers, and words that change no decision.
12. Evaluate direct, wrapper, one-off, approval-bypass, and enforcement-bypass cases.
13. Remove undefined qualifiers such as `carefully`, `appropriate`, `if needed`, `handle`, and `work with`.
14. Reduce tokens only after authority, permissions, bypass closure, and boundary cases are stable.
15. Repeat normalization, bypass closure, compression, and boundary review until every case preserves its decision.

## Handoff

Return the normalized draft, closed-bypass notes, removed duplicates, preserved authority facts, and unresolved conflicts to the invoking role.
