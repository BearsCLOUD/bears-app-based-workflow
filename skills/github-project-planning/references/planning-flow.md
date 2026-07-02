# GitHub Project planning flow

Use this flow before development orchestration. It creates or selects a planning surface, fills required metadata, and produces a planning PASS handoff.

Official GitHub references:

- Projects overview: <https://docs.github.com/issues/planning-and-tracking-with-projects/learning-about-projects/about-projects>
- Fields: <https://docs.github.com/en/issues/planning-and-tracking-with-projects/understanding-fields>
- Adding items: <https://docs.github.com/en/issues/planning-and-tracking-with-projects/managing-items-in-your-project/adding-items-to-your-project>
- Projects GraphQL API: <https://docs.github.com/en/issues/planning-and-tracking-with-projects/automating-your-project/using-the-api-to-manage-projects>

## Intake

Capture these inputs first:

```text
project_owner=<user-or-org>
project_number=<existing-number-or-new-authorized>
project_url=<existing-url-or-empty>
planning_goal=<roadmap|migration|release|repo-boundary|workstream>
owner_repos=<owner/repo list>
local_paths=<repo checkout paths>
metadata_mutation=<none|authorized>
route_targets=<paths requiring route/audit>
operator_authorization=<packet-or-none>
```

If `metadata_mutation=none`, produce a review packet and exact mutation request. Do not create or update GitHub metadata.

## Project selection or creation

1. Prefer an existing canonical Project for the workstream.
2. For `BearsCLOUD/apps` migration planning, use Project #20 unless the operator explicitly says otherwise.
3. Create a new Project only when the operator packet names owner, title, scope, retention policy, and metadata mutation permission.
4. Record Project URL, number, owner, target repositories, and planning owner role.

## Field setup

1. Ensure every required field from `field-model.md` exists or is requested.
2. Use single-select fields for stable enums.
3. Use text fields for exact repo/path/role strings when GitHub has no native type.
4. Use date fields only for time-bound roadmap views.
5. Store field IDs when available for later GraphQL mutation.

## Item setup

1. Add Issues or draft items only when metadata mutation is authorized.
2. Prefer Issues when work needs acceptance criteria, comments, links, assignees, labels, milestones, or closeout evidence.
3. Prefer sub-issues when the parent outcome is one roadmap item and children are bounded repo/path slices.
4. Use draft items only for placeholders that cannot yet name an owner repo, local path, or validation target.
5. Convert draft items to Issues before development handoff.

## Field fill sequence

For each item, fill in this order:

1. `Owner repo`
2. `Local path`
3. `Owner role`
4. `Issue type`
5. `Workstream`
6. `Validation target`
7. `Blocker status`
8. `Priority`
9. `Status`

Split the item before fill when one value cannot cover the whole item.

## View setup

Create or verify views from `views-and-roadmap.md`. At minimum, planning PASS requires Backlog, Ready, Blocked, In progress, Review, Done, Roadmap, and Repo boundary views.

## PASS gate

Planning PASS requires:

- Project URL and number are known;
- required fields exist or an exact missing-field request is recorded;
- required views exist or an exact missing-view request is recorded;
- every ready item has owner repo, local path, owner role, issue type, workstream, blocker status, and validation target;
- blocker items state the exact missing permission, credential, access, role coverage, or operator decision;
- `projectdevsubagents` handoff inputs are complete for development work.

Return `status: review` when any condition is missing.
