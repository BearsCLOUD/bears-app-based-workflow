# Open Issues Workstreams for `BearsCLOUD/bears_plugin`

Source input: all 109 open GitHub issues in the live repo snapshot on 2026-06-27T20:00:00Z.
Rule: issues are backlog input, not source of truth. If a proposed fix would break existing functionality, keep the issue open and add a comment that says what breaks and why.
Coverage: 109 assigned, 0 missing, 0 duplicates. `#517` is excluded because it is closed; `#518` is included.

## Workstream 1: Roadmap and autostart control

**Controller role:** `bears-development-workflow-orchestrator`
**Live controller agent:** `Dalton` / `019f0aa3-676e-7870-97cb-0e33c1d92e4a`
**Mini-model workers:** `bears-explorer, bears-worker`

Issues:
- #413 P0: Add executable workflow roadmap graph
- #422 P0: Refactor main autostart workflow to roadmap-first execution
- #423 P0: Add roadmap backlog ingestion and fillability reconciler
- #467 P0: Add issue-autostart lease cancellation and recovery invariants
- #468 P0: Add immutable GitHub issue source snapshot gate for goal/autostart intake
- #481 P0: Add issue-daemon autostart eligibility parity gate
- #504 P0: Add stable issue delivery identity and title-drift lease gate
- #505 P0: Add repo-qualified issue reference contract for global planner and roadmap bridge
- #514 P0: Add migration hazard taxonomy gate for issue autostart safety
- #515 P0: Add workflow roadmap and issue-priority freshness gate
- #516 P0: Add roadmap decomposition autostart inheritance gate
- #518 P0: Add global planner resource-conflict and parallelization lane gate

## Workstream 2: Agent runtime, subagents, runners, locks, and policy

**Controller role:** `bears-subagent-orchestration-engineer`
**Live controller agent:** `Bacon` / `019f0aa3-a57c-7851-b716-ffb2bb973129`
**Mini-model workers:** `bears-worker, bears-runtime-verifier, bears-docs-maintainer`

Issues:
- #1 Align subagent reasoning policy and session reuse gates
- #370 P0: Add executable agent worker runtime dispatcher
- #372 P0: Add deterministic runners for git, validation, cache sync, and evidence compaction
- #373 P1: Refactor helper role eligibility and support-only authority
- #374 P1: Add context-economy packet contracts for no-parent-context subagents
- #375 P1: Add worktree and file-scope locking for parallel agent work
- #376 P1: Rework Codex hooks into guard and enqueue-only controls
- #381 P1: Add GitHub repository inventory drift audit for plugin-described repos
- #404 P0: Enforce solved issue closure after codex exec delivery
- #406 P0: Add controlled cheap workspace research orchestrator
- #407 P0: Add workspace layout and knowledge authority contracts
- #408 P0: Add AGENTS.md and instruction surface contracts
- #409 P0: Add Codex memory and context-cache audit controls
- #414 P0: Add Codex workflow execution decision gates
- #416 P0: Add OpenCode headless executor adapter for bounded subagents
- #417 P0: Add MCP tool access policy for exec agents
- #418 P0: Add skill and agent-role context budget governance
- #419 P0: Add per-commit agent usage and context analytics ledger
- #421 P0: Add GitOps workflow degradation and rollback gates
- #426 P0: Add goal-state orchestrator for Codex exec role workflows
- #430 P0: Add file-scoped execution plan and session reuse pool
- #431 P0: Add workspace semantic graph and metadata store
- #441 P0: Add proof-driven prompt compiler and context pack assembly
- #442 P0: Add Clarification Architect role for drift-free goal questions
- #447 P0: Add codex exec goal cycle controller with resume-safe state
- #451 P0: Add multi-level capability harness for agent-first workflow testing
- #452 P0: Extend infra evidence adapter with OpenCode observability/SLO packet
- #453 P0: Add agent capability ladder experiment runner and comparative decision gate
- #454 P1: Add explicit closeout waiver packet for AGENTS-blocked unittest suites
- #455 P1: Promote capability harness L7 subagent scenario to dispatcher-backed fixture execution
- #456 P0: Add CD application dependency DAG and workflow sequence gate
- #457 P0: Add bears_doctor component coverage reconciler
- #458 P0: Extend infra evidence adapter with GitHub Actions safety packet
- #459 P0: Add Pants-based test target graph and impacted check runner
- #462 P1: Add CUE/JSON Schema contract pilot for external review audit packets
- #474 P0: Add paginated GitHub issue fact ingestion gate for daemon
- #488 P0: Add Codex runtime env custody and proxy health gate for issue daemon
- #489 P0: Fix orchestrator role and runner fail-open gaps found by review
- #490 P0: Add daemon commit evidence persistence and proof bundle gate

