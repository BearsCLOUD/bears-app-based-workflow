---
name: projectdevsubagents
description: "Use for Bears development orchestration from ready GitHub Project work items and linked Issues. Parent controls L2 lanes, L2 uses helper subagents, implementation is done by @Bears L3 workers, and completion is confirmed by a separate L3 critic."
---

# Project Dev Subagents

Use this skill for **development orchestration from ready GitHub Project work items and linked Issues**.

This skill starts after the owning planning flow or an explicit operator packet provides ready work items, owner repo, target paths, dependencies, acceptance criteria, and closeout fields.

## Dictionary

- `task` means one bounded work unit: one GitHub Issue or Project item slice, one repo boundary, one exact target set, one owning role, one execution lane, and one proof requirement.
- `wave` means one parent-dispatched batch of dependency-ready tasks that may run in parallel when their repos and target sets do not overlap.
- Use only `task` and `wave` for orchestration units in this skill. Do not introduce extra unit names.

## Boundary

In scope:

- consume ready GitHub Project items, linked Issues, sub-issues, PR metadata, Actions metadata, Release metadata, and role-routing evidence;
- split ready work into task packets;
- coordinate L2 orchestrators, L2 helper subagents, L3 workers, L3 critics, and gitflow closeout;
- update Project/Issue state only from evidence;
- report exact Project/Issue execution status.

Out of scope:

- creating a new GitHub Project unless an explicit operator packet says so;
- choosing the organization's Project field model;
- replacing roadmap governance;
- replacing issue-type policy;
- replacing repo-local specs, acceptance criteria, or product ownership;
- doing implementation in the parent or L2 lane.

## Required upstream artifacts

Before execution, the parent must provide one of these:

- a ready project-task packet plus a project analysis packet with execution handoff marked ready;
- existing GitHub Project/Issue state plus explicit operator approval that replaces those packets.

The plan must define owner repo, target paths, route-selected roles, dependencies, proof requirement, and closeout fields for every task.

## Required topology

```text
Parent agent
  -> L2 GitHub/project orchestrator subagents
      -> L2 helper subagents for bounded metadata/decomposition/support work
      -> L3 @Bears implementation/review subagents
      -> L3 role-improvement subagent when role gaps appear
      -> L3 critic subagent for every completed task
  -> one persistent gitflow closeout subagent
```

## Parent control lane

The parent agent is orchestration-only. Parent allowed actions:

- select the existing Project, repository set, issue query, L2 lanes, and ready analysis packet;
- start or reuse L2 orchestrators;
- pass Project item ids, Issue ids, PR ids, Actions metadata ids, Release ids, target paths, and role-routing targets;
- wait for L2 evidence packets;
- integrate L2 closeout packets;
- request commit/push closeout through `bears-git-workflow-helper`;
- report exact Project/Issue status.

Parent forbidden actions:

- file writes;
- implementation commands;
- direct Project administration; pass explicit operator-authorized metadata requests to L2 instead;
- `git add`, `git commit`, `git push`, merge, or force push;
- direct PR mutation; pass explicit operator-authorized metadata requests to L2 instead;
- runtime, deploy, provider, secret, repository settings, branch protection, or production mutation.

## L2 orchestrator lane

Each L2 orchestrator must run the `bears-github-project-issues-orchestrator` role. L2 is not a developer. L2 turns ready Project work into bounded tasks.

L2 must use helper subagents for bounded support work when it can run without blocking the critical path. Helper subagents may read assigned metadata, prepare decomposition notes, draft task packets, compare closeout evidence, or prepare Project/Issue update text. Helper subagents must not implement, edit files, commit, push, mutate runtime, or change Project/Issue state unless the parent packet explicitly authorizes that exact metadata action through L2.

L2 allowed actions:

- read assigned Project items and linked Issues, sub-issues, PR metadata, Actions metadata, Releases, labels, milestones, blockers, and dependency notes;
- verify repo/path ownership from the provided routing evidence or exact owner packet;
- classify each item by repo boundary, @Bears role, write scope, proof requirement, and blocker state;
- create or update Issues, sub-issues, links, labels, milestones, assignees, and Project fields only when the parent packet authorizes that exact metadata mutation;
- split work into L3 `/goal` packets;
- spawn L3 workers with route-selected @Bears role names;
- spawn one role-improvement L3 worker when role coverage is missing;
- spawn one L3 critic for every task before marking it done;
- integrate L3 worker and L3 critic closeout into Project and Issue state from evidence.

L2 forbidden actions:

- implementation file writes;
- shell implementation commands;
- commit, push, merge, or force push;
- deploy or runtime mutation;
- repository settings, branch protection, secret, variable, webhook, GitHub App, billing, or environment mutation;
- reading secrets, raw logs, raw chats, raw VPN configs, credentials, or production data.

## L2 execution loop

For each assigned task:

