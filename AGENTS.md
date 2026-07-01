# @Bears Plugin Router

## Scope
- This directory is the source checkout for the `@Bears` Codex governance plugin.
- It owns Bears action rules, roles, contracts, validators, workflow policy, hooks, and CD policy.
- Codex daemon / Knowledge Orchestrator runtime implementation belongs to `/srv/bears/dev/app/codexdaemon` and `BearsCLOUD/codexdaemon`.

## Required refs
- Plugin manifest: `.codex-plugin/plugin.json`.
- Role catalog: `assets/catalog/platform-role-catalog.v1.json`.
- Git/CD contracts: `assets/catalog/git-deploy-contract.v1.json` and `assets/catalog/cd-kube-deploy-contract.v1.json`.
- Canonical plugin constitution: `assets/catalog/plugin-constitution.v1.json`.
- Canonical role gate: `scripts/platform_roles.py`.

## Functional map
- `agents/*.toml` — canonical Bears role profiles; sync generated OpenCode agents with `scripts/opencode_agent_sync.py`.
- `skills/*/SKILL.md` — Codex skills for governance, role gates, deployment review, Kubernetes, Infisical, DNS, health, Spec Kit flow, and Secret Factory.
- `assets/catalog/*.v1.json` — machine-readable policy catalogs for roles, workflow gates, Git/CD, closeout, and governance.
- `assets/schemas/*.schema.json` and `schemas/*.schema.json` — JSON packet contracts for plugin governance and runtime-state-neutral workflow packets.
- `scripts/*.py` — deterministic routers, validators, closeout tools, cache sync, role gates, and governance helpers.
- `hooks.json` and `hooks/*.py` — Codex hook guards for session start, prompt submit, tool use, and stop closeout.
- `workflows/*/workflow.yml` — governed workflow definitions; Git/CD authority still comes from catalogs and Kubernetes desired state.
- `capabilities/*` — bounded capability packages; current pilot is plugin constitution governance.
- `docs/reference/*.md` and `docs/runbooks/*` — human reference and operator runbooks for governance surfaces.
- `runtime/` — local state only; do not use it as source policy, do not commit it, and avoid raw log or transcript reads.

## Instruction ownership inside @Bears
- `agents/*.toml` are role execution profiles. Use them only after `scripts/platform_roles.py route <path>` or a task packet selects that role.
- Role profiles define specialist scope, allowed evidence, forbidden actions, handoff shape, and validation focus.
- Role profiles do not own product registration, Git/CD policy, deployment policy, or secret exceptions.
- `assets/catalog/*.v1.json` owns machine policy. `scripts/*.py` and `hooks/*.py` enforce it. `skills/*/SKILL.md` owns task workflow. `docs/reference/*.md` explains it.
- After role profile changes, run `python3 scripts/opencode_agent_sync.py sync --target repo` and restart long-running OpenCode runtime before relying on generated `.opencode/agent/*.md`.

## External runtime boundary
- `BearsCLOUD/codexdaemon` owns daemon source, Knowledge Orchestrator runtime code, Codex Exec job handling, issue-daemon implementation, daemon packaging, runtime schemas, and runtime tests.
- This plugin may route, validate, or govern `codexdaemon`; it must not carry daemon runtime implementation.
- Route `/srv/bears/dev/app/codexdaemon` through `bears-codex-daemon-engineer` before codexdaemon implementation.

## Rules
- Keep artifacts and contracts in English.
- Keep `AGENTS.md` compact; put executable policy in plugin catalogs, scripts, skills, and tests.
- `kubernetes_deployment` is valid only when backed by Kubernetes desired state and `local_cd`; local host or manual deploy paths are policy violations.
- Git work branches are restricted to `main` or `dev` unless an explicit task packet names another branch.
- `dev` is only for prod-deployed product repos; current prod-deployed products are `seller` and `platform`.
- Prod-deployed product registration must define canonical repo, local path, `dev` work branch, `main` deploy branch, local `@Bears` CD selector, and GitHub Releases versioning.
- Every discovered drift must have a GitHub issue in the owning repository before closeout. If ownership is unclear, create the issue in the nearest control repository and name the ownership gap.
- Every completed task must end with commit plus push for the changed tracked repo, including instruction-only changes.
- Keep Git clean after push; do not stage unrelated dirty files, and report any carried dirty paths.
- Do not store secrets, raw logs, kubeconfigs, tokens, private chats, production data, `.env` values, or `.knowledge/**` artifacts.

## Entity terms
- Use exact terms `local_cd` and `kubernetes_deployment` when those surfaces are changed.
- Artifacts and subagent messages must use English only.
- Wording must stay strict, concise, and entity-bound.

## Canonical checkout
- The canonical @Bears source checkout is `/srv/bears/plugins/bears`.
- Do not edit, commit, close out, or report plugin work from a hidden `/tmp` worktree when the canonical checkout exists.
- If an approved isolated worktree is required, capture canonical dirty status, preserve a backup path, sync back to `/srv/bears/plugins/bears`, and make exact validation pass there before closeout.

## Workflow gates
- There is exactly one Codex plugin for this governance model: `/srv/bears/plugins/bears`.
- Keep lifecycle order: route gate -> constitution gate -> research gate.
- Telegram workflow governance stays here as a skill/catalog/script bundle owned by `bears-telegram-platform-engineer`.
- Do not recreate a standalone Telegram plugin, app, connector, MCP server, or runtime surface except the exact cataloged `/srv/bears/plugins/bearstg` read-only MCP plugin.

## Validation
- Local commit validation owns blocking plugin test proof.
- Closeout proof must cite `runtime/local-commit-validation/<main_sha>.json`.
- GitHub Actions `.github/workflows/validate.yml` is operator-dispatched diagnostics.
- Agents must not run repo validator suites or tests manually unless operator-approved, except route/audit gates and file-shape checks named by the active route.
