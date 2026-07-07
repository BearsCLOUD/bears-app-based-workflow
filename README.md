# Bears Workflow Overlay

Bears is the Bears workspace governance overlay for GitHub Spec Kit and shared workflow gates.

It is intended to be a Bears-owned overlay only. The source boundary is defined in [`docs/reference/spec-kit-source-boundary.md`](docs/reference/spec-kit-source-boundary.md).

Standalone `bears-speckit` plugin or layer claims are deprecated. The canonical flow is `@bears` plugin orchestration, ignored generated `.specify` workspace state, and upstream Spec Kit skills from `/srv/bears/.agents/skills`.

## Instruction drift policy

`AGENTS.md` files are routers only. Executable policy lives in `assets/catalog/*.v1.json`, `scripts/*.py`, `hooks/*.py`, `skills/*/SKILL.md`, and tests.

Entity terms are hard policy: `app` means a product application source under `/srv/bears/dev/app` or `BearsCLOUD/apps`; `project` means a GitHub Project planning board with linked Issues and metadata fields. Use `target`, `registered target`, `repo`, `path`, `workspace surface`, or `app directory` for filesystem/source ownership.

Use exact child paths with `scripts/subagents_roles.py route` and `scripts/subagents_roles.py audit`. Parent paths that only classify a group must not authorize implementation.

Infisical is custody and injection only. Kubernetes desired state plus `local_cd` owns runtime software proof. `/srv/bears/control-plane/infisical` is bootstrap or preflight support, not runtime deployment evidence.

It adds Bears-specific orchestration for:

- research before specification;
- GitHub prior-art review;
- best-practice review;
- UI/UX-friendly interface research;
- requirements checklists before planning;
- explicit review gates;
- deterministic subagents roles gate before research;
- deterministic prototype/spike gate before design, plan, tasks, analyze, and implementation;
- deterministic design artifact gate before plan, tasks, analyze, and implementation;
- analyze/drift review before implementation;
- workspace-control rules for `/srv/bears`;
- governance, role, blocker, deploy, and workflow-validation packets.
- session worker runtime control for Codex sessions that execute current Spec Kit truth.
- deterministic roadmap control for `/goal`-started runs at `assets/catalog/roadmap-control.v1.json` and `scripts/roadmap_control.py`.
- deterministic historical scenario classification and main-only drift guards for deprecated agent GitHub dev CD at `assets/catalog/agent-github-dev-cd.v1.json` and `scripts/agent_github_dev_cd.py`.
- deprecated Agent GitHub dev CD auto-merge guard through `verify-dev-auto-merge`; it blocks under main-only plugin delivery and grants no active local_cd authority.
- governed validation hook runner for named repo-local control checks.
- registry-gated target artifact checks for `/srv/bears`;
- required stage-boundary audit subagents after non-product work.
- orchestration-only parent-agent mode with the exact agent runtime matrix and explicit nested delegation controllers.
- explicit parent control lane for route, validation, status, issue-planning, evidence integration, and subagent closeout actions.
- deterministic Codex custom-agent registration drift checks and explicit sync for canonical agent TOML files in `agents/` into Codex agent directories.
- bounded no-subagent mode for side answers and read-only no-op turns.
- subagent mode allows at most 100 active subagents or descendants in one workflow (depth max 3).
- Spec Kit as the planning core for broad, non-product, repo-boundary, plugin, infra, Kubernetes, and migration work.
- Bears target-native skill chain for constitution, functional specification, GitHub Project planning, pre-execution analysis, and `app-dev` execution.
- infrastructure network map placement in `/srv/bears/docs`, /srv/bears/dev/infrastructure/network planning boundaries, and DNS workflow governance.
- unified machine-first closeout validation through `assets/catalog/bears-doctor.v1.json` and `scripts/bears_doctor.py`.
- workspace hygiene classification and safe cleanup planning through `assets/catalog/workspace-hygiene.v1.json` and `scripts/workspace_hygiene.py`.
- codexdaemon governance routing while daemon runtime implementation, issue-daemon execution, Codex Exec job handling, runtime schemas, and runtime tests consolidate into canonical `BearsCLOUD/apps`; `BearsCLOUD/codexdaemon` is deprecated/archive-candidate migration input only.


## Canonical platform role governance

`plugins/bears` is the canonical owner for shared Bears platform role governance and the only Codex plugin authorized for this Bears governance model. Use `scripts/subagents_roles.py` and `assets/catalog/platform-role-catalog.v1.json` before platform-part implementation or subagent delegation. Missing specialist coverage is `ROLE_COVERAGE_BLOCKER`.

Exact absolute `/srv/bears/plugins/bears` means the parent `/srv/bears` gitlink pointer only and routes to `workspace_root_submodule_gitlinks`. Relative `plugins/bears` and source-repo identities such as `BearsCLOUD/bears_plugin` are decomposition-only classifiers. Neither target may authorize child working-tree implementation. For implementation or audit, target an exact child file or child lane such as `/srv/bears/plugins/bears/AGENTS.md`, `assets/catalog/platform-role-catalog.v1.json`, `.github/ISSUE_TEMPLATE/config.yml`, `.github/workflows/validate.yml`, `scripts/git_discipline.py`, `scripts/roadmap_control.py`, `assets/catalog/telegram-runtime-readiness.v1.json`, or `scripts/skill_catalog.py`.

`assets/catalog/plugin-governance-language-policy.v1.json` is the hard language and wording policy for this plugin. Artifacts and subagent messages must use English only. Wording must stay strict, concise, and entity-bound. Do not use generic `deploy` when the entity is `local_cd` or `kubernetes_deployment`. Do not add sample, example, or illustrative sections.

`assets/catalog/platform-role-catalog.v1.json` is the role-principle governance gate for this plugin. `autoCI` or local commit validation runs `scripts/subagents_roles.py validate` for catalog, doc, README, manifest, and tests coverage, and `scripts/subagents_roles.py ledger-audit` for a change packet. Agents must not run those commands manually unless the operator names the exact command in the current turn. The gate fails closed when required fields are missing or `status` is not `pass`, `fail`, or `needs-redesign`.

Repo-proof validation is deterministic and repo-only. It scans the configured governance artifacts and policy docs. It does not claim live runtime chat proof.