## Workstream 3: Issue daemon service loop and closeout pipeline

**Controller role:** `bears-development-workflow-orchestrator`
**Live controller agent:** `Gibbs` / `019f0aa3-ddec-7150-8794-e403442c0061`
**Mini-model workers:** `bears-worker, bears-runtime-verifier`

Issues:
- #470 P0: Add orchestrator issue-daemon queue handoff and reconciliation gate
- #477 P0: Add issue discovery coverage and overflow gate for daemon service
- #478 P0: Add issue-daemon polling backoff and GitHub API budget gate
- #487 P0: Add issue-daemon service config template placeholder contract
- #491 P0: Add issue-daemon service-loop cycle ledger and evidence retention gate
- #492 P0: Add issue-daemon service liveness heartbeat and stale-cycle gate
- #493 P0: Add issue-daemon service manager identity and config-to-unit parity gate
- #494 P0: Add issue-daemon runtime state atomicity and single-writer gate
- #495 P0: Add issue-daemon runtime config generation and loop-root freshness gate
- #496 P0: Add issue-daemon dispatch idempotency checkpoint and side-effect journal gate

## Workstream 4: Knowledge Orchestrator control plane

**Controller role:** `bears-development-workflow-orchestrator`
**Live controller agent:** `Arendt` / `019f0aa4-b8bc-70d2-bc97-4b3bd6d5205e`
**Mini-model workers:** `bears-worker, bears-runtime-verifier`

Issues:
- #499 P0: Add knowledge orchestrator result validation and quarantine gate
- #500 P0: Add Knowledge Orchestrator workspace boundary and skip-git-repo-check custody gate
- #501 P0: Add Knowledge Orchestrator Codex Exec timeout and stuck-lock recovery gate
- #502 P0: Add Knowledge Orchestrator repo-visible runtime artifact gate
- #503 P0: Add Knowledge Orchestrator active-goal execution gate and dormant parity contract
- #506 P0: Add Knowledge Orchestrator state-mutating command lock matrix and resume single-writer gate
- #507 P0: Add Knowledge Orchestrator runtime role profile custody gate
- #509 P0: Add Knowledge Orchestrator operator-answer unblock contract
- #511 P0: Add Knowledge Orchestrator event ledger schema and durability gate
- #512 P0: Add Knowledge Orchestrator systemd env/workspace unit parity gate
- #513 P0: Add Knowledge Orchestrator work-item lifecycle and DAG integrity gate

## Workstream 5: CD, Kubernetes, and deployment custody

**Controller role:** `bears-deploy-platform-engineer`
**Live controller agent:** `Hegel` / `019f0aa5-95ae-7021-a7d1-84ca523cfe2b`
**Mini-model workers:** `bears-worker, bears-runtime-verifier, bears-docs-maintainer`

Issues:
- #379 P2: Align main-only delivery with failed diagnostics and remediation scopes
- #380 P0: Close auth/gateway split governance drift before downstream merges
- #410 P1: Add executable surface promotion system
- #461 P1: Add Dagger delivery validation wrapper for local and CI parity
- #464 P0: Add infra evidence freshness and commit-binding gate
- #465 P0: Add structured Kubernetes manifest safety validator for CD contracts
- #466 P0: Add CD evidence packet and artifact coverage gate
- #469 P0: Add manifest-derived Kubernetes API preflight coverage gate
- #471 P0: Add generated CD bootstrap manifest safety and custody gate
- #472 P0: Add async validation proof parity and closeout authority gate
- #473 P0: Add async validation queue identity and shard-lineage gate
- #475 P0: Add server-side apply field ownership and drift gate for CD
- #476 P0: Add CD rollout impact and restart budget gate
- #479 P0: Add deployment branch protection and required-check evidence gate
- #480 P0: Add CD local image build provenance and k3d import custody gate
- #482 P0: Add CD contract-to-infra test expectation parity gate
- #483 P0: Add CD checkout identity and deploy-argument attestation gate
- #484 P0: Add pre-push closeout authority gate for issue daemon live execution
- #485 P0: Add daemon closeout manifest ordering and commit-bound coverage gate
- #486 P0: Add CD rollback strategy compatibility gate for local-image deployments
- #497 P0: Add prod CD workflow routing registry and unmanaged deploy gate
- #498 P0: Add CD kubeconfig source parity and runner-credential custody gate

