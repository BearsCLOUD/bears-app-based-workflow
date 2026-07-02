# Agentic Enterprise Workflow

## Purpose

This workflow keeps Bears orchestration small, parallel, measurable, and reusable. It governs agent work; it does not create product code, GitOps files, infra payloads, connectors, MCP servers, apps, runtime services, or production mutations.

## Technical terms

- Constitution: the top-level rule set for agentic workflow behavior.
- Repo domain: one logical repository boundary for a scope: `platform`, `gitops`, `infra`, or `product_infra`.
- Scope: one repo domain, one measurable output, one owner lineage, one timebox, one token budget, and one validation path.
- Owner lineage: durable mapping from L2 owner to L3 executor and L3 doc agent for a scope family.
- Decision log: file-backed record of user facts, user directives, agent decisions, contradictions, and user-input requests.
- Clarification gate: post-research decision point that asks the operator only when the answer changes architecture, cost, security, SaaS standards, agent-development standards, or conflicting user facts.
- Degradation packet: metrics-backed decision to continue, throttle one scope, isolate one scope, block workflow, or roll back runtime activation.
- Delivery complete: final state where the main commit passed CI, the local plugin cache matches that exact SHA, and effective hooks proof exists.

## Files

- Catalog: `assets/catalog/agentic-enterprise-workflow.v1.json`.
- Constitution: `assets/catalog/agentic-enterprise-constitution.v1.json`.
- Validator: `scripts/agentic_enterprise_workflow.py`.
- Schemas: `assets/schemas/agentic-enterprise-workflow.v1.schema.json`, `assets/schemas/agentic-enterprise-constitution.v1.schema.json`, `assets/schemas/decision-log.v1.schema.json`, and `assets/schemas/scope-matrix.v1.schema.json`.
- Hooks: `hooks.json`, `hooks/session_start.py`, `hooks/pre_task_guard.py`, and `hooks/pre_tool_policy.py`.
- Fixtures: `tests/fixtures/agentic_enterprise_workflow/`.
- Cache sync: `assets/catalog/plugin-cache-sync.v1.json`, `assets/schemas/plugin-cache-sync-state.v1.schema.json`, `scripts/plugin_cache_sync.py`, and `runtime/plugin-cache-sync/plugin-cache-sync-state.v1.json`.

## Four repo domains

| Domain | Owns | Must not own |
| --- | --- | --- |
| `platform` | Reusable product core: auth, gateway, queues, Redis, shared APIs, tenant registry, provider gateway. | Cluster desired state, host bootstrap, product-specific runtime overrides, Bears governance catalogs. |
| `gitops` | Desired state: Helm values, Kustomize overlays, Argo/Flux apps, promotion, rollback, secret refs. | Business logic, product feature code, agent governance rules, raw secrets. |
| `infra` | Shared host, cluster, network, bootstrap, workspace runtime, shared observability runtime. | Product logic, GitOps promotion state, product adapters, raw secret values. |
| `product_infra` | Product-specific infra adapters, runtime requirements, resource profiles, observability requirements. | Shared platform core, shared host bootstrap, global governance catalogs, production desired-state source. |

`/srv/bears/kubernetes` is transitional evidence for `gitops` and `infra` until the repo split packet exists.

## Agent layers

| Layer | Responsibility | Must not do |
| --- | --- | --- |
| L1 head orchestrator | Strategy, scope matrix, task decomposition, task matrix writing, compact controller state, L2 governance packets, goal block/unblock from state. | Code edits, tests, raw logs, raw subagent messages, MCP/skill/plugin discovery, subagent spawn per task. |
| L2 domain orchestrator | Domain research, domain governance, scope-boundary review, L3 assignment review, progress review, remediation governance. | Task decomposition, subagent spawn per task, global L1 state overwrite, cross-domain writes without split, final merge authority. |
| L3 executor | Exact task execution, docs, schemas, fixtures, bounded output packets. | Scope redefinition, owner-lineage changes, raw secret reads, unbounded search. |

## Required lifecycle

Every user message creates a scope row. The row starts with research, then clarification gate, L1 task decomposition, and L2 governance review. The workflow does not spawn one subagent for each task.