Executable lifecycle authority: `assets/catalog/agent-workflow-map.v1.json`. `autoCI` or local commit validation validates it after workflow-map, lifecycle, gate, state-binding, or workflow documentation changes. Agents must not run the validator manually unless the operator names the exact command in the current turn. The map defines the lifecycle order, `global_review` / `fix_wave` loop, blocking gates, worker-state paths, and hook automation policy.

The executable map preserves the constitution sequence: route gate -> subagents-roles gate -> research gate.

Intermediate stages record evidence and continue orchestration. Subagents may close intermediate tasks. Global review gates closeout and merge-ready decisions. `closeout`, `merge_ready`, and `cleanup` are blocking gates. Root workflow-state is an aggregate and index only; each worker writes `runtime/agent-workflow/<goal_id>/workers/<worker_id>/worker-state.v1.json`. Runtime hooks are not registered or enabled without hook trust and effective-hooks proof.

Small exact-file bugfixes may skip the full Spec Kit packet only when they do not change boundaries, runtime, deploy, restricted-data handling, or public behavior. Repo split, infra, plugin, Kubernetes, and migration work must follow the executable map.

## Subagents roles gate

`subagents-roles` validates the Bears plugin source boundary before research starts.

Technical terms:

- subagents-roles gate: the policy check after route gate and before research gate.
- change-check packet: a JSON file that records changed surfaces, agent impact, context plan, validation, operator boundary, cost, and status.
- fail closed: reject the change when required proof is missing.

Constitution checklist:

- Route gate names the exact child target.
- Packet names `/srv/bears/plugins/bears/assets/catalog/platform-role-catalog.v1.json` or route/audit evidence.
- Changed surfaces stay inside exact subagents roles governance paths.
- Lifecycle proof states `after route_gate and before research_gate`.
- Change stays inside `/srv/bears/plugins/bears`.
- Product apps, connectors, MCP servers, runtime services, product behavior, and production mutation paths are absent.
- Blocked-pattern text is absent.
- Upstream Spec Kit remains external.
- Exact primary specialist or helper role exists for implementation.
- Restricted-data reads and output are absent.
- Catalog, validator, README inventory, manifest, capability inventory, docs, and tests stay synchronized.

Validation entrypoints owned by `autoCI` or local commit validation:

- `python3 scripts/subagents_roles.py validate`
- `python3 scripts/subagents_roles.py ledger-audit`

Constitution check:

- Agent work simplified:
- Token/context cost reduced or justified:
- Repeated file reads reduced:
- Future validator/catalog/rule added:
- Reusable evidence path:
- Human decision boundary:
- Failure mode if this is skipped:

## Issue 20 research gate

### Target behavior

`roadmap-control` and `subagent-orchestration-policy` expose `issue-20-research-gate`. Their validators enforce research required, skip, artifact, UX, source-bounds, and validation-impact rules.

### Decision table or policy matrix

| Condition | Required result |
| --- | --- |
| Work is broad, new, risky, drift-prone, workflow, runtime, integration, UI/UX, automation, plugin, infra, Kubernetes, migration, or boundary-sensitive | `research.md` and `prior-art.md` required before specification, plan, tasks, analyze, and implementation |
| Operator/developer/user-facing, CLI, workflow, status, error, recovery, or notification behavior changes | `ux-research.md` required |
| Operator gives explicit research skip | Research skip may validate with approval reference and reason |
| One exact-file edit has no boundary, runtime, deploy, restricted-data, public behavior, workflow, UI, UX, or automation pattern change | Research skip may validate |
| Required research artifact is missing, lacks required sections, lacks required sources, or claims unbounded or proprietary copying | Reject packet with `RESEARCH_ARTIFACT_REQUIRED` |

### Artifact placement

With a Spec Kit feature directory, store `research.md`, `prior-art.md`, and `ux-research.md` in that directory. Before the feature directory exists, store a bounded section in this README or the narrowest target docs path, then move the artifacts into the feature directory after Spec Kit creates it.

### Required artifact sections

Each research artifact must include Decision or Recommendation, Rationale, Alternatives considered, Risks and constraints, Validation implications, and Sources when web or repository research was used. Artifacts must be bounded summaries and must not copy large source text or proprietary content.


## Prototype/spike gate

The prototype gate runs after research and before design when research or design leaves unresolved high-risk uncertainty that can be cheaply tested. The artifact is `prototype.md` or `spike.md` under the feature directory or the narrowest target docs path.

Required artifact fields: hypothesis or uncertainty; prototype scope and non-goals; commands or checks run; findings and evidence summary; decision outcome; validation implications; cleanup or discard requirements.

Skip is valid only for one narrow exact-file bugfix with no boundary, runtime, deploy, restricted-data, or public behavior change, or for an already-proven implementation pattern with named evidence. Prototype output is throwaway evidence. It becomes durable implementation only after review selects it for implementation scope.

The validator rejects prototype claims with production mutation, restricted-data reads, broad implementation, durable implementation, missing artifact when required, or missing decision outcome. Operator approval is required before implementation when material behavior, runtime, boundary, UI/UX, or architecture changes remain after prototype findings.

## Issue 21 prototype artifact contract

### Target behavior

`roadmap-control` and `subagent-orchestration-policy` expose `issue-21-prototype-spike-gate`. Their validators enforce prototype required, skip, safety, decision, artifact, and operator-review rules.

### Decision table or policy matrix

| Condition | Required result |
| --- | --- |
| Research or design leaves unresolved high-risk uncertainty that can be cheaply tested | `prototype.md` or `spike.md` required before design, plan, tasks, analyze, and implementation |
| One exact-file bugfix has no boundary, runtime, deploy, restricted-data, or public behavior change | Prototype skip may validate |
| Implementation pattern is already proven and evidence is named | Prototype skip may validate |
| Prototype claim includes production mutation, restricted-data read, broad implementation, or durable implementation | Reject packet with `PROTOTYPE_ARTIFACT_REQUIRED` |
| Required prototype lacks decision outcome or artifact path | Reject packet with `PROTOTYPE_ARTIFACT_REQUIRED` |
| Material behavior, runtime, boundary, UI/UX, or architecture changes remain | Operator approval required before implementation |



## Design artifact gate

