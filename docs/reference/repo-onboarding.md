# Governed repository onboarding

This surface closes #412.

## States
Repositories are `read_only`, `candidate`, `write_scoped`, `blocked`, or `manual_review`. Non-plugin repositories default to `read_only`.

## Write scope proof
A repository may become `write_scoped` only when it has a local worktree, valid AGENTS or instruction surface, effective hook proof, authority topic mapping, explicit allowed write paths, closeout policy, and no blocking drift.

## Commands
- `scripts/repo_onboarding.py inventory --json`
- `scripts/repo_onboarding.py validate`
- `scripts/repo_onboarding.py doctor --json`

Autostart may read governed repository metadata, but cross-repo writes are denied unless the repository is `write_scoped`.
