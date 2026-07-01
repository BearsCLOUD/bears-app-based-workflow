# Capability Governance Rules

This file is the retained governance-core source for capability layout, validator coverage, environment packets, optimization lanes, effective configuration, performance controls, offload controls, programmatic surfaces, and refactor closeout. It replaces the deleted draft capability file as the validator source path.

## P1-09 parity-and-restricted-data-validation

Parity and restricted-data checks must be executable validators. They must read only checked-in fixtures and sanitized evidence packets, and they must fail when required pass/fail fixtures or restricted-data markers are missing.

## P1-10 environment-packet-validation

Environment operations must use typed packets with target surface, authorization evidence, rollback path, and dry-run/apply intent. Default apply is forbidden.

## P1-11 optimization-lane-validation

Optimization claims must bind to an environment packet, measured baseline, proposed change, rollback, and affected surfaces. Claims without evidence fail validation.

## P1-12 effective-config-resolution

Effective configuration must resolve trusted layers only, preserve redacted fields, and reject ignored project keys, raw config values, untrusted remotes, or unvalidated programmatic surfaces.

## P1-13 codex-performance-control

Performance changes must state measured cost, required command, operator authorization when permissions change, rollback, and complete surface coverage.

## P1-14 codex-offload-control

Offload surfaces must define permission policy, write isolation, cleanup command, environment packet, and matching effective-config snapshot.

## P1-15 codex-programmatic-surface-control

Programmatic control surfaces must define environment owner, authentication policy, surface policy, environment packet, and effective-config snapshot.

## P1-16 automation-first-refactor-gate

Refactor closeout must prefer executable validators and checked fixtures over instruction-only claims. Policy-only closeout fails.

## P1-17 executable-logic-preference

Capability rules that claim pass/fail authority must map to executable validators, status fields, and pass/fail fixtures. Router text alone is not enough.

## Audit debt tracking authority

New audit findings for workflow defects, cache drift, hook proof gaps, agent registration drift, or CI closure risk must be recorded in `assets/catalog/tech-debt-matrix.v1.json` and validated by `scripts/tech_debt_matrix.py`.

This reference file may retain historical weak-spot notes, but those notes are not closure authority. Closure authority requires machine-readable state refs, acceptance rows, and validator output from the tech-debt matrix.

Do not append new `W*` weak-spot sections here. Add or update a tech-debt matrix item instead, then cite that item from human-facing docs when needed.

## Retired prose audit register

Dated workflow findings that used `W*` weak-spot sections are retired from this reference file. The last prose register covered `W1` through `W207`; Git history keeps that dated snapshot.

Current workflow debt authority is `assets/catalog/tech-debt-matrix.v1.json`. New or reopened findings for workflow defects, cache drift, hook proof gaps, agent registration drift, CI closure risk, or governance-reference coverage gaps must be recorded as matrix items with state refs, acceptance rows, owner, severity, and status.

Relevant executable checks:

- `python3 scripts/tech_debt_matrix.py validate`
- `python3 scripts/tech_debt_matrix.py status --json`
- `python3 scripts/platform_roles.py route <target>`
- `python3 scripts/platform_roles.py audit <target>`

This file remains a rule index only. It is not a closure register, audit log, runtime proof, CI proof, or cache-sync proof.