The design artifact gate runs after research and prototype review and before Spec Kit plan, tasks, speckit-analyze, role gate, and implementation. It is mandatory for workflow policy, orchestration policy, subagent policy, hook behavior, roadmap control, role gate, runtime contract, validator behavior, operator interaction, developer interaction, and UI/UX flow changes.

The durable artifact is `design.md` in the feature or spec directory when a Spec Kit packet exists. Without a feature directory, the durable artifact is the bounded section `README.md#issue-22-design-artifact-contract`. Implementation packets must reject missing design with `DESIGN_ARTIFACT_REQUIRED` unless an approved skip or narrow bugfix skip validates.

Approved skip requires explicit operator approval, approval reference, and reason. Narrow bugfix skip requires one exact-file scope and no boundary, runtime, deploy, restricted-data, or public behavior change.

## Issue 22 design artifact contract

### Problem statement

Workflow issues used different design shapes. That drift weakened alignment between catalogs, validators, docs, tests, and Spec Kit artifacts.

### Current behavior

`roadmap-control`, `subagent-orchestration-policy`, and `role-gate-methodology` validated their own rules but did not share one deterministic design artifact contract.

### Target behavior

The three catalogs expose one `issue-22-design-artifact-contract`. The three validators enforce the contract and reject implementation packets that need design but lack a valid artifact or valid skip.

### Decision table or policy matrix

| Condition | Required result |
| --- | --- |
| Change touches workflow policy, orchestration policy, subagent policy, hook behavior, roadmap control, role gate, runtime contract, validator behavior, operator interaction, developer interaction, or UI/UX flow | Design artifact required before plan, tasks, analyze, and implementation |
| Behavior branches, policy branches, state transitions, or operator paths exist | Design artifact must include a decision table or policy matrix |
| Explicit operator approval exists | `approved_skip` may bypass design for that packet |
| One exact-file bugfix has no boundary, runtime, deploy, restricted-data, or public behavior change | `narrow_bugfix_skip` may bypass design for that packet |
| Required design is missing and no skip validates | Reject packet with `DESIGN_ARTIFACT_REQUIRED` |

### Affected artifacts and ownership

| Owner slice | Artifacts |
| --- | --- |
| bears-workflow-overlay-platform-engineer | `assets/catalog/roadmap-control.v1.json`, `scripts/roadmap_control.py`, `tests/test_roadmap_control.py`, `.codex-plugin/plugin.json`, `skills/app-constitution/SKILL.md`, `skills/app-research/SKILL.md`, `skills/app-specify/SKILL.md`, `skills/app-plan/SKILL.md`, `skills/app-analyze/SKILL.md` |
| bears-subagent-orchestration-engineer | `assets/catalog/subagent-orchestration-policy.v1.json`, `scripts/subagent_orchestration_policy.py`, `tests/test_subagent_orchestration_policy.py` |
| bears-subagents-roles-governor | `README.md`, `AGENTS.md`, `assets/catalog/role-gate-methodology.v1.json`, `scripts/role_gate_methodology.py`, `tests/test_role_gate_methodology.py` |

### Validator impact

`roadmap_control.py`, `subagent_orchestration_policy.py`, and `role_gate_methodology.py` validate `design_artifact_contract` and expose `validate_implementation_packet(packet, contract)`.

### Documentation impact

`README.md`, `AGENTS.md`, `skills/app-*/*`, and `.codex-plugin/plugin.json` describe the design gate position and skip policy.

### Test plan

Local commit validation targeted tests cover required design, approved skip, narrow bugfix skip, missing decision table for branch behavior, missing validator impact, and missing design for all three validator surfaces. Local agents must not run pytest, unittest, or repo validator suites unless the operator explicitly lifts the ban.

### Compatibility notes

The contract adds repo-only governance validation. It does not add product apps, connectors, MCP servers, runtime services, production deploy behavior, or product behavior.

### Safety boundaries

The change stays inside allowed governance catalogs, validators, docs, metadata, and tests. It does not read, print, store, or expose restricted data.

### Open questions

None for issue #22. Future issues may add feature-directory `design.md` files under their own allowed write scope.

### Review gate condition

Closeout requires platform role route/audit evidence, exact local commit validation proof, plugin cache-sync state, or a named blocker.


## Agent registration sync

Canonical role profiles live in agent TOML files in `agents/`. They are not claimed to be auto-discovered from this plugin root.

Use `python3 scripts/agent_registration_sync.py check --target user --json` for read-only drift evidence. Use `python3 scripts/agent_registration_sync.py audit-roles --json` for sequential canonical role audit evidence. Use `python3 scripts/agent_registration_sync.py sync --target user` or `--target repo` for explicit materialization into `~/.codex/agents` or `.codex/agents`.

`agents/openai.yaml` is UX metadata only, not custom-agent TOML registration. No SessionStart hook is enabled for this sync.

Reference: `docs/reference/agent-registration-sync.md`.

## Main-only local validation and plugin cache delivery

- Catalogs: `assets/catalog/ci-requirements.v1.json`, `assets/catalog/plugin-cache-sync.v1.json`, `assets/catalog/tech-debt-matrix.v1.json`.
- Local environment command: `bin/bears-plugin install|update|doctor` writes generated local path config outside plugin source and refreshes installed plugin state.
- Cache sync watcher remains autoCD-owned; local commit hook installation remains local commit validation owned.
- Plugin workflow task commits land on `main`; PR/review/branch-dependent closeout is not a workflow authority.
- The git `pre-commit` hook runs `python3 scripts/local_commit_validation.py run --staged` to block failing staged changes. The git `post-commit` hook runs `python3 scripts/local_commit_validation.py run --commit-sha HEAD` and writes `runtime/local-commit-validation/<commit_sha>.json` for exact-SHA proof.
- `.github/workflows/validate.yml` runs diagnostics on `main` push. `workflow_dispatch` with `emergency_full_suite=true` remains operator-only full-suite diagnostics.
- Local Codex cache sync starts only after exact `main` commit has local commit validation `status=pass`. The watcher runs `codex plugin marketplace upgrade bears-plugin --json` and `codex plugin add bears@bears-plugin --json`.
- Closeout requires `runtime/local-commit-validation/<main_sha>.json` with `status=pass`, plus `runtime/plugin-cache-sync/plugin-cache-sync-state.v1.json` with `delivery_complete=true`, exact installed cache SHA equal to `main_sha`, and effective hooks proof for `hooks.json` plus `hooks/`. The `Stop` hook blocks only explicit closeout intent when delivery is incomplete; it does not commit, push, run tests, or run validators.
- Local validation failure, sync failure, missing hooks, workflow defect, deferred dirty, or runtime degradation creates a row in `assets/catalog/tech-debt-matrix.v1.json`; closure requires exact local validation proof and plugin cache sync state evidence.