## Workstream 6: Seller route and cutover safety

**Controller role:** `bears-product-app-zone-engineer`
**Live controller agent:** `Helmholtz` / `019f0aa7-670a-7d90-ab28-13c0b14cefac`
**Mini-model workers:** `bears-worker, bears-runtime-verifier`

Issues:
- #424 P0: Add global seller migration long-term planning graph
- #427 P0: Add cross-repo source snapshot ledger for seller migration planner
- #449 P0: Add seller migration agent/profile binding validator
- #508 P0: Add canonical seller route identity and domain-alias normalization gate
- #510 P0: Add seller cutover approval evidence normalization and placeholder-ban gate

## Workstream 7: Planning, graph, and audit surfaces

**Controller role:** `bears-docs-maintainer`
**Live controller agent:** `Ramanujan` / `019f0aa8-3d0f-72b1-90ad-81211434a56b`
**Mini-model workers:** `bears-explorer, bears-worker`

Issues:
- #425 P0: Make issue state, changelog, and decisions first-class audit surfaces
- #433 P0: Add planning metrics ledger and storage-neutral analytics export contract
- #436 P0: Add cross-repo generated issue lineage and idempotent reconciler
- #440 P0: Add code property graph extraction for governed repositories
- #443 P0: Add model-checking invariants for orchestrator safety
- #444 P0: Add question answer ledger for goal orchestration
- #445 P0: Add closed-loop goal plan reconciler for question-driven decomposition
- #448 P1: Add drift metrics and eval gates for question-to-plan orchestration
- #460 P0: Add policy-as-code invariant gate for closeout and audit safety
- #463 P2: Evaluate Temporal only after closeout and policy gates are executable

## Comment-first / review-only items

- #422 roadmap-first execution umbrella: keep as tracker if direct closure would hide child roadmap work.
- #424 seller migration umbrella: keep as tracker if direct closure would hide child seller route/cutover work.
- #426 goal-state orchestrator umbrella: keep as tracker until child runtime contracts land.
- #463 Temporal evaluation: comment-only until closeout and policy gates are executable.
- #489 if the fix would loosen fail-open behavior without replacement checks.
- Any issue that asks for a broad replacement of a working path instead of a guarded parallel path.

## Active controller agents

- `Dalton` `019f0aa3-676e-7870-97cb-0e33c1d92e4a` — Roadmap and autostart control — `bears-development-workflow-orchestrator`
- `Bacon` `019f0aa3-a57c-7851-b716-ffb2bb973129` — Agent runtime, subagents, runners, locks, and policy — `bears-subagent-orchestration-engineer`
- `Gibbs` `019f0aa3-ddec-7150-8794-e403442c0061` — Issue daemon service loop and closeout pipeline — `bears-development-workflow-orchestrator`
- `Arendt` `019f0aa4-b8bc-70d2-bc97-4b3bd6d5205e` — Knowledge Orchestrator control plane — `bears-development-workflow-orchestrator`
- `Hegel` `019f0aa5-95ae-7021-a7d1-84ca523cfe2b` — CD, Kubernetes, and deployment custody — `bears-deploy-platform-engineer`
- `Helmholtz` `019f0aa7-670a-7d90-ab28-13c0b14cefac` — Seller route and cutover safety — `bears-product-app-zone-engineer`
- `Ramanujan` `019f0aa8-3d0f-72b1-90ad-81211434a56b` — Planning, graph, and audit surfaces — `bears-docs-maintainer`

## Execution order

1. Roadmap and autostart control.
2. Agent runtime, subagents, runners, locks, and policy.
3. Issue daemon service loop and closeout pipeline.
4. Knowledge Orchestrator control plane.
5. CD, Kubernetes, and deployment custody.
6. Seller route and cutover safety.
7. Planning, graph, and audit surfaces.
