# Roadmap Control

## Purpose

`assets/catalog/roadmap-control.v1.json` is the deterministic roadmap control surface for the Bears plugin. It controls `/goal`-started roadmap runs, Spec Kit slice concurrency, subagent spawn gates, audit freshness, and session reuse.

Technical terms:

- **Roadmap slice**: one bounded part of a goal with one lane, role, scope, and validation target.
- **Spec snapshot**: fixed digest set for the current `spec.md`, `plan.md`, and `tasks.md` state at task start.
- **Scope lock**: record that blocks two active workers from writing the same files.
- **Reuse key**: deterministic key that allows a worker session to continue only when all binding fields still match.

## Hard rules

1. Roadmap runs start only through `/goal`.
2. One roadmap may control several Spec Kit specs at the same time only with current spec snapshots and non-overlapping scope locks.
3. The pre-task hook runs before spawn, resume, reuse, manage, or close.
4. Worker spawn is blocked until the operator answers missing-data questions and drift questions.
5. The main agent is orchestration-only. Allowed action tokens are exactly `route`, `split`, `assign`, `wait`, `integrate_evidence`, `run_validators`, `close`, `report`, and `pre_task_hook`. Forbidden action tokens are exactly `file_read_as_content_collector`, `file_write`, `git_add`, `git_commit`, `git_push`, `pull_request_mutation`, and `implementation_tool_use`.
6. Active subagents are capped at 100. Maximum depth is 3.
7. Multiple orchestrators are allowed only for explicit controller roles from `subagent-orchestration-policy.v1.json`.
8. Every audit uses a fresh subagent with `context_policy = fresh_no_parent_context`, no parent context, and no resume/reuse.
9. Session reuse must bind `goal_id`, `roadmap_id`, `roadmap_slice`, spec snapshot, lane, role, scope fingerprint, repo state, and validation target.

Assignment packets, subagent task text, and subagent messages must use English only.
Name `local_cd` or `kubernetes_deployment` when one of those entities is the concrete target. Do not fall back to generic `deploy`.
Fresh audit subagents use no parent context.
Repo-proof validation covers only repo artifacts. It does not claim live runtime chat proof.

## Objective roadmap in the catalog

The catalog includes `roadmap_for_this_objective` for this implementation:

1. `phase-1-route-and-baseline`: route/audit `roadmap_control`, read local rules, keep unrelated edits untouched.
2. `phase-2-catalog-and-validator`: write the catalog and `scripts/roadmap_control.py`.
3. `phase-3-tests-and-reference`: add unit tests and this reference.
4. `phase-4-closeout`: collect local-commit-owned validation evidence, record expected route/audit status, and report evidence.

## Validation

Local commit validation owns roadmap validator and unit-test execution. Manual execution requires one exact operator-named command:

- Local commit validation owns `python3 scripts/roadmap_control.py validate`; manual execution requires one exact operator-named command.
- Local commit validation owns `python3 scripts/subagent_orchestration_policy.py validate`; manual execution requires one exact operator-named command.
- Local commit validation owns `python3 -m unittest tests.test_roadmap_control tests.test_subagent_orchestration_policy`; manual execution requires one exact operator-named command.
- Local commit validation owns `python3 scripts/validate_overlay.py --json validate --strict-overlay-skills`; manual execution requires one exact operator-named command.

The local-commit-owned `validation.commands` list must match the `roadmap_control.required_validations` list in `assets/catalog/platform-role-catalog.v1.json`:

- Local commit validation owns `python3 scripts/subagents_roles.py validate`; manual execution requires one exact operator-named command.
- Local commit validation owns `python3 scripts/roadmap_control.py validate`; manual execution requires one exact operator-named command.
- Local commit validation owns `python3 -m unittest tests/test_roadmap_control.py tests/test_subagents_roles.py`; manual execution requires one exact operator-named command.

The validator also verifies controller role names and route-required validation parity against:

- `assets/catalog/platform-role-catalog.v1.json`
- `assets/catalog/subagent-orchestration-policy.v1.json`

## Write boundary

This control surface is limited to:

- `assets/catalog/roadmap-control.v1.json`
- `scripts/roadmap_control.py`
- `tests/test_roadmap_control.py`
- `docs/reference/roadmap-control.md`

It does not add apps, connectors, MCP servers, runtime services, production deploy behavior, or product code.
