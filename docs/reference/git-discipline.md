# Git Discipline

Git discipline means the exact closeout order an agent must use before it writes a commit.

Technical terms:

- dirty status: changed or untracked files shown by `git status --short`.
- staged files: files already selected for the next commit by `git add`.
- diff check: `git diff --check`; it fails on whitespace errors.
- ancestry merge: Git proof that a branch tip is already reachable from the base branch.
- squash merge: GitHub merge mode that writes a new commit on the base branch, so ancestry proof can be false after the PR is merged.
- gitlink: a parent repository entry that pins a submodule path to a commit object.
- assignment packet: JSON task handoff that may carry an explicit branch prefix override.
- safe worker git identity: fixed local `user.name` and `user.email` used for worker commits.
- branch-base preflight: read-only check that current branch, base, worktree cleanliness, and assignment paths match before edits or publish.
- force-add: `git add -f` or `git add --force`, which stages ignored paths.

## Gate files

- Catalog: `assets/catalog/git-discipline.v1.json`.
- Validator: `scripts/git_discipline.py`.
- Tests: `tests/test_git_discipline.py`.

## Required closeout order

Run these commands from the repository root:

```bash
git status --short --branch
git diff --check
# run validators and tests tied to the changed files
git add -A
git diff --cached --check
python3 scripts/git_discipline.py inspect --repo . --json
git commit -m "<imperative English summary>"
git status --short --branch
```

## Canonical plugin checkout

For @Bears plugin work, `/srv/bears/plugins/bears` is the only canonical source checkout.

Before editing plugin files, prove:

```bash
python3 scripts/git_discipline.py plugin-worktree-preflight --repo /srv/bears/plugins/bears --json
pwd
git rev-parse --show-toplevel
git config --get core.worktree || true
git status --short --branch
```

`plugin-worktree-preflight` is read-only. It must return `PLUGIN_WORKTREE_PASS` before plugin edits. `pwd` and `git rev-parse --show-toplevel` must both be `/srv/bears/plugins/bears`. `core.worktree` must be empty or `/srv/bears/plugins/bears`. A hidden `/tmp` worktree is allowed only with operator approval or an issue assignment packet that names it. That packet must include canonical dirty-state backup, sync-back plan, exact LCV proof, and plugin cache sync proof from `/srv/bears/plugins/bears`.

## Hard rules

- Completed task slice means validated, committed, and pushed. Leaving completed dirty work is forbidden.
- Commit and push every completed task slice immediately after validation, including small docs-only edits.
- If unrelated dirty files exist, stage and commit only the completed slice's explicit allowlisted files and report carried dirty paths.
- If a hard safety hold prevents commit or push, the slice is not complete; report the exact blocker, owner, and GitHub issue, and keep gitflow hold active.
- Gitflow must reject completion claims without commit/push evidence or an explicit blocker with owner and issue.
- Do not stage or commit secrets, credentials, private keys, `.env` files, raw production data, raw logs, shell history, or raw VPN configs.
- Do not use `git reset`, `git clean`, `git checkout`, `git switch`, `git stash`, `git merge`, `git rebase`, `git revert`, or `git config --global` as automatic cleanup.
- Do not allow commit authority until local Git config has `Bears Codex Worker <codex-worker@bears.local>`.
- Do not query GitHub or provider account profile fields to recover commit identity.
- Do not mutate global Git config automatically.
- Do not claim a branch is unmerged until GitHub PR state and ancestry proof have both been checked.
- Do not delete worktree-attached, backup, dirty-preserve, open-PR, closed-unmerged, remote-unverified, or local-unverified branches.
- Do not delete local or remote branches unless the operator explicitly asks for that cleanup command.
- Do not create, stage, commit, push, or open a PR until `branch-base-preflight` proves the branch is attached, clean, based on the intended base, and not a merged PR branch.
- Do not use `git add -f` for ignored workspace surfaces such as `dev/**` unless the packet has explicit operator approval, exact path allowlist, and owning contract.
- If `git diff --check` or `git diff --cached --check` fails, fix the files before commit.
- If work outside the repository was changed, report it as not included in the commit.
- For ledger or gitlink closeout, run `closeout-preflight`; pass every assignment write path with `--allowed-path`; any other changed path returns `DIRTY_WORKTREE_BLOCKER`.
- Commit messages are English imperative summaries.

## Validator usage

