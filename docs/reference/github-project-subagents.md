# GitHub Project Subagents Reference

## Purpose

This reference binds GitHub planning surfaces to Bears parent, L2, and L3 lanes.

## Surfaces

- GitHub Projects v2: items, views, fields, field options, workflows, charts, draft issues, linked Issues, and linked Pull Requests.
- Issues: issue type, state, body, comments, labels, milestones, assignees, timeline, linked branches, linked Pull Requests, and dependencies.
- Sub-issues: parent issue, child issue, priority, progress, and multi-level decomposition.
- Pull Requests: review state, mergeability, linked Issues, check suites, review metadata, and base/head refs.
- Actions and Checks: workflow runs, check suites, check runs, conclusions, artifacts metadata, and rerun eligibility.
- Releases, Tags, and Packages: version tags, release notes, release assets metadata, packages metadata, and container package refs.
- Discussions, Wiki, and Pages: non-actionable decisions, public knowledge, Q&A, and announcements.
- Code and security metadata: code scanning alerts, secret scanning alert metadata, Dependabot alerts, and advisories.
- Deployments and Environments: deployment records, environment names, deployment status metadata, and protection-rule metadata.
- Repository collaboration metadata: branches, commits, compare output, CODEOWNERS, repository topics, rules metadata, and team metadata.

## Lane rules

Parent lane selects Projects, repositories, Issues, and L2 orchestrators. It does not implement, write files, mutate Git, mutate runtime, or mutate repository settings.

L2 lane uses `bears-github-project-issues-orchestrator`. It may mutate GitHub planning metadata only when the parent packet authorizes mutation. It does not implement or run implementation commands.

L3 lane uses the exact route-selected @Bears role with `gpt-5.4-mini` and `reasoning=high`. It owns one issue or Project item slice inside one repo boundary and one allowed write scope.

## Required validator

Run:

```bash
python3 scripts/github_project_subagents.py validate
```

For assignment packets, run:

```bash
python3 scripts/github_project_subagents.py validate-assignment <packet.json>
```
