---
name: instruction-hardening
description: Apply a repeatable method for converting approved instruction meaning into compact, scoped policy rules while preserving authority, distinct actions, and unresolved conflicts.
---

# Instruction Hardening

## Boundary

This skill supplies a repeatable editing method. The invoking role owns the final wording, policy decisions, permissions, acceptance criteria, and result format. This skill does not choose authority, invent meaning, or resolve a conflict that the input leaves unresolved.

## Security-critical terms

Define a term only when ambiguity changes permissions or safety:

- `execute`: start code or a command directly or through a script, task runner, wrapper, container, plugin, MCP tool, remote command, module entrypoint, or side-effecting import;
- `external write`: create, edit, or delete state outside the declared local workspace;
- `destructive action`: remove or overwrite state when the declared recovery path is absent or materially incomplete;
- `material scope expansion`: add targets, permissions, systems, or deliverables beyond the approved request.

Do not impose a closed action dictionary. Preserve distinct meanings such as `use`, `inspect`, and `execute`. Normalize two terms only when they select the same behavior in the declared scope.

## Inputs

- Approved meaning and audience.
- Authority refs in priority order.
- Exact target and object scope.
- Required triggers, inputs, actions, permissions, constraints, acceptance criteria, outputs, and escalation targets.
- Optional explicit conflict-resolution rules with their authority and scope.

## Method

1. **Policy** — Convert prose into rules. Retain only triggers, inputs, actions, constraints, permissions, acceptance criteria, outputs, and conflict outcomes.
2. **Dict** — Normalize only true synonyms in the declared scope. Preserve behaviorally distinct verbs.
3. **Scope** — Bind each rule to exact repositories, paths, globs, shell access, machine automation, network access, Git actions, or external systems.
4. **Objects** — Replace informal objects with exact paths, globs, object classes, scripts, task runners, automation targets, tools, plugins, or MCP servers. Represent a recursive file class as `**/*.ext`.
5. **Actions** — State the real operation without mapping it to an unrelated canonical verb.
6. **Mode** — Label each rule `Allowed`, `Forbidden`, `Required`, `Ask`, or `Escalate` when the role's result format uses those modes.
7. **Conflict** — Apply authority order. For contradictory rules with equal authority and overlapping scope, retain `INSTRUCTION_CONFLICT` unless an explicit applicable resolution rule was supplied.
8. **Bypass scan** — Identify direct and transitive paths to each security-critical forbidden action.
9. **Close bypasses** — Cover wrappers, module entrypoints, side-effecting imports, scripts, task runners, containers, remote commands, plugins, MCP tools, and nested commands.
10. **Dedup** — Combine rules only when action, object, scope, condition, authority, and outcome match.
11. **Compress** — Remove narration, repeated qualifiers, and words that change no decision.
12. **Red-team** — Evaluate direct, wrapper, one-off, approval-bypass, and verification-bypass cases.
13. **Drift** — Remove `carefully`, `appropriate`, `if needed`, `handle`, `work with`, and any term without a fixed effect.
14. **Token** — Reduce tokens only after authority, permissions, bypass closure, and cases are stable.
15. **Regression** — Repeat Policy, Dict, Bypass, Compress, Red-team, and Drift until every case retains its decision.

## Handoff

Give the invoking role the normalized draft, closed-bypass notes, removed duplicates, preserved authority facts, and unresolved conflicts. The role applies its own acceptance criteria and emits its own result contract.
