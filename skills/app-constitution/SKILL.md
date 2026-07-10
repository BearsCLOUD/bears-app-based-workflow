---
name: app-constitution
description: Create or update the first-stage app constitution for Bears app workflow work. Use when Codex needs a Spec Kit-style baseline before app research, specification, graph planning, analysis, or implementation.
---

# App Constitution

## Output

Write `docs/app-constitution.md` for the app target. If a wave already exists, link it instead of duplicating details.

## Required sections

- Target app path or repo.
- Product owner or decision source.
- In-scope users, actors, and runtime surfaces.
- Non-negotiable rules and constraints.
- Data ownership and secret boundaries.
- Acceptance evidence required before a wave can close.
- Open decisions that block specification or planning.

## Rules

- Keep the constitution app-local; do not write workspace-wide rules.
- Record concrete decisions only. Put uncertain items under `Open decisions`.
- Do not create implementation tasks here.
- Send missing product choices to `app-specify`.
- Send missing source or domain knowledge to `app-research`.
