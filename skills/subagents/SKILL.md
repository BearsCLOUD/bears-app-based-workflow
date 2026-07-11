---
name: subagents
description: Initialize the persistent selector, then select and dispatch bounded L3 helpers, workers, and critics after app-dev L2 or solo-L2 decomposition.
---

# Subagents

## Ownership

This procedure receives only work that the primary already classified `DELEGATED` under the active caller instruction chain and `/srv/bears/contracts/developer_instructions_contract.md`. `DIRECT` work remains with the primary and never enters this procedure. After delegation, the selector chooses L3 execution coverage; it must never decide whether work is `DIRECT` or `DELEGATED`.

This instruction procedure is the sole owner of:

- one persistent selector for each coherent delegated workstream;
- role selection for one concrete L3 assignment;
- selector, helper, worker, and critic lifecycle inside the L3 dispatch boundary;
- `role-request.v1`, `role-selection.v1`, `dispatch-packet.v1`, and `result-packet.v1`.

`app-dev` owns fixed parent-as-L1 orchestration, lane partitioning, and L2 decomposition. Outside app-dev, a solo parent performs the same decomposition as L2. Other `app-*` skills provide stage goals, payloads, outputs, and transitions. This skill never receives or decomposes a task, creates L1 or L2, partitions lanes, chooses ledger tasks, or performs target work. `AGENTS.md` and contracts remain instruction authorities. Role TOML files define only role-specific behavior.

## Hard boundary

This boundary begins only after the primary has classified the work `DELEGATED` under the active caller instruction chain and contract. For an assignment inside that work, parent, L1, and L2 may speak with the user, plan, manage subagents, and combine compact packets. They must not read or edit files, inspect logs, use a terminal or Git, call scripts, access MCP or runtime state, use the network, or run commands.

Every such action for that `DELEGATED` assignment requires an L3 helper, worker, or critic selected through this skill. Missing role registration, selector, subagent capability, or slot returns `DELEGATION_BLOCKED`. Primary execution is never a fallback after `DELEGATED` entry. `DIRECT` work never enters this procedure.

## Selector lifecycle

1. An app-dev L2 receives one `role-selector` agent reference for each coherent workstream in its L1 lane packet. A solo parent acting as L2 creates one selector per coherent workstream.
2. Reuse that read-only selector for every concrete assignment until workstream closeout. Never create a selector per worker or assignment.
3. Send every `role-request.v1` to that agent reference; the caller never selects a role itself.
4. The selector returns exactly one primary role. It may add one helper and one critic.
5. Reuse the selector and, for follow-ups to the same deliverable, the selected role. Replace that role only for terminal failure, changed competence, or a true scope split.
6. End the selector only after workstream closeout.

The selector is a fast, low-cost decision helper. It must explain why the role exists and why it fits this request. If no exact profile fits, it returns `ROLE_GAP`; it must not substitute a nearby role.

When `required_role` is set by an owning procedure, the selector verifies that exact profile's registration, boundary, model, and sandbox. It returns a fail-closed status instead of choosing another role.

## `role-request.v1`

The caller sends this packet directly to its persistent selector:

```yaml
schema: role-request.v1
task_id: <stable owning task id>
workstream_id: <stable coherent delegated workstream id>
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
reuse_role_from: <prior assignment id or none>
stage_payload: <optional app-stage fields>
```

The caller must decompose its task and supply one concrete assignment. Do not ask the selector to inspect task data, split a lane, choose a ledger task, or infer missing scope. Ask it only to choose L3 execution coverage.

## `role-selection.v1`

The selector returns:

```yaml
schema: role-selection.v1
task_id: <same task id>
workstream_id: <same workstream id>
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
reused_from_assignment: <prior assignment id or none>
```

`registration-stale` means the profile exists in the plugin but is not registered. `runtime-reload-required` means registration changed after the current task started. Both fail closed.

## L3 dispatch

- A solo parent acts as the L2 analogue and may start the selected L3 directly for one concrete assignment.
- An app-dev L2 starts the selected L3 for one concrete assignment it decomposed within its L1 lane bounds.
- The caller starts at most one L3 helper, worker, or critic at a time. Run helper before worker and critic after worker when selected.
- L3 returns to its caller. It does not create L4 unless the current user explicitly authorizes that depth.
- L4 is forbidden by default.
- Return `DELEGATION_BLOCKED` when the assignment lacks an exact goal, target scope, allowed actions, or completion criteria. Do not accept a stage, lane, or undecomposed task as an assignment.
- Forbid L3 redecomposition, selector ownership inside L3, sibling critics, and parent execution fallback after delegated entry.
- Do not create assignments for word counts, predicates, waits, cachebuster-only work, or intermediate Git actions. One final Git-closeout assignment is the only Git-assignment exception.

If a selected helper discovers work rather than completing it, the caller defines a new assignment id and sends a new role request to the persistent selector. Do not expand the helper's scope.

## `dispatch-packet.v1`

Before starting L3, send:

