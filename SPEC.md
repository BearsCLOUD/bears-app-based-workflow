# Bears Plugin Specification

## Scope

`/srv/bears/plugins/bears` is the canonical Bears governance plugin for shared platform workflow control. It is the only Codex plugin authorized for this Bears governance model.

Standalone `bears-speckit` plugin or layer claims are deprecated. Generated `.specify` workspace files are ignored and must not become plugin source. Spec Kit core skills stay upstream in `/srv/bears/.agents/skills`; `@bears` only orchestrates them through Bears-owned workflow skills such as `speckit-bears-flow`.

Canonical source after split:

- remote: `https://github.com/BearsCLOUD/bears_plugin`;
- workspace mount: Git submodule at `/srv/bears/plugins/bears`;
- manifest field: `.codex-plugin/plugin.json` `repository`;
- broad repo identity: parent-only classifier, never implementation authority.

It owns:

- platform role coverage and `ROLE_COVERAGE_BLOCKER` behavior;
- the universal role-gate methodology and exact blocker packet contract;
- the `auth_core -> bears_gateway -> cd_deploy_stage` workflow spine;
- Bears-owned skills for governance, role gate, blocker evaluation, deploy gate, workflow validation, and `/goal` prompt generation;
- deterministic roadmap control for `/goal`-started workflow runs, including multi-spec concurrency control and session reuse binding;
- session worker runtime catalogs and validators for Codex sessions that execute current Spec Kit truth under Bears control;
- subagent orchestration policy for non-product stage-boundary audits, with legacy post-task aliases only for compatibility;
- project registry gate and the registry-gated `project-mandate` checklist skill;
- Telegram workflow governance as a skill-bundle surface under `/srv/bears/plugins/bears/skills/bears-telegram-workflow` plus sibling Telegram skills, catalogs, scripts, and tests;
- plugin constitution governance at `assets/catalog/plugin-constitution.v1.json` and `scripts/plugin_constitution.py`;
- executable capability inventory at `capabilities/inventory.v1.json` and plugin constitution wrapper at `capabilities/plugin_constitution/`;
- the English-only artifact and subagent-message policy at `assets/catalog/plugin-governance-language-policy.v1.json`;
- JSON-first governance schemas and deterministic validators;
- unified machine-first closeout validation through `assets/catalog/bears-doctor.v1.json` and `scripts/bears_doctor.py`;
- workspace hygiene classification and stale artifact cleanup policy through `assets/catalog/workspace-hygiene.v1.json` and `scripts/workspace_hygiene.py`;
- Spec Kit initialization policy for ignored generated `.specify` scripts, templates, workflow registry, integration metadata, and constitution.

The language policy is hard: `artifact_language=en`, `subagent_message_language=en`, and wording stays strict, concise, and entity-bound. Use `local_cd` and `kubernetes_deployment` when those entities are intended. Do not use generic `deploy`. Do not add sample, example, or illustrative sections.

Repo-proof validation is deterministic and repo-only. It scans the configured governance artifacts and policy docs. It does not claim live runtime chat proof.

## Plugin Constitution

The plugin owns `assets/catalog/plugin-constitution.v1.json`, `scripts/plugin_constitution.py`, `docs/reference/plugin-constitution.md`, `tests/test_plugin_constitution.py`, and `capabilities/plugin_constitution/` as the constitution gate for Bears plugin governance changes.

Required lifecycle order for complex work is:

1. route gate;
2. constitution gate;
3. research gate;
4. prototype gate;
5. design gate;
6. Spec Kit gate;
7. role gate;
8. subagent execution;
9. validation;
10. stage-boundary audit.

The constitution gate checks the one-plugin boundary, absence of apps/connectors/MCP/runtime/product behavior, external Spec Kit boundary, executable capability-inventory boundary, exact role coverage, English entity-bound artifacts, restricted-data exclusion, and inventory sync.

Validation entrypoint requirements for this surface are:

- `python3 scripts/plugin_constitution.py validate`
- `python3 scripts/plugin_constitution.py inspect-change --packet <path>`
- `python3 scripts/platform_roles.py route /srv/bears/plugins/bears/assets/catalog/plugin-constitution.v1.json`
- `python3 scripts/platform_roles.py audit /srv/bears/plugins/bears/assets/catalog/plugin-constitution.v1.json`

