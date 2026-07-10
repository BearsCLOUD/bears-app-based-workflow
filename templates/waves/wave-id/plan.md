# Wave Plan: <wave-id>

## Wave ID

`<wave-id>`

## Research basis

- `<research-ref>` explains `<constitution-ref>`.

## Sequential microtasks

| Order | Task ID | Constitution refs | Research refs | Target paths | Depends on | Owner role | Critic role | Definition of done | Proof requirement | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `task-id` | `cap-example` | `waves/<wave-id>/research.md#section` | `<path>` | none | `implementation-owner` | `reviewer` | `<done>` | `<proof from existing artifacts or none-required>` | `ready_for_graph` |

## Ledger updates

- Mirror the microtasks in `docs/app-task-ledger.v1.json`.

## Graph modeling handoff

- `app-functional-graph` models each approved microtask as one or more dev-stage graph nodes and writes node refs back to the ledger.

## Drift notes

- `<drift-or-none>`

## Next skill

- `app-functional-graph`
