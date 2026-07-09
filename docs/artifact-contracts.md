# Workflow Artifact Contracts

## `docs/app-constitution.md`

Required sections:

1. `Functional summary`
2. `Core capabilities`
3. `Actors and runtime surfaces`
4. `Constraints and evidence`
5. `Functional gaps`
6. `Open decisions`
7. `Execution constraints`
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

Each microtask row must include order, task id, constitution refs, research refs, target paths, dependencies, owner role, critic role, definition of done, proof requirement, and status.

## `waves/<wave-id>/analysis.md`

Required sections:

1. `Wave and target`
2. `Inputs reviewed`
3. `Lineage check`
4. `Implementation comparison`
5. `File reuse audit` when plugin files or skills are the target
6. `Broken links`
7. `Status`
8. `Next skill`

Allowed statuses: `pass`, `needs-constitution`, `needs-research`, `needs-plan`, `needs-graph`, `needs-dev`, `blocked`.

File reuse audit dimensions: usefulness, consistency, brevity, unambiguity, instruction coverage, portability, degradation resistance, continuous-development readiness, and no-test-tooling risk.

## Packets

Packets returned in responses or handoffs must use the versioned fields in `docs/handoff-packet-contracts.md`. A downstream skill must not require fields that the upstream packet contract does not provide.
