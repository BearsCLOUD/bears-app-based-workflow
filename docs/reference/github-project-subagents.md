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

Parent lane selects Projects, repositories, Issues, and L2 orchestrators. It does not implement, write files, mutate Git, mutate Project or PR metadata directly, mutate runtime, or mutate repository settings. It passes explicit operator-authorized metadata requests to L2.

Before parallel L2 fan-out, the parent must run a capacity preflight: prove available L2 slots, each lane's L3 spawn capacity, exact Issue scope, target file or contract, route/audit target, validation path, and 240s/270s cutoff. If capacity is unknown or at thread limit, the parent starts only one smaller L2 lane or returns `FAST_BLOCKER`.

L2 lane uses `bears-github-project-issues-orchestrator` with `gpt-5.5` and `reasoning=medium`. It may mutate GitHub planning metadata only when the parent packet authorizes mutation. It does not implement or run implementation commands.

L3 lane uses the exact route-selected @Bears role with `gpt-5.4-mini` and `reasoning=high`. It owns one issue or Project item slice inside one repo boundary and one allowed write scope.

## Runtime proxy deadline enforcement

If `bears-development-workflow-orchestrator` acts as runtime proxy for `role=bears-github-project-issues-orchestrator`, it must follow the L2 limits from the role profile, `skills/app-dev/SKILL.md`, this reference, `assets/catalog/github-project-subagents.v1.json`, and `scripts/github_project_subagents.py`.

Current drift issue #25 is `BearsCLOUD/bears_plugin#25`.

The fallback runtime proxy must:

- return a parent-visible `READY`, `WIP`, or `FAST_BLOCKER` packet inside the first minute;
- treat `WIP` as metadata/decomposition only, with no L3 spawn and a declared cutoff;
- create or update a smaller Issue or issue comment and return `FAST_BLOCKER` when L3 spawn fails or capacity is unavailable;
- after timeout, retry with one issue, one L3 max, one target file or contract, and one validation path;
- update `BearsCLOUD/bears_plugin#26` on repeated timeout before retrying smaller;
- prefer metadata-only Issue/comment reinforcement before another L3 after a repeated timeout;
- return `FAST_BLOCKER` before 240 seconds when no PASS is ready;
- close descendants before 240 seconds and before `FAST_BLOCKER`;
- leave no WIP on `FAST_BLOCKER` or timeout;
- run post-close bounded WIP proof before claiming a target is clean or absent;
- treat cleanup lane timeout as new workflow drift, not as `CLEANED_NO_WIP`;
- run cleanup as a separate first-class L2 lane with a shorter cleanup cutoff than implementation lanes;
- require each cleanup L2 packet to name exactly one cleanup target, one status proof command, and no issue metadata mutation unless explicitly assigned;
- return parent-visible `CLEANUP_PASS` or `FAST_BLOCKER` before the parent cutoff; post-cutoff cleanup success is drift evidence only;
- record the `BearsCLOUD/apps#105` and `BearsCLOUD/apps#110` cleanup timeout event as drift evidence, not a repeatable pattern;
- inspect assigned Issue labels and latest checkpoint comments before L3 dispatch;
- return `FAST_BLOCKER` or metadata-only output before file-changing work when labels include `validation-conflict`, `blocked`, `objective-runtime-proof-required`, or `needs-gitflow-closeout` without parent-issued commit-closeout scope;
- treat `CHECKPOINT_STATUS: BLOCKED / validation contract conflict before closeout` as a no-L3 blocker;
- treat `gitflow-ready` as parent gitflow closeout scope only, not permission to implement more code;
- record `BearsCLOUD/apps#110` lane `019f27ca-3d8d-7540-aa10-6edff4efcdf5` as validation-conflict drift evidence only, not a repeatable pattern;
- never report PASS after elapsed time greater than 300 seconds;
- require exact new-file authorization from the Issue, sub-issue, or parent packet before any L3 creates a new file;
- skip broad Project scans when the parent provides exact Issues and route/audit evidence;
- forbid implementation pools until this enforcement text and catalog/script guard are present.

## Required gates

autoCI ownership checks:

- local commit validation selects `subagents_roles.route` and `subagents_roles.audit` for the changed target paths;
- agents record computed owner roles and expected status names only;
- manual route/audit runs require one exact operator-named command in the current turn.

CI/local-commit-owned or operator-approved catalog validator:

```bash
python3 scripts/github_project_subagents.py validate  # local-commit-owned
```

CI/local-commit-owned or operator-approved assignment-packet validator:

```bash
python3 scripts/github_project_subagents.py validate-assignment <packet.json>  # local-commit-owned
```
