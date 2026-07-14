---
name: app-dev
description: Execute repo-scoped ledger tasks through worker and critic waves with linked correction runs.
---

# App Dev

## Ownership

- Keep the `DIRECT` primary as the stage owner for the repo queue, target changes, review, correction routing, protocol decisions, journal events, and the outgoing handoff.
- Keep `workflow-orchestrator` L1 limited to grouping repo handoffs, creating one persistent repo-L2 per independent repo, and gating cross-repo dependencies.
- Never let L1 own a stage, dispatch an L3, or replace a missing repo-L2.
- Keep one persistent repo-L2 with role `domain-lane-orchestrator` as the stage owner for one `repo_ref` in `DELEGATED` mode.
- Keep `owner_session_ref=none` for `DIRECT` and one non-`none` repo-L2 `owner_session_ref` across the complete `DELEGATED` run.
- Require the repo-L2 to invoke every app-worker, critic, reader, and writer L3 through `$subagents`.
- Require the repo-L2 to consume only bounded `result-packet.v2` results and never perform target work itself.
- Never let an L3 write the journal, update the ledger outside its task contract, select a transition, or emit the stage handoff.

## Input

- Accept only a repo-scoped `app-stage-handoff.v4` status `plan-ready` or `ready` whose build and source snapshot are current.
- Require complete `app-task-ledger.v3` records with status `ready` or `waiting` and every schema field.
- Require `ready` only when every dependency has a terminal `done` result and `waiting` otherwise.
- Require at least one `ready` record.
- Require the handoff `stage_payload` to provide the repo cwd, batch ref, wave ref, queue order, and complete current task records.
- Reject mixed repos, duplicate queue positions, or missing dependency refs.
- Reject widened targets, stale graph refs, or fields outside the task schema.
- Resolve routes and task states only from `contracts/app-workflow-definition.v3.json`.

## Delegation protocol

Use `contracts/delegation-packets.v2.json` as the only packet authority for `delegation-entry.v1`, `assignment-authority.v1`, `typed-agent-dispatch.v1`, `dispatch-packet.v3`, `result-packet.v2`, and `app-task-dispatch.v2`.

Bind every delegated start to the exact installed profile, use `fork_turns=none`, preserve the authority identity tuple, and reject parent execution fallback.

Send one complete current task at a time inside `dispatch-packet.v3.stage_payload` and never expose the full queue or a future task to an L3.

Use one persistent app-worker session per repo wave, accept one result before continuing it, and use a new assignment id for every continuation.

## Worker wave

1. Promote each `waiting` task to `ready` only after every dependency has a terminal `done` result, then select the next `ready` task by declared dependency order and `queue_sequence`.
2. Move only that task through `ready` to `in_progress` before mutation.
3. Perform the bounded change directly in `DIRECT` mode or dispatch one `app-worker` through `$subagents` in `DELEGATED` mode.
4. Require at least one retained full Git commit ref for every task result.
5. Record one native v3 task result with nonempty `commit_refs`, nonempty `changed_paths`, and exact terminal status.
6. Require `changed_paths` to stay inside both task target paths and allowed files.
7. Require task-result artifact refs to equal implementation refs plus evidence refs.
8. Require task-result trace refs to cover the task, requirement, functionality, and graph refs.
9. Include every ref from task `retirement_commit_refs` in its task-result `commit_refs`.
10. Keep a failed task terminal, keep its dependents non-ready, and continue only with independent ready work.
11. Close the worker session when its repo wave has no remaining ready task.

## Critic wave

1. Review immutable `base_commit..wave_head` only after proving forward ancestry and exact equality between its commit set and the task-result commits.
2. Perform the bounded review directly in `DIRECT` mode or dispatch one fresh `wave-change-critic` through `$subagents` in `DELEGATED` mode.
3. Supply task results, failed-task refs, requirement refs, changed targets, evidence refs, and applicable trust, secret, identity, authorization, callback, ingress, and publication boundaries.
4. Require the critic to remain read-only and report each contradiction, implementation gap, provenance gap, or scope violation with exact refs.
5. Keep one critic session open for rereview and never create a duplicate or cross-repo critic.
6. Record each completed finding review with its full run task set, exact `base_commit..wave_head`, and `finding_refs`.
7. Record exactly one final clean full-scope review with empty `finding_refs` after every task result.

## Correction run

1. Route the current run to `$app-plan` with `needs-plan` and exact source, result, review, and finding refs when new ledger work is required.
2. Require `$app-plan` to record terminal `needs-plan` without changing the source-run task scope.
3. Require each new remediation task to preserve the source refs in `remediation_basis`.
4. Start one linked run with `remediates_run_ref` and only those remediation tasks in scope.
5. Run the linked tasks through a new app-worker wave and return its pinned range to the original critic session.
6. Repeat only while a routable finding or remediation task remains open.

## Completion

1. Reconcile every authoritative task-result, review, and ledger change through `$app-context-index`.
2. Route source, decision, graph, and task-work gaps to `needs-research`, `needs-spec`, `needs-graph`, or `needs-plan` respectively.
3. Return `blocked` only for a credential, access, or explicit operator stop; for every non-implemented route record its stage event, reconcile, validate the canonical handoff, and stop the run.
4. Select `implemented` only when every task result is `done` and no remediation task remains open.
5. Record one repo-handoff whose only direct cause is the final clean review.
6. Put exact `task_result_refs`, `review_refs`, and `final_review_ref` in the implemented `stage_payload`.
7. Put exact `commit_refs`, `commit_ranges`, and remediation task ids in `stage_payload.remediation_refs`.
8. Bind the handoff owner mode, owner session, and repo to the recorded run.
9. Bind the handoff wave, trace links, and build to the recorded run.
10. Bind the handoff source snapshot and journal digest to the recorded run.
11. Preserve the run's exact task scope and record only actual native v3 lifecycle events with `handoff_payload_digest` over canonical outgoing `stage_payload` through the `DIRECT` primary or repo-L2.
12. Reconcile the resulting journal and call `app-graph.handoff_validate` for the complete candidate.
13. Emit the validated build-bound repo handoff to `app-analyze`.