```text
scope_row -> research -> clarification_gate -> l1_task_decomposition -> l2_governance_review -> l3_assignment -> bounded_execution -> progress_packet -> local_commit_validation_read -> commit_to_main -> local_commit_validation_pass -> cache_sync_done -> effective_hooks_proof -> delivery_complete
```

## Goal agent modes

The executable `/goal` modes are `goal_1_agent` and `goal_parallel_l1`.

`goal_1_agent` creates its own state file first, researches, decomposes the operator `/goal` prompt into scopes, persists scopes in state, and solves scopes sequentially through Bears Spec Kit flow. It uses helper agents for token economy, git/CI/cache closeout, and review/fix support. Review/fix stops only on a real blocker. Subagents spawn with `fork_context=false` and `parent_context=none`.

`goal_parallel_l1` creates its own state file first, normalizes the operator `/goal` prompt into scopes, persists scopes in state, and for the selected scope runs research, development-area design, requirements, and Spec Kit logic in sequence. It spawns one L2 subagent for the approved Spec Kit plan, then continues its own sequential workflow without L2 tracking or waiting. L2 helper subagents spawn with `fork_context=false` and `parent_context=none`.

## Main-only delivery rule

Bears plugin workflow commits go directly to `main`. Pull requests, GitHub review threads, and development branches are not delivery authority for this plugin workflow. The local git `pre-commit` hook blocks failing staged changes, and the local git `post-commit` hook records `runtime/local-commit-validation/<main_sha>.json` with `status=pass` for the exact `main` SHA. GitHub Actions runs diagnostics on `main` push and keeps `workflow_dispatch` for operator emergency full-suite diagnostics. The local Codex plugin cache updates on this host only after exact local commit validation passes for the exact `main` SHA. Task closeout is invalid until `runtime/plugin-cache-sync/plugin-cache-sync-state.v1.json` records `delivery_complete=true` and effective hooks proof. The `Stop` hook blocks explicit closeout intent when delivery is incomplete; ordinary Stop events without closeout intent pass.

## Small scope rule

A scope is invalid when it crosses repo domains, lacks measurable output, lacks owner lineage, exceeds time or token policy, or overlaps another write scope. `SessionStart` or the first guard creates `runtime/agent-workflow/current-enterprise-orchestrator-state/workflow-matrix/orchestrator-state.json` for the L1 run. Active hook control derives `duration_min` from `started_at_epoch` when event metadata omits duration. It denies `PreTask` and `PreToolUse` when compact state or event metadata proves a scope is over the 5 minute hard split threshold without split or decomposition state. It also denies token metadata over the workflow token budget without throttle or split state. Governed L1/L2/L3 work with no time or token control metadata is denied; unmanaged side answers receive `control_not_armed`.

## Decision log rule

User facts and user directives outrank agent decisions. Conflicting active user facts or directives create a contradiction record with `status=blocked` and `needs_user_input=true`. Raw chat text is not stored.

## Hook policy

The hot path reads compact state, the compiled workflow catalog, plugin delivery state, and metadata-only git status. It may create one compact ignored runtime state file for the current L1 run.

| Hook | SLO |
| --- | --- |
| `PreToolUse` | `<150 ms` |
| internal pre-task guard via `UserPromptSubmit` | `<250 ms` |
| `SessionStart` | `<500 ms` |
| closeout guard via `Stop` | `<500 ms` |

Hooks must not run tests, broad search, network calls, raw log reads, workspace scans, or secret reads. Deterministic enforcement stays in validators and CI.

## Runtime degradation rule

Metrics are `duration_min`, `token_spend`, `errors`, `heartbeat_stale_minutes`, and `progress_delta`. Actions are `continue`, `throttle_scope`, `isolate_scope`, `block_workflow`, and `rollback_runtime_activation`. Only the problem scope stops; unrelated scopes continue in parallel.

## External pattern used

The workflow adopts Symphony patterns without vendoring code: scope as a state machine, one authoritative state, isolated write scopes, proof-of-work packets, and stall remediation.

## Validator usage

CI runs the validator:

```text
python3 scripts/agentic_enterprise_workflow.py validate
```

Before commit, agents may only parse syntax and review diffs when the operator forbids manual tests.