## Deprecated Agent GitHub dev CD reference

- Catalog: `assets/catalog/agent-github-dev-cd.v1.json`
- Validator: `scripts/agent_github_dev_cd.py`
- Reference: `docs/reference/agent-github-dev-cd.md`
- `classify-task --prompt-file <path>` emits `dev`, `prod`, `bugfix`, `hot_bugfix`, `issue`, and `goal` `development_scenario` tasks; conflicting markers split into separate tasks.
- `verify-scenario-policy --packet <path>` is mandatory before scenario, local_cd, or production-mutation routing.
- Dev CD is deprecated reference only. The plugin emits no active dev-CD authority, no active local_cd branch gate, no kubernetes_deployment mutation, no production deploy, and no repo-stored secrets.
- Fixed GitHub issue identifiers are `type:bugfix`, `type:idea`, and `type:develop-ready`.
- `type:develop-ready` is produced from repository constitution alignment, research, and accepted operator decisions.
- agent pickup may start bounded development only for `type:develop-ready` after route gate, constitution evidence, research evidence, accepted decision evidence, owning role, task packet, duplicate guard, and `verify-agent-pickup --dry-run` pass.
- agent pickup blocks unlabeled, idea-only, bugfix-only, blocked, human-review (`needs-human` or `manual-only`), secret, credentials, deploy, production, and security-review issues.

## Source repository and submodule boundary

- Canonical plugin source repo: `BearsCLOUD/bears_plugin`.
- Canonical local mount after split: Git submodule at `/srv/bears/plugins/bears`.
- Plugin manifest repository: `https://github.com/BearsCLOUD/bears_plugin`.
- Split planning issue: `https://github.com/BearsCLOUD/bears-codex-workspace/issues/3`.
- CI lane: `.github/workflows/validate.yml`.
- Source repo identity and submodule remote identity are parent-only classifiers. They must not authorize broad plugin edits.
- Broad plugin-root path targets also stay parent-only. They orient the route and block handoff until an exact child surface is selected.
- Exact plugin file paths still route to their concrete primary-capable roles.

The universal invariant is strict: the orchestrator must block development unless the requested concrete part has exactly one valid primary specialist or helper role at the same granularity as the requested write scope. Group, parent, controller, or reviewer coverage is never enough for child implementation.

Agent role classification is executable. Every `agents/*.toml` file declares top-level `role_kind`, `execution_class`, and `primary_eligible`; `scripts/subagents_roles.py` and `scripts/agent_registration_sync.py` compare those values to the catalog role or profile mapping before closeout. `scripts/agent_registration_sync.py` also requires each `developer_instructions` block to name its own agent, include the exact `- Role override: <description>` line, and pass the sequential `audit-roles` packet.

Use:

- `python3 scripts/subagents_roles.py route <target>` for deterministic classification.
- `python3 scripts/subagents_roles.py audit <target>` before implementation handoff; handoff remains blocked until validation passes.
- `python3 scripts/role_gate_methodology.py validate` to prove the universal blocker methodology and catalog alignment.
- `python3 scripts/project_registry_gate.py gate <target>` only when App Target Gate needs compatibility registry evidence. Missing registration is `PROJECT_REGISTRATION_BLOCKER`.
- `python3 scripts/subagent_orchestration_policy.py validate` after non-product closeout or subagent policy edits.
- `python3 scripts/agent_registration_sync.py validate` to prove canonical agent TOMLs and sync contract.
- `python3 scripts/agent_registration_sync.py audit-roles --json` to prove every canonical agent role has its task-area developer-instruction override.

Forward-test coverage must keep these regressions blocked: child-under-group fallback, alias/path drift that widens coverage, ambiguous ownership, and controller/broad-role fallback.

Subagent mode is strict:

- The main or parent agent is orchestration-only. Allowed action tokens are exactly `route`, `split`, `assign`, `wait`, `integrate_evidence`, `run_validators`, `close`, `report`, and `pre_task_hook`.
- Agent runtime policy: main agent uses gpt-5.5 with medium; audit, complex-task, and subagent-spawning agents use gpt-5.5 with high; file/log/info collection agents use gpt-5.4-mini with medium. Operator wording middle maps to Codex schema value `medium`; allowed reasoning effort values are `medium` and `high`.
- Nested subagents are allowed only for explicit delegation-controller roles listed in `assets/catalog/subagent-orchestration-policy.v1.json`.
- The deploy controller can split Kubernetes, Proxmox read-only evidence, network evidence, runtime verification, and rollback review lanes. None of those lanes may mutate production or bypass approval gates.

Compatibility migration routing is exact:

- `/srv/bears/dev` is an external migration reference, not root-owned dev-core authority.
- `/srv/bears/projects` is deleted and must not be recreated; it is not parent implementation authority.
- `/srv/bears/legacy/seller/apps/auth_core`, `gateway`, and `payment_service` are legacy-source checkouts only for universal platform extraction; seller and `seller.bears.ru` do not own Bears core.
- `kube`, `kubernetes`, `bears-infra`, and `/srv/bears/kubernetes` route to Kubernetes repo-boundary governance.
- `android-emulator` routes to the The Ants Android emulator platform `.225` lane.
- `sentry` routes to the `.226` Sentry/observability future lane and governed Sentry runtime-plugin capability design.
- `/srv/bears/dev/app` is the canonical product-app repo root for `BearsCLOUD/apps`; `/srv/bears/dev/app/theants` is an app directory or migration/archive route, not a separate canonical repository.
- `/srv/bears/dev/app/vpn` routes to `bears-vpn-project-governance-engineer` for VPN project governance/specs; `/srv/bears/dev/app/vpn/androidapp` and `winapp` route to `bears-vpn-client-app-engineer`; `vpnbot` and exact VPN Telegram notifier files route to `bears-vpn-bot-engineer`; `amnezia-split` and `wireguard-amnezia` route to `bears-vpn-runtime-engineer`; disabled/offline `proxy` routes to `bears-vpn-proxy-engineer`; `traefik` routes to `bears-vpn-ingress-engineer` for GitFlow-only ingress config review.
- Feature 006 `spec.md`, `plan.md`, and `governance/` route to `bears-telegram-platform-engineer`; `/srv/bears/control-plane/workspace-control/tests` routes to `bears-subagents-roles-governor` for agent reviewer role test governance.

