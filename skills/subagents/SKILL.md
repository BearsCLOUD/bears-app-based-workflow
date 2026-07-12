---
name: subagents
description: Deterministically choose an installed L3 profile, dispatch typed bounded work, and preserve authority-bound worker and critic sessions.
---

# Subagents

## Ownership

This procedure receives only work already classified `DELEGATED` under the active caller instruction chain. `DIRECT` work remains with the primary and never enters this procedure.

Before selection, apply `delegation-entry.v1`. A missing, invalid, stale, or mismatched delegation gate returns `DIRECT_REQUIRED` and leaves the primary in DIRECT mode. If this conversation already contains raw filesystem, log, runtime, network, or tool access overlapping the delegated target, return `FRESH_TASK_REQUIRED` before selection or dispatch. A conversation containing only sanitized compact refs is eligible. The replacement task must enter DELEGATED before target access; this procedure cannot sanitize an already mixed conversation retroactively.

`app-dev` fixes `workflow-orchestrator` at L1 and one persistent `domain-lane-orchestrator` L2 per repo workflow. Outside app-dev, a solo parent performs the L2 analogue. This procedure owns only deterministic L3 role choice, `dispatch-packet.v2`, bounded dispatch, and `result-packet.v1` handling. It does not classify or decompose work, choose a canonical task, manage a repo queue, or perform target work.

The installed `agents/*.toml` files are the active catalog. Profiles that declare orchestration are fixed outside L3 selection; all other profiles are eligible only through the ordered rules below. `AGENTS.md` and linked caller contracts remain instruction authorities; profile TOML files define role-specific behavior.

Each profile declares one `Role identity` line in `developer_instructions`: exact profile name, level, and trusted `role_kind`. Discover this metadata from the same regular non-symlink TOML catalog; never maintain a fixed role list or count. A packet role or role kind that differs from the selected profile identity is `PACKET_REJECTED`.

## Trusted authority and typed dispatch

Before packet construction, resolve one immutable `assignment-authority.v1` through the trusted assignment channel. It must bind the existing `delegation_authority_ref`, `assignment_authority_ref`, `workstream_id`, opaque canonical `repo_ref`, nonempty `trust_boundary`, exact role, agent level, derived role kind, and `security_trigger_ref`. Packet identity must match byte-for-byte. Do not normalize a repo ref, accept an alias, infer authority from the packet, or copy security predicate facts into packet inputs.

Dispatch follows `typed-agent-dispatch.v1`: call the subagent transport with explicit `agent_type=<selected profile>` and `fork_turns=none`. `task_name` is only a task label and never selects or proves a role. If the available transport cannot set an explicit agent type, the exact profile is unavailable, or compatible L3 depth is unavailable, return `DELEGATION_BLOCKED` before spawn and target access. Never substitute `default`, encode the role in `task_name`, or fall back to parent execution.

Only `caller_level: L2|solo-l2` may dispatch L3. In app-dev, L1 creates the typed `domain-lane-orchestrator` L2 and never calls this procedure as an L3 recipient.

## Dispatcher-only boundary

After `DELEGATED` entry, the parent, L1, and L2 may speak with the user, plan, manage compact queues, start L3, and combine result packets. They must not read or edit target files, inspect logs, use terminal or Git, call scripts, access MCP or runtime state, use the network, or run commands. Every target action requires one bounded L3 assignment selected here. Parent execution is never a fallback.

Only an app-dev persistent `domain-lane-orchestrator` repo-L2 may retain `capacity-wait` when an L3 slot is unavailable; it resumes only on a slot-available signal and never polls. For every generic, solo-L2, or otherwise non-app delegated assignment, slot exhaustion returns `DELEGATION_BLOCKED`; do not wait, poll, substitute, or create a profile.

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
7. Choose `security-analysis-critic` only for a separate read-only security assessment whose trusted assignment authority supplies a named `security_trigger_ref` backed by a satisfied trust-boundary, secrets/identity/authorization, callback/ingress, or promotion-sensitive predicate. Packet-supplied trigger facts, unknown predicates, and unsatisfied predicates are invalid. Its methodology and outcome must be distinct from any primary wave review; duplicate critics are forbidden.
8. For any other bounded read-only workspace inspection, choose `explorer`.
9. For any other bounded mutation, choose `worker`.

The caller records the matched rule and concrete fact as `selection_basis`, and copies the selected profile boundary as `capability_boundary`. Neither field may broaden the profile or assignment. Rules 3, 7, and 8 may use intrinsic bounded read-only shell inspection of named files, repository metadata, or pinned diff refs only to acquire assessment evidence; they do not authorize runtime commands, scripts, network, acceptance mechanics, mutation, or a command-outcome assignment.

