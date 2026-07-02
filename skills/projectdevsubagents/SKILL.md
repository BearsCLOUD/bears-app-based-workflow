---
name: projectdevsubagents
description: "Use for Bears development orchestration from GitHub Projects and Issues where the parent controls only L2 orchestrators, L2 orchestrators control only Project/Issue state and L3 assignments, and all implementation is executed by @Bears L3 subagents with gpt-5.4-mini high."
---

# Project Dev Subagents

Use this skill for **development orchestration from GitHub Project work items**.

This skill does not define GitHub Project administration. Project administration means creating Projects, choosing fields, designing views, building roadmap structure, and setting long-lived planning policy. That belongs to `$app-docs2project-bears` or the owning repo/workstream governance. This skill starts after a Project or issue set exists, `$bears-project-analyze` has returned `pass` or an operator-approved advisory handoff, and the parent provides ready Project/Issue state for orchestration.

## Boundary

In scope:

- consume GitHub Project items, linked Issues, sub-issues, PR metadata, Actions metadata, Release metadata, and route/audit results;
- split Project work into L3 assignment packets;
- coordinate L2 orchestrators and L3 workers;
- update Project/Issue state only from evidence;
- request gitflow closeout;
- report exact Project/Issue execution status.

Out of scope:

- creating a new Project unless an explicit operator packet says so;
- deciding the organization's Project field model;
- replacing roadmap governance;
- replacing issue-type policy;
- replacing repo-local specs, acceptance criteria, or product ownership;
- doing implementation in the parent or L2 lane.

## Apps repo boundary

For `BearsCLOUD/apps`, `apps` is the repository name and `/srv/bears/dev/app` is the local repo root. Do not create or route `/srv/bears/dev/app/apps`.

Project-management policy may choose one canonical Project for `BearsCLOUD/apps` or another approved structure. This skill consumes that Project/Issue state and treats app directories or legacy source repos as work items, Issues, or sub-issues according to that policy.

## Required upstream artifacts

Before execution, the parent must provide one of these:

- `app-docs2project-bears.project-task-packet` plus `bears-project.analysis-packet` with `execution_handoff=ready`;
- existing GitHub Project/Issue state plus explicit operator approval that replaces those packets.

The plan must define owner repo, target paths, route-selected roles, dependencies, validation, and closeout fields for every item.

## Required topology

```text
Parent agent
  -> L2 GitHub/project orchestrator subagents
      -> L3 @Bears implementation/review subagents
      -> L3 role-improvement subagent when role gaps appear
  -> one persistent gitflow closeout subagent
```

## Parent control lane

The parent agent is orchestration-only. Parent allowed actions:

- select the existing Project, repository set, issue query, L2 lanes, and ready analysis packet;
- start or reuse L2 orchestrators;
- pass Project item ids, Issue ids, PR ids, Actions metadata ids, Release ids, and route/audit targets;
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

Each L2 orchestrator must use `bears-github-project-issues-orchestrator`. L2 is not a developer. L2 turns Project work into bounded L3 tasks.

## First-minute parent gate

Immediately after assignment receipt, before route/audit, issue enrichment, Project field reads beyond the assigned item, or file reads beyond the issue title/body, L2 must answer the parent inside 60 seconds with exactly one of these packets:

- `FAST_BLOCKER`: no writes, no metadata mutation, no L3 dispatch. Use this when deterministic completion inside the parent wait gate is not already proven.
- `FIRST_MINUTE_PASS`: deterministic proof that the child-only execution path can finish inside the parent wait gate, including the preexisting child Issue or approved issue template, exact repo/path boundary, route target, role target, write scope, validation path, worker path, closeout path, and remaining time budget.

A later `PASS`, `READY`, or closeout after the first 60 seconds does not satisfy this gate. Classify it as workflow drift, not success.

For tiny child-only slices, L2 may dispatch L3 only when the first-minute packet cites one of these precomputed paths:

- a precomputed child-Issue template that already defines repo, target files, role, allowed writes, validation, and closeout fields; or
- a deterministic patch-template path for a one-file slice with exact validation and rollback instructions.

If neither path exists, L2 must return `FAST_BLOCKER` or decompose to a smaller child-only Issue instead of attempting implementation.

Repeated first-minute gate misses after issue #17 or issue #18 are active workflow drift. Before retrying the product child, open or fix a new drift issue in the owning repository and link the missed run evidence.

L2 allowed actions:

- read assigned Project items and linked Issues, sub-issues, PR metadata, Actions metadata, Releases, labels, milestones, blockers, and dependency notes;
- verify repo/path ownership through route/audit;
- classify each item by repo boundary, @Bears role, write scope, validation path, and blocker state;
- create or update Issues, sub-issues, links, labels, milestones, assignees, and Project fields only when the parent packet authorizes metadata mutation;
- split work into L3 `/goal` packets;
- spawn L3 workers with route-selected @Bears role names;
- spawn one role-improvement L3 worker when route/audit exposes role drift;
- integrate L3 closeout into Project and Issue state from evidence.

L2 forbidden actions:

- implementation file writes;
- shell implementation commands;
- commit, push, merge, or force push;
- deploy or runtime mutation;
- repository settings, branch protection, secret, variable, webhook, GitHub App, billing, or environment mutation;
- reading secrets, raw logs, raw chats, raw VPN configs, credentials, or production data.

## Decomposition and retry rules

- Parent talks to L2 only; L2 talks to L3 only.
- The first-minute parent gate is mandatory before all decomposition, route/audit, metadata enrichment, file reads, or L3 dispatch.
- When decomposition is needed, L2 must create and link child Issues, add each child to the GitHub Project, and then return `DECOMPOSED_ONLY`.
- `DECOMPOSED_ONLY` means no L3 dispatch in the same five-minute wave.
- One decomposition wave may create at most two child Issues unless a precomputed child-Issue template has explicit operator approval.
- If more than two child Issues are needed, L2 creates the first two, records dependency/order links, sets only required status/linkage metadata, and returns `PARTIAL_DECOMPOSED_ONLY` before the five-minute parent wait expires.
- `PARTIAL_DECOMPOSED_ONLY` means remaining child Issues and optional Project field fills are deferred to later parent assignments; no L3 dispatch in that wave.
- During decomposition, postpone optional Project field fills and avoid broad Project field work in the same wave.
- Returning `DECOMPOSED_ONLY` or `PARTIAL_DECOMPOSED_ONLY` before timeout has priority over complete metadata cleanup.
- If required child metadata already exists before assignment, L2 may proceed child-by-child after verifying each child is visible and dependency-ready.
- For a tiny child-only slice, check direct worker, precomputed child-Issue template, and deterministic patch-template availability within the first minute; if none is confirmed, return `FAST_BLOCKER` immediately and do not start a slow implementation attempt.
- If the direct worker path is available, use it for the tiny child-only slice; do not wrap that launch in nested codex exec.
- If the direct worker path is unavailable but the prewritten patch-template fallback is confirmed, use that one-file slice path; do not invent a new edit flow.
- Before any L3 spawn, compare remaining budget against runner startup plus edit validation; if the budget cannot cover both, stop and return a blocker instead of starting L3.
- These decomposition limits do not widen metadata mutation authority; parent/operator authorization is still required.
- The first child execution is a separate parent assignment after the child Issue and Project metadata are visible.
- Do not combine decomposition and first L3 execution in one five-minute wave.
- After a tiny-slice timeout, retry only that child slice with a child-only packet; skip broad discovery.
- Keep issue #65's codex exec 60s timeout before edits and issue #59's parent >5min cleanup rule; these guardrails do not widen authority. If issue #65 timeout repeats after issue #16, treat it as repeated timeout drift and return `FAST_BLOCKER` instead of starting a slow implementation attempt.
- `RESET` and `CLEANUP` packets are terminal; do not continue or start L3 after either packet.
- When the parent sends timeout `RESET` or `CLEANUP`, L2 must stop waiting on L3 at once, ignore any late L3 `READY` or `PASS`, and return `DRIFT_CLEANED`.
- After timeout `RESET` or `CLEANUP`, post-timeout evidence must be comments only; do not change Project fields, issue state, or closeout state from late output.
- A timeout `READY` result is rejected; close uncommitted work and do not commit or push.
- Late `READY` or `PASS` after timeout `RESET` or `CLEANUP` is rejected, even if the child work finished.
- Parallel L2 fan-out is allowed only for dependency-ready disjoint scopes.
- Parent timeout after combined decomposition + execution is workflow drift, even when no files changed.
- If the same timeout or first-minute drift repeats after issue #17 or issue #18, open a new active drift issue, link it to the original evidence, and do not retry the product child until that drift is fixed.
- Regression example: `BearsCLOUD/apps#38` -> `#45` and `#46`; L2 started L3 `019f2437-d47a-7590-b8fe-37c02d7a49d5`; parent wait exceeded five minutes; the worker was interrupted; no files changed in `/srv/bears/dev/app/callsaver`.

## L2 execution loop

For each assigned Project item or Issue:

1. Read only the assigned item identifier and issue title/body, then return `FAST_BLOCKER` or `FIRST_MINUTE_PASS` to the parent inside 60 seconds.
2. If `FIRST_MINUTE_PASS` was returned, load only the ready plan/analysis packet, current Project item, linked Issue, sub-issues, linked PRs, Actions/check metadata, and existing field values required by that pass proof.
3. Identify the canonical owner repo, local path, target paths, issue type, acceptance criteria, and blocker notes.
4. Run route/audit for the target path.
5. If route/audit returns `ROLE_COVERAGE_BLOCKER`, create a role-improvement L3 packet and keep the implementation item blocked.
6. Split work when repo boundary, @Bears role, write scope, validation path, or deploy/runtime boundary differs.
7. If decomposition is needed, create and link at most two child Issues per wave, add only required Project status/linkage metadata, and return `DECOMPOSED_ONLY` or `PARTIAL_DECOMPOSED_ONLY`; do not dispatch L3 in the same wave.
8. Build one L3 packet per split only after the child metadata is visible, dependency-ready, and either preexisted or came from a prior parent assignment.
9. Validate every materialized L3 packet only through local-commit-owned or operator-approved `python3 scripts/github_project_subagents.py validate-assignment <packet.json>` evidence.
10. Dispatch L3 workers only when the first-minute proof remains true after route/audit and required metadata checks.
11. Collect L3 closeout packets.
12. Update Project/Issue state only from L3 evidence, validation proof, commit SHA, PR metadata, Release metadata, or blocker proof.
13. Request gitflow closeout when files changed.
14. Report item status to the parent.

## L3 worker lane

- Use the exact @Bears role returned by route/audit.
- Use `model=gpt-5.4-mini` and `reasoning=high`.
- One L3 assignment covers one issue or Project item slice, one repo boundary, one allowed write scope, and one validation path.
- L3 must return changed files, validation evidence, blockers, issue/project item ids, requested Project field updates, and forbidden surfaces untouched.
- L3 must not directly mutate Project fields unless the L2 packet explicitly asks for a closeout comment or metadata update.

## L3 assignment packet

```text
/goal
lane=l3
role=<route-selected @Bears role>
model=gpt-5.4-mini
reasoning=high
github_project_item=<item id/url>
github_issue=<owner/repo#number>
repo=<local path and owner/repo>
target=<exact files/paths>
route_audit_evidence=<route/audit command result or packet id>
metadata_mutation_authorized=<true|false>
allowed_actions=<bounded list>
forbidden_actions=<bounded list>
acceptance_criteria=<issue checklist or Project item requirement>
validation=<exact commands or metadata checks>
completion_criteria=<closeout proof required by L2>
closeout_updates=<Project fields and Issue comment requested from L2>
```

## Done rule

L2 may mark the work done only when the closeout packet contains:

- L3 result for every split;
- validation PASS or explicit blocker issue;
- commit SHA and push proof when files changed;
- linked PR, Release, or deployment metadata when required by the item;
- Issue closeout comment text;
- Project/Issue state updates derived from evidence.

## GitHub surface coverage

Before L3 dispatch, L2 must inspect and reconcile only the metadata needed for the assigned item:

- Project item ids, linked content ids, field values, status, and blockers;
- Issues, issue types, sub-issues, labels, milestones, assignees, linked branches, linked PRs, and dependencies;
- Pull requests, review state, mergeability metadata, check suite status, and linked issues;
- Actions status metadata without raw log reads;
- Releases, tags, packages, and deployment notes when delivery is in scope;
- Discussions only when the work needs a non-actionable decision record;
- Wiki and Pages metadata only for public knowledge or docs pointers;
- Code scanning, secret scanning alert metadata, Dependabot alerts, and security advisories only through a security-review route;
- Deployments and Environments metadata only for planning; runtime or environment mutation requires the exact deploy route;
- Repository collaboration metadata, including branches, commits, compare output, CODEOWNERS, repository topics, rules metadata, and teams metadata, as read-only planning evidence.

## Required gates

Agent-local route gates before L2 or L3 dispatch:

```bash
python3 scripts/platform_roles.py route <target-path>
python3 scripts/platform_roles.py audit <target-path>
```

CI/local-commit-owned or operator-approved validator before closeout after changes to this skill, the GitHub orchestrator role, or the GitHub Project subagent catalog:

```bash
python3 scripts/github_project_subagents.py validate  # local-commit-owned
```

CI/local-commit-owned or operator-approved assignment-packet validator before L2 or L3 dispatch when packet files are materialized:

```bash
python3 scripts/github_project_subagents.py validate-assignment <packet.json>  # local-commit-owned
```

See `references/github-project-issue-flow.md` and `../../docs/reference/github-project-subagents.md` for the exact orchestration sequence and surface matrix.