## Agent GitHub dev CD governance

The plugin owns `assets/catalog/agent-github-dev-cd.v1.json`, `scripts/agent_github_dev_cd.py`, and `docs/reference/agent-github-dev-cd.md` as a deprecated, non-authoritative reference for former `/goal` branch control, remote per-agent branches, fresh no-parent-context audit review, `goal -> dev` auto-merge, and dev CD through `/srv/bears/kubernetes`. Active plugin delivery is main-only through `assets/catalog/agentic-enterprise-workflow.v1.json` `delivery_policy`.

The GitHub diagnostics lane is `.github/workflows/validate.yml`. The validator must fail when:

- `pull_request`, `merge_group`, or `push` is active for plugin delivery;
- `jobs.dev-cd-gate` or `jobs.unit-fast` is present;
- required diagnostics commands do not include `ci_requirements`, `platform_roles`, `agent_github_dev_cd`, overlay validation, and `test_selection` catalog validation;
- automatic plugin tests run from GitHub instead of the local git `pre-commit` and `post-commit` hooks;
- the deprecated reference grants active dev auto-merge, active local_cd, branch-dependent closeout, or cluster mutation from the plugin;
- production deploy is allowed anywhere in this flow.

Fixed GitHub issue identifiers are `type:bugfix`, `type:idea`, and `type:develop-ready`. `type:develop-ready` is produced from repository constitution alignment, research, and accepted operator decisions.

agent pickup may start bounded development only for `type:develop-ready` after route gate, constitution evidence, research evidence, accepted decision evidence, owning role, task packet, duplicate guard, and `verify-agent-pickup --dry-run` pass. agent pickup blocks unlabeled, idea-only, bugfix-only, blocked, human-review (`needs-human` or `manual-only`), secret, credentials, deploy, production, and security-review issues.

## Skill discovery source of truth

`assets/catalog/plugin-skill-catalog.v1.json` is the canonical active/disabled skill catalog. `scripts/skill_catalog.py` validates the catalog and generates `docs/generated/README.skill-inventory.md` plus `docs/generated/SPEC.skill-inventory.md`. Disabled skill directories MUST NOT contain `SKILL.md`; preserved content stays in `SKILL.disabled.md`.

## Telegram workflow skill bundle

Telegram is governed inside this canonical plugin as skills, catalogs, scripts, and tests. `bears-telegram-workflow` is a skill name and route target, not a separate plugin.

The governed Telegram skill-bundle surfaces are:

- `/srv/bears/plugins/bears/skills/bears-telegram-workflow`;
- `/srv/bears/plugins/bears/skills/telegram-aiogram-migration`;
- `/srv/bears/plugins/bears/skills/telegram-quality-testing`;
- `/srv/bears/plugins/bears/skills/telegram-plugin-skill-factory`;
- `/srv/bears/plugins/bears/assets/catalog/telegram-*.json`;
- `/srv/bears/plugins/bears/scripts/telegram_*.py`.

The canonical route for Telegram workflow governance is:

`python3 /srv/bears/plugins/bears/scripts/platform_roles.py route /srv/bears/plugins/bears/skills/bears-telegram-workflow`

It must select `bears-telegram-platform-engineer`. No standalone `/srv/bears/plugins/bears-telegram-workflow` plugin, app, connector, MCP server, or live Telegram runtime is authorized by this skill bundle. The canonical Bears role gate is first, and Telegram validators are secondary.

## Non-goals

- No apps/connectors in this plugin root.
- No MCP servers in this plugin root.
- No standalone `bears-speckit` plugin or layer.
- No upstream Spec Kit skill vendoring.
- No product runtime edits from the plugin root.
- No production deployment, live secret access, or raw production-data handling.

## Role model

Every registered role must define `name`, `description`, `developer_instructions`, `model`, `model_reasoning_effort`, and `sandbox_mode` in TOML. Each `developer_instructions` block must name its own agent and include the exact `description` as the role-specific override.

Missing role coverage for any shared platform part is a hard `ROLE_COVERAGE_BLOCKER`. The only allowed next write is the missing role/catalog/governance artifact needed to restore coverage.

