# Workflow Artifact Contracts

## `docs/app-constitution.md`

Required sections:

1. `Functional summary`
2. `Core capabilities`
3. `Actors and runtime surfaces`
4. `Constraints and evidence`
5. `Functional gaps`
6. `Open decisions`
7. `AGENTS alignment note`
8. `Next skill`

Each capability or gap needs a stable id, owner, evidence need, and state.

## `waves/index.md`

Each row needs wave id, constitution refs, status, current stage, next skill, and source refs.

## `waves/<wave-id>/research.md`

Required sections:

1. `Wave ID`
2. `Scope`
3. `Constitution mapping`
4. `Known behavior`
5. `Sources`
6. `Decisions`
7. `Unknowns`
8. `Clarifications`
9. `Plan inputs`
10. `Drift notes`
11. `Next skill`

Each research explanation must point to constitution ids.

## `waves/<wave-id>/plan.md`

Required sections:

1. `Wave ID`
2. `Research basis`
3. `Sequential microtasks`
4. `Ledger updates`
5. `Graph modeling handoff`
6. `Drift notes`
7. `Next skill`

Each microtask must point to constitution refs and research refs.

## `waves/<wave-id>/analysis.md`

Required sections:

1. `Wave and target`
2. `Inputs reviewed`
3. `Lineage check`
4. `Implementation comparison`
5. `Broken links`
6. `Status`
7. `Next skill`

Allowed statuses: `pass`, `needs-constitution`, `needs-research`, `needs-plan`, `needs-graph`, `needs-dev`, `blocked`.

## Packets

Packets returned in responses or handoffs must include stage, wave id, refs, target paths when relevant, owner skill, next skill, completion criteria, and drift notes.
