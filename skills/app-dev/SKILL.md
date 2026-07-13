---
name: app-dev
description: Execute repo-scoped ledger tasks through worker, critic, and remediation waves.
---

# App Dev

## Ownership

- Keep the `DIRECT` primary as the stage owner for the repo queue, target changes, review, remediation, protocol decisions, journal events, and the outgoing handoff.
- Keep `workflow-orchestrator` L1 limited to grouping repo handoffs, creating one persistent repo-L2 per independent repo, and gating cross-repo dependencies.
- Never let L1 own a stage, dispatch an L3, or replace a missing repo-L2.
- Keep one persistent repo-L2 with role `domain-lane-orchestrator` as the stage owner for one `repo_ref` in `DELEGATED` mode.
- Require the repo-L2 to invoke every app-worker, critic, reader, and writer L3 through `$subagents`.
- Require the repo-L2 to consume only bounded `result-packet.v2` results and never perform target work itself.
- Never let an L3 write the journal, update the ledger outside its task contract, select a transition, or emit the stage handoff.

## Input

- Accept only a repo-scoped `app-stage-handoff.v4` status `plan-ready` or `ready` whose build and source snapshot are current.
- Require complete `app-task-ledger.v3` task records with status `ready`, closed decisions, current graph refs, exact target paths, allowed files, dependencies, completion definition, proof requirement, and evidence refs.
- Require the handoff `stage_payload` to provide the repo cwd, batch ref, wave ref, queue order, and complete current task records.
- Reject mixed repos, duplicate queue positions, open dependencies, widened targets, stale graph refs, or fields outside the task schema.
- Resolve routes and task states only from `contracts/app-workflow-definition.v3.json`.

## Delegation protocol

Use `contracts/delegation-packets.v2.json` as the only packet authority for `delegation-entry.v1`, `assignment-authority.v1`, `typed-agent-dispatch.v1`, `dispatch-packet.v3`, `result-packet.v2`, and `app-task-dispatch.v2`.

Bind every delegated start to the exact installed profile, use `fork_turns=none`, preserve the authority identity tuple, and reject parent execution fallback.

Send one complete current task at a time inside `dispatch-packet.v3.stage_payload` and never expose the full queue or a future task to an L3.

Use one persistent app-worker session per repo wave, accept one result before continuing it, and use a new assignment id for every continuation.

## Worker wave

1. Select the next `ready` task by declared dependency order and `queue_sequence` without changing its meaning or targets.
2. Move only that task through `ready` to `in_progress` before mutation.
3. Perform the bounded change directly in `DIRECT` mode or dispatch one `app-worker` through `$subagents` in `DELEGATED` mode.
4. Require one retained task commit or a clean removal of the failed change.
5. Record one task result with status `done` or `failed`, exact implementation refs, changed targets, commit ref, cleanup state, and evidence refs.
6. Keep a failed task terminal, keep its dependents non-ready, and continue only with independent ready work.
7. Close the worker session when its repo wave has no remaining ready task.

## Critic wave

1. Review the immutable `base_commit..wave_head` after the worker wave closes.
2. Perform the bounded review directly in `DIRECT` mode or dispatch one fresh `wave-change-critic` through `$subagents` in `DELEGATED` mode.
3. Supply task results, failed-task refs, requirement refs, changed targets, evidence refs, and applicable trust, secret, identity, authorization, callback, ingress, and publication boundaries.
4. Require the critic to remain read-only and report each contradiction, implementation gap, provenance gap, or scope violation with exact refs.
5. Keep one critic session open for rereview and never create a duplicate or cross-repo critic.

## Remediation wave

1. Route each failed-task or critic finding to `$app-plan` under the same stage owner.
2. Require the repo-L2 in `DELEGATED` mode to execute every planning read or write through `$subagents`.
3. Create new remediation task ids and preserve the original terminal task and review refs.
4. Run the remediation tasks through a new app-worker wave.
5. Return the pinned remediation range to the original critic session for rereview.
6. Repeat only while a routable critic finding or remediation task remains open.

## Completion

1. Reconcile every authoritative task-result, review, and remediation change through `$app-context-index`.
2. Return `needs-spec` for a product or decision conflict and return `needs-plan` for a task, implementation, evidence, review, or remediation gap that requires new ledger work.
3. Return `blocked` only for a credential, access, or explicit operator stop.
4. Select `implemented` only after the worker, critic, and remediation lifecycle has no open finding or remediation task.
5. Put completed, failed, task-result, review-result, commit-range, and remediation refs in `stage_payload`.
6. Validate the candidate `app-stage-handoff.v4` against workflow v3.
7. Record only actual native v3 delegation, task-result, review, remediation, and repo-handoff events through the `DIRECT` primary or repo-L2.
8. Reconcile the resulting journal and emit one build-bound repo handoff to `app-analyze`.
