---
name: projectdevsubagents
description: "Use for Bears development driven by GitHub Projects and Issues where the parent may only control orchestrator subagents, L2 orchestrators may only manage project/issue state and L3 assignments, and all implementation work is executed by @Bears L3 subagents with gpt-5.4-mini high."
---

# Project Dev Subagents

Use this skill when development must be planned and executed from GitHub Projects and Issues.

## Required topology

```text
Parent agent
  -> L2 GitHub/project orchestrator subagents
      -> L3 @Bears implementation/review subagents
      -> L3 role-improvement subagent when role gaps appear
  -> one persistent gitflow closeout subagent
```

## Parent control lane

The parent agent must not do implementation work. Parent allowed actions:

- select project and repositories;
- start or reuse L2 orchestrators;
- pass project, issue, PR, Actions, Release, and role-gate packets;
- wait for L2 evidence;
- integrate L2 closeouts;
- request commit/push closeout through `bears-git-workflow-helper`;
- report exact status.

Parent forbidden actions:

- file writes;
- implementation commands;
- `git add`, `git commit`, `git push`;
- direct PR mutation except explicit operator-requested metadata action;
- runtime, deploy, provider, secret, or production mutation.

## L2 orchestrator rules

Each L2 orchestrator must use `bears-github-project-issues-orchestrator` or an exact domain orchestrator role. L2 allowed actions:

- read and update GitHub Project planning metadata when authorized;
- create or update Issues, sub-issues, labels, milestones, assignees, links, and project fields;
- link PRs, project items, Actions status, Releases, and dependency notes;
- split work into L3 packets;
- spawn L3 workers with @Bears role names;
- spawn one role-improvement L3 worker when route/audit exposes role drift;
- integrate L3 closeouts into Project and Issue state.

L2 forbidden actions:

- implementation file writes;
- shell implementation commands;
- commit, push, merge;
- deploy or runtime mutation;
- reading secrets, raw logs, raw chats, raw VPN configs, credentials, or production data.

## L3 worker rules

- Use the exact @Bears role returned by route/audit.
- Use `model=gpt-5.4-mini` and `reasoning=high`.
- One L3 assignment covers one issue or project item slice, one repo boundary, one allowed write scope, and one validation path.
- L3 must return changed files, issue/project item ids, validation evidence, blockers, and forbidden surfaces untouched.

## GitHub surface coverage

Before implementation, L2 must inspect and reconcile:

- Project purpose, views, fields, status values, automation, and item ids;
- Issues, issue types, sub-issues, labels, milestones, assignees, linked branches, linked PRs, and dependencies;
- Pull requests, review state, mergeability metadata, check suite status, and linked issues;
- Actions status metadata without raw log reads;
- Releases, tags, packages, and deployment notes when delivery is in scope;
- Discussions only when the work needs a non-actionable decision record.

See `references/github-project-issue-flow.md` for the exact packet sequence.