```bash
python3 scripts/git_discipline.py validate
python3 scripts/git_discipline.py inspect --repo /srv/bears/plugins/bears --json
python3 scripts/git_discipline.py inspect --repo /srv/bears --allowed-path plugins/bears --allowed-path plans.md --json
python3 scripts/git_discipline.py closeout-preflight --repo /srv/bears --allowed-path specs/008/tasks.md --expected-branch-prefix codex/closeout- --json
python3 scripts/git_discipline.py closeout-preflight --repo /srv/bears --allowed-path plugins/bears --expected-branch-prefix codex/closeout- --gitlink-proof plugins/bears:<old-object>:<target-object>:<source-pr-merge-commit> --json
python3 scripts/git_discipline.py branch-inventory --repo /srv/bears/plugins/bears --base origin/main --json
python3 scripts/git_discipline.py branch-closeout-gate --repo /srv/bears/plugins/bears --base origin/main --github-prs-json /tmp/prs.json --json
python3 scripts/git_discipline.py gitlink-audit --repo /srv/bears --tree-ref origin/main --path kubernetes --expected-target <sha> --local-checkout /srv/bears/kubernetes --json
python3 scripts/git_discipline.py branch-prefix-check --branch codex/<slice> --assignment-packet <assignment.json> --json
python3 scripts/git_discipline.py branch-base-preflight --repo /srv/bears/plugins/bears --intended-base origin/main --expected-branch-prefix codex/ --allowed-path scripts/git_discipline.py --allow-assigned-changes --json
python3 scripts/git_discipline.py clean-worktree-target --canonical-root /srv/bears --worktree-root /srv/bears/dev/workspace/<name> --worktree-target /srv/bears/dev/workspace/<name>/specs/006-bears-platform-telegram/governance/<file>.json --json
python3 scripts/git_discipline.py ignored-staging-check --command "git add -f dev/PROJECTS.md" --json
```

The validator is read-only. It does not stage, commit, push, reset, clean, stash, merge, or rebase.

`inspect --allowed-path` is read-only. It reports `disallowed_changed_paths` and blocks commit readiness when dirty paths are outside the assignment write set.

`inspect` also checks the safe worker git identity. It emits only `worker_git_identity_configured` and the fixed `worker_git_identity_label`. Missing, unsafe, or global-only identity keeps `commit_allowed_after_validation=false`.

`closeout-preflight` is read-only. It is required before ledger or gitlink closeout commit, push, PR ready, or merge. It requires an assignment write-path list, an expected task branch or branch prefix, and `--gitlink-proof <path>:<old-object>:<target-object>:<source-pr-merge-commit>` when a gitlink is part of the closeout. Gitlink proof is checked against the parent repo old object from `HEAD` and target object from the index.

The branch inventory command is read-only. It does not fetch, prune, delete, switch, merge, or push.

`branch-closeout-gate` is read-only. It must run after a PR merge when branch cleanup evidence is needed. It returns `BRANCH_CLOSEOUT_READY` only when local cleanup candidates, remote cleanup candidates, and merged worktree-attached branches are all zero.

`gitlink-audit` is read-only. It proves the parent gitlink target with `git ls-tree <tree-ref> -- <path>`, reports the local submodule HEAD when provided, and marks local checkout evidence unusable when it does not match the parent target. Local checkout claims fail closed on stale local submodule state. Parent gitlink claims can pass while still reporting the stale local checkout.

`branch-prefix-check` is read-only. Run it before `git push` or PR creation. It returns `branch_prefix_check=PASS` only when the branch starts with `codex/` or when an assignment packet contains `branch_prefix_override.prefix`, `branch_prefix_override.reason`, and `branch_prefix_override.approved_by`, and the branch starts with that override prefix.

`branch-base-preflight` is read-only. Run it before first edit and again before `git add`, `git commit`, `git push`, and `gh pr create`. It blocks detached HEAD, `[gone]` upstream, wrong branch, wrong branch prefix, disallowed changed paths, missing base, base not ancestor, and merged-PR branches. Use `--allow-assigned-changes` only after every dirty path is listed with `--allowed-path`.

`clean-worktree-target` is read-only. It maps an isolated physical worktree path back to the canonical route path so route gates use `canonical_target` while edits use `worktree_target`.

`ignored-staging-check` is read-only. It blocks force-add commands for ignored workspace surfaces unless explicit approval, exact path allowlist, and owning contract are present.

## Issue ownership

| Issue | Branch hygiene lane |
| --- | --- |
| BearsCLOUD/bears_plugin#133 | clean worktree and gitlink closeout guard |
| BearsCLOUD/bears_plugin#88 | branch-base preflight |
| BearsCLOUD/bears_plugin#144 | `codex/` branch-prefix governance |
| BearsCLOUD/bears_plugin#128 | gitlink sync target audit |
| BearsCLOUD/bears_plugin#132 | merge authority lane |
| BearsCLOUD/bears_plugin#120 | durable PASS evidence before merge handoff |

## Remote branch inventory

`branch-inventory` also emits `remote_branches`. Remote branch cleanup remains read-only and requires explicit operator approval before `git push origin --delete`.

Remote branch classes:

- `remote_main_branch`: remote `main` or `master`; never delete.
- `remote_tracking_local_present`: a local branch still exists; resolve local state first.
- `remote_github_merged_cleanup_candidate`: GitHub PR state proves the branch merged.
- `remote_ancestry_merged_cleanup_candidate`: Git ancestry proves the remote branch is reachable from base.
- `remote_open_pr_review_required`: open PR exists.
- `remote_closed_unmerged_review_required`: closed unmerged PR exists.
- `remote_without_pr_review_required`: no merged PR or ancestry proof.
