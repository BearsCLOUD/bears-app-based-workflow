# Plugin Constitution Capability

## Status

- Task: P1-04 plugin-constitution-pilot.
- Lifecycle: dual inventory row with legacy canonical source phase.
- Authority: `python3 scripts/plugin_constitution.py validate` remains authoritative in Phase 1.

## Entrypoints

- Legacy authoritative command: `python3 scripts/plugin_constitution.py validate`.
- Compatibility wrapper command: `python3 capabilities/plugin_constitution/scripts/validate.py --json`.

## Package files

- `capability.json`: capability metadata aligned with `capabilities/inventory.v1.json`.
- `scripts/validate.py`: deterministic wrapper around legacy validation.
- `fixtures/pass/catalog.valid.json`: passing catalog fixture.
- `fixtures/fail/catalog.invalid.json`: failing catalog fixture.
- `tests/test_validate.py`: wrapper and inventory alignment tests.

## Restricted data

This package uses checked-in governance artifacts only. It must not read secrets, tokens, private keys, `.env` values, raw logs, raw chat, raw VPN configs, production data, credentials, or shell history.