The canonical methodology is:

- the orchestrator must classify the requested write scope into a concrete part;
- exactly one valid primary specialist or helper role must own that concrete part;
- group, parent, controller, or reviewer roles may classify or review but cannot satisfy the primary-role invariant for child implementation;
- `/srv/bears/plugins/bears` and `plugins/bears` are broad governance-root router targets only; they classify the plugin root through the parent route and must not authorize child implementation handoff;
- broad or mixed-scope requests must decompose before implementation;
- implementation handoff remains blocked until `scripts/platform_roles.py audit <target>` passes.

The file-backed methodology lives in `assets/catalog/role-gate-methodology.v1.json` and validates with `scripts/role_gate_methodology.py validate`. Its independent control audit is complete only when parent-only coverage, broad-role fallback, ambiguous ownership, unknown/unmapped parts, and missing role artifacts all fail closed.

## Compatibility migration routing

`/srv/bears/dev` is an external migration reference for `control`, `platform`, `products`, `quality`, `infrastructure`, and `ops`, not root-owned dev-core authority. `/srv/bears/projects` is a deprecated transitional source and cannot provide parent-scope implementation coverage.

The catalog must route these targets without fallback:

- `/srv/bears/dev` -> `bears-platform-role-governor`;
- `kube`, `kubernetes`, `bears-infra`, and `/srv/bears/kubernetes` -> `bears-deploy-platform-engineer`;
- `android-emulator` and `/srv/bears/dev/platform/android-emulator` -> `bears-android-emulator-platform-engineer`;
- `sentry` and `/srv/bears/dev/quality/sentry-observability` -> `bears-observability-platform-engineer`;
- `/srv/bears/dev/app/theants` is the canonical The Ants registered app route; `/srv/bears/projects/theants` is a legacy compatibility input only -> `bears-product-app-zone-engineer`;
- `/srv/bears/dev/quality/e2e` -> `bears-analytics-quality-engineer`;
- `/srv/bears/dev/ops/runbooks` -> `bears-ops-runbook-engineer`;
- `/srv/bears/dev/control/provenance` -> `bears-platform-role-governor`.

Kubernetes production CD for registered Bears infra targets is governed by `assets/catalog/git-deploy-contract.v1.json`, `assets/catalog/cd-kube-deploy-contract.v1.json`, and `scripts/bears_auto_cd.py`. The Git contract owns `dev` to `main` merge policy and target mapping; the CD contract owns only what deploys, from where, and the ordered Kubernetes actions. Production apply is automatic from the infra repo `main` GitHub Actions path; local agents do not run the deploy.

## Workflow routing

Workflow routing stays inside the one-plugin Bears model:

- plugin functionality layer owns Bears skills, workflows, catalogs, validators, schemas, agents, actions, capability inventory, tests, README, SPEC, and reference docs;
- generated `.specify` workspace files stay ignored and must not become plugin source;
- generated Spec Kit feature artifacts store project requirements, plans, tasks, research, design, and checklists only;
- external upstream layer owns `/srv/bears/.agents/skills/speckit-*` and the installed `specify` CLI;
- upstream Spec Kit command skills resolve from `/srv/bears/.agents/skills`;
- `speckit-bears-flow` is a Bears-owned orchestration skill, not a standalone plugin or layer;
- the canonical Bears role gate runs first for every Telegram change request;
- formatting/UI uses `telegram-quality-testing`;
- Aiogram migration uses `telegram-aiogram-migration`;
- skill lifecycle, discovery metadata, and policy updates use `telegram-plugin-skill-factory`;
- child subagents MUST rerun role routing for their bounded target before work starts.
- all roadmap work uses `/goal` entrypoint and runs through `assets/catalog/roadmap-control.v1.json`.

## Shared spine dependency

The debug and rollout spine is ordered:

`auth_core -> bears_gateway -> cd_deploy_stage`

1. `auth_core`
2. `bears_gateway`
3. `cd_deploy_stage`

Gateway or deploy implementation work must not bypass unresolved auth platform gates. Deploy changes require explicit consumer graph, rollback shape, and post-deploy evidence shape before CI behavior changes.