Kubernetes production CD for registered Bears infra targets is governed by `assets/catalog/git-deploy-contract.v1.json`, `assets/catalog/cd-kube-deploy-contract.v1.json`, and `scripts/bears_auto_cd.py`. The Git contract owns `dev` to `main` merge policy and target mapping. The CD contract owns only what deploys, from where, and the ordered Kubernetes actions. Production apply is automatic from the infra repo `main` GitHub Actions path; local agents do not run the deploy.

Sentry runtime-plugin governance is exact:

- Runtime repo: `BearsCLOUD/bears-sentry-runtime-plugin`.
- Runtime path: `/srv/bears/runtime-plugins/sentry`.
- Governance repo: `BearsCLOUD/bears_plugin`.
- Governance path: `/srv/bears/plugins/bears`.
- Owner role: `bears-observability-platform-engineer`.
- Reviewer role: `bears-platform-security-reviewer`.
- Trust boundary: Sentry API data can include secrets, user identifiers, private stack data, and production runtime signals; this Codex plugin stores only governance metadata and redacted evidence rules.
- Allowed operations: read-only issue summaries, Sentry project health summaries, release error counts, issue count trends, alert status summaries, and redacted validation packets.
- Forbidden operations: Sentry settings mutation, raw event payload export, stacktrace frame export, trace/span/breadcrumb/attachment/raw-log export, credential reads, user email/IP/cookie/header/request-body exposure, Sentry project deletion, integration token management, alert rule mutation, production data exposure without explicit operator approval and security review, and runtime code inside `/srv/bears/plugins/bears`.
- Redaction default: deny every Sentry field unless `assets/catalog/platform-role-catalog.v1.json` allowlists it under `runtime_plugin_capability.redaction_rules.allowed_fields`.
- Evidence default: redacted-only summaries and counts.

The first debug workflow is the ordered spine `auth_core -> bears_gateway -> cd_deploy_stage`; Telegram/Aiogram workflow stays last unless the operator explicitly narrows the task to Telegram.

The spine has a strict readiness packet at `assets/catalog/auth-gateway-deploy-readiness.v1.json`. `autoCI` or local commit validation owns `python3 scripts/auth_gateway_deploy_readiness.py validate`. The optional file-backed validator `python3 scripts/auth_gateway_deploy_readiness.py --check-files validate` stays available for future enforcement after the root registry and neutral platform subtree are durable. Agents must not run those commands manually unless the operator names the exact command in the current turn.

The spine required inputs route to neutral `/srv/bears/dev/platform/src/bears_platform/{auth,gateway,deploy}` paths. Seller paths are allowed only as tenant legacy source, route-pack evidence, or test fixture.

Exact universal-core subtrees under `/srv/bears/dev/platform/src/bears_platform/auth`, `gateway`, and `billing` must route to their matching shared platform specialist roles. Exact contract test files may route to the same matching specialist or helper role; the broad tests directory must stay unmapped. They must not fall back to seller ownership or broad checkout ownership.

## Roadmap control and session orchestration

- Roadmap runs are deterministic and must be started through `/goal` only.
- Multiple active Spec Kit specs are allowed only via roadmap slices and non-overlapping scope locks.
- A pre-task hook runs before `spawn`, `resume`, `reuse`, `manage`, and `close`; it must ask for operator answers about missing data and drift before any progress.
- The main or parent agent is orchestration-only. Allowed action tokens are exactly `route`, `split`, `assign`, `wait`, `integrate_evidence`, `run_validators`, `close`, `report`, and `pre_task_hook`.
- Forbidden parent action tokens are exactly `file_read_as_content_collector`, `file_write`, `git_add`, `git_commit`, `git_push`, `pull_request_mutation`, and `implementation_tool_use`.
- Maximum concurrency for active subagents is 100 as a hard max safety cap, not the normal active execution target.
- The reusable worker pool uses a lower default cap for actively executing workers. Idle reusable workers do not count against that default active cap.
- Worker states are `active`, `idle`, `reusable`, `fresh-required`, and `stale`.
- Reuse is valid only with the same role, same repo boundary, compatible write scope, no restricted-data taint, a compact continuation packet, and successful `python3 scripts/session_workers_runtime.py validate-runtime --runtime-dir <dir>` before session reuse or fork.
- Audit lanes with `inherit_parent_context=false` require `fresh-required` workers, no parent context, and no resume/reuse.
- The parallel audit lane runs during active workflow, has no implementation authority, emits auditable events, creates or updates deduplicated GitHub issues for findings, and blocks only hard-stop findings.
- Long `wait_agent` calls must name target agent, expected artifact, owner lane, timeout, and fallback action. After repeated empty timeout, the parent chooses local read-only check, delayed integration, or a real blocker only by blocker definition.
- Final integration accepts evidence artifacts, not plain waiting.
- Stale workers close when role, repo boundary, write scope, continuation packet, validation target, branch, worktree, restricted-data taint, operator decision, audit completion, or assignment completion invalidates reuse.

Parent control lane:

| Control area | Allowed action |
| --- | --- |
| Routing | Select target and primary role |
| Task split | Build assignment packets |
| Validation | Request named validation hooks and validators, and status checks |
| Evidence read | Read exit codes, bounded summaries, git status, and changed-file names |
| GitHub planning | Create or update planning issues only when the operator requests it |
| Integration | Integrate subagent evidence and close stale or completed subagents |

The lane grants no implementation authority. It forbids file writes, implementation commands, `git add`, `git commit`, `git push`, pull request mutation without explicit operator request, broad file-content collection, raw secrets, raw logs, raw chat, raw VPN configs, and production data.

No-subagent mode is bounded:

