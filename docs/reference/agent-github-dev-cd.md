# Agent GitHub Dev CD

This document is a deprecated reference for the former Agent GitHub dev-CD flow.
It is not active workflow authority.
Active Bears plugin delivery is main-only and is governed by `assets/catalog/agentic-enterprise-workflow.v1.json` `delivery_policy`.

Technical terms:

- PR: Pull Request, a request to merge one branch into another branch.
- Draft PR: a PR marked as not ready for merge.
- CI: optional diagnostics checks.
- CD: automatic deployment after an approved merge.
- local_cd: GitHub-controlled CI/CD behavior.
- development scenario: deterministic startup task lane selected from prompt markers.
- agent_current_runtime: the current agent execution runtime at `/srv/bears`; it is not production.
- external emergency authority: operator-approved production emergency lane outside this plugin root.
- workflow mode: the declared branch-shape policy for one historical `/goal` run.
- sequential: one historical `/goal` implementation lane.
- parallel: multiple historical agent branches for one goal branch.
- typed merge packet: JSON packet with exact PR, head, checks, state-file policy, title, draft, rollback, and authority fields.
- commit trailer: a `Key: value` marker stored in the last lines of a commit message.
- dispatch plan artifact: historical JSON file that described a dev deploy request.
- topology evidence file: deterministic JSON file used by `classify-mode` and `verify-live-topology`.
- evidence file: non-secret repo file under `docs/evidence/dev-cd/`.
- Local agent runner: routes and starts bounded workers.
- issue type: a GitHub label that marks the decision lane for one issue.
- duplicate guard: proof that another open issue or active worker is not already handling the same bounded scope.

## Authority status

- `agent-github-dev-cd` is `deprecated_reference_only`.
- It grants no active branch, PR, auto-merge, local_cd, kubernetes_deployment, runtime, connector, product app, MCP, or production authority.
- `verify-dev-auto-merge` remains as an executable drift guard and returns `DEV_AUTO_MERGE_BLOCKED` with `DEV_AUTO_MERGE_DEPRECATED_MAIN_ONLY_DELIVERY`.
- Active plugin task commits target `main` only.
- PR, GitHub review, dev branch, and branch-dependent closeout are not active workflow authority.
- Closeout requires `delivery_complete=true` in `runtime/plugin-cache-sync/plugin-cache-sync-state.v1.json` for the exact `main` SHA.

## Main-only replacement

- Replacement authority: `assets/catalog/agentic-enterprise-workflow.v1.json` `delivery_policy`.
- Required closeout gates: `commit_to_main`, `local_commit_validation_pass`, `cache_sync_done`, and `effective_hooks_proof`.
- `.github/workflows/validate.yml` must not define `pull_request`, `merge_group`, or `jobs.dev-cd-gate` for this plugin delivery lane.
- The only active GitHub Actions diagnostics trigger for plugin delivery is operator `workflow_dispatch`.
- Automatic plugin closeout proof runs locally through git `pre-commit` and `post-commit` hooks; GitHub push on `main` runs diagnostics for the pushed commit.
- Allowed parent actions: `route`, `split`, `assign`, `wait`, `integrate_evidence`, `run_validators`, `close`, `report`, `pre_task_hook`.
- Parent agent must not run `file_read_as_content_collector`, `file_write`, `git_add`, `git_commit`, `git_push`, `pull_request_mutation`, or `implementation_tool_use`.

## Preserved classifiers

The classifier remains usable for historical packet checks and must not create active dev-CD authority.

Validator commands:

```bash
python3 scripts/agent_github_dev_cd.py classify-task --prompt-file <path>
python3 scripts/agent_github_dev_cd.py verify-scenario-policy --packet <path>
python3 scripts/agent_github_dev_cd.py classify-mode --goal-id <goal-id> --development-scenario <development_scenario>
python3 scripts/agent_github_dev_cd.py verify-live-topology --goal-id <goal-id> --development-scenario <development_scenario>
python3 scripts/agent_github_dev_cd.py merge-authority-check --packet <path> --expected-repository <owner/repo> --expected-pr-number <number> --expected-head-ref <head-ref> --expected-head-sha <head-sha> --expected-base-ref <base-ref>
python3 scripts/agent_github_dev_cd.py verify-dev-auto-merge --packet <path> --expected-repository <owner/repo> --expected-pr-number <number> --expected-head-ref <head-ref> --expected-head-sha <head-sha> --expected-base-ref dev
```

`development_scenario` values remain `dev`, `prod`, `bugfix`, `hot_bugfix`, `issue`, and `goal`.
`dev`, `prod`, and `bugfix` now resolve to main-only delivery gates.
`hot_bugfix` still requires external emergency authority and git backfill before main-only delivery.

## Historical issue gates

Fixed GitHub issue identifiers remain:

- `type:bugfix`
- `type:idea`
- `type:develop-ready`

`type:develop-ready` requires concrete body fields:

- Concrete problem.
- Exact targets/surfaces.
- Required change.
- Acceptance criteria.
- Validation commands.
- Duplicate guard.
- Safety boundary.

agent pickup remains blocked for unlabeled issues, idea-only issues, bugfix-only issues, blocked labels, human-review labels, secret labels, credentials labels, deploy labels, production labels, and security-review labels.

Validator commands:

```bash
python3 scripts/agent_github_dev_cd.py verify-issue-metadata --issue-packet <path>
python3 scripts/agent_github_dev_cd.py verify-agent-pickup --issue-packet <path> --dry-run
```

structured evidence is mandatory for route gate, constitution evidence, research evidence, accepted operator decision evidence, owning role, task packet, duplicate guard, and dry-run result.
`.github/ISSUE_TEMPLATE/01-governance-work.yml` remains the metadata-only promotion path.

## Historical merge and dev-CD markers

These names are retained only to let validators reject stale authority drift:

- `MERGE_ALLOWED`
- `MERGE_BLOCKED_EMPTY_CHECK_ROLLUP`
- `MERGE_BLOCKED_DRAFT_PR`
- `MERGE_BLOCKED_OUTDATED_HEAD`
- `DEV_AUTO_MERGE_ALLOWED`
- `DEV_AUTO_MERGE_BLOCKED_MAIN_TARGET`
- `DEV_AUTO_MERGE_DEPRECATED_MAIN_ONLY_DELIVERY`
- `verify-dev-auto-merge`
- `jobs.dev-cd-gate`
- `artifacts/dev-cd-dispatch-gate.json`
- `docs/evidence/dev-cd/`
- `/srv/bears/kubernetes`

Historical commit evidence used `Workflow-State`, `Merge-Authority-State`, `Runtime-Evidence`, `Rollback-Note`, and `Kubernetes-Dispatch-Plan: artifacts/dev-cd-dispatch-gate.json`.
The phrase `referenced evidence files are absent` marks a hard failure in historical packet validation.
The historical local_cd step was plan-only and must not run `kubectl`, `helm`, or production deploy commands.
