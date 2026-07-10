---
name: subagents
description: Initialize the persistent selector, then select and dispatch bounded L3 helpers, workers, and critics after app-dev L2 or solo-L2 decomposition.
---

# Subagents

## Ownership

This instruction procedure is the sole owner of:

- role selection for one concrete L3 assignment;
- selector, helper, worker, and critic lifecycle inside the L3 dispatch boundary;
- `role-request.v1`, `role-selection.v1`, `dispatch-packet.v1`, and `result-packet.v1`.

`app-dev` owns fixed parent-as-L1 orchestration, lane partitioning, and L2 decomposition. Outside app-dev, a solo parent performs the same decomposition as L2. Other `app-*` skills provide stage goals, payloads, outputs, and transitions. This skill never receives or decomposes a task, creates L1 or L2, partitions lanes, chooses ledger tasks, or performs target work. `AGENTS.md` and contracts remain instruction authorities. Role TOML files define only role-specific behavior.

## Hard boundary

Parent, L1, and L2 may speak with the user, plan, manage subagents, and combine compact packets. They must not read or edit files, inspect logs, use a terminal or Git, call scripts, access MCP or runtime state, use the network, or run commands.

Every such action requires an L3 helper, worker, or critic selected through this skill. Missing role registration, selector, subagent capability, or slot returns `DELEGATION_BLOCKED`. Direct execution is never a fallback.

## Selector lifecycle

1. An app-dev L2 receives one `role-selector` agent reference in its L1 lane packet. A solo parent acting as L2 creates that selector once.
2. Reuse the same read-only selector for every concrete assignment until closeout. Never create a selector per worker.
3. Send every `role-request.v1` to that agent reference; the caller never selects a role itself.
4. The selector returns exactly one primary role. It may add one helper and one critic.
5. Reuse the selector after partial results or a changed assignment. End it only after task closeout.

The selector is a fast, low-cost decision helper. It must explain why the role exists and why it fits this request. If no exact profile fits, it returns `ROLE_GAP`; it must not substitute a nearby role.

When `required_role` is set by an owning procedure, the selector verifies that exact profile's registration, boundary, model, and sandbox. It returns a fail-closed status instead of choosing another role.

## `role-request.v1`

The caller sends this packet directly to its persistent selector:

```yaml
schema: role-request.v1
task_id: <stable owning task id>
assignment_id: <stable concrete assignment id>
caller_level: solo-l2|L2
goal: <one exact outcome>
work_kind: <concrete action class>
target_zone: <repo, runtime target, or bounded surface>
instruction_refs: [<already-known authority refs>]
allowed_actions: [<explicit actions>]
forbidden_actions: [<explicit exclusions>]
risk: [<security, data, deploy, cross-service, or none>]
dependencies: [<closed prerequisite ids>]
expected_output: <one compact result>
required_role: <exact role when an owning procedure mandates one; otherwise none>
stage_payload: <optional app-stage fields>
```

The caller must decompose its task and supply one concrete assignment. Do not ask the selector to inspect task data, split a lane, choose a ledger task, or infer missing scope. Ask it only to choose L3 execution coverage.

## `role-selection.v1`

The selector returns:

```yaml
schema: role-selection.v1
task_id: <same task id>
assignment_id: <same assignment id>
status: selected|ROLE_GAP|registration-stale|runtime-reload-required
primary_role: <one exact installed role or null>
primary_kind: helper|worker|critic|null
role_purpose: <why this role was created>
selection_reason: <why it matches this assignment>
model: <profile model>
model_reasoning_effort: <profile effort>
sandbox_mode: read-only|workspace-write
exact_goal: <bounded L3 goal>
target_scope: <exact paths, target ids, or bounded surface>
helper_role: <optional exact role>
critic_role: <optional exact role>
```

`registration-stale` means the profile exists in the plugin but is not registered. `runtime-reload-required` means registration changed after the current task started. Both fail closed.

