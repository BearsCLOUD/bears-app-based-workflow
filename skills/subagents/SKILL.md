---
name: subagents
description: Deterministically choose one installed plugin profile and dispatch one bounded L3 assignment after app-dev L2 or solo-L2 decomposition.
---

# Subagents

## Ownership

This procedure receives only work already classified `DELEGATED` under the active caller instruction chain and `/srv/bears/contracts/developer_instructions_contract.md`. `DIRECT` work remains with the primary and never enters this procedure.

`app-dev` owns fixed L1 and L2 orchestration, lane partitioning, and L2 decomposition. It fixes `workflow-orchestrator` at L1 and `domain-lane-orchestrator` at L2; this procedure never selects, starts, or replaces them. Outside app-dev, a solo parent performs the L2 analogue. This procedure owns only deterministic L3 role choice, `dispatch-packet.v2`, bounded L3 dispatch, and `result-packet.v1` handling. It does not classify or decompose work, select a ledger task, or perform target work.

The plugin has exactly these nine profiles:

- `worker`
- `explorer`
- `diagnostic-command-runner`
- `primary-source-researcher`
- `runtime-evidence-reader`
- `security-analysis-critic`
- `workflow-orchestrator`
- `domain-lane-orchestrator`
- `role-profile-architect`

`workflow-orchestrator` and `domain-lane-orchestrator` are fixed outside this procedure; the other seven profiles are eligible for L3 dispatch here. `AGENTS.md` and linked contracts remain instruction authorities; profile TOML files define role-specific behavior.

## Dispatcher-only boundary

After `DELEGATED` entry, the parent, L1, and L2 may speak with the user, plan, decompose, start and manage L3, and combine compact packets. They must not read or edit target files, inspect logs, use a terminal or Git, call scripts, access MCP or runtime state, use the network, or run commands. Every target action requires one bounded L3 assignment selected by this procedure. Parent execution is never a fallback.

Return `DELEGATION_BLOCKED` if the required installed profile, subagent capability, or slot is unavailable. Do not substitute a nearby profile, create a profile, or propose profile creation.

## Assignment admission

Before role choice, require one concrete assignment with:

- one exact outcome and stable `assignment_id`;
- exact target scope, allowed actions, forbidden actions, risks, and completion criteria;
- sanitized authority and input references;
- one capability boundary; and
- an explicit read-only or mutation mode.

Split mixed read/write outcomes into separate assignment ids and choose each role independently. A mutation assignment may include only the bounded context and diff inspection intrinsic to its already-specified change; discovery, diagnosis, research, runtime evidence, or independent review is a separate read-only assignment. Reject a stage, lane, undecomposed task, hidden prerequisite, or widened follow-up.

One packet starts exactly one L3 for exactly one assignment. L3 returns to its caller and must not redecompose the assignment or create L4. L4 requires explicit current-user approval.

## Deterministic L3 role choice

Apply these rules in order and stop at the first match:

1. Choose `role-profile-architect` only when the current user directly requested a concrete semantic role-profile create, merge, split, or delete operation. Never infer this role from a missing profile or another assignment.
2. For a read-only assignment whose sole outcome requires one explicitly bounded local diagnostic command, choose `diagnostic-command-runner`. Runtime, service, public-source, test, validation, and mutation work do not match this rule.
3. For a read-only assignment whose sole outcome is current evidence from public primary sources, choose `primary-source-researcher`.
4. For a read-only assignment whose sole outcome is bounded sanitized runtime, service-interface, or runtime-backed automation evidence, choose `runtime-evidence-reader`.
5. For a read-only assessment of a supplied change that crosses a trust, secret, identity, callback, ingress, or promotion boundary, choose `security-analysis-critic`. Any evidence prerequisite or remediation is a separate assignment.
6. For any other bounded read-only workspace inspection, choose `explorer`.
7. For any other bounded mutation, choose `worker`.

The caller records the matched rule and concrete assignment fact as `selection_basis`, and copies the selected profile's permitted boundary as `capability_boundary`. Neither field may broaden the profile or assignment.

## `dispatch-packet.v2`

Before starting L3, send:

```yaml
schema: dispatch-packet.v2
task_id: <stable owning task id>
workstream_id: <stable coherent delegated workstream id>
assignment_id: <stable concrete assignment id>
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

Every field is required. Use `[none]` only where the schema permits it. `inputs` may contain paths, assignment ids, evidence ids, or compact fact ids, never raw file bodies, diffs, logs, command dumps, secrets, credentials, tokens, or production data. Return `PACKET_REJECTED` before dispatch when a field is absent, scope is not bounded, references are not sanitized, the role does not match the ordered rules, or a field exceeds the selected capability boundary.

## Assignment lifecycle

- An agent reference exists only for its `assignment_id`. The caller may send that agent a follow-up only when the assignment id, outcome, role, target scope, and capability boundary remain unchanged.
- A new outcome, scope, role, or assignment id requires a fresh deterministic choice and a new L3 start. Keep no cross-assignment agent or role-reuse state.
- If an L3 discovers additional work, it returns a compact fact and stops. The caller creates a new assignment rather than widening the active one.
- Do not dispatch hidden helpers, automatic critics, sibling critics, repeated waits, polling loops, or parallel duplicate assessments.

## Git boundary

`worker` owns its full cohesive bounded patch. It inspects only its task-owned diff, stages only its changed files within `target_paths`, and creates one task-scoped local conventional commit. It must not stage unrelated worktree state. Other L3 profiles do not stage or commit.

Push is a separate assignment requiring explicit current-task user authorization. A local commit never implies push, and force-push to a shared branch is forbidden.

## autoCI boundary

autoCI is the only component authorized to execute tests, validators, audits, schemas, lints, cache checks, or plugin validation. Agents do not execute, simulate, cachebust, or produce ad hoc acceptance evidence.

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

Reject a result that omits consumed-input provenance or contains raw file bodies, diffs, logs, command dumps, secrets, credentials, tokens, or production data. Do not merge, forward, or persist rejected content.

## Failure outcomes

These outcomes apply only after `DELEGATED` entry:

- `DELEGATION_BLOCKED`: the assignment is incomplete, the required exact profile is not installed or available, or the subagent tool or required slot cannot start. Report the exact missing field or capability and stop dependent work without substitution or profile proposal.
- `PACKET_REJECTED`: a dispatch or result violates schema, bounded scope, capability, or sanitized-provenance rules. Identify only the violated rule and require a sanitized replacement.
- `partial` or `blocked` L3 result: preserve its compact facts and unresolved risk, then require a new bounded assignment or user decision; do not widen the active assignment.

Never convert a failure into parent, L1, or L2 target execution.
