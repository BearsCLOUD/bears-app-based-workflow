# Formal Semantics Kernel

The formal semantics kernel is the JSON authority for accepted workflow facts in the `@Bears` plugin.

## Canonical files

- Kernel catalog: `assets/catalog/formal-semantics-kernel.v1.json`.
- Type catalog: `assets/catalog/semantic-type-system.v1.json`.
- Kernel schema: `assets/schemas/formal-semantics-kernel.v1.schema.json`.
- Type schema: `assets/schemas/semantic-type.v1.schema.json`.
- Relation schema: `assets/schemas/semantic-relation.v1.schema.json`.
- CLI validator: `scripts/formal_semantics.py`.
- Test surface: `tests/test_formal_semantics.py`.
- Reference doc: `docs/reference/formal-semantics-kernel.md`.

JSON catalogs and schemas are the source of truth. This page explains the file set and validator wiring only.

## Terms

- Semantic type: JSON label for a workflow entity such as `goal`, `file`, `role`, `validator`, or `term`.
- Relation: directed JSON edge between two typed entities.
- Closed-world: the catalog list is complete for validator decisions.
- Candidate fact: proposed fact that cannot unlock execution.
- Accepted fact: validator-approved fact that downstream rules may query.

## Required type packet

Each semantic type record uses this exact key set:

```json
{
  "id": "goal",
  "parent_types": [],
  "allowed_relations": ["implements"],
  "closed_world": true,
  "authority_source": "assets/catalog/semantic-type-system.v1.json",
  "validator": "scripts/formal_semantics.py validate --json"
}
```

## Required relations

The kernel relation catalog must include these directed relation ids:

```text
is_a
part_of
depends_on
requires
blocks
enables
implements
validates
owns
reads
writes
uses
produces
consumes
proves
supersedes
conflicts_with
```

## Rules

- Unknown semantic type blocks material workflow decisions.
- Unknown relation blocks graph writes.
- Relation direction must validate before a fact is accepted.
- Closed-world relations are authoritative and cannot be invented by LLM output.
- Open-world uncertainty must be stored as `candidate`, not truth.
- LLM output may propose facts; validators alone accept facts.
- A candidate fact cannot unlock execution.
- An accepted fact may be queried by downstream rules.

## Commands

```text
python3 scripts/formal_semantics.py validate
python3 scripts/formal_semantics.py check-fact --packet <path> --json
python3 scripts/formal_semantics.py check-relation --packet <path> --json
python3 scripts/formal_semantics.py doctor --json
```

## Integration points

- #431 semantic graph must use this type and relation kernel.
- #429 file-context records must use semantic types.
- #413 roadmap nodes must use typed relations.
- #414 decision packets must reference accepted semantic facts.
- #415 principles and goals must map to semantic types.
- `assets/catalog/bears-doctor.v1.json` must expose `formal_semantics_status` with `python3 scripts/formal_semantics.py doctor --json`.
- `assets/catalog/test-selection.v1.json` must route kernel changes to `tests/test_formal_semantics.py` and metadata validators.
- `assets/catalog/artifact-registry.v1.json`, `assets/catalog/decision-ledger.v1.json`, and `assets/catalog/release-notes.v1.json` must include #435 metadata coverage.

## Acceptance checks

- Type catalog validates.
- Invalid relation direction fails.
- Unknown semantic type fails.
- Candidate fact cannot unlock execution.
- Accepted semantic fact can be queried by downstream rules.
- `bears_doctor` reports formal semantics status.