## Packet contract

`../../contracts/delegation-packets.v1.json` is the single active definition for `delegation-entry.v1`, `assignment-authority.v1`, `typed-agent-dispatch.v1`, `dispatch-packet.v2`, `result-packet.v1`, and `app-task-dispatch.v1`. Every delegated start uses an explicit agent type and `fork_turns=none`; inherited conversation context and parent execution fallback are forbidden.

Every contract field is required. Dispatch and result preserve `delegation_authority_ref`, `assignment_authority_ref`, `workstream_id`, `assignment_id`, `repo_ref`, `trust_boundary`, `security_trigger_ref`, role, agent level, role kind, and role-specific session identity. Use `[none]` only where the stage permits it. `inputs` may contain paths, assignment ids, evidence ids, or compact fact ids, never raw authority facts, bodies, diffs, logs, command dumps, secrets, credentials, tokens, or production data. Return `PACKET_REJECTED` before dispatch when a field is absent, unbounded, unsanitized, authority-mismatched, role-mismatched, or outside the capability boundary.

### App task stage payload

Rule 2 additionally requires the contract's `app-task-dispatch.v1` object inside `stage_payload`. The caller exposes only the current complete task. Full wave, future task, and queue disclosure is `PACKET_REJECTED`. `start` creates the single app-worker session for `(repo_ref, wave_id)`; `continue` must preserve `repo_ref`, `wave_id`, and `wave_session_id` while using a new task and `assignment_id`.

## Assignment lifecycle

- Persistent mutation workers and critics use stable role-specific session ids. Their immutable identity is the authority refs, repo, workstream, role, role kind, trust boundary, security trigger, and session id.
- Dispatch permits `session_action: start|continue`; a paired result permits `continue|close`. `continue` uses `followup_task` on the exact open session with a new assignment id. Reject duplicate starts, identity drift, dispatch `close`, result `start`, stale results, and reuse after close.
- A fix returns to the original mutation-worker session. Rereview returns to the original primary-critic session. At most one assignment is active per session.
- Helpers are nonpersistent: dispatch `start`, result `close`, both session ids `none`, and no reuse. Tombstone the closed assignment id.
- An app-worker receives exactly one task at a time. Its caller accepts that task result before continuing; a different repo, workstream, role, or authority cannot reuse it. Logical wave ids remain governed by `app-task-dispatch.v1` inside the stable outer worker session.
- If an L3 finds additional work, it returns a compact fact and stops. The caller creates a new bounded assignment without widening authority.
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

Every L3 returns the exact result envelope and statuses defined by the plugin-local packet contract.

An app-worker result has exactly one fact:

```yaml
schema: app-task-change.v1
assignment_id: <same new assignment id>
task_id: <same canonical task id>
repo_ref: <same repo ref>
wave_id: <same wave id>
wave_session_id: <same session id>
worker_session_id: <same outer worker session id>
queue_sequence: <same queue position>
wave_result_action: continue|close
status: done|failed
commit_ref: <retained commit ref or null after full cleanup>
changed_targets: [<exact changed targets or empty after full cleanup>]
cleanup_state: clean|coherent_partial_commit
partial_state_ref: <coherent partial-state ref or null>
source_review_refs: [<same canonical task source review refs or none>]
```

Reject a result with missing provenance, an invalid app-task fact, multiple app-task facts or commits, or raw bodies, diffs, logs, command dumps, secrets, credentials, tokens, or production data. Do not forward rejected content.

## Failure outcomes

- `DIRECT_REQUIRED`: delegation authority is absent or invalid; remain DIRECT and do not initialize selection.
- `FRESH_TASK_REQUIRED`: overlapping raw DIRECT target access already occurred in this conversation; restart the delegated work in a clean task.
- `DELEGATION_BLOCKED`: the assignment is incomplete, a non-app delegated assignment has no available L3 slot, or the required exact profile, capability, or dispatch mechanism is unavailable. Report the missing fact and stop dependent work without substitution.
- `PACKET_REJECTED`: a dispatch or result violates schema, bounded scope, capability, session, immutable-review, or sanitized-provenance rules. Require a sanitized replacement.
- Generic `partial` or `blocked`: preserve compact facts and unresolved risk, then require a new bounded assignment or user decision. For app tasks, the nested fact still records canonical `done|failed` and cleanup state.

Never convert failure into parent, L1, or L2 target execution.
