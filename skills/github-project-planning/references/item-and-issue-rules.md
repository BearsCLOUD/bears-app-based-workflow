# Item and Issue rules

Use these rules to choose Project items, Issues, sub-issues, comments, labels, and milestones.

Official GitHub references:

- Adding items: <https://docs.github.com/en/issues/planning-and-tracking-with-projects/managing-items-in-your-project/adding-items-to-your-project>
- Sub-issues: <https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/adding-sub-issues>
- Issue types: <https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/managing-issue-types-in-an-organization>

## Decision table

| Need | Use | Rule |
| --- | --- | --- |
| Durable work with acceptance criteria | Issue | Use for development, migration, validation, governance, docs, and blockers. |
| Parent outcome with bounded children | Parent Issue + sub-issues | Use when one roadmap item has separate repo/path/role slices. |
| Placeholder without repo/path/role | Draft item | Keep in Backlog. Convert before execution. |
| Status note or evidence update | Issue comment | Use only with metadata mutation authorization. |
| Cross-cutting grouping | Label | Use stable labels; do not encode fields only as labels. |
| Date or release grouping | Milestone | Use only when the repo owns the release or migration milestone. |
| One-off external wait | Blocker field + issue comment | Do not create a new issue unless the wait needs owner/action tracking. |

## Issue rules

- Every execution-ready issue must include acceptance criteria, validation target, owner repo, local path, owner role, and blocker status.
- Use sub-issues instead of one large issue when children need different repos, paths, roles, validation, or deploy boundaries.
- Route `the apps repository`, `the apps checkout`, Apps Project #20, and app lane planning to `$app-plan`; do not create app workflow issues here.
- Do not create current-slice implementation work as wishes. Wishes are future-only.
- Do not use labels or milestones as the only source of owner role, local path, validation target, or blocker state.

## Comment rules

- Comments must be evidence-backed: route/audit result, validation result, commit SHA, PR metadata, release metadata, explicit blocker proof, or operator authorization.
- Do not paste raw logs, secrets, tokens, `.env` values, private chats, shell history, production data, or raw CI logs.
- Use short comments with links to redacted artifacts when detailed proof exists elsewhere.

## Metadata mutation gate

Before any GitHub mutation, require a packet that names:

```text
mutation_authorized=true
allowed_mutations=<project|field|view|issue|sub_issue|comment|label|milestone|item_field list>
owner=<user-or-org>
project_number=<number when known>
repositories=<owner/repo list>
reason=<planning purpose>
forbidden_mutations=<repo settings|branch protection|secrets|variables|environments|webhooks|production state>
```

Without this packet, return a review packet and exact proposed mutations.