## L3 dispatch

- A solo parent acts as the L2 analogue and may start the selected L3 directly for one concrete assignment.
- An app-dev L2 starts the selected L3 for one concrete assignment it decomposed within its L1 lane bounds.
- The caller starts at most one L3 helper, worker, or critic at a time. Run helper before worker and critic after worker when selected.
- L3 returns to its caller. It does not create L4 unless the current user explicitly authorizes that depth.
- L4 is forbidden by default.
- Return `DELEGATION_BLOCKED` when the assignment lacks an exact goal, target scope, allowed actions, or completion criteria. Do not accept a stage, lane, or undecomposed task as an assignment.

If a selected helper discovers work rather than completing it, the caller defines a new assignment id and sends a new role request to the persistent selector. Do not expand the helper's scope.

## `dispatch-packet.v1`

Before starting L3, send:

```yaml
schema: dispatch-packet.v1
task_id: <stable owning task id>
assignment_id: <stable concrete assignment id>
stage: <skill or workflow stage>
role: <selected exact role>
agent_kind: helper|worker|critic
caller_level: solo-l2|L2
cwd: <exact working directory or none>
target_paths: [<bounded paths or target ids>]
instruction_refs: [<authority files or contracts>]
inputs: [<known input refs; no raw secret content>]
stage_payload: <stage-owned fields>
allowed_actions: [<explicit actions>]
forbidden_actions: [<explicit exclusions>]
completion_criteria: [<observable outcomes>]
return_schema: result-packet.v1
automation_evidence_refs: [<existing autoCI refs or none>]
```

Use a workspace reader, runtime evidence, diagnostic command, Git, autoCI evidence, or token-budget helper when that bounded action is required. Never hide helper work inside the parent packet.

## Automation boundary

Do not request tests, validators, audits, cache checks, cachebusters, quick validation, or plugin validation from any agent. External autoCI runs those after commit. `autoci-evidence-reader` may read generated evidence only after it exists. Pending or missing evidence is never `PASS`.

## L3 lifecycle

1. Start `helper_role` only when the assignment needs a narrow prerequisite.
2. Convert its `result-packet.v1` into known inputs; do not forward raw files or logs.
3. Start `primary_role` with its declared `primary_kind`; it owns the assignment outcome.
4. Start `critic_role` only for the selected risk or acceptance surface. A critic reports findings; it does not silently widen or rewrite worker scope.
5. If fixes are needed, define a new assignment, ask the selector for the correct worker, and issue a new packet.
6. Merge compact results and close the assignment only when its completion criteria are met. The caller closes the owning task after all assignments finish.

## `result-packet.v1`

Every L3 returns:

```yaml
schema: result-packet.v1
task_id: <same task id>
assignment_id: <same assignment id>
role: <executed role>
agent_kind: helper|worker|critic
status: done|partial|blocked
facts: [<compact verified facts>]
files_read: [<exact paths or none>]
files_changed: [<exact paths or none>]
commands_run: [<sanitized command names or none>]
git_state: <commit/status fact or not-applicable>
automation_evidence: [<existing evidence refs or none>]
risks: [<unresolved concrete risk or none>]
next_action: <exact next dispatch, user decision, or none>
```

Do not return raw file bodies, logs, command dumps, secrets, or production data.

## Failure outcomes

- `ROLE_GAP`: no installed role has the required boundary, model, and sandbox. Route the role proposal to `role-profile-architect`; do not execute the dependent assignment.
- `DELEGATION_BLOCKED`: the concrete assignment is incomplete, or the selector, subagent tool, required slot, or selected role cannot start. Report the missing field or capability and stop the dependent work.
- `registration-stale`: run the explicit plugin installer through an authorized L3 config helper or operator, then start a new task.
- `runtime-reload-required`: start a new Codex task before dispatch.

Never convert these outcomes into parent execution.
