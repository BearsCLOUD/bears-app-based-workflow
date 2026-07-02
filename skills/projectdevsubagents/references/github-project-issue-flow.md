# GitHub Project and Issue flow

GitHub Projects are planning boards with items, views, fields, automation, and charts. Issues track actionable work and can have sub-issues. Pull requests carry code-review state. Actions carry check metadata. Releases and tags carry versioned delivery state.

## L2 intake packet

```text
project_owner=<user-or-org>
project_number=<number>
project_url=<url>
repositories=<owner/repo list>
issues=<issue numbers or query>
views=<required views>
fields=<required field names>
status_field=<field name>
blocked_field=<field name>
role_field=<field name>
delivery_field=<field name>
```

## Planning sequence

1. Load Project metadata: item ids, issue or PR content ids, field ids, views, workflows, and current field values.
2. Load Issues: title, body, state, type, labels, milestone, assignees, parent/sub-issue links, linked PRs, blockers, and acceptance criteria.
3. Normalize every Project item to an owner repo, @Bears role, status, blocker state, validation path, and next L3 assignment.
4. Create missing Issues only for actionable implementation, validation, role drift, deploy evidence, or closeout debt.
5. Use sub-issues for decomposed work under the parent issue when the parent remains the durable objective.
6. Add or update Project fields after L3 closeout, not before evidence exists.
7. Keep draft issues only for planning placeholders that are not ready for L3 assignment.
8. Link PRs to Issues and Project items before closeout.
9. Read Actions metadata only; do not read raw logs unless a role and operator packet allow it.
10. Use Releases or tags only when the delivery surface requires versioned evidence.

## L3 assignment from GitHub item

```text
/goal
role=<route-selected @Bears role>
model=gpt-5.4-mini
reasoning=high
github_project_item=<item id/url>
github_issue=<owner/repo#number>
repo=<local path and owner/repo>
target=<exact files/paths>
allowed_actions=<bounded list>
forbidden_actions=<bounded list>
acceptance_criteria=<issue checklist or project field target>
validation=<exact commands or metadata checks>
closeout_updates=<project fields and issue comment requested from L2>
```

## Role-improvement assignment

Spawn a role-improvement L3 worker when route/audit returns `ROLE_COVERAGE_BLOCKER`, a selected role lacks exact write scope, or the role text permits forbidden implementation authority. The worker may edit only role/profile/catalog/validator files allowed by the role-development packet.
