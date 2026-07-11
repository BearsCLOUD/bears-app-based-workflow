---
name: subagents
description: Deterministically choose an installed L3 profile, dispatch bounded work, and preserve the repo-wave app-worker session exception.
---

# Subagents

## Ownership

This procedure receives only work already classified `DELEGATED` under the active caller instruction chain and `/srv/bears/contracts/developer_instructions_contract.md`. `DIRECT` work remains with the primary and never enters this procedure.

`app-dev` fixes `workflow-orchestrator` at L1 and one persistent `domain-lane-orchestrator` L2 per repo workflow. Outside app-dev, a solo parent performs the L2 analogue. This procedure owns only deterministic L3 role choice, `dispatch-packet.v2`, bounded dispatch, and `result-packet.v1` handling. It does not classify or decompose work, choose a canonical task, manage a repo queue, or perform target work.

The plugin has exactly these eleven profiles:

- `worker`
- `app-worker`
- `explorer`
- `diagnostic-command-runner`
- `primary-source-researcher`
- `runtime-evidence-reader`
- `wave-change-critic`
- `security-analysis-critic`
- `workflow-orchestrator`
- `domain-lane-orchestrator`
- `role-profile-architect`

The two orchestrators are fixed outside this procedure; the other nine profiles are eligible for L3 dispatch. `AGENTS.md` and linked contracts remain instruction authorities; profile TOML files define role-specific behavior.

## Dispatcher-only boundary

After `DELEGATED` entry, the parent, L1, and L2 may speak with the user, plan, manage compact queues, start L3, and combine result packets. They must not read or edit target files, inspect logs, use terminal or Git, call scripts, access MCP or runtime state, use the network, or run commands. Every target action requires one bounded L3 assignment selected here. Parent execution is never a fallback.

If an L3 slot is unavailable, return or retain a generic `capacity-wait` state and resume only on a slot-available signal. Never repeatedly poll. Return `DELEGATION_BLOCKED` only when the required installed profile, capability, or dispatch mechanism is unavailable; do not substitute or create a profile.

## Assignment admission

Before role choice, require one concrete assignment with:

- one exact outcome and a new stable `assignment_id`;
- exact target scope, allowed and forbidden actions, risks, and completion criteria;
- sanitized authority and input refs;
- one capability boundary; and
- explicit read-only or mutation mode.

Split mixed read/write outcomes into separate assignment ids. A mutation may include only bounded context and diff inspection intrinsic to its specified change; discovery, diagnosis, research, runtime evidence, or independent review is separate. Reject a stage, repo queue, undecomposed noncanonical task, hidden prerequisite, or widened follow-up.

One packet dispatches one L3 assignment. An L3 returns to its caller and must not redecompose or create L4. L4 requires explicit current-user approval.

## Deterministic L3 role choice

Apply these rules in order and stop at the first match:

1. Choose `role-profile-architect` only when the current user directly requested a concrete semantic role-profile create, merge, split, or delete operation. Never infer this role from a missing profile or another assignment.
2. Choose `app-worker` for a mutation packet containing one valid `app-task-dispatch.v1`. This rule precedes generic mutation; no other packet selects `app-worker`.
3. Choose `wave-change-critic` when the sole outcome is the primary immutable review of one repo wave pinned by exact `base_commit` and `wave_head`. Live `HEAD`, worktree state, or a cross-repo range is invalid.
4. For a read-only assignment whose sole outcome requires one explicitly bounded local diagnostic command, choose `diagnostic-command-runner`. Runtime, service, public-source, test, validation, and mutation work do not match.
5. For a read-only assignment whose sole outcome is current evidence from public primary sources, choose `primary-source-researcher`.
6. For a read-only assignment whose sole outcome is bounded sanitized runtime, service-interface, or runtime-backed automation evidence, choose `runtime-evidence-reader`.
7. Choose `security-analysis-critic` only for a separate read-only security assessment with a deterministic trigger: a trust boundary; secrets, identity, or authorization; callback or ingress; or a promotion/security-sensitive surface. Its methodology and outcome must be distinct from any primary wave review; duplicate critics are forbidden.
8. For any other bounded read-only workspace inspection, choose `explorer`.
9. For any other bounded mutation, choose `worker`.

The caller records the matched rule and concrete fact as `selection_basis`, and copies the selected profile boundary as `capability_boundary`. Neither field may broaden the profile or assignment. Rules 3, 7, and 8 may use intrinsic bounded read-only shell inspection of named files, repository metadata, or pinned diff refs only to acquire assessment evidence; they do not authorize runtime commands, scripts, network, acceptance mechanics, mutation, or a command-outcome assignment.

## `dispatch-packet.v2`

Before dispatch, send every required field:

```yaml
schema: dispatch-packet.v2
task_id: <stable owning task id>
workstream_id: <stable coherent delegated workstream id>
assignment_id: <new concrete assignment id>
stage: <skill or workflow stage>
caller_level: solo-l2|L2
role: <one exact eligible installed profile>
selection_basis: <matched ordered rule and concrete fact>
capability_boundary: <exact selected-profile boundary>
cwd: <exact working directory or none>
target_paths: [<bounded paths or target ids>]
instruction_refs: [<authority files or contracts>]
inputs: [<sanitized stable refs or none>]
stage_payload: <stage-owned fields or none>
allowed_actions: [<explicit actions>]
forbidden_actions: [<explicit exclusions>]
risk: [<security, data, deploy, cross-service, or none>]
completion_criteria: [<observable outcomes>]
return_schema: result-packet.v1
automation_evidence_refs: [<existing autoCI refs or none>]
```