| Condition | Required result |
| --- | --- |
| Side conversation answer | Allowed with nearest role instructions; no mutation; no non-product audit subagents |
| Question-only explanation | Allowed with nearest role instructions; no mutation; no non-product audit subagents |
| One read-only status command | Allowed with nearest role instructions; no mutation; no non-product audit subagents |
| Bounded repo inspection with no mutation | Allowed with nearest role instructions; no mutation; no non-product audit subagents |
| Small exact-file bugfix that existing policy allows | Allowed only as admission; before write, upgrade to normal gated mode |
| Repo-boundary change | Block no-subagent mode; use normal gated mode |
| Plugin policy change | Block no-subagent mode; use normal gated mode |
| Runtime, deployment, migration, or secret-handling change | Block no-subagent mode; use normal gated mode |
| Multi-file implementation | Block no-subagent mode; use normal gated mode |
| Operator explicitly requests subagents | Block no-subagent mode; use subagent mode |

No-subagent mode never bypasses a required role gate. When mutation starts, normal gated mode owns validation and audit decisions.

## Issue 17 validation hook runner design

### Problem statement

Plugin control checks need one governed request shape. Direct ad hoc command requests from each parent or subagent weaken command scope, output bounds, and closeout evidence.

### Current behavior

Policy validation, role routing, registry gates, overlay checks, roadmap validation, and git-discipline validation are Python scripts. Subagent closeout packets recorded a validation command string and did not require a named hook result.

### Target behavior

`subagent-orchestration-policy` exposes `validation_hook_runner`. Parent agents and subagents request a `hook_id`; the hook maps to an allowlisted repo-local Python script and fixed args. The result records `hook_id`, `cwd`, `command_id`, `exit_code`, `sanitized_summary`, and `validation_target`.

### Decision table or policy matrix

| Condition | Required result |
| --- | --- |
| Agent needs role route or role audit evidence | Use `role_route` or `role_audit` hook with `validation_target` |
| Agent needs target-registry evidence | Use `project_registry_gate` hook with `validation_target` |
| Agent needs plugin policy validation | Use `subagent_policy_validate`, `overlay_validate`, `roadmap_validate`, or `git_discipline_validate` |
| Agent needs dirty closeout path coverage | Use `python3 scripts/git_discipline.py closeout-preflight --repo <repo> --allowed-path <path> --expected-branch-prefix <prefix> --gitlink-proof <path>:<old-object>:<target-object>:<source-pr-merge-commit> --json` for gitlink paths and block on `DIRTY_WORKTREE_BLOCKER` or `CLOSEOUT_PREFLIGHT_BLOCKED` |
| Agent needs branch cleanup evidence | Use `python3 scripts/git_discipline.py branch-inventory --repo <repo> --base <base> --json` before any local or remote branch delete request |
| Agent needs post-merge branch closeout proof | Use `python3 scripts/git_discipline.py branch-closeout-gate --repo <repo> --base <base> --github-prs-json <prs.json> --json` and require zero cleanup candidates |
| Agent needs branch prefix proof before push or PR | Use `python3 scripts/git_discipline.py branch-prefix-check --branch <branch> --assignment-packet <assignment.json> --json`; require `branch_prefix_check=PASS` |
| Agent needs gitlink closeout proof | Use `closeout-preflight` with `--gitlink-proof <path>:<old-object>:<target-object>:<source-pr-merge-commit>` before closeout commit, push, PR ready, or merge; use `python3 scripts/git_discipline.py gitlink-audit --repo <parent-repo> --tree-ref <ref> --path <gitlink-path> --expected-target <sha> --local-checkout <path> --json` only for local checkout target verification |
| Agent maps branch hygiene work to issues | Use `branch_cleanup_policy.issue_mapping` in `assets/catalog/git-discipline.v1.json` |
| Agent asks for an unknown hook | Reject request |
| Agent asks for arbitrary shell, inline command, env read, credential read, raw log read, or production data read | Reject request |
| Hook output contains raw stdout, raw stderr, env, token, secret, password, private key, API key, or authorization field | Reject result |
| Subagent closeout reports validation evidence | Include bounded validation hook result |

### Affected artifacts and ownership

| Owner slice | Artifacts |
| --- | --- |
| bears-subagent-orchestration-engineer | `assets/catalog/subagent-orchestration-policy.v1.json`, `scripts/subagent_orchestration_policy.py`, `tests/test_subagent_orchestration_policy.py`, `tests/test_plugin_validation_scripts.py` |
| bears-platform-security-reviewer | restricted-data output policy review |

### Validator impact

`scripts/subagent_orchestration_policy.py` validates the hook allowlist, fixed args, result schema, forbidden request kinds, forbidden result fields, and closeout hook result packet. `tests/test_plugin_validation_scripts.py` proves hook scripts exist under `scripts/`.

### Documentation impact

README and `.codex-plugin/plugin.json` state the named-hook model and restricted-data boundaries.

### Test plan

Targeted tests cover valid hook config, unknown hook rejection, arbitrary shell rejection, missing result fields, raw output field rejection, closeout hook result validation, script existence, and restricted output fields.

### Compatibility notes

This is governance design only. It does not add product apps, connectors, MCP servers, runtime services, production runtime mutation, or a shell runner.

### Safety boundaries

Hooks return bounded JSON or concise text evidence. They reject raw output fields, env reads, credentials, raw logs, raw VPN configs, and production data.

### Open questions

None for issue #17.

### Review gate condition

Closeout requires subagent policy validation, overlay validation, targeted tests, role route/audit evidence, and security review evidence for restricted-data handling.

Operator note: in this repo, "Telegram workflow" means governance rules for Telegram bot approval, status, callback, and message-UI flows. It does not mean a live Telegram bot, runtime, connector, product app, or MCP surface inside this plugin.

Telegram workflow governance still lives inside this canonical plugin as internal skills, catalogs, scripts, and tests. `bears-telegram-workflow` is a skill name only; do not recreate `/srv/bears/plugins/bears-telegram-workflow` as a standalone plugin, product app, connector, MCP surface, or runtime.


## Secret Factory governance

`assets/catalog/secret-factory.v1.json`, `scripts/secret_factory.py`, `skills/secret-factory/SKILL.disabled.md`, and `docs/reference/secret-factory.md` define the preserved write-only Secret Factory governance docs. It creates only catalog-listed local generated values and writes them to Infisical without reading, printing, storing, logging, committing, or exposing the value. Provider-owned values return a provider handoff packet.

