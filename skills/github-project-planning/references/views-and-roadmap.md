# Views and roadmap

Use these views to make Project state executable and reviewable.

Official GitHub reference: <https://docs.github.com/issues/planning-and-tracking-with-projects/learning-about-projects/about-projects>

## Required views

| View | Filter or grouping | Purpose |
| --- | --- | --- |
| Backlog | `Status=Backlog` | Unready or unsorted items. |
| Ready | `Status=Ready` and `Blocker status=None` | Development handoff queue. |
| Blocked | `Blocker status` not `None` or `Status=Blocked` | Access, permission, credential, role, operator, or policy stops. |
| In progress | `Status=In progress` | Active work only. |
| Review | `Status=Review` | Awaiting validation, PR review, or evidence review. |
| Done | `Status=Done` | Closed only after validation target is satisfied. |
| Roadmap | grouped by target date, release, workstream, or migration stage | Time or stage planning. |
| Repo boundary | grouped by `Owner repo` then `Local path` | Catch multi-repo and wrong-path drift. |

## Roadmap rules

- Use roadmap grouping only after owner repo and local path are filled.
- Use one roadmap item per owner repo/local path/owner role/validation target combination.
- Move blocked items out of Ready even when the roadmap date is near.
- Keep migration stages explicit: inventory, boundary check, infra/local_cd safety, implementation, validation, archive readiness.
- For deploy/runtime roadmap items, reference Kubernetes desired state and local_cd selectors. Do not treat local host processes or manual deploy commands as final PASS.

## Ready view gate

An item may appear in Ready only when:

- it has an Issue, not only a draft item;
- `Owner repo`, `Local path`, `Owner role`, `Issue type`, `Workstream`, `Blocker status`, and `Validation target` are filled;
- `Blocker status=None`;
- route/audit target is known for implementation or governance work;
- metadata mutation requirements are either complete or not needed.

## Blocked view gate

Use Blocked for hard stops only:

- missing access;
- missing permission;
- missing credential;
- secret-custody decision;
- role coverage blocker;
- explicit operator stop;
- policy stop;
- external dependency with no local action available.

Turn ordinary risk, sequencing, or unknown detail into a task or review item, not a blocker.
