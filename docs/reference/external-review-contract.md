# External Review Contract

## Purpose

This contract validates repo-visible external review packets.

JSON Schema is the source of truth. The CUE file is only a pilot mirror for tool checks.

## Commands

- `python3 scripts/external_review_contract.py validate`
- `python3 scripts/external_review_contract.py check --packet <path> --json`

## Packet rules

- `closed` or `superseded` requires proof.
- A behavior-changing surface requires a changelog.
- A governance change requires a decision.
- Every packet must point at `assets/schemas/external-review-audit.v1.schema.json#/$defs/contract_packet`.

## CUE pilot

- If `cue` is missing, the report returns `tool_missing`.
- If the pilot is disabled, the report returns `pilot_disabled`.
- If `cue` runs, the report returns `pass` only after a successful `cue eval`.

## Packets

- `tests/fixtures/external_review_contract/good/closed_with_proof.json`
- `tests/fixtures/external_review_contract/bad/missing_proof.json`
- `tests/fixtures/external_review_contract/bad/missing_changelog.json`
- `tests/fixtures/external_review_contract/bad/missing_decision.json`