The deploy core workflow artifact itself is a concrete governed part. It must route to `bears-deploy-platform-engineer` before edits to `workflows/auth-gateway-deploy-core/workflow.yml`. Workflow routing for Telegram remains subordinate to this shared spine order and must not fork a second plugin lane.

## Shared spine dependency and workflow routing

Shared spine dependency is enforced for all governed implementation work: `auth_core -> bears_gateway -> cd_deploy_stage`.

Workflow routing must keep this sequence intact before any implementation opens gates.

- Subagent packet contract: each handoff includes role artifact path, role-gate status, disjoint-scope statement, and evidence plan.
- Subagent packet contract role artifact path must point to a registered role file under `agents/*.toml`.
- Disjoint-scope statement is required when requests mix unrelated scopes.
- Each handoff packet must include heartbeat/status packet and closeout packet references.

## Strict spine readiness packet

The plugin owns `assets/catalog/auth-gateway-deploy-readiness.v1.json` as the JSON-first gate record for the shared spine.

The packet records:

- ordered surface gates for `auth_core`, `bears_gateway`, and `cd_deploy_stage`;
- the plugin-owned specialist role selected for each surface;
- required repo artifacts and current missing artifacts;
- blocker evidence, required evidence before opening, safe validation commands, rollback shape, and deploy impact.

`scripts/auth_gateway_deploy_readiness.py validate` must pass before any cross-surface implementation or deploy decision can be treated as ready. The validator must fail when:

- the spine order changes;
- a surface route no longer matches the platform role catalog;
- a gate is opened before earlier spine gates are open;
- repo artifact presence is stale;
- raw secret-like values appear in the packet.

## Goal prompt generation

The plugin includes a `bears-goal-prompt-generator` role and `bears-goal-prompt` skill. They generate compact copy-pasteable `/goal` prompts from messy operator intent. They do not start goals unless the operator explicitly asks to start one.

Generated `/goal` prompts must use the compact field shape: objective, truth layer, completion condition, validation, and forbidden scope. The validator at `skills/bears-goal-prompt/scripts/validate_goal_prompt.py` enforces the 500 character target, 2000 character normal edge, and 4000 character maximum.


## Secret Factory Governance

The plugin owns `assets/catalog/secret-factory.v1.json`, `scripts/secret_factory.py`, `skills/secret-factory`, `docs/reference/secret-factory.md`, `agents/bears-secret-factory-engineer.toml`, and `tests/test_secret_factory.py` as the write-only Secret Factory governance surface.

The Secret Factory creates only catalog-listed local generated values. It writes generated values to Infisical through API v4 create-secret semantics without reading back, printing, storing on disk, passing through command-line arguments, logging, committing, or documenting the value.

Provider-issued API keys, OAuth client secrets, SSH keys, TLS keys, payment credentials, wallet keys, and other external-owner materials are refused with a provider handoff packet.

Validation must fail when role-route or role-audit fails, allowed generators drift from catalog, mandatory refusal classes are missing, request fields violate schema, Infisical API URL is non-HTTPS or not in the catalog allowlist, output contains secret material, or skill instructions/docs/tests drift from catalog claims.

Validation entrypoint requirements for this surface are:

- `python3 scripts/platform_roles.py validate`
- `python3 scripts/platform_roles.py route /srv/bears/plugins/bears/assets/catalog/secret-factory.v1.json`
- `python3 scripts/platform_roles.py audit /srv/bears/plugins/bears/assets/catalog/secret-factory.v1.json`
- `python3 scripts/secret_factory.py validate`
- `python3 scripts/validate_overlay.py --json validate --strict-overlay-skills`

Local commit validation owns test execution for this surface through `scripts/local_commit_validation.py` and `scripts/test_selection.py`. The local git `pre-commit` hook blocks failing staged changes; the local git `post-commit` hook runs impacted fast tests for the exact commit. GitHub Actions is operator-dispatched diagnostics only. Local agents must not run pytest, unittest, or repo validator suites unless the operator explicitly lifts the ban.

## Session Workers Runtime

The plugin owns `assets/catalog/session-workers-runtime.v1.json` and `scripts/session_workers_runtime.py` as the canonical contract for Codex session workers.