1. Read the ready plan packet, current Project item, linked Issue, sub-issues, linked PRs, Actions/check metadata, and existing field values needed for that task.
2. Identify the canonical owner repo, local path, target paths, issue type, acceptance criteria, and blocker notes.
3. Use helper subagents for bounded metadata/decomposition/support work when useful and safe.
4. If role coverage is missing, create a role-improvement L3 packet and keep the implementation task blocked.
5. Split work into separate tasks when repo boundary, @Bears role, write scope, proof requirement, or deploy/runtime boundary differs.
6. If decomposition is needed, create and link child Issues for the current wave, add only required Project status/linkage metadata, and return decomposition status; do not dispatch implementation in the same wave.
7. Build one L3 worker packet per task only after the child metadata is visible, dependency-ready, and either preexisted or came from a prior parent assignment.
8. Dispatch L3 workers only when the task has exact target paths, allowed actions, forbidden actions, acceptance criteria, and proof requirement.
9. Collect L3 worker closeout packets.
10. Dispatch one L3 critic for each task that claims completion.
11. Update Project/Issue state only from L3 worker evidence, L3 critic confirmation, commit SHA, PR metadata, Release metadata, or blocker proof.
12. Request gitflow closeout when files changed.
13. Report task and wave status to the parent.

## L3 worker lane

- Use the exact @Bears role selected for the target path.
- Use `model=gpt-5.4-mini` and `reasoning=high`.
- One L3 worker assignment covers one task.
- L3 worker must return changed files, proof evidence, blockers, issue/project item ids, requested Project field updates, and forbidden surfaces untouched.
- L3 worker must not directly mutate Project fields unless the L2 packet explicitly asks for a closeout comment or metadata update.

## L3 critic lane

- Use a separate L3 critic subagent for every task that claims completion.
- Use `model=gpt-5.5` and `reasoning=high`.
- Start with no parent context and no start context.
- Provide only the task packet, the L3 worker closeout packet, and the critic review request.
- The critic must confirm whether the task is 100% complete against the task packet.
- The critic must return exactly one of: `TASK_CONFIRMED_100`, `TASK_INCOMPLETE`, or `TASK_BLOCKED`.
- `TASK_CONFIRMED_100` must name the evidence that proves every acceptance criterion and every forbidden surface remained untouched.
- `TASK_INCOMPLETE` must name each missing requirement and the exact next task needed.
- `TASK_BLOCKED` must name the blocker, owner, and issue URL or requested issue placement.
- L2 must not mark a task done without `TASK_CONFIRMED_100` from the critic.

## L3 worker assignment packet

```text
/goal
lane=l3_worker
role=<route-selected @Bears role>
model=gpt-5.4-mini
reasoning=high
github_project_item=<item id/url>
github_issue=<owner/repo#number>
repo=<local path and owner/repo>
task=<one bounded task>
target=<exact files/paths>
metadata_mutation_authorized=<true|false>
allowed_actions=<bounded list>
forbidden_actions=<bounded list>
acceptance_criteria=<issue checklist or Project item requirement>
proof_requirement=<exact evidence required>
completion_criteria=<closeout proof required by L2>
closeout_updates=<Project fields and Issue comment requested from L2>
```

## L3 critic assignment packet

```text
/goal
lane=l3_critic
role=bears-critic
model=gpt-5.5
reasoning=high
context_policy=no_parent_context_no_start_context
input_task_packet=<exact L3 worker assignment packet>
input_worker_closeout=<exact L3 worker closeout packet>
review_request=Confirm whether this task is 100% complete against the task packet.
allowed_actions=<read provided packets only; inspect referenced changed files only when the task packet permits it>
forbidden_actions=<file writes; implementation commands; Project/Issue mutation; commit; push; runtime mutation; secret access>
completion_criteria=<TASK_CONFIRMED_100|TASK_INCOMPLETE|TASK_BLOCKED with required evidence>
```

## Done rule

A task is done only when all required evidence exists for that task:

- L3 worker result for the task;
- `TASK_CONFIRMED_100` from the L3 critic;
- commit SHA and push proof when files changed;
- linked PR, Release, or deployment metadata when required by the task;
- Issue closeout comment text;
- Project/Issue state updates derived from evidence.

A wave is done only when every task in the wave is done, blocked with an explicit owner and issue URL, or deferred into a named later wave.

## GitHub surface coverage

Before L3 dispatch, L2 must inspect and reconcile only the metadata needed for the assigned task:

- Project item ids, linked content ids, field values, status, and blockers;
- Issues, issue types, sub-issues, labels, milestones, assignees, linked branches, linked PRs, and dependencies;
- Pull requests, review state, mergeability metadata, check suite status, and linked issues;
- Actions status metadata without raw log reads;
- Releases, tags, packages, and deployment notes when delivery is in scope;
- Discussions only when the work needs a non-actionable decision record;
- Wiki and Pages metadata only for public knowledge or docs pointers;
- code/security alert metadata only through a security-review route;
- Deployments and Environments metadata only for planning; runtime or environment mutation requires the exact deploy route;
- repository collaboration metadata, including branches, commits, compare output, CODEOWNERS, repository topics, rules metadata, and teams metadata, as read-only planning evidence.

See `references/github-project-issue-flow.md` and `../../docs/reference/github-project-subagents.md` for orchestration sequence and surface matrix.