Every field is required. Use `[none]` only where permitted. `inputs` may contain paths, assignment ids, evidence ids, or compact fact ids, never raw bodies, diffs, logs, command dumps, secrets, credentials, tokens, or production data. Return `PACKET_REJECTED` before dispatch when a field is absent, unbounded, unsanitized, role-mismatched, or outside the capability boundary.

### App task stage payload

Rule 2 additionally requires this nested object inside `stage_payload`:

```yaml
app_task_dispatch:
  schema: app-task-dispatch.v1
  task_record: <one current complete canonical task record>
  repo_ref: <task repo ref>
  repo_cwd: <exact repo cwd>
  batch_id: <task batch id>
  wave_id: <task wave id>
  wave_session_id: <stable repo-wave session id>
  queue_sequence: <task queue position>
  session_action: start|continue
  previous_task_result_ref: <null only for start; prior result ref for continue>
```

The caller exposes only the current complete task. Full wave, future task, and queue disclosure is `PACKET_REJECTED`. `start` creates the single app-worker session for `(repo_ref, wave_id)`; `continue` must preserve `repo_ref`, `wave_id`, and `wave_session_id` while using a new task and `assignment_id`.

## Assignment lifecycle

- Normally, a new assignment id, outcome, scope, or role requires a fresh L3. Follow-up is allowed only inside the same assignment with unchanged outcome, role, target scope, and capability boundary.
- The sole cross-assignment reuse exception is `role: app-worker` with unchanged `repo_ref`, `wave_id`, and `wave_session_id` and a valid `session_action: continue`. Every other L3 assignment uses a fresh agent.
- An app-worker receives exactly one task at a time. Its caller accepts that task result before continuing the session; a different repo, wave, session, or role cannot reuse it.
- If an L3 finds additional work, it returns a compact fact and stops. The caller creates a new assignment rather than widening the active one.
- Do not dispatch hidden helpers, automatic or duplicate critics, repeated waits, or polling loops.

## Git and failure boundary

Every write-capable L3 owns its cohesive bounded patch, inspects only its task-owned diff, stages only changed files inside `target_paths`, and creates one task-scoped local conventional commit. It never stages unrelated state. An app task retains exactly one commit when it finishes or preserves a safe coherent partial change; if a failed task's diff is fully removed, it retains no commit and reports that cleanup. A task never creates multiple commits. Read-only L3s do not stage or commit.

A failed canonical app task remains `failed` and is never reopened. Its dependent tasks become not ready; its app-worker session may continue only with later independent ready tasks. Push is a separate assignment requiring explicit current-task authorization, and force-push to a shared branch is forbidden.

## Immutable review boundary

`wave-change-critic` reviews one repo's pinned `base_commit..wave_head`, never live `HEAD` or worktree state. It receives failed task refs as known gaps and cannot fix, mutate, commit, or run autoCI. `security-analysis-critic` is optional only under rule 7 and remains a separate result. There is no aggregate cross-repo review.

## autoCI boundary

autoCI is the only component authorized to execute tests, validators, audits, schemas, lints, cache checks, or plugin validation. L3 agents do not execute, simulate, cachebust, or produce ad hoc acceptance evidence.

Reading existing autoCI evidence is a separate read-only assignment: choose `runtime-evidence-reader` for runtime-, service-, API-, or MCP-backed evidence and `explorer` for generated file evidence. Only authentic evidence for the exact full commit yields `passed` or `failed`; missing, pending, stale, mismatched, or unauthenticated evidence yields `not_run`. `not_run` is nonblocking unless an explicit task or branch policy requires evidence.

## `result-packet.v1`

Every L3 returns:

```yaml
schema: result-packet.v1
task_id: <same task id>
workstream_id: <same workstream id>
assignment_id: <same assignment id>
role: <executed exact role>
status: done|partial|blocked
consumed_input_refs: [<sanitized dispatch refs actually used or none>]
facts: [<compact verified facts>]
files_read: [<exact paths or none>]
files_changed: [<exact paths or none>]
commands_run: [<sanitized command names or none>]
git_state: <commit/status fact or not-applicable>
automation_evidence: [<existing evidence refs or none>]
risks: [<unresolved concrete risk or none>]
next_action: <exact next dispatch, user decision, or none>
```

An app-worker result has exactly one fact:

```yaml
schema: app-task-change.v1
task_id: <same canonical task id>
assignment_id: <same new assignment id>
repo_ref: <same repo ref>
batch_id: <same batch id>
wave_id: <same wave id>
wave_session_id: <same session id>
queue_sequence: <same queue position>
status: done|failed
commit_ref: <retained commit ref or null after full cleanup>
changed_targets: [<exact changed targets or empty after full cleanup>]
cleanup_state: clean|coherent_partial_commit
partial_state_ref: <coherent partial-state ref or null>
```

Reject a result with missing provenance, an invalid app-task fact, multiple app-task facts or commits, or raw bodies, diffs, logs, command dumps, secrets, credentials, tokens, or production data. Do not forward rejected content.

## Failure outcomes

- `DELEGATION_BLOCKED`: the assignment is incomplete or the required exact profile, capability, or dispatch mechanism is unavailable. Report the missing fact and stop dependent work without substitution.
- `PACKET_REJECTED`: a dispatch or result violates schema, bounded scope, capability, session, immutable-review, or sanitized-provenance rules. Require a sanitized replacement.
- Generic `partial` or `blocked`: preserve compact facts and unresolved risk, then require a new bounded assignment or user decision. For app tasks, the nested fact still records canonical `done|failed` and cleanup state.

Never convert failure into parent, L1, or L2 target execution.
