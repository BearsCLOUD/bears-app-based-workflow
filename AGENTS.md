# @Bears Plugin Router

## Scope
- This directory is the source checkout for the `@Bears` Codex governance plugin.
- It owns Bears action rules, roles, contracts, validators, workflow policy, hooks, and CD policy.
- Codex daemon / Knowledge Orchestrator runtime routes through `/srv/bears/dev/app/codexdaemon`; the canonical product-app repository is `BearsCLOUD/apps`. `BearsCLOUD/codexdaemon` is a deprecated/archive-candidate source only.

## Required refs
- Plugin manifest: `.codex-plugin/plugin.json`.
- Role catalog: `assets/catalog/platform-role-catalog.v1.json`.
- Git/CD contracts: `assets/catalog/git-deploy-contract.v1.json` and `assets/catalog/cd-kube-deploy-contract.v1.json`.
- Canonical plugin constitution: `assets/catalog/plugin-constitution.v1.json`.
- Canonical role gate: `/srv/bears/plugins/bears/scripts/platform_roles.py`.

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
- `BearsCLOUD/apps` is the canonical product-app repository for codexdaemon source after consolidation. `BearsCLOUD/codexdaemon` may be routed only as a deprecated/archive-candidate migration source until archived.
- This plugin may route, validate, or govern `codexdaemon`; it must not carry daemon runtime implementation.
- Route `/srv/bears/dev/app/codexdaemon` through `bears-codex-daemon-engineer` before codexdaemon implementation.

## Rules
- Keep artifacts and contracts in English.
- Keep `AGENTS.md` compact; put executable policy in plugin catalogs, scripts, skills, and tests.
- `kubernetes_deployment` is valid only when backed by Kubernetes desired state and `local_cd`; local host or manual deploy paths are policy violations.
- For every Bears parent work session, start or reuse one long-lived parallel `gitflow` subagent using `bears-git-workflow-helper` instructions with model `gpt-5.4-mini`, reasoning `high`, and no parent/start context.
- Reuse the same `gitflow` subagent for the entire parent work; do not spawn a new `gitflow` subagent for each step.
- The `gitflow` subagent is a closeout lane only. It must not run general read-only audits, review unrelated repos, or replace owner-role validation.
- The parent agent must not wait for `gitflow` subagent feedback on the critical path.
- Completed task slice means validated, committed, and pushed. Leaving completed dirty work is forbidden.
- After validation, immediately send the same `gitflow` subagent a `commit+push required` closeout notice with repo path, explicit allowlisted changed files, validation result, target branch, and intended commit message.
- If unrelated dirty files exist, commit only the completed slice's explicit allowlisted files and report carried dirty paths.
- If a hard safety hold prevents commit or push, the slice is not complete; report the exact blocker, owner, and GitHub issue, and keep gitflow hold active.
- The `gitflow` subagent closes only explicit assigned Git tasks. It must reject completion claims without commit/push evidence or an explicit blocker. The main agent owns final clean-status reporting and must not treat `gitflow` as a general auditor.
- Deployment, infrastructure, Kubernetes desired-state, CD, runtime rollout, rollback, network/egress, and cluster-evidence tasks must also start or reuse one long-lived parallel `infra/deploy/kube` subagent.
- The infra/deploy/kube subagent uses `bears-deploy-platform-engineer` instructions with model `gpt-5.5`, reasoning `high`, and no parent/start context. Reuse the same infra/deploy/kube subagent for the entire parent work.
- The parent sends start, scope-change, validation, and closeout packets to that subagent and does not wait for feedback on the critical path unless a hard blocker is already known.
- The infra/deploy/kube subagent is an audit and governance lane only; it does not replace exact role gates, Kubernetes desired state, local `@Bears` CD, or branch/secret policies.
- Instruction, `AGENTS.md`, role-prompt, developer-instruction routing, workflow prose, governance-doc, and instruction-ownership tasks must also start or reuse one long-lived parallel `instructions/AGENTS` subagent.
- The instructions/AGENTS subagent uses `bears-docs-maintainer` instructions with model `gpt-5.5`, reasoning `high`, and no parent/start context. Reuse the same instructions/AGENTS subagent for the entire parent work.
- The parent sends start, scope-change, validation, and closeout packets to that subagent and does not wait for feedback on the critical path unless a hard blocker is already known.
- The instructions/AGENTS subagent is an audit and governance lane only; it does not replace nearest `AGENTS.md`, exact route gates, `@Bears` catalogs/scripts/skills, Git closeout, or generated-agent sync requirements.
- Git work branches are restricted to `main` or `dev` unless an explicit task packet names another branch.
- Use `main` for this plugin, workspace-control, infra desired-state, dev-instance production apps/services, and non-prod product repos.
- Dev-instance production means the app/service production runtime intentionally lives on the current dev instance through Kubernetes desired state and local `@Bears` CD. It stays main-only because `main` is the source of truth for that runtime.
- The `@Bears` plugin is a dev-instance production governance app; plugin work happens directly on `main`.
- Use `dev` only for product repos that have a separate production promotion branch. Current `dev` product exceptions are `seller` and `platform`.
- Prod-deployed product registration must define canonical repo, local path, branch class, `dev` work branch when used, `main` deploy branch, local `@Bears` CD selector, and GitHub Releases versioning.
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
- Codex Telegram operator feedback is skill-driven by `skills/codex-telegram-operator-gate` and the configured `codex-telegram` MCP server; do not register or enable a Telegram `PreToolUse` hook gate.
- Legacy `/srv/bears/plugins/codex-telegram-operator` is a migration source only; it must not own Bears governance, Telegram runtime, MCP runtime, or hook authority.
- Do not recreate a standalone Telegram plugin, app, connector, MCP server, or runtime surface except the exact cataloged `/srv/bears/plugins/bearstg` read-only MCP plugin.

## Validation
- Local commit validation owns blocking plugin test proof.
- Closeout proof must cite `runtime/local-commit-validation/<main_sha>.json`.
- GitHub Actions `.github/workflows/validate.yml` is operator-dispatched diagnostics.
- Agents must not run repo validator suites or tests manually unless operator-approved, except route/audit gates and file-shape checks named by the active route.
