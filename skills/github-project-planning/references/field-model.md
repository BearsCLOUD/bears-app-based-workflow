# GitHub Project field model

Use these fields for Bears Project planning. Preserve exact names unless an existing Project already has a compatible field.

Official GitHub reference: <https://docs.github.com/en/issues/planning-and-tracking-with-projects/understanding-fields>

## Required fields

| Field | Type | Required values or format | Purpose |
| --- | --- | --- | --- |
| Status | Single select | Backlog, Ready, Blocked, In progress, Review, Done | Current planning or execution state. |
| Priority | Single select | P0, P1, P2, P3 | Operator-facing order. |
| Owner repo | Text or repository-like text | `BearsCLOUD/<repo>` | Canonical GitHub repository. |
| Local path | Text | absolute path, for example `the apps checkout` | Canonical local checkout or evidence path. |
| Owner role | Text or single select | exact @Bears role name | Route-selected role for execution or governance. |
| Issue type | Single select | Epic, Feature, Task, Bug, Migration, Governance, Validation, Docs, Blocker, Research | Work item category. |
| Workstream | Single select or text | app, platform, infra, plugin, migration, docs, ops, security, QA, release | Planning lane. |
| Blocker status | Single select | None, Access, Permission, Credential, Secret custody, Role coverage, Operator decision, External dependency, Policy stop | Hard stop classification. |
| Validation target | Text | command, check, route/audit target, or evidence packet | Closeout proof expected before Done. |

## Field rules

- Do not mark `Status=Ready` unless `Owner repo`, `Local path`, `Owner role`, `Issue type`, `Workstream`, `Blocker status`, and `Validation target` are filled.
- Use `Blocker status=None` for normal risks. Do not call ordinary sequencing or uncertainty a blocker.
- Use exact @Bears role names. Do not use team names, generic labels, or inferred owners.
- Use one repo and one local path per item. Split multi-repo work.
- Use one validation target per item. Split when validation differs.
- For deploy/runtime work, validation target must name Kubernetes desired-state or local_cd evidence. Product source tests alone are not final live PASS.

## Optional fields

Use optional fields only when the Project needs them:

| Field | Type | Use |
| --- | --- | --- |
| Target date | Date | Roadmap view. |
| Release | Text | GitHub Release or version tag. |
| Parent issue | Text | Parent issue URL when sub-issue UI is unavailable. |
| Route target | Text | Exact path for `subagents_roles.py route/audit`. |
| Consumer workflow | Single select | `github-project-planning` or another named consumer workflow. |
| Mutation authorization | Single select | none, read-only, authorized | External metadata mutation gate. |
