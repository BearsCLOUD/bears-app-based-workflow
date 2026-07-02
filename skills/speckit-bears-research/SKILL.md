---
name: speckit-bears-research
description: Produce Spec Kit-style research artifacts before specification work, covering GitHub prior art, external best practices, UI/UX-friendly interfaces, risks, and documented recommendations for Bears targets.
---

# Bears Spec Kit Research

Use this skill before `$speckit-specify`, plan, tasks, analyze, or implementation when the research gate conditions match.

## Purpose

Create research artifacts that are structured like Spec Kit outputs and can be consumed by later prototype, specification, planning, task, analysis, and implementation steps.

## Required gate conditions

Run research for broad, new, risky, drift-prone, workflow, runtime, integration, UI/UX, automation, plugin, infra, Kubernetes, migration, or boundary-sensitive work.

Run `ux-research.md` when operator-facing, developer-facing, user-facing, CLI, workflow, status, error, recovery, notification, UI, or UX behavior is affected.

Skip research only with explicit operator skip or one exact-file scope with no boundary, runtime, deploy, restricted-data, public behavior, workflow, UI, UX, or automation pattern change.

## Required research tracks

1. **GitHub prior art**
   - Search for existing implementations, related repositories, issues, discussions, and patterns.
   - Record reusable ideas, license or compatibility concerns, stale/unmaintained examples, and explicit non-goals.

2. **Best practices**
   - Research how mature projects solve similar problems.
   - Capture patterns, anti-patterns, operational risks, validation expectations, and migration constraints.

3. **UI/UX-friendly interfaces**
   - Research operator-facing, developer-facing, or end-user interface patterns relevant to the feature.
   - Document clarity, navigation, status, error, recovery, accessibility, and low-noise notification guidance.

## Output files

Write under the current feature directory when it exists:

- `research.md` — consolidated decisions and rationale.
- `prior-art.md` — GitHub/project examples and comparison notes.
- `ux-research.md` — user-friendly interface patterns and recommendations.

If no feature directory exists yet, write a bounded section under `README.md` or the narrowest target docs path, then move it into the feature after `$speckit-specify` creates one.

## Required structure

Each artifact must include:

- `Decision` or `Recommendation`
- `Rationale`
- `Alternatives considered`
- `Risks and constraints`
- `Validation implications`
- `Sources` with links when web research was used
- `Sources` with repository paths when repository research was used
- `Prototype trigger` with unresolved high-risk uncertainty and cheap bounded check when present

## Boundaries

- Do not copy large source text or proprietary content.
- Prefer official documentation, primary repositories, and maintained examples.
- Mark stale or unverified claims explicitly.
- Keep user-facing summaries concise and write target artifacts in English.