The runtime invariant is:

1. **Truth**: current Spec Kit artifacts.
2. **Control**: this Bears plugin.
3. **Work**: Codex sessions/session workers.

Codex sessions are workers, not memory. Every worker must carry a registered role, explicit lane, bounded target paths, allowed write scope, forbidden scope, current Spec Kit artifact snapshot, validation target, evidence target, heartbeat packet reference, and closeout packet reference.

The canonical lanes are `constitution`, `specification`, `planning`, `docs`, `auth`, `gateway`, `deploy`, `validation`, `review`, `audit`, and `implementation`. The canonical states are `available`, `claimed`, `running`, `waiting`, `blocked`, `stale`, `completed`, and `closed`.

Historical resume, reuse, or fork is allowed only after `python3 scripts/session_workers_runtime.py validate-runtime --runtime-dir <dir>` passes and lane, role, scope, current repo state, current Spec Kit snapshot, and reuse key remain compatible. If validation fails or compatibility is missing, the worker must start a fresh session with current Spec Kit truth plus bounded prior evidence.

`/speckit-implement` is one controlled implementation lane only. It must not be treated as a global executor for unrelated work.

## Roadmap Control

- Roadmap control is a dedicated gate at `assets/catalog/roadmap-control.v1.json` and `scripts/roadmap_control.py`.
- Roadmap runs can start only via `/goal` and must bind one `roadmap_id` with one or more deterministic `roadmap_slice` units.
- Multiple active Spec Kit specs are allowed only with non-overlapping scope locks and current snapshots for each slice.
- Pre-task hook is mandatory before `spawn`, `resume`, `reuse`, `manage`, or `close`; it must request operator answers for both missing data and drift.
- Main or parent agent has orchestration-only mode. Allowed action tokens are exactly `route`, `split`, `assign`, `wait`, `integrate_evidence`, `run_validators`, `close`, `report`, and `pre_task_hook`.
- Forbidden main or parent action tokens are exactly `file_read_as_content_collector`, `file_write`, `git_add`, `git_commit`, `git_push`, `pull_request_mutation`, and `implementation_tool_use`; that work belongs to exact-role subagents.
- Maximum active subagents is 100 and max depth is 3.
- Audit workers must be fresh each time; they must not reuse and must not inherit parent context.
- Session reuse and fork require exact bindings for `goal_id`, `roadmap_id`, `roadmap_slice`, `spec_snapshot_id`, `spec_snapshot_digest`, `lane`, `role`, `scope_fingerprint`, `repo_state`, `validation_target`, and pre-action `validate-runtime` evidence.

## Subagent packet contract

Subagent handoff remains role-bound and bundle-scoped. In subagent mode the main or parent agent is orchestration-only with the exact allowed tokens `route`, `split`, `assign`, `wait`, `integrate_evidence`, `run_validators`, `close`, `report`, and `pre_task_hook`. Implementation belongs to exact-role subagents with disjoint scopes.

Subagent mode has a hard limit of 100 active subagents or descendants in one workflow (max depth 3).

Agent runtime policy: main agent uses gpt-5.5 with medium; audit, complex-task, and subagent-spawning agents use gpt-5.5 with high; file/log/info collection agents use gpt-5.4-mini with medium. Operator wording middle maps to Codex schema value `medium`; allowed reasoning effort values are `medium` and `high`.

Nested subagents may be created only by explicit delegation-controller roles in `assets/catalog/subagent-orchestration-policy.v1.json`:

- `bears-deploy-platform-engineer` for Kubernetes, Proxmox read-only evidence, network evidence, runtime verification, and rollback review lanes;
- `bears-subagent-orchestration-engineer` for plugin policy, validator, docs placement, and restricted-data safety review lanes;
- `bears-platform-role-governor` for route audit, registry consistency audit, project-mandate gate review, and user-information placement lanes.

Every handoff packet must include:

- role and role artifact path;
- lane and bounded target paths;
- allowed write scope and forbidden scope;
- disjoint-scope statement for child writes;
- current Spec Kit artifact snapshot;
- validation command or evidence target;
- heartbeat/status packet;
- closeout packet.

Missing role coverage or missing packet fields keeps the handoff at `ROLE_COVERAGE_BLOCKER`.