```yaml
schema: dispatch-packet.v1
task_id: <stable owning task id>
workstream_id: <stable coherent delegated workstream id>
assignment_id: <stable concrete assignment id>
stage: <skill or workflow stage>
role: <selected exact role>
agent_kind: helper|worker|critic
caller_level: solo-l2|L2
cwd: <exact working directory or none>
target_paths: [<bounded paths or target ids>]
instruction_refs: [<authority files or contracts>]
inputs: [<sanitized known input refs or none; never raw content>]
stage_payload: <stage-owned fields>
allowed_actions: [<explicit actions>]
forbidden_actions: [<explicit exclusions>]
completion_criteria: [<observable outcomes>]
return_schema: result-packet.v1
automation_evidence_refs: [<existing autoCI refs or none>]
```

Every dispatch packet must include `inputs`. Use `[none]` only when the assignment has no upstream input. Each entry must be a sanitized stable reference, such as a path, assignment id, evidence id, or compact fact id. Before starting any L3, return `PACKET_REJECTED` when `inputs` is absent or any packet field contains raw file bodies, logs, command dumps, secrets, credentials, tokens, or production data. Do not copy prohibited content into another field as a substitute for provenance.

Use a workspace reader, runtime evidence, diagnostic command, Git, autoCI evidence, or token-budget helper when that bounded action is required. Never hide helper work inside the parent packet.

## Automation boundary

Do not request machine completion execution, cache activity, cachebusters, or ad hoc evidence production from any agent. External autoCI owns those actions after commit. `automation-status-reader` may project generated evidence only after it exists. Its public `automation-status.v1` object contains exactly `schema`, `status`, `commit`, `timestamp`, and `evidence_ref`; `status` is exactly `passed`, `failed`, or `not_run`. Only an authentic receipt for the exact full commit can produce `passed` or `failed`; missing, pending, stale, mismatched, or unauthenticated evidence produces `not_run`. `not_run` is nonblocking unless an explicit branch or task policy makes evidence mandatory. Missing evidence never authorizes agents to develop or activate autoCI.

## L3 lifecycle

1. Start `helper_role` only when the assignment needs a narrow prerequisite.
2. Convert its compact facts into sanitized known input refs and preserve its `consumed_input_refs` provenance; do not forward raw files or logs.
3. Start `primary_role` with its declared `primary_kind`; one selected editor owns the full cohesive patch rather than file-by-file assignments.
4. Start one `critic_role` for the combined diff or acceptance surface. A critic reports findings; it does not silently widen or rewrite worker scope.
5. If fixes are needed, define a follow-up assignment in the same workstream, set `reuse_role_from`, and reuse the same editor and critic for correction and reassessment unless terminal failure, changed competence, or a true scope split requires replacement.
6. After critic acceptance, create exactly one distinct final Git-closeout assignment. Keep the same `task_id`, `workstream_id`, and selector; use a new `assignment_id` and set `reuse_role_from` to the accepted patch assignment. This separate permission and deliverable boundary is the sole Git-assignment exception.
7. Merge compact results and close the workstream only after Git closeout or an exact Git-boundary blocker. The caller closes the owning task after all workstreams finish.
8. Do not issue repeated waits, polling loops, or parallel duplicate critics from this lifecycle.

## `result-packet.v1`

Every L3 returns:

```yaml
schema: result-packet.v1
task_id: <same task id>
workstream_id: <same workstream id>
assignment_id: <same assignment id>
role: <executed role>
agent_kind: helper|worker|critic
status: done|partial|blocked
consumed_input_refs: [<sanitized dispatch input refs actually used or none>]
facts: [<compact verified facts>]
files_read: [<exact paths or none>]
files_changed: [<exact paths or none>]
commands_run: [<sanitized command names or none>]
git_state: <commit/status fact or not-applicable>
automation_evidence: [<existing evidence refs or none>]
risks: [<unresolved concrete risk or none>]
next_action: <exact next dispatch, user decision, or none>
```

Every result must include `consumed_input_refs` and may cite only sanitized references from the dispatch packet. Do not return raw file bodies, logs, command dumps, secrets, credentials, tokens, or production data. Reject and do not merge, forward, or persist a result that omits consumed-input provenance or contains prohibited content.

## Failure outcomes

These outcomes apply only to work already classified `DELEGATED`; `DIRECT` work never enters this procedure.

- `ROLE_GAP`: no installed role has the required boundary, model, and sandbox. Route the role proposal to `role-profile-architect`; do not execute the dependent assignment.
- `DELEGATION_BLOCKED`: the concrete assignment is incomplete, or the selector, subagent tool, required slot, or selected role cannot start. Report the missing field or capability and stop the dependent work.
- `PACKET_REJECTED`: a dispatch or result packet lacks required input provenance or contains prohibited raw content. Reject it before L3 start or result consumption, identify only the violated rule, and require a sanitized replacement.
- `registration-stale`: run the explicit plugin installer through an authorized L3 config helper or operator, then start a new task.
- `runtime-reload-required`: start a new Codex task before dispatch.

Never convert these outcomes into parent execution after `DELEGATED` entry.
