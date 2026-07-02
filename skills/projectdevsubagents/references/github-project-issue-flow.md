# GitHub Project development orchestration flow

This file defines how L2 orchestrators execute development from existing GitHub Project and Issue state. It does not define how to administer a Project, choose long-lived fields, or design roadmap views.

## L2 intake packet

```text
project_owner=<user-or-org>
project_number=<number>
project_url=<url>
repositories=<owner/repo list>
items=<project item ids or query>
issues=<issue numbers or query>
metadata_mutation=<none|authorized>
route_targets=<paths requiring route/audit>
closeout_policy=<commit/push/proof requirements>
```

## Item execution sequence

1. Load Project item metadata and linked Issue or PR content.
2. Load linked Issues, sub-issues, labels, milestones, assignees, blockers, dependencies, and acceptance criteria.
3. Load linked PR metadata, check suite status, Release/tag/package metadata, and deployment metadata only when the item needs it.
4. Resolve the canonical owner repo and local checkout path.
5. Run route/audit for every target path.
6. Classify the item as implementation, review, validation, role-improvement, infra/deploy metadata, security metadata, docs, or closeout.
7. Split the item when repo boundary, role, write scope, validation path, or deploy/runtime boundary differs.
8. Create or update Issues and sub-issues only when `metadata_mutation=authorized`.
9. Generate one L3 `/goal` packet per split.
10. Dispatch L3 workers.
11. Collect L3 closeout packets.
12. Request gitflow closeout when any L3 worker changed files.
13. Update Project/Issue state from evidence only.
14. Report final item state to the parent.

## L3 assignment from Project item

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

## Role-improvement assignment

Spawn a role-improvement L3 worker when route/audit returns `ROLE_COVERAGE_BLOCKER`, a selected role lacks exact write scope, or role text permits forbidden implementation authority. The worker may edit only role/profile/catalog/validator files allowed by the role-development packet.

## Project state update rule

L2 may update Project fields or Issue comments only from these evidence types:

- route/audit packet;
- L3 closeout packet;
- validation result;
- commit SHA and push proof;
- PR metadata;
- Release/tag/package metadata;
- explicit blocker proof.

Do not update Project state from chat-only agreement, guessed status, or unvalidated implementation claims.

## Out-of-scope Project management

Do not use this flow to choose the organization's Project field model, create one Project per app, design roadmap views, configure Project automation, mutate repository settings, or replace issue-type governance. Use the owning Project-management governance for those actions.

## Apps repo boundary

For `BearsCLOUD/apps`, `apps` is the repository name and `/srv/bears/dev/app` is the local repo root. Do not create or route `/srv/bears/dev/app/apps`.

A Project-management policy may choose a canonical Project for `BearsCLOUD/apps`. This flow consumes that Project/Issue state and treats app directories or legacy source repos as work items, Issues, or sub-issues according to that policy.