Validation for this surface uses the full chain:

- `python3 scripts/subagents_roles.py validate`
- `python3 scripts/subagents_roles.py route /srv/bears/plugins/bears/assets/catalog/secret-factory.v1.json`
- `python3 scripts/subagents_roles.py audit /srv/bears/plugins/bears/assets/catalog/secret-factory.v1.json`
- `python3 scripts/secret_factory.py validate`
- `python3 scripts/validate_overlay.py --json validate --strict-overlay-skills`

Local commit validation owns blocking closeout proof for this surface through `scripts/local_commit_validation.py` and `scripts/test_selection.py`; pre-commit blocks staged failures, post-commit records exact-SHA proof, and GitHub Actions runs diagnostics on `main` push.

## Skill inventory

Single source of truth: `assets/catalog/plugin-skill-catalog.v1.json`. Generated fragments: `docs/generated/README.skill-inventory.md` and `docs/generated/SPEC.skill-inventory.md`. `autoCI` or local commit validation owns `python3 scripts/skill_catalog.py validate` and `python3 scripts/skill_catalog.py generate --check`. Agents must not run those commands manually unless the operator names the exact command in the current turn.

Do not maintain a second manual skill list in this README. Use the generated block below for reader-facing discovery.

## Other plugin contents

Use executable catalogs and validators as the inventory authority:

- capability inventory: `capabilities/inventory.v1.json`;
- skill inventory: `assets/catalog/plugin-skill-catalog.v1.json`;
- role inventory: `assets/catalog/platform-role-catalog.v1.json`;
- workflow authority: `assets/catalog/agent-workflow-map.v1.json`;
- CI policy: `assets/catalog/ci-requirements.v1.json`;
- plugin boundary: `assets/catalog/platform-role-catalog.v1.json`, `scripts/subagents_roles.py`, and `docs/reference/subagents-roles.md`.
- overlay validator: `scripts/validate_overlay.py`.

Additional reader references:

- `docs/reference/git-discipline.md` — reference doc for Git closeout, branch inventory, branch prefix checks, gitlink target audits, and branch cleanup issue ownership.
- `docs/reference/workflow-backlog-lane.md` — snapshot-backed workflow backlog execution order and issue mapping.
- `docs/reference/workflow-backlog-issue-classification.tsv` — bounded open-issue classification snapshot.
- `scripts/project_registry_gate.py` — deterministic compatibility gate that can feed App Target Gate with registered-target evidence and enforce `spec_required`, `spec_path`, `plan_path`, and `tasks_path` when registry entries still require it.

## Ignored local generated state

- `.specify/` — generated Spec Kit workspace state initialized with Specify CLI 0.11.5; upstream skills remain external; these files are ignored and must not be committed as plugin source.

## Private action caller requirements

`actions/subagents-roles-gate/action.yml` requires caller workflow `permissions: contents: read` so GitHub can fetch this private action repository. The action does not perform checkout or clone, and does not require secrets, tokens, provider settings, runtime access, or production data. `platform-repo-root` must resolve under `GITHUB_WORKSPACE`; absolute paths outside that workspace and relative escapes are rejected before target file checks.

Required caller permission block:

```yaml
permissions:
  contents: read
```

## Workflow authority

`assets/catalog/agent-workflow-map.v1.json` is the primary executable process authority for lifecycle order, transitions, review gates, state bindings, dirty triage, worker state files, hook automation policy, subagent waves, and role/stage compatibility. `autoCI` or local commit validation owns `python3 scripts/agent_workflow_map.py validate`; agents must not run it manually unless the operator names the exact command in the current turn.

The `specify`, `checklist`, `plan`, `tasks`, `analyze`, and `implement` steps are upstream Spec Kit core steps and must resolve from `/srv/bears/.agents/skills`, not from this plugin or a deprecated standalone `bears-speckit` layer. Generated `.specify` files store local Spec Kit scripts, templates, workflow registry, integration metadata, and constitution; they are ignored and must not become plugin source.

Layer split:

- Plugin functionality layer: Bears skills, workflows, catalogs, validators, schemas, agents, actions, capability inventory, tests, README, SPEC, and reference docs.
- Generated Spec Kit layer: ignored `.specify/` state plus generated `spec.md`, `plan.md`, `tasks.md`, research, design, and checklist artifacts.
- External upstream layer: `/srv/bears/.agents/skills/speckit-*` and the installed `specify` CLI.

When a plugin skill, workflow, catalog path, capability inventory, role route, validator, or manifest claim changes, sync `.codex-plugin/plugin.json`, README inventory, catalog aliases, validators, and tests in the same lifecycle stage. Superseded checks must name the active replacement validation command.

Git-backed local plugin updates use `bin/bears-plugin update` on the server after local config is installed, or the marketplace commands from `.agents/plugins/marketplace.json` when refreshing through Codex marketplace. Restart Codex after upgrade when the process needs plugin reload. Do not rely on manual cache copy as the normal update path.

When those steps are split across Codex sessions, the sessions are treated as workers rather than memory. The Bears plugin owns the lane/state/scope packet contract, while current Spec Kit artifacts remain the truth source. `/speckit-implement` is one controlled implementation lane, not a global executor.

## Canonical source policy

This plugin must keep `.specify` generated workspace files ignored. This plugin must not vendor upstream Spec Kit `speckit-*` command skills. Upstream Spec Kit core skills belong in `/srv/bears/.agents/skills`. Bears app workflow lives in `app-*`; `app-research` replaces plugin-local Speckit research. Plugin-local Speckit overlay skills are removed from active plugin discovery.

<!-- BEARS_SKILL_INVENTORY: START -->
<!-- generated by scripts/skill_catalog.py; edit assets/catalog/plugin-skill-catalog.v1.json -->
# Generated Bears skill inventory

Canonical catalog: `assets/catalog/plugin-skill-catalog.v1.json`.

Active skills expose `SKILL.md` and are discoverable by the plugin loader.

## Active skills

