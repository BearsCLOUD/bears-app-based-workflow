---
name: app-constitution
description: Create or update the first-stage app constitution for Bears app workflow work. Use when Codex needs a Spec Kit-style baseline before app research, specification, graph planning, analysis, or implementation.
---

# App Constitution

## Delegation first

For work already classified `DELEGATED`, act as the solo L2 analogue: decompose the stage payload below, then follow `$subagents` for each concrete L3 assignment before any data access. `DIRECT` work never enters `$subagents`.

## Stage payload

- App id and app repo or path supplied by the user or a workspace-reader result.
- Product owner or decision source.
- Known actors and runtime surfaces.
- Existing constitution or wave refs, when known.
- Product constraints and unresolved decisions.

## L3 output

The selected L3 writes `docs/app-constitution.md` with:

- target app repo or path;
- product owner or decision source;
- in-scope users, actors, and runtime surfaces;
- non-negotiable rules and constraints;
- data ownership and secret boundaries;
- evidence required before wave closeout;
- open decisions that block specification or planning.

If a wave already owns detail, link it instead of copying it. Return `app-stage-handoff.v1` with status `constitution-ready`, the constitution ref, constraint refs, open-decision refs, evidence-gap refs, and `next_stage: app-research`.

## Stage rules

- Keep the constitution app-local; do not write workspace rules.
- Record confirmed decisions. Put unresolved items under `Open decisions`.
- Do not create implementation tasks.
- Route the constitution to `app-research`, which creates or selects a wave and preserves product-decision and evidence gaps. Do not call `app-specify` before a wave id and research ref exist.
