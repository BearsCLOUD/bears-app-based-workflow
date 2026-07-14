---
name: subagents
description: Select one installed L3 profile and dispatch one authority-bound assignment through dispatch-packet.v3.
---

# Subagents

## Ownership

Accept only work already classified `DELEGATED` by the active caller instruction chain.

Keep `DIRECT` work with the primary and never route it through this skill.

Require one persistent repo-L2 with role `domain-lane-orchestrator` to own every `DELEGATED` app stage and its repo boundary.

Keep L1-to-repo-L2 lane coordination outside this skill.

Require L1 to use native collaboration with `repo-lane-dispatch.v1` and one persistent repo-L2 session.

Permit a generic non-app delegated caller to use `caller_level: solo-l2` only when its authority packet allows it.

Invoke every L3 only through this skill and never call a named worker, critic, reader, or writer directly.

Never let an L3 append, rewrite, or synthesize a workflow journal event.

## Entry Gate

Apply `delegation-entry.v1` before role selection.

Return `DIRECT_REQUIRED` when delegation authority is missing, stale, invalid, or mismatched.

Return `FRESH_TASK_REQUIRED` when the conversation already contains raw target access that overlaps the delegated scope.

Allow entry only from a clean or compact-reference context and never claim that a mixed context was sanitized retroactively.

Return `DELEGATION_BLOCKED` when the exact profile binding, compatible L3 depth, or required dispatch mechanism is unavailable.

Never substitute a default profile or parent execution.

## Authority

Resolve one immutable `assignment-authority.v1` through the trusted assignment channel before packet construction.

Require byte-identical delegation authority, assignment authority, workstream, repo, trust boundary, role, level, role kind, and session identity across dispatch and result.

Discover role identity from the selected regular non-symlink installed profile and reject packet identity drift.

Derive authority and session lifecycle only from `role_kind`; use specialization only to match the bounded subject and never as a grant.

Treat `task_name` only as a label and bind the selected role through packet identity plus its exact installed `config_file` instruction ref.

Use `fork_turns=none` and set a transport role selector when the transport provides one.

## Assignment Admission

Require one exact outcome, one new assignment id, exact target paths, allowed and forbidden actions, risks, completion conditions, sanitized input refs, one capability boundary, and one read-only or mutation mode.

Split mixed read and write outcomes into separate assignments.

Reject a stage, repo queue, undecomposed task, hidden prerequisite, full wave disclosure, future task disclosure, or widened follow-up.

Permit one packet to dispatch one L3 assignment and require the L3 to return to its caller without creating L4.

## L3 Selection

Apply these rules in order and stop at the first match:

1. Choose `role-profile-architect` only for a concrete role-profile create, merge, split, or delete operation directly requested by the current user.
2. Choose `app-worker` only for a mutation packet containing one valid `app-task-dispatch.v2`.
3. Choose `wave-change-critic` only for the primary read-only review of one repo wave pinned by exact `base_commit` and `wave_head`.
4. Choose `diagnostic-command-runner` only for one bounded local diagnostic command whose result is the sole outcome.
5. Choose `primary-source-researcher` only for current evidence from public primary sources.
6. Choose `graph-evidence-reader` only for bounded evidence from the six declared read-only app-graph MCP tools.
7. Choose `explorer` for any other bounded read-only workspace inspection.
8. Choose `worker` for any other bounded mutation.

Record the matched rule and concrete fact in `selection_basis` and copy the selected profile boundary into `capability_boundary`.

Never let either field broaden the selected profile or assignment.

## Packet Contract

Use `../../contracts/delegation-packets.v2.json` as the single packet authority.

Use only `dispatch-packet.v3`, `result-packet.v2`, and `app-task-dispatch.v2` for new delegated work.

Require every contract field and preserve every authority, identity, session, input, and evidence ref.

Keep packet inputs reference-only and exclude raw authority bodies, diffs, logs, command dumps, secrets, credentials, tokens, and production data.

Treat complete lane, dispatch, result, app-task, and outgoing handoff packets as typed transient protocol inputs.

Preserve the exact authority, assignment, task, role, role kind, profile, and packet-schema identity required by the immutable v3 event `delegation_record`.

Never present an unrepresented packet body as graph evidence.

Return `PACKET_REJECTED` before dispatch or forwarding when a packet is incomplete, unbounded, unsanitized, authority-mismatched, role-mismatched, session-mismatched, or outside capability.

## Session Lifecycle

- Keep mutation-worker and primary-critic sessions persistent only within their authority-bound repo workstream.
- Use `start` or `continue` in dispatch and `continue` or `close` in result.
- Use `followup_task` with a new assignment id for each continuation.
- Reject duplicate starts, concurrent assignments in one session, stale results, identity drift, invalid actions, and reuse after close.
- Start a new app-worker session for a different repo wave.
- Return rereview to the original open critic session.
- Keep helpers nonpersistent with `start`, `close`, and both session ids set to `none`.
- Stop an L3 that discovers additional work and require the caller to create a new bounded assignment.
- Never dispatch hidden helpers, duplicate critics, repeated waits, or polling loops.

## Mutation and Review

Require every write-capable L3 to own one bounded cohesive patch, inspect only its task diff, stage only its target paths, and create at most one task-scoped local commit.

Require a failed app task to retain one coherent partial commit or remove its diff before returning.

Keep a failed canonical task terminal and keep dependent tasks non-ready.

Require `wave-change-critic` to review only its pinned repo range, remain read-only, and return exact findings without mutation.

Require fixes to use a new remediation task and require rereview through the original open critic session.

Keep push as a separate explicitly authorized assignment and forbid force-push to a shared branch.

## Result

Require every L3 to return `result-packet.v2` with consumed input and authority refs, bounded facts, files read, files changed, commands run, Git state, evidence, risks, and next action.

Require an app-worker result to contain one app-task-change fact with matching assignment, task, repo, wave, session, queue, status, commit, changed-target, cleanup, evidence, and source-review refs.

Reject multiple app-task facts, multiple commits, missing provenance, raw payload bodies, or journal mutations.

Return `PACKET_REJECTED`, `DELEGATION_BLOCKED`, `DIRECT_REQUIRED`, or `FRESH_TASK_REQUIRED` exactly when its defined condition occurs.

Never convert a failure into target execution by the parent or repo-L2.
