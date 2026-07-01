# Session Workers Runtime

## Invariant

- **Truth**: current Spec Kit artifacts.
- **Control**: `/srv/bears/plugins/bears` catalogs, role gate, and validators.
- **Work**: Codex sessions and session workers.

Codex sessions are workers, not memory.

## Worker lanes

The canonical lanes are:

- `constitution`
- `specification`
- `planning`
- `docs`
- `auth`
- `gateway`
- `deploy`
- `validation`
- `review`
- `audit`
- `implementation`

Each worker must bind exactly one explicit lane and one registered role from `assets/catalog/platform-role-catalog.v1.json`.

## Spec binding and concurrency

Concurrent workers may develop multiple Spec Kit specifications at the same time when every worker has one exact Spec Kit binding:

- `spec_id`
- `spec_path`
- `spec_kit_snapshot`

`spec_kit_snapshot.spec_id` and `spec_kit_snapshot.spec_path` must match the worker fields. Different `spec_id` values do not bypass scope locks. Concurrent workers are valid only when active `scope-locks.json` entries do not overlap.

## Required worker contract

Every worker must carry all of the following in `session-workers.json`:

- worker id
- status
- explicit lane
- registered role
- `goal_id`
- `roadmap_id`
- `questionnaire_ref`
- `context_policy`
- `spec_id`
- `spec_path`
- bounded target paths
- allowed write scope
- forbidden scope
- roadmap slice
- pre-task hook packet
- deterministic `reuse_key`
- current Spec Kit artifact snapshot
- validation target
- evidence target
- heartbeat packet reference
- closeout packet reference
- resume policy

Workers are not durable memory containers. Historical evidence can be attached only as bounded prior evidence under the resume policy.

## Pre-task hook fields

The worker, heartbeat packet, and closeout packet carry the same pre-task hook fields:

- `hook_id`
- `task_id`
- `task_path`
- `goal_id`
- `roadmap_id`
- `questionnaire_ref`
- `context_policy`
- `spec_id`
- `spec_path`
- `roadmap_slice`
- `repo_head`
- `missing_data_evidence`
- `drift_answer_evidence`
- `task_start_authorization`

These fields bind runtime packets to the Spec Kit task that started the worker. `missing_data_evidence` records the operator answers for missing inputs. `drift_answer_evidence` records the operator answers for changed context. `task_start_authorization` must authorize `spawn`, `reuse`, `manage`, and `close` before any worker action starts.

## Runtime artifacts

A compliant runtime directory contains these canonical files:

- `session-workers.json`
- `orchestration-state.json`
- `worker-heartbeat.json`
- `worker-closeout.json`
- `scope-locks.json`
- `session-reuse-index.json`

`session-workers.json` is the registry. `orchestration-state.json` is the state view. `scope-locks.json` prevents overlapping writes. `worker-heartbeat.json` and `worker-closeout.json` are per-worker packets referenced from the registry. `session-reuse-index.json` is the deterministic session reuse registry.

## Session reuse index

`session-reuse-index.json` uses `sha256-json-v1`. The `reuse_key` is computed from:

- goal id
- roadmap id
- lane
- registered role
- scope fingerprint
- repo head
- spec id
- spec path
- Spec Kit snapshot id
- roadmap slice

Resume or reuse is allowed only when the worker `reuse_key` matches the reuse index entry and all compatibility fields are true. Each reuse index entry must also record `validation_target`, `continuation_packet_ref`, `restricted_data_taint`, `last_validation_at`, and `selection_decision`. Allowed selection decisions are `reuse`, `fresh`, and `close_then_fresh`. `restricted_data_taint=true` blocks reuse. Audit lanes cannot select `reuse`.

## States

Workers move through the canonical states:

- `available`
- `claimed`
- `running`
- `waiting`
- `blocked`
- `stale`
- `completed`
- `closed`

`stale` means the worker packet or repo state can no longer be trusted without refresh. `closed` means the worker is intentionally retired and should not resume.

## Resume, reuse, and fork rule

Historical session resume, reuse, or fork is allowed only when all of the following match the current request:

- goal id
- roadmap id
- lane
- registered role
- bounded scope
- current repo state
- current Spec Kit snapshot
- roadmap slice

If any compatibility check fails, spawn a fresh worker with current Spec Kit truth plus bounded prior evidence.

Session reuse or fork also requires a successful pre-action runtime validation:

```bash
python3 scripts/session_workers_runtime.py validate-runtime --runtime-dir <dir>
```

The worker `resume_policy.pre_action_validation` packet must record that command, `exit_code=0`, and `compatibility_status=compatible`. If the command fails or compatibility is not complete, spawn a fresh worker with bounded prior evidence.

## Audit lane rule

Audit lane workers must start fresh. They must set `context_policy=fresh_no_parent_context`. They must set `resume_policy.requested_action=fresh`. They must not resume or reuse historical state. Their pre-task hook must set `parent_context_allowed=false` and must not set `parent_worker_id`. The worker record must not set `parent_worker_id`. The reuse index entry must set `reuse_allowed=false`.

## Closeout quality rule

Subagent closeout packets are English-only artifacts. Cyrillic text is rejected. `limitations` entries use `code`, `severity`, and `details`; a `blocking` limitation cannot accompany a passing `completed` or `closed` closeout. Review and audit closeouts must include clean checkout metadata with `dirty_shared_checkout_used=false` and `validated_at_expected_sha=true`.

## Wait agent result rule

After every `wait_agent`, the parent must compare returned status keys to requested target ids before integration. If no requested target id appears, the parent must emit `WAIT_AGENT_TARGET_MISMATCH` with requested ids, returned ids, and next safe action. The parent must not advance the stage. It must keep waiting for, interrupt, or explicitly close the originally requested agents before dependent work.

## Capacity fallback reconciliation

Before capacity fallback or replacement launch, the parent must inspect the worker session tail, declared checkout, and GitHub branch or PR state. It must place every partial subagent state into one bucket:

- `active`: claimed, running, waiting, or stale worker. Keep waiting, interrupt, or explicitly close it.
- `completed-needs-close`: completed worker that is not closed. Inspect closeout, PR URLs, validation evidence, and dirty files; then integrate or close it.
- `failed-needs-review`: capacity, error, errored, or failed worker result. Review session tail, tool outputs, checkout state, and open PRs before replacement or quarantine.
- `unknown-needs-refresh`: missing, null, unreported, or unknown status. Refresh worker status, session tail, checkout state, and GitHub state before replacement.
- `blocked-needs-parent-action`: blocked worker. Parent must resolve, rescope, quarantine, or close it.

Unknown and completed-open workers are not free capacity. Only `closed` workers are free capacity. A duplicate worker for the same task id is blocked until the prior worker is integrated, quarantined, or closed.

## Implementation lane rule

`/speckit-implement` is one controlled implementation lane. It is not a global executor and must not absorb unrelated docs, review, planning, validation, or audit work.

## Validation

Use:

```bash
cd /srv/bears/plugins/bears
python3 scripts/session_workers_runtime.py validate
python3 scripts/session_workers_runtime.py validate-runtime --runtime-dir <dir>
```

The runtime validator checks lane/role compatibility, required worker fields, Spec Kit binding, pre-task hook reflection, scope locks, heartbeat/closeout packets, deterministic reuse index, and resume/reuse/fork compatibility rules.
