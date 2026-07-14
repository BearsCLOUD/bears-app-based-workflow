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

Create one `task_kind: remediation` task for each routable review or result gap and bind its graph, evidence, `remediation_basis.run_ref`, `source_event_refs`, and `finding_refs`.

Never reopen, renumber, or overwrite a terminal task or change functional-map meaning in this stage.

## Completion

1. Require the `DIRECT` primary to perform the bounded reads and writes itself.
2. Require the repo-L2 in `DELEGATED` mode to decompose each bounded read or write and dispatch each L3 through `$subagents`.
3. Return `needs-research` for a source gap, `needs-spec` for unresolved product meaning, and `needs-graph` for missing or drifted semantic mapping.
4. Return `waiting` when tasks exist but none is dependency-ready.
5. Return `no-work` when no executable task remains; keep `task_refs` empty before ordinary scope and preserve them after corrective analysis.
6. Let ordinary `plan-ready` establish exact nonempty `task_refs` before execution.
7. On corrective input, validate terminal `needs-plan` with unchanged source-run scope, then record and validate linked run-start `plan-ready` with only the exact remediation tasks.
8. Put exact task records, repo cwd, batch ref, wave ref, dependency refs, target paths, and allowed files in `stage_payload`.
9. Reconcile the changed ledger through `$app-context-index` and reject any structural finding before handoff.
10. For each outgoing boundary, record only its actual native v3 event with the canonical payload digest, reconcile the journal, and call `app-graph.handoff_validate`.
11. Emit the build-bound handoff with the target resolved from workflow v3.
