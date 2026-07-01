# Plugin Constitution Capability Router

## Scope

- Own only the Phase 1 pilot capability package for Bears plugin constitution governance.
- Keep `scripts/validate.py` as a wrapper around the legacy authoritative validator.
- Do not claim Phase 2 authority while `canonical_source_phase` is `legacy`.

## Functional map

- Parent plugin map: `/srv/bears/plugins/bears/AGENTS.md#functional-map`.
- `capability.json` — capability identity, authority, and legacy source phase.
- `schemas/validation-result.schema.json` — local capability result packet contract.
- `scripts/validate.py` — wrapper entrypoint for plugin constitution validation.
- `tests/test_validate.py` and fixtures — capability-local coverage only.

## Boundary

- Allowed reads: checked-in plugin constitution catalog, reference docs, manifest, role catalog, and capability fixtures.
- Forbidden reads: secrets, tokens, private keys, `.env` values, raw logs, raw chat, raw VPN configs, production data, credentials, and shell history.
- Forbidden writes: product code, runtime services, deployment behavior, apps, connectors, MCP servers, and Codex environment files.

## Validation

- `python3 capabilities/plugin_constitution/scripts/validate.py --json`
- `python3 scripts/capability_layout.py validate --json`
- `python3 -m unittest capabilities/plugin_constitution/tests/test_validate.py`
