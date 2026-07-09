---
name: app-constitution
description: Create or update the first-stage app constitution as the functional source of truth for sequential Bears app workflow artifacts. Use when Codex needs functional capabilities, gaps, decisions, constraints, evidence needs, or drift routing before research, planning, graph modeling, analysis, or development.
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
7. `Host policy notes`
8. `Next skill`

## Capability and gap rules

- Give every capability and gap a stable id.
- Record owner, evidence need, and state for every capability.
- Record impact, evidence, and route for every gap.
- Keep host policy notes separate from functional truth.
- Do not depend on a specific host instruction file, workspace path, MCP server, hook, or runtime.

## Drift rules

- Functional drift is resolved here before research, plan, graph, or dev changes.
- Research drift must point back to a constitution id or add a constitution gap.
- Plan drift must point back to a constitution id and research explanation.
- Graph drift must point back to a constitution id, research explanation, and plan microtask.
- Host-policy drift is an execution constraint and must not rewrite functional truth.

## Rules

- Do not create research waves, plan microtasks, graph nodes, or dev packets here.
- Route missing source or domain knowledge to `app-research`.
- Route unresolved functional choices to `app-research` or helper `app-specify`.
- Route ready constitution ids to `app-research`.
- Do not ask agents to run validation, test, audit, route, cache, cachebuster, quick-validate, or plugin-validate scripts manually.
