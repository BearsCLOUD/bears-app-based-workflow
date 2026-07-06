# App task ledger and Project metadata flow

This file defines how L2 orchestrators execute development from app-local task ledger state. GitHub Project data is a planning and status view. GitHub Issues are notification records only for blockers, incidents, bugs, or operator questions.

## L2 intake packet

```text
app_directory=<path under /srv/bears/dev/app>
functional_graph=<app_directory>/docs/app-functional-graph.v1.json
task_ledger=<app_directory>/docs/app-task-ledger.v1.json
project_refs=<GitHub Project item ids or urls>
notification_refs=<GitHub Issue urls already authorized as notifications>
route_targets=<paths requiring route/audit>
closeout_policy=<commit/push/proof requirements>
metadata_mutation=<none|project-status-authorized|notification-authorized>
```

## Task execution sequence

1. Load `docs/app-functional-graph.v1.json`.
2. Load `docs/app-task-ledger.v1.json`.
3. Require `$app-functional-graph` evidence before wave grouping; validator
   execution belongs to `autoCI` or local commit validation unless the operator
   names the exact command in the current turn.
4. Select dependency-ready ledger tasks with `status=ready`.
5. Confirm every selected task has `functionality_refs`, `graph_node_refs`, owner role, lane, allowed paths, status matrix, and evidence expectations.
6. Resolve the canonical owner repo and local checkout path.
7. Record expected route/audit owner coverage for every target path; route/audit
   execution belongs to `autoCI` or local commit validation unless the operator
   names the exact command in the current turn.
8. Split the task when repo boundary, role, write scope, proof path, deploy/runtime boundary, functionality ref, or graph node ref differs.
9. Generate one L3 `/goal` packet per split.
10. Dispatch L3 workers.
11. Collect L3 closeout packets and critic confirmation.
12. Request gitflow closeout when any L3 worker changed files.
13. Update the app task ledger and Project item status from evidence only.
14. Record GitHub Issue URLs only after explicit manual notification authorization.
15. Report final ledger state to the parent.

## L3 assignment from ledger task

```text
/goal
lane=l3
role=<route-selected @Bears role>
model=gpt-5.4-mini
reasoning=high
app_directory=<path under /srv/bears/dev/app>
task_id=<ledger task id>
functional_graph=<app_directory>/docs/app-functional-graph.v1.json
task_ledger=<app_directory>/docs/app-task-ledger.v1.json
functionality_refs=<functionality ids>
graph_node_refs=<functionality_id:node_id refs>
graph_edge_refs=<functionality_id:from->to refs or none>
repo=<local path and owner/repo>
target=<exact files/paths>
route_audit_evidence=<route/audit command result or packet id>
metadata_mutation_authorized=<true|false>
allowed_actions=<bounded list>
forbidden_actions=<bounded list>
acceptance_criteria=<ledger acceptance ids>
validation=<exact safety commands or metadata checks>
completion_criteria=<closeout proof required by L2>
ledger_updates=<fields L2 must update after evidence>
```

## Mini runtime proxy packet for L3

Use this packet only when L2 must pass a tiny L3 slice through a constrained runtime proxy. The packet must keep the route/audit result intact and must not widen the worker scope.

```text
mini_runtime_proxy=true
proxy_lane=l3
proxy_reason=<exact missing or constrained runtime capability>
route_selected_role=<exact @Bears role returned by route/audit>
route_selected_profile=<exact role/profile name passed to the worker>
task_id=<ledger task id>
functionality_refs=<functionality ids>
graph_node_refs=<functionality_id:node_id refs>
repo=<local path and owner/repo>
target=<one exact file or one exact path>
allowed_write_boundary=<exact files/paths the worker may edit>
forbidden_surfaces=<paths, runtimes, metadata, deploy, secret, or settings surfaces the worker must not touch>
metadata_mutation_authorized=<true|false>
first_minute_progress_proof=<READY|WIP|FAST_BLOCKER packet id or exact proof text>
first_minute_proof_time=<UTC timestamp or elapsed seconds from assignment receipt>
execution_lane=tiny_one_file_or_one_path
post_fix_no_wip_gate=<exact command proving task-owned WIP is absent after PASS>
validation=<exact command or metadata check>
completion_criteria=<closeout proof required by L2>
```

Required rules:

- `route_selected_role` and `route_selected_profile` must match the route-selected @Bears role/profile name; a proxy role name may not replace them.
- `allowed_write_boundary` must preserve the L2 packet write scope exactly. `forbidden_surfaces` must preserve every forbidden path, runtime, metadata, deploy, secret, and settings surface.
- Write work may continue only after `first_minute_progress_proof` exists. Missing proof returns `FAST_BLOCKER` with no writes and no L3 dispatch.
- After a timeout, failed proxy run, or missing worker-authority proof, use only one tiny execution lane until one post-fix `PASS` plus `post_fix_no_wip_gate` proves no task-owned WIP.
- The proxy may not batch multiple ledger tasks, repos, target files, role scopes, validation paths, functionality refs, graph node refs, or closeout paths.

## Role-gap escalation

When route/audit returns `ROLE_COVERAGE_BLOCKER`, a selected role lacks exact write scope, or role text grants forbidden implementation authority, L2 records a blocker and returns it to the parent. Do not spawn L3 for role edits from app-dev.

## Project and notification update rule

L2 may update Project fields, app task ledger fields, or notification refs only from these evidence types:

- graph and ledger validation packet;
- route/audit packet;
- L3 closeout packet;
- critic confirmation;
- commit SHA and push proof;
- PR metadata;
- Release/tag/package metadata;
- objective runtime proof metadata;
- explicit blocker proof.

Do not update status from chat-only agreement, guessed status, or unvalidated implementation claims.

## Out-of-scope Project management

Do not use this flow to choose the organization's Project field model, create one Project per app, design roadmap views, configure Project automation, mutate repository settings, or replace issue-type governance. Use the owning Project-management governance for those actions.

## Apps repo boundary

For `BearsCLOUD/apps`, `apps` is the repository name and `/srv/bears/dev/app` is the local repo root.

A Project-management policy may choose a canonical Project for `BearsCLOUD/apps`. This flow consumes Project item metadata as a planning/status view. Execution identity remains the app task ledger task id.
