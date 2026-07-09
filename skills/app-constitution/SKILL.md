---
name: app-constitution
description: Create or update the first-stage app constitution as the functional source of truth for sequential Bears app workflow artifacts. Use when Codex needs functional capabilities, gaps, decisions, constraints, evidence needs, or drift routing before research, planning, graph modeling, development, or analysis.
---

# App Constitution

## Purpose

Maintain `docs/app-constitution.md` as the source of truth for functional capabilities, gaps, decisions, constraints, and evidence needs.

## Required sections

1. `Functional summary`
2. `Core capabilities`
3. `Actors and runtime surfaces`
4. `Constraints and evidence`
5. `Functional gaps`
6. `Open decisions`
7. `Execution constraints`
8. `Next skill`

## Capability and gap rules

- Give every capability and gap a stable id.
- Record owner, evidence need, and state for every capability.
- Record impact, evidence, and route for every gap.
- Keep execution constraints separate from functional truth.
- Do not depend on a specific host instruction file, workspace path, role inventory, MCP server, hook, or runtime.

## Drift rules

- Functional drift is resolved here before research, plan, graph, dev, or analysis changes.
- Research drift must point back to a constitution id or add a constitution gap.
- Plan drift must point back to a constitution id and research explanation.
- Graph drift must point back to a constitution id, research explanation, and plan microtask.
- Execution-constraint drift must not rewrite functional truth.

## Routing rules

- Route missing source or domain evidence to `app-research`.
- Route unresolved actors, flows, data ownership, errors, or acceptance criteria to helper `app-specify` after research cannot resolve them.
- Route ready constitution ids to `app-research`.

## Rules

- Do not create research waves, plan microtasks, graph nodes, dev packets, or test tooling here.
- Do not ask agents to run validation, test, audit, route, cache, cachebuster, quick-validate, or plugin-validate scripts manually.
