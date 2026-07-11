---
name: app-dev
description: Orchestrate repo-scoped app waves through persistent L2 queues, exact app-worker tasks, immutable review, and remediation. Use when graph-linked ledger work is dependency-ready and bounded by exact targets.
---

# App Dev

## Ownership boundary

For work already classified `DELEGATED`, `app-dev` fixes the parent as `workflow-orchestrator` L1 and creates persistent `domain-lane-orchestrator` L2s by `repo_ref`. L1 groups and gates repo workflows; each L2 owns only its repo queue, dependency readiness, app-worker sessions, reviewers, remediation anchors, and repo-scoped closeout. Each L2 follows `$subagents` for deterministic L3 selection and dispatch. `DIRECT` work never enters this procedure.

L1 and L2 use compact packets only. They do not access files, logs, terminal, Git, scripts, MCP, runtime, or network state, and they never perform L3 work.

## Required input

Accept canonical `app-stage-handoff.v1` status `plan-ready` from `app-plan` or `ready` from `app-analyze`. It carries every common field defined by `app-functional-graph` and complete canonical `task_records`. Each task includes:

- `task_id`, `repo_ref`, `batch_id`, `wave_id`, `queue_sequence`, `task_kind`, and `source_review_refs`;
- requirement, functionality, graph-node, artifact, and automation-evidence refs;
- exact targets, allowed files, owner role, lane, dependencies, closed decision state, and ready status;
- definition of done, proof requirement, and ledger update contract.

Reject mixed-repo records, duplicate queue positions, incomplete tasks, or tasks with open decisions, stale graph refs, or unclosed dependencies.

## Fixed L1 orchestration

1. Group canonical tasks by `repo_ref`; preserve deterministic `queue_sequence` within each wave and never mix repositories in one L2.
2. Create one persistent `domain-lane-orchestrator` L2 for each independent repo workflow. A repo-L2 may enter `capacity-wait` before a worker slot is available; it resumes only on a slot-available signal and never polls repeatedly.
3. Give each L2 only its repo records, repo cwd/ref, dependency refs, target bounds, completion criteria, and compact capacity state.
4. Gate a cross-repo dependency only in the dependent repo-L2. Independent repo-L2s continue; never create one global serial queue.
5. Prevent concurrent mutation where dependency or target overlap exists. Mutation workers have capacity priority; reviewers use remaining capacity.
6. Forward each repo-scoped implemented handoff independently to `app-analyze`. Never aggregate task, review, commit, or remediation refs across repositories.

L1 never treats `$subagents` as a recipient and never replaces a missing L2 or L3 with parent execution.

## Repo-L2 task execution

1. Own exactly one `repo_ref` queue. Determine readiness from canonical dependencies without changing task meaning, targets, ids, or order, and never decompose a canonical task again.
2. One canonical task is one exact L3 mutation assignment with a new `assignment_id`, one `result-packet.v1`, and no more than one retained commit. For each `(repo_ref, wave_id)`, start one `app-worker` session with a stable `wave_session_id`, then continue that same session for later ready tasks.
3. Send exactly one current complete task at a time through `dispatch-packet.v2.stage_payload.app_task_dispatch`. Never disclose the full wave, future tasks, or queue to the app-worker.
4. Reuse an L3 only when its role is `app-worker` and `repo_ref`, `wave_id`, and `wave_session_id` are unchanged. Every reviewer, planner, helper, other role, other repo, other wave, or other session requires a fresh agent.
5. Accept one task result before selecting the next ready task. Update only fields allowed by `ledger_update_contract` through `ready -> in_progress -> done|failed`.
6. A failed canonical task stays `failed` and is never reopened. Before another task, its mutation is either captured in one safe coherent partial commit or fully removed. Mark dependents not ready, retain the failed ref as a known gap, and continue the same app-worker session with later independent ready tasks.
7. Close the wave session when ready tasks are exhausted. Do not poll blocked work or reopen the session; route failed refs through review and remediation.

## App task packet and result

An app-worker dispatch nests this complete object inside `dispatch-packet.v2.stage_payload`:

```yaml
app_task_dispatch:
  schema: app-task-dispatch.v1
  task_record: <one current complete canonical task record>
  repo_ref: <same task repo_ref>
  repo_cwd: <exact repository cwd>
  batch_id: <same task batch_id>
  wave_id: <same task wave_id>
  wave_session_id: <stable session id for this repo and wave>
  queue_sequence: <same task queue_sequence>
  session_action: start|continue
  previous_task_result_ref: <null only for start; immediately preceding session result ref for continue>
```

The corresponding `result-packet.v1` contains exactly one `app-task-change.v1` fact with `assignment_id`, `task_id`, `repo_ref`, `wave_id`, `wave_session_id`, `queue_sequence`, `status: done|failed`, `commit_ref` where a coherent change was retained, exact `changed_targets`, `cleanup_state: clean|coherent_partial_commit`, `partial_state_ref`, and `source_review_refs`. A failed result identifies its coherent partial-state ref or confirms the diff was removed. One task has one result and never more than one commit.

## Immutable repo-wave review

1. After a repo wave closes, start one fresh `wave-change-critic` for that repo only. Review the immutable pinned `base_commit..wave_head`, never live `HEAD` or a worktree, and supply failed task refs as known gaps.
2. Never create an aggregate cross-repo critic. A `security-analysis-critic` is optional only when a deterministic trigger exists: a trust boundary; secrets, identity, or authorization; callback or ingress; or a promotion/security-sensitive surface. It must use a distinct security methodology; duplicate critics are forbidden.
3. Reviewers are read-only: they cannot fix, mutate, commit, or run autoCI. Primary and justified specialist review results remain separate refs.
4. Immutable review of a prior wave may overlap the next independent, non-overlapping wave. A dependency or target overlap waits. Mutation workers retain capacity priority and reviewers use only remaining capacity.

## Repo remediation queue

After review, the repo-L2 merges failed task refs, the primary review ref, and any justified specialist review ref into remediation inputs. It snapshots the current repo queue and creates `remediation-anchor.v1` immediately after that snapshot's tail. Independent tasks already in the snapshot run before the anchor; tasks admitted later are placed after the anchor.

At the anchor, start a fresh separate `app-plan` assignment. It creates a new remediation wave with new canonical task ids, `task_kind: remediation`, and source review refs; original tasks remain terminal `done|failed`. Insert the new remediation tasks at the anchor before later-admitted tasks. Remediation follows the normal app-worker session, immutable repo-wave review, and repo remediation rules.

## Stage rules and handoff

- Do not invent work outside the ledger, overlap mutable targets, or start tasks with missing graph refs, open decisions, or open dependencies.
- Return product decisions to `app-specify` and planning gaps to `app-plan`. Never write functional graph meaning, graph anchors, wave plans, or analysis artifacts.
- Each repo-L2 returns one canonical repo-scoped `app-stage-handoff.v1` directly as its outer contract, with every common field. Status `implemented` adds `repo_ref`, `completed_task_refs`, `failed_task_refs`, `task_result_refs`, `review_result_refs`, `commit_range_refs`, and `remediation_task_refs`, and targets `app-analyze`. Never wrap or nest this handoff in `domain-lane-closeout.v1`; do not emit a generic cross-repo merge.
- `needs-plan` adds `source_handoff_ref`, `ledger_coverage_refs`, and `implementation_state_by_requirement`; `needs-spec` adds `source_handoff_ref` and `question_refs`; `blocked` adds `blocker_refs` and `operator_action_refs`. Use `blocked` only for access, credentials, unavailable sources, or explicit operator stops.
