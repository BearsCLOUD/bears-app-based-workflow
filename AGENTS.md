# @Bears Plugin Router

## Scope
- This directory is the source checkout for the `@Bears` Codex governance plugin.
- It owns Bears action rules, roles, workflow policy, hooks, CD policy, and Dagger objective-runtime-proof policy.
- Codex daemon / Knowledge Orchestrator runtime routes through the `BearsCLOUD/apps` repo at `source_subpath=codexdaemon`. `BearsCLOUD/codexdaemon` is a deprecated/archive-candidate source only.

## Entity terms
- `app` means a Bears product application source directory in the `BearsCLOUD/apps` repository or a workspace-local checkout selected by generated local config.
- `project` means a GitHub Project planning board with linked Issues and metadata fields. Do not say `project` for a local repo, path, workspace directory, or product app.
- Say `target`, `registered target`, `repo`, `path`, `workspace surface`, or `app directory` for filesystem/source ownership.

## Required refs
- Plugin manifest: `.codex-plugin/plugin.json`.
- Role catalog: `assets/catalog/platform-role-catalog.v1.json`.
- Git/CD contracts: `assets/catalog/git-deploy-contract.v1.json` and `assets/catalog/cd-kube-deploy-contract.v1.json`.
- Canonical subagents roles: `assets/catalog/platform-role-catalog.v1.json`.
- Canonical role gate: `scripts/subagents_roles.py` from this plugin checkout.

## Functional map
- `agents/*.toml` — canonical Bears role profiles; do not sync them into OpenCode agents.
- `skills/*/SKILL.md` — Codex skills for governance, role gates, deployment review, Kubernetes, Infisical, DNS, health, Spec Kit flow, and Secret Factory.
- `assets/catalog/*.v1.json` — machine-readable policy catalogs for roles, workflow gates, Git/CD, closeout, and governance.
- `assets/schemas/*.schema.json` and `schemas/*.schema.json` — legacy/internal guardrail schemas only; they must not serve as app PASS evidence.
- `scripts/*.py` — deterministic routers, closeout tools, cache sync, role gates, Dagger proof wrappers, and governance helpers.
- `hooks.json` and `hooks/*.py` — Codex hook guards for session start, prompt submit, tool use, and stop closeout.
- `workflows/*/workflow.yml` — governed workflow definitions; Git/CD authority still comes from catalogs and Kubernetes desired state.
- `capabilities/*` — bounded capability packages; current pilot is subagents roles governance.
- `docs/reference/*.md` and `docs/runbooks/*` — human reference and operator runbooks for governance surfaces.
- `runtime/` — local state only; it is not source policy, do not commit it, and do not read raw logs or transcripts.

## Instruction ownership inside @Bears
- `agents/*.toml` are role execution profiles. Activate them only after `scripts/subagents_roles.py route <path>` or a task packet selects that role.
- Role profiles define specialist scope, allowed evidence, forbidden actions, handoff shape, and validation focus.
- Role profiles do not own product registration, Git/CD policy, deployment policy, or secret exceptions.
- `assets/catalog/*.v1.json` owns machine policy. `scripts/*.py` and `hooks/*.py` enforce it. `skills/*/SKILL.md` owns task workflow. `docs/reference/*.md` explains it.
- After role profile changes, keep role behavior in `agents/*.toml` and plugin skills/catalogs only; OpenCode is deployment-only and must not receive generated Bears agent files.

## External runtime boundary
- `BearsCLOUD/apps` is the canonical product-app repository for codexdaemon source after consolidation. `BearsCLOUD/codexdaemon` may be routed only as a deprecated/archive-candidate migration source until archived.
- This plugin may route, validate, or govern `codexdaemon`; it must not carry daemon runtime implementation.
- Route `BearsCLOUD/apps:codexdaemon` through `bears-codex-daemon-engineer` before codexdaemon implementation.

## Rules
- Keep artifacts and contracts in English.
- Keep this file as a router. Do not duplicate full role, Git, branch, subagent, CD, deploy, or closeout policy here.
- `assets/catalog/*.v1.json` owns machine policy. `scripts/*.py`, `hooks/*.py`, `skills/*/SKILL.md`, and tests enforce it.
- Do not run route/audit manually before plugin changes. Role coverage runs through `autoCI` or local commit validation, and plans record only the computed owner role and expected status names.
- `kubernetes_deployment` is valid only with Kubernetes desired state and `local_cd`. Local host processes, local `infisical run`, manual `kubectl apply`, and manual secret injection are not final live PASS evidence.
- Infisical is secret custody and environment injection only. Runtime software proof must pass through Kubernetes refs, workload evidence, and health proof.
- `control-plane/infisical` is bootstrap or preflight support only; it is not the runtime desired-state owner.
- Follow the root Git closeout rule: every Git-tracked file change must end with a local commit in the owning repo.
- Stage only task-owned files; before push, inspect autoCI/local commit validation evidence for known errors and fix known errors before push.
- Do not store secrets, raw logs, kubeconfigs, tokens, private chats, production data, `.env` values, or `.knowledge/**` artifacts.

## Entity terms
- Say exact terms `local_cd` and `kubernetes_deployment` when those surfaces are changed.
- Artifacts and subagent messages must use English only.
- Wording must stay strict, concise, and entity-bound.

## Portable checkout
- The canonical @Bears source checkout is the current Git checkout for this plugin.
- Plugin source must not depend on server-specific absolute paths. Local generated config may store real host paths outside the plugin source.
- Do not edit, commit, close out, or report plugin work from a hidden temp worktree when the canonical checkout exists.
- If an approved isolated worktree is required, capture canonical dirty status, preserve a backup path, sync back to the canonical checkout, and make exact validation pass there before closeout.

## Workflow gates
- There is exactly one Codex plugin for this governance model: this `@Bears` plugin checkout.
- Keep lifecycle order: route gate -> subagents-roles gate -> research gate.
- Telegram workflow governance stays here as a skill/catalog/script bundle owned by `bears-telegram-platform-engineer`.
- Codex Telegram operator feedback is skill-driven by `skills/codex-telegram-operator-gate` and the configured `codex-telegram` MCP server; do not register or enable a Telegram `PreToolUse` hook gate.
- Legacy `codex-telegram-operator` plugin checkout is a migration source only; it must not own Bears governance, Telegram runtime, MCP runtime, or hook authority.
- Do not recreate a standalone Telegram plugin, product app, connector, MCP server, or runtime surface except the exact cataloged `bearstg` read-only MCP plugin and the plugin-owned `mcp` instruction zones server documented in `docs/reference/instruction-artifacts-mcp.md`.

## Proof and safety checks
- Plugin policy must not treat tests, validators, schemas, lint, route/audit, or static checks as PASS evidence.
- Platform/full product proof routes to Dagger ObjectiveRuntimeProof; final live software PASS routes to Kubernetes desired state with `kubernetes_deployment` plus `local_cd`.
- Agents must not run repo validator suites, tests, or route/audit manually unless the operator names one exact command.
- Local commit validation and autoCI own blocking plugin test, validator, and route/audit proof.
- Closeout proof must cite `runtime/local-commit-validation/<main_sha>.json` after the commit exists when that artifact is available.
- Agents may inspect current commit or PR GitHub Checks, Actions runs, statuses, logs, and artifacts as safety context only.
- Deep Kubernetes desired-state Git history reads are forbidden unless the operator explicitly requests bounded history work in the current turn.
