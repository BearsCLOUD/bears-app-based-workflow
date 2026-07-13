---
name: app-plan
description: Create repo-scoped graph-linked implementation and remediation tasks in topological order.
---

# App Plan

## Ownership

- Keep the `DIRECT` primary as the stage owner for target access, ledger changes, protocol decisions, journal events, and the outgoing handoff.
- Keep one persistent repo-L2 with role `domain-lane-orchestrator` as the stage owner for `DELEGATED` work.
- Require the repo-L2 to invoke every L3 assignment through `$subagents` and consume only its bounded result packet.
- Never let an L3 write the journal, select a transition, or emit the stage handoff.

## Input

- Accept only `app-stage-handoff.v4` status `graph-ready`, `waiting`, or `needs-plan` for the same repo boundary.
- Require a current `$app-context-index` result whose build and source snapshot match the handoff.
- Resolve task fields and transitions only from `contracts/app-task-ledger.v3.schema.json` and `contracts/app-workflow-definition.v3.json`.
- Use declared graph dependencies, impact results, and topological layers instead of inferring order from prose.
- Follow every opaque cursor until no cursor remains before treating graph or ledger coverage as complete.

## Planning

Create or update `waves/<wave-id>/plan.md` and executable tasks in `docs/app-task-ledger.v3.json`.

Keep each task inside one `repo_ref` and include every field required by `app-task-ledger.v3`.

Create tasks only for decision-complete requirements with current functionality, graph entity, target, source snapshot, and dependency refs.

Set `owner_role` to `DIRECT-primary` in `DIRECT` mode and `repo-L2` in `DELEGATED` mode.

Use only `waiting` or `ready` for newly planned ordinary work.

Set `ready` only when every prerequisite is closed and every target boundary is exact.

Create a new task with `task_kind: remediation` for each routable review or result gap and link it through graph and evidence refs.

Never reopen, renumber, or overwrite a terminal task.

Never change functional-map meaning in this stage.

## Completion

1. Require the `DIRECT` primary to perform the bounded reads and writes itself.
2. Require the repo-L2 in `DELEGATED` mode to decompose each bounded read or write and dispatch each L3 through `$subagents`.
3. Return `needs-spec` for unresolved product meaning and return `needs-graph` for missing or drifted semantic mapping.
4. Return `waiting` when tasks exist but none is dependency-ready.
5. Return `no-work` when all mapped requirements have implementation and evidence refs with no executable task remaining.
6. Return one repo-scoped `plan-ready` handoff when at least one canonical task is `ready`.
7. Put exact task records, repo cwd, batch ref, wave ref, dependency refs, target paths, and allowed files in `stage_payload`.
8. Reconcile the changed ledger through `$app-context-index` and reject any structural finding before handoff.
9. Validate the candidate `app-stage-handoff.v4`, record only the actual native v3 stage event, and reconcile the resulting journal.
10. Emit the build-bound handoff with the target resolved from workflow v3.
