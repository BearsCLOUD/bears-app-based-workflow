# Workflow Artifact Contracts

This file owns artifact shapes. Skills own the procedure for producing them; `SPEC.md` and `docs/workflow-stage-gates.md` own stage order and routing.

## `docs/app-constitution.md`

When the file exists, its only unconditional content is:

```markdown
# App Constitution

- App: `<exact-app-id-or-path>`
```

Add only populated sections. Every record is a level-three heading followed by these exact labeled fields:

```markdown
## Capabilities

### cap-example

- Condition: <trigger or precondition>
- Actor/System: <exact actor or system>
- Observable result: <verifiable result>
- Source: <exact reference>

## Constraints

### constraint-example

- Rule: <one mandatory app restriction>
- Source: <exact reference>

## Functional gaps

### gap-example

- Required behavior: <required result>
- Observed behavior: <observed result>
- Consequence: <specific effect>
- Observation source: <exact reference>

## Open decisions

### decision-example

- Question: <one question>
- Blocked IDs: <affected stable ids>
- Decision authority: <person or role that decides>

## Inferences

### inference-example

- Label: `inference`
- Inference: <explicit conclusion>
- Source facts: <exact references and facts>
- Research route: `app-research`
```

Each record covers one independently changeable rule, gap, question, or inference. Reuse an exact source link instead of repeating text owned by `SPEC.md`, research, a plan, or code. There is no minimum, target, or maximum line count; never add or remove content to reach a size.

An exact source resolves to a heading, symbol, URL fragment, or `docs/app-user-evidence.md#user-msg-*` anchor. A bare file, directory, session label, or paraphrase is not exact.

Do not emit empty sections or tables, placeholder records, or `None`, `N/A`, or `TBD`. Do not store session execution constraints or a next-skill field. The only next main stage is `app-research`.

An inference is a research target, not functional truth. It must not enter a plan, ledger, or functional graph. Verified research must replace it with a source-backed `cap-*` or `gap-*` before planning.

If no exact record can be written, do not create or retain a header-only file. Ask one concrete question instead.

## `docs/app-user-evidence.md`

This artifact is optional and may exist only when `docs/app-constitution.md` cites it. A user-message citation must be `docs/app-user-evidence.md#user-msg-0001`; references such as `user said`, `session`, or a paraphrase are invalid.

When the file exists, it starts with `# App User Evidence` and contains at least one cited entry.

Each entry uses a stable, never-reused `user-msg-*` id and this shape:

```markdown
## user-msg-0001

- Status: `active`
- Captured (UTC): `YYYY-MM-DD`
- Constitution IDs: `cap-example`
- Context: <optional authored context in English; omit when unnecessary>

> <unchanged verbatim excerpt>
```

Allowed statuses are `active`, `superseded`, and `withdrawn`. The quote is the shortest continuous excerpt that preserves the condition and result, and it stays in the user's language. Do not alter a quote after commit. A correction creates a new entry and marks the old entry `superseded` or `withdrawn`. Two conflicting active entries require a `decision-*` record.

`Constitution IDs` lists every constitution record that cites the entry.

Omit `Context` when it adds no meaning. Do not emit an empty entry or use `None`, `N/A`, or `TBD`.

Never store secrets, credentials, or production data. If no safe continuous excerpt exists, ask the user for a sanitized statement instead.

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

Research must read every `docs/app-user-evidence.md#user-msg-*` entry cited by the constitution. `Plan inputs` may expose only `cap-*` and `gap-*` records that the research explicitly confirms. An `inference-*` remains in research until verification produces a source-backed constitution record.

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

Microtask constitution refs may contain only research-confirmed `cap-*` and `gap-*` ids. `constraint-*`, `decision-*`, and `inference-*` records cannot substitute for an eligible functional ref.

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

In `wave-research.packet.v1`, user-evidence links use the existing `source_refs` field. They do not change packet names, fields, or versions.
