---
name: bears-goal-prompt
description: "Create, refine, review, or troubleshoot a Codex /goal prompt for Bears work; turns fuzzy intent into a compact, bounded, verifiable objective packet without starting the goal unless explicitly requested."
---

# Bears Goal Prompt

Generate or review copy-pasteable `/goal` prompts for long-running Bears work. `/goal` means a durable objective attached to a Codex thread. It is an execution-control contract, not memory and not source truth.

Do not call `create_goal`, `get_goal`, or `update_goal` unless the operator explicitly asks to start, inspect, or close a goal.

## Length contract

- Target: 500 characters or less.
- Normal edge: 501-2000 characters only with a named reason.
- Extended max: 2001-4000 characters only for explicit operator demand or a short prompt that points to an approved file.
- Forbidden: over 4000 characters.
- If detail does not fit, move detail to an authoritative file and keep the `/goal` compact.

## Required compact shape

Emit this shape by default:

```text
/goal <single objective>. Truth: <files/docs/commands>. Done: <binary end state>. Validate: <commands/evidence>. Forbidden: <paths/actions/data>.
```

Add `Workers:`, `Blockers:`, `Ask:`, `Audit:`, or `Budget:` only when needed. Budget appears only when the operator supplied one.

## Fit gate

Emit `/goal` only when all are true:

1. The task is bigger than one normal turn and smaller than a backlog.
2. There is one objective and one stopping condition.
3. The truth layer names authoritative files, docs, issues, commands, or runtime checks.
4. Validation is executable or artifact-backed.

If any item is missing, recommend `/plan` or ask one concise clarification question.

## Workflow

1. Identify target path, owner, and whether role routing is needed.
2. For Bears platform or plugin scope, run:
   - `python3 the @Bears plugin checkout/scripts/subagents_roles.py route <target>`
3. Draft the shortest prompt that preserves objective, truth, done, validation, and forbidden scope.
4. Save the prompt to a temp file and cite local-commit-owned validation:
   - Automatic evidence owns `python3 the @Bears plugin checkout/skills/bears-goal-prompt/scripts/validate_goal_prompt.py --prompt-file <file> --json`; manual execution requires operator approval.
5. If the prompt exceeds 500 characters, rerun with `--reason <why>`.
6. If the prompt needs 2001-4000 characters, also add `--allow-extended`.
7. Do not return a prompt that fails validation.

## Bears hard rules

- Add no-secrets, no-raw-logs, no-production-data, and no-production-mutation constraints.
- Missing specialist coverage is `ROLE_COVERAGE_BLOCKER`.
- Preserve `auth_core -> bears_gateway -> cd_deploy_stage` unless the operator narrowed scope.
- `workspace-map` is operator-disabled.

## Output

Return only:

1. `Goal fit:` `fit`, `fit-after-/plan`, or `not-fit`, plus one reason.
2. The final `/goal` prompt in one fenced `text` block.
3. `Checks:` character count, validator command result, unresolved blockers.

## Reject or rewrite

Reject or rewrite prompts that are vague, backlog-shaped, missing truth, missing validation, missing forbidden scope, secret-bearing, over 4000 characters, or asking for silent product/architecture approvals during the run.

## References

- `references/goal-prompt-best-practices.md`
- Validator: `scripts/validate_goal_prompt.py`
