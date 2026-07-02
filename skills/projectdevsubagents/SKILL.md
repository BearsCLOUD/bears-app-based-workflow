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

## L2 execution loop

For each assigned Project item or Issue:

1. Load the ready plan/analysis packet, current Project item, linked Issue, sub-issues, linked PRs, Actions/check metadata, and existing field values.
2. Identify the canonical owner repo, local path, target paths, issue type, acceptance criteria, and blocker notes.
3. Run route/audit for the target path.
4. If route/audit returns `ROLE_COVERAGE_BLOCKER`, create a role-improvement L3 packet and keep the implementation item blocked.
5. Split work when repo boundary, @Bears role, write scope, validation path, or deploy/runtime boundary differs.
6. Build one L3 packet per split.
7. Validate every materialized L3 packet only through local-commit-owned or operator-approved `python3 scripts/github_project_subagents.py validate-assignment <packet.json>` evidence.
8. Dispatch L3 workers.
9. Collect L3 closeout packets.
10. Update Project/Issue state only from L3 evidence, validation proof, commit SHA, PR metadata, Release metadata, or blocker proof.
11. Request gitflow closeout when files changed.
12. Report item status to the parent.

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
