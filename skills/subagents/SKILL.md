---
name: subagents
description: "Use when a Bears task must select, start, constrain, review, or close subagents, including role-bound L2/L3 delegation, parent-control-only mode, reusable workers, gitflow closeout lanes, and subagent evidence packets."
---

# Subagents

Use this skill before starting, reusing, assigning, waiting for, or closing Bears subagents.

## Hard rules

- Read `/srv/bears/AGENTS.md` and `/srv/bears/plugins/bears/AGENTS.md` before subagent assignment.
- Run route and audit for the target path before assigning work:
  - `python3 /srv/bears/plugins/bears/scripts/platform_roles.py route <target>`
  - `python3 /srv/bears/plugins/bears/scripts/platform_roles.py audit <target>`
- A parent agent in subagent mode is control-only. Allowed parent actions are route, split, assign, wait, integrate evidence, run named validators, close agents, GitHub planning metadata updates requested by the operator, and final report.
- Parent agents must not write implementation files, run implementation commands, mutate Git, mutate runtime, or read restricted data while subagent mode is active.
- Subagent prompts must start with `/goal` on line 1 and include explicit completion criteria.
- Subagent artifacts and subagent messages are English-only.
- Reuse one persistent `gitflow` subagent per parent session for commit/push closeout.
- Do not reuse an audit subagent for writable work.
- Close completed or abandoned subagents before starting new waves when their evidence is no longer needed.

## Runtime matrix

| Lane | Role source | Model | Reasoning | Authority |
| --- | --- | --- | --- | --- |
| Parent control lane | current parent | surface default | high when available | control only |
| L2 orchestrator | `agents/*orchestrator*.toml` or route-selected helper | `gpt-5.5` unless packet says lower | high | assign and integrate only |
| L3 worker | route-selected @Bears role | `gpt-5.4-mini` | high | owns exact assigned work slice |
| Gitflow closeout | `bears-git-workflow-helper` | `gpt-5.4-mini` | high | commit/push assigned files only |
| Audit/review | route-selected reviewer | `gpt-5.4-mini` or role default | high | read-only unless role says otherwise |

## Assignment packet

Every subagent assignment must include:

```text
/goal
role=<@Bears role name>
model=<model>
reasoning=<high|medium>
repo=<owner/repo or local path>
target=<exact file/dir/issue/project item>
allowed_actions=<bounded list>
forbidden_actions=<bounded list>
inputs=<issue/project/spec/plan refs>
expected_outputs=<files, packets, comments, or evidence>
validation=<commands or metadata checks>
completion_criteria=<measurable done state>
restricted_data=false
```

## Evidence integration

Parent closeout must list:

- role and subagent id;
- assigned target and allowed scope;
- changed files or GitHub item ids;
- validation commands with exit codes or exact metadata checks;
- blockers only when access, credentials, permission, explicit stop, or linked contract blocks progress.

See `references/role-lanes.md` for role-lane selection.
