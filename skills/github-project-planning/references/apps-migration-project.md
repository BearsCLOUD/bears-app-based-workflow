# BearsCLOUD/apps migration Project

Use this reference when planning `BearsCLOUD/apps` migration or archive readiness.

Canonical Apps planning Project: <https://github.com/users/BearsCLOUD/projects/20>

## Required Project #20 fields

The Apps planning Project must include these migration fields:

| Field | Format | Rule |
| --- | --- | --- |
| `source_repo` | `owner/repo` or legacy local evidence path | Original repo or source being migrated. |
| `app_directory` | path under `/srv/bears/dev/app` | Target app directory inside the canonical apps repo. |
| `migration_stage` | inventory, boundary_check, infra_local_cd_safety, platform_boundary, implementation, validation, archive_readiness, archived | Current migration stage. |
| `infra_local_cd_safety` | blocked, review, pass | Kubernetes desired state and local_cd references are safe. |
| `platform_boundary` | blocked, review, pass | Generic platform logic is routed to `/srv/bears/dev/platform`; app repo owns product-specific logic only. |
| `archive_readiness` | blocked, review, pass | Old repo/path can be archived as evidence-only. |

## Apps migration rules

- `BearsCLOUD/apps` is the canonical product-app repo.
- Local root is `/srv/bears/dev/app`.
- Do not create or route `/srv/bears/dev/app/apps`.
- Old child repos are migration/archive evidence only after consolidation.
- New product-app issues must be filed in or linked to `BearsCLOUD/apps`.
- Old child-repo issues must link to umbrella issue <https://github.com/BearsCLOUD/apps/issues/1> before archive.
- Source migration issue URLs are tracked by the Anscombe packet matrix; do not duplicate every source URL in docs.

## Archive gate

Archive readiness requires all of these:

1. umbrella issue linked;
2. source repo migration issue linked;
3. item is present in Project #20;
4. `source_repo` filled;
5. `app_directory` filled;
6. `migration_stage` at archive readiness or archived;
7. `infra_local_cd_safety=pass`;
8. `platform_boundary=pass`;
9. `archive_readiness=pass`;
10. old repo/path removed as deploy or build source from Kubernetes desired state, local_cd contracts/selectors, workflows, runbooks, manifest READMEs, and secret-custody docs.

## Planning handoff

When Project #20 planning is ready for execution, hand off to `projectdevsubagents` with:

```text
project_url=https://github.com/users/BearsCLOUD/projects/20
project_number=20
owner_repo=BearsCLOUD/apps
local_path=/srv/bears/dev/app
items=<Project item ids or issue ids>
required_fields=source_repo,app_directory,migration_stage,infra_local_cd_safety,platform_boundary,archive_readiness
route_targets=<exact local paths>
metadata_mutation=<none|authorized>
```