## Non-product stage-boundary audits

For non-product work outside a registered product repo, the orchestrator must run four audit subagents once per lifecycle stage boundary before final closeout. Legacy post-task wording remains alias-only and must not override the stage-boundary cadence:

1. plugin-fit audit — decides whether `@bears` needs a skill, catalog, validator, or workflow update;
2. new-functionality drift audit — checks role routes, registry state, validators, and boundary docs;
3. documentation and restricted-data safety audit — checks required docs and confirms raw restricted data was not used;
4. user-information capture audit — records stable user facts in the narrowest durable owner after drift checks pass.

The machine policy is `assets/catalog/subagent-orchestration-policy.v1.json`. It keeps old post-task identifiers as compatibility aliases while enforcing the canonical stage-boundary rule. It validates with:

```bash
python3 scripts/subagent_orchestration_policy.py validate
```

## Project registry gate

`project-mandate` is a checklist only. It must not run for arbitrary `/srv/bears` paths.

Before `project-mandate`, run:

```bash
python3 scripts/project_registry_gate.py gate <target-path>
```

The gate checks `/srv/bears/dev/registry/projects.v1.json`, then routes the target through `platform_roles.py`. If the target is not registered, the gate returns `PROJECT_REGISTRATION_BLOCKER`. The human registry remains `/srv/bears/dev/PROJECTS.md`.

<!-- BEARS_SKILL_INVENTORY: START -->
<!-- generated by scripts/skill_catalog.py; edit assets/catalog/plugin-skill-catalog.v1.json -->
# Generated skill discovery boundary

`assets/catalog/plugin-skill-catalog.v1.json` is the single source of truth for active and disabled Bears plugin skills.

Active discoverable skills: `bears-blocker-eval`, `bears-deploy-gate`, `bears-goal-prompt`, `bears-codex-health`, `bears-governance-check`, `bears-role-gate`, `bears-workflow-validate`, `development-workflow-orchestration`, `platform-role-governance`, `python-codeflow`, `project-mandate`, `secret-factory`, `speckit-bears-flow`, `speckit-bears-research`, `yandex360-dns`, `bears-kubernetes-ops`, `bears-infisical-ops`.

Disabled preserved skill docs: `bears-telegram-workflow`, `telegram-aiogram-migration`, `telegram-plugin-skill-factory`, `telegram-quality-testing`.

A disabled skill directory is valid only when `SKILL.md` is absent and `SKILL.disabled.md` is present.
<!-- BEARS_SKILL_INVENTORY: END -->

Canonical agent workflow map: `assets/catalog/agent-workflow-map.v1.json`.

## Agentic Enterprise 4-Domain Workflow

The plugin must provide governance for four logical repo domains: `platform`, `gitops`, `infra`, and `product_infra`. The plugin is the governance/control-plane overlay and must not become a generator for product code, GitOps desired state, infra payloads, apps, connectors, MCP servers, runtime services, or production mutation.

The workflow contract lives in `assets/catalog/agentic-enterprise-workflow.v1.json`. The constitution lives in `assets/catalog/agentic-enterprise-constitution.v1.json`. The deterministic validator is `scripts/agentic_enterprise_workflow.py`. The hook manifest is `hooks.json`.

Every scope must include exactly one repo domain, measurable output, timebox, token budget, owner lineage, research-first stage, and validation path. Cross-domain or oversized scopes split before work starts. L2 owners stay attached to domain and scope family. L3 execution and L3 documentation agents stay attached to the same L2 owner for future reuse.

Decision logs use `bears-decision-log.v1` and record `user_fact`, `user_directive`, `agent_decision`, `contradiction`, and `needs_user_input`. Active conflicting user facts or directives block the scope until clarification. The clarification gate runs only after research and only for architecture, cost, security, SaaS-standard, agent-development-standard, or user-fact conflict decisions.

Hooks must stay fast: `PreToolUse` below 150 ms, `PreTask` below 250 ms, and `SessionStart` below 500 ms. Hook code must not run tests, broad search, network calls, raw log reads, workspace scans, or secret reads. CI validates the workflow with `python3 scripts/agentic_enterprise_workflow.py validate`.