- `skills/bears-goal-prompt` — Generate bounded and verifiable Codex goal prompts for Bears work.
- `skills/subagents-roles` — Govern @Bears subagents-roles expected owner-role coverage, autoCI route/audit proof, role-principle ledger, and role-safe subagent coordination.
- `skills/bears-agents` — Govern @Bears role lifecycle, role coverage gaps, role TOML updates, and registration drift.
- `skills/python-codeflow` — Independent reusable L3-local Python standard for bounded Python worker tasks.
- `skills/app-constitution` — Create or update one Bears app constitution with target, owner, layer map, artifact map, and drift handling.
- `skills/app-research` — Research external solutions, prior art, product logic, integrations, UI/UX patterns, providers, and market constraints for Bears app targets.
- `skills/app-specify` — Create or update app specifications from operator intent, constitution rules, app-research evidence, and repo evidence.
- `skills/app-functional-graph` — Create, update, validate, and consume app-local functional graph and app task ledger files for app-plan and app-dev.
- `skills/app-plan` — Convert Bears app docs into app task ledger tasks and Apps Project #20 status items with functional graph refs.
- `skills/github-project-planning` — Plan and administer non-app GitHub Projects, fields, views, issues, sub-issues, item hygiene, and planning PASS packets; app workflow planning belongs to app-plan.
- `skills/app-analyze` — Analyze app workflow artifacts, functional graph, task ledger, lane maps, roles, proof requirements, and app-dev handoff for drift.
- `skills/yandex360-dns` — DNS governance workflow for bears.ru through Yandex 360 using presence-only checks, dry-run plan review, and read-only governance evidence only.
- `skills/subagents` — Govern Bears subagent selection, L2/L3 delegation, parent-control-only mode, gitflow closeout lanes, and evidence packets.
- `skills/app-dev` — Execute app task ledger tasks through L2 lane orchestrators, L2 helpers, L3 workers, and L3 critics.
- `skills/instruction-hardening` — Harden Bears docs/contracts instruction refactors and human-readable agent instructions from instruction-artifacts MCP evidence with semantic preservation, bypass closure, compression, and weighted rubric scoring.

## Disabled preserved skill docs
- `skills/secret-factory/SKILL.disabled.md` — Removed from active discovery by operator request on 2026-07-07.
- `skills/codex-telegram-operator-gate/SKILL.disabled.md` — Removed from active discovery by operator request on 2026-07-07.
- `skills/bears-infisical-ops/SKILL.disabled.md` — Removed from active discovery by operator request on 2026-07-07.
- `skills/bears-kubernetes-ops/SKILL.disabled.md` — Removed from active discovery by operator request on 2026-07-07.
- `skills/bears-plugin-update/SKILL.disabled.md` — Removed from active discovery by operator request on 2026-07-07.
- `skills/bears-blocker-eval/SKILL.disabled.md` — Removed from active discovery by operator request on 2026-07-07.
- `skills/bears-codex-health/SKILL.disabled.md` — Removed from active discovery by operator request on 2026-07-07.
- `skills/bears-deploy-gate/SKILL.disabled.md` — Removed from active discovery by operator request on 2026-07-07.
<!-- BEARS_SKILL_INVENTORY: END -->

Canonical agent workflow map: `assets/catalog/agent-workflow-map.v1.json`.

## Agentic enterprise workflow

The Bears plugin owns a compact agentic enterprise workflow surface:

- `assets/catalog/agentic-enterprise-constitution.v1.json` stores the role-scoped principles: Docs-as-Code, Contract-first, Schema-first, DRY, modularity, single responsibility, executable validation, file-backed state, no hidden state, metrics, ADR, Policy-as-Code, and Observability-as-Code.
- `assets/catalog/agentic-enterprise-workflow.v1.json` defines four repo domains: `platform`, `gitops`, `infra`, and `product_infra`. The plugin validates boundaries and must not generate product, GitOps, infra, connector, MCP, product app, runtime-service, or production-mutation payloads.
- `assets/catalog/subagent-orchestration-policy.v1.json` lists L2 domain delegation controllers for `platform`, `gitops`, `infra`, and `product_infra`. Each L2 controller may spawn only `bears-token-budget-helper`, `bears-git-workflow-helper`, and `bears-review-fix-helper` with `fork_context=false` and `parent_context=none`.
- `scripts/agentic_enterprise_workflow.py` validates the constitution, workflow catalog, decision logs, scope matrices, and hook decisions. Local commit validation is the closeout authority; operator-dispatched GitHub diagnostics may run this validator only as non-closeout evidence.
- `assets/catalog/tech-debt-matrix.v1.json` records workflow debt as state-file-backed rows. `scripts/tech_debt_matrix.py validate` keeps local validation failures and workflow defects executable instead of chat-only.
- `hooks.json` wires Codex `SessionStart`, `UserPromptSubmit`, `PreToolUse`, and `Stop` to compact guards; `UserPromptSubmit` runs the internal pre-task guard, and `Stop` runs the closeout delivery guard. `SessionStart` or the first guard creates the ignored runtime L1 state file, hook control derives duration from that state, governed L1/L2/L3 work without time or token control metadata is denied, and work over 5 minutes must split. Hook hot path reads compact state, compiled catalog, plugin delivery state, and metadata-only git status; it does not run tests, broad search, network calls, raw logs, workspace scans, or secret reads.
- `docs/reference/agentic-enterprise-workflow.md` documents scope size, owner lineage, decision log, clarification gate, runtime degradation, and hook SLOs.

Required L1 flow: user message -> `scope_row` -> `research` -> clarification gate when allowed -> `l1_task_decomposition` -> `l2_governance_review`. L1 owns task decomposition and task matrix writing; L2 owns governance review, not task splitting. Do not spawn a subagent for each task; spawn only from a validated assignment packet after L2 governance review. L3 owns exact tasks, docs, schemas, and fixtures.

Test selection authority: `assets/catalog/test-selection.v1.json`. The local git `pre-commit` hook blocks failing staged changes; the local git `post-commit` hook runs impacted fast tests for the commit diff and writes exact-SHA proof under `runtime/local-commit-validation/`. GitHub Actions runs `main` push diagnostics but does not update the local Codex cache. `workflow_dispatch` with `emergency_full_suite=true` is operator-only. Interactive agents must not run test-selection, pytest, unittest, or repo validator suites unless the operator explicitly lifts the ban.
