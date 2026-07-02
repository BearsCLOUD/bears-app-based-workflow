---
name: speckit-bears-flow
description: Run the Bears opinionated Spec Kit flow with research, deterministic prototype/spike gate, deterministic design artifact gate, requirements checklist, plan, tasks, analyze, implementation, validation, and scoped commit discipline.
---

## Entity terms

`app` means a Bears product application source directory under `/srv/bears/dev/app` or `BearsCLOUD/apps`. `project` means a GitHub Project planning board with linked Issues and metadata fields. Use `target`, `registered target`, `repo`, `path`, `workspace surface`, or `app directory` for filesystem/source ownership.

# Bears Spec Kit Flow

Use this `@bears` workflow skill as the Bears planning core for broad, non-product, repo-boundary, plugin, infra, Kubernetes, or migration work. It is not a deprecated standalone `bears-speckit` plugin or layer. Small exact-file bugfixes may skip the full packet only when there is no boundary, runtime, deploy, restricted-data, or public behavior change.

For Bears target-native work that needs durable project rules, functional documentation, GitHub Projects planning, or execution from Project items, use the Bears target skill chain: `$bears-project-constitution` -> `$bears-project-specify` -> `$github-project-planning` when Project fields/views are needed -> `$bears-project-plan` -> `$bears-project-analyze` -> `$projectdevsubagents`.

Upstream Spec Kit command skills (`speckit-specify`, `speckit-checklist`, `speckit-plan`, `speckit-tasks`, `speckit-analyze`, and `speckit-implement`) resolve from `/srv/bears/.agents/skills`, not from this plugin.

## Flow

1. **Route gate**: identify target path, repo, owner, registry entry, and candidate specialist role.
2. `$speckit-bears-research` for GitHub prior art, external best practices, UX-facing interface research, risks, constraints, alternatives, and validation implications when research gate conditions match.
3. **Prototype/spike gate**: require `prototype.md` or `spike.md` when research or design leaves unresolved high-risk uncertainty that can be cheaply tested.
4. `$speckit-specify` from `/srv/bears/.agents/skills` to create or update `spec.md`.
5. `$speckit-checklist` from `/srv/bears/.agents/skills` to validate requirement quality.
6. **Design artifact gate**: require `design.md` in the feature or spec directory, or `README.md#issue-22-design-artifact-contract` until a feature directory exists, before plan, tasks, analyze, and implementation.
7. **Review gate**: stop for operator approval before planning when requirements changed materially.
8. `$speckit-plan` from `/srv/bears/.agents/skills` to create or update design and implementation plan artifacts.
9. **Review gate**: stop for operator approval before task generation when architecture, runtime, or target boundaries changed materially.
10. `$speckit-tasks` from `/srv/bears/.agents/skills` to generate dependency-ordered implementation tasks.
11. `$speckit-analyze` from `/srv/bears/.agents/skills` to detect cross-artifact drift; implementation stays blocked until it passes or the operator explicitly rescope-fixes the packet. For GitHub Project-backed Bears plans, run `$bears-project-analyze` on the constitution, spec, docs, Project items, Issues, route/audit roles, validation, dependencies, and `$projectdevsubagents` handoff.
12. **Spec Kit gate**: require `spec.md`, `plan.md`, `tasks.md`, and analyze PASS, or for Bears target-native flow require constitution packet, specification packet, GitHub Project plan packet, and `$bears-project-analyze` PASS.
13. **Role gate**: prove each selected `tasks.md` item or GitHub Project item matches the exact Bears specialist role.
14. **Subagent execution**: the main agent orchestrates; subagents execute concrete tasks from `tasks.md` or `$projectdevsubagents` executes ready GitHub Project items. Tasks marked `[P]` or disjoint Project items should run in parallel when paths are disjoint and role coverage exists.
15. `$speckit-implement` from `/srv/bears/.agents/skills` or `$projectdevsubagents` only after the implementation scope is approved.
16. Run narrow validation and report all failures.
17. Run the four non-product audits once at the stage boundary, not after each small file edit.

## Bears target-native chain

Use this chain when the requested output is target governance, functional documentation, GitHub Project planning, or execution from Issues rather than upstream Spec Kit feature artifacts:

1. `$bears-project-constitution` records project rules, artifact owners, forbidden actions, validation duties, and amendment rules.
2. `$bears-project-specify` creates or updates functional requirements and user/operator/developer documentation from the constitution and repo evidence.
3. `$github-project-planning` defines or verifies GitHub Project fields, views, issue hygiene, and metadata mutation gates when the planning surface is missing or stale.
4. `$bears-project-plan` maps requirements into GitHub Project items, Issues, dependencies, route-selected roles, validation, and L2/L3 handoff packets.
5. `$bears-project-analyze` checks constitution, spec, docs, Project plan, Issues, route/audit roles, validation, dependencies, and execution handoff for drift.
6. `$projectdevsubagents` executes only after analysis returns `pass` or the operator explicitly approves a scoped execution with listed advisory findings.

Do not let `$projectdevsubagents` create the Project planning model. It consumes the Project/Issue state created or approved by `$bears-project-plan`.

## Review gate definition

A review gate is an operator approval pause. It is not a code review. The agent must summarize the artifact delta, risks, validation expectation, and next action, then wait for approval when the gate condition is met.

## Research gate conditions

Run research by default when any of these are true:

- The feature is broad, new, risky, drift-prone, workflow, runtime, integration, UI/UX, automation, plugin, infra, Kubernetes, migration, or boundary-sensitive.
- The user asks to investigate GitHub, best practices, or similar projects.
- Operator/developer/user-facing, CLI, workflow, status, error, recovery, or notification behavior is affected.

Required artifacts are `research.md` and `prior-art.md`. Add `ux-research.md` when UI/UX, CLI, workflow, status, error, recovery, notification, operator, developer, or user-facing behavior is affected.

Each artifact must include Decision or Recommendation, Rationale, Alternatives considered, Risks and constraints, Validation implications, and Sources when web or repository research was used.

Store the artifacts in the Spec Kit feature directory when it exists. Before it exists, store a bounded section in `README.md` or the narrowest target docs path, then move the artifacts into the feature directory after Spec Kit creates it.

Skip research only with explicit operator skip or one exact-file scope with no boundary, runtime, deploy, restricted-data, public behavior, workflow, UI, UX, or automation pattern change.

Research artifacts must be bounded summaries. Do not copy large source text or proprietary content.

## Bears workspace rules

- Treat `/srv/bears` as workspace-control root, not one product repository.
- Use nearest target `AGENTS.md` for implementation work.
- Keep artifacts in English and user replies in concise Russian.
- Do not expose secrets or raw production data.
- Do not use `workspace-map` while it is operator-disabled. For broad, cross-target, runtime-bound, or boundary-sensitive work, use `/srv/bears/docs` network records, nearest target docs, and scoped read-only runtime proof. Use legacy `infra` MCP/cache only when explicitly targeting its cache or implementation behavior; it is not a default source of truth for runtime, deploy, network, host, domain, Docker, VPN, or Proxmox facts.
- Keep `.codex-plugin/plugin.json`, README inventory, catalog aliases, validators, and tests synchronized when plugin metadata or workflow claims change.
- Superseded checks must name the active replacement validation command.

## Prototype/spike gate conditions

Require `prototype.md` or `spike.md` under the feature directory or narrowest target docs path when research or design leaves unresolved high-risk uncertainty that can be cheaply tested. The artifact must record hypothesis or uncertainty, prototype scope and non-goals, commands or checks run, findings and evidence summary, decision outcome, validation implications, and cleanup or discard requirements.

Skip prototype only for a narrow exact-file bugfix with no boundary, runtime, deploy, restricted-data, or public behavior change, or for an already-proven implementation pattern with named evidence. Prototype output is throwaway evidence, not durable implementation. Operator approval is required before implementation when material behavior, runtime, boundary, UI/UX, or architecture changes remain.

## Design artifact gate conditions

Require the design artifact for workflow policy, orchestration policy, subagent policy, hook behavior, roadmap control, role gate, runtime contract, validator behavior, operator interaction, developer interaction, and UI/UX flow changes. Behavior branches, policy branches, state transitions, or operator paths require a decision table or policy matrix. Approved skip and narrow bugfix skip are the only valid bypasses.
