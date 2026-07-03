# @Bears Plugin Router

## Scope
- This directory is the source checkout for the `@Bears` Codex governance plugin.
- It owns Bears action rules, roles, workflow policy, hooks, CD policy, and Dagger objective-runtime-proof policy.
- Codex daemon / Knowledge Orchestrator runtime routes through `/srv/bears/dev/app/codexdaemon`; the canonical product-app repository is `BearsCLOUD/apps`. `BearsCLOUD/codexdaemon` is a deprecated/archive-candidate source only.

## Entity terms
- `app` means a Bears product application source directory under `/srv/bears/dev/app` or the `BearsCLOUD/apps` repository.
- `project` means a GitHub Project planning board with linked Issues and metadata fields. Do not use `project` for a local repo, path, workspace directory, or product app.
- Use `target`, `registered target`, `repo`, `path`, `workspace surface`, or `app directory` for filesystem/source ownership.

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
- `assets/schemas/*.schema.json` and `schemas/*.schema.json` — legacy/internal guardrail schemas only; they must not be used as app PASS evidence.
- `scripts/*.py` — deterministic routers, closeout tools, cache sync, role gates, Dagger proof wrappers, and governance helpers.
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
- Keep this file as a router. Do not duplicate full role, Git, branch, subagent, CD, deploy, or closeout policy here.
- `assets/catalog/*.v1.json` owns machine policy. `scripts/*.py`, `hooks/*.py`, `skills/*/SKILL.md`, and tests enforce it.
- Run `python3 scripts/platform_roles.py route <exact-path>` and `python3 scripts/platform_roles.py audit <exact-path>` before plugin changes.
- `kubernetes_deployment` is valid only with Kubernetes desired state and `local_cd`. Local host processes, local `infisical run`, manual `kubectl apply`, and manual secret injection are not final live PASS evidence.
- Infisical is secret custody and environment injection only. Runtime software proof must pass through Kubernetes refs, workload evidence, and health proof.
- `control-plane/infisical` is bootstrap or preflight support only; it is not the runtime desired-state owner.
- Completed plugin changes must be validated, committed, and pushed from `/srv/bears/plugins/bears`; stage only task-owned files and report carried dirty paths.
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
- Do not recreate a standalone Telegram plugin, product app, connector, MCP server, or runtime surface except the exact cataloged `/srv/bears/plugins/bearstg` read-only MCP plugin.

## Objective runtime proof policy
- Platform Dagger proof lives in `/srv/bears/dev/platform/dagger/`; plugin policy must route agents to that entrypoint.
- Final live PASS is `/srv/bears/kubernetes` `kubernetes_deployment` plus `local_cd` proof.
- Do not create or close work through a test, contract, validator, schema, lint, or static-check layer. Those may remain only as internal safety guardrails and never as PASS evidence.
- If any role, skill, catalog, hook, issue packet, or docs surface still uses validation-layer acceptance, migrate it to Dagger objective runtime proof or remove the obsolete reference.

## Safety checks
- Route/audit gates are agent-local ownership checks; they are not PASS evidence.
- Repo suites, tests, validators, schemas, lint, Docker checks, Kubernetes checks, browser checks, and ad hoc checks are safety-only unless a human explicitly requests one named command.
- Plugin closeout for app/platform behavior must cite an ObjectiveRuntimeProof packet or final Kubernetes live proof, not validation artifacts.
- Agents may inspect current commit or current PR GitHub Checks, GitHub Actions runs, statuses, logs, and artifacts as safety context only.
- Deep `/srv/bears/kubernetes` Git history reads are forbidden unless the operator explicitly requests bounded history work in the current turn.
- GitHub Actions `.github/workflows/validate.yml` is operator-dispatched diagnostics only.
