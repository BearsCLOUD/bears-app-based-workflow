# Bears Capability Inventory

This directory owns the executable capability inventory for the @Bears plugin.

## Authority

- `inventory.v1.json` maps every V2 capability ID to its current legacy, planned, dual, capability, or deprecated state.
- `capability.schema.json` defines the machine-readable inventory and capability row fields.
- `scripts/capability_layout.py` validates inventory coverage, active skill front-door mapping, disabled-skill exclusion, hot-path exceptions, and cache status packets.

## Boundaries

- This directory is plugin governance source only.
- It does not add apps, connectors, MCP servers, runtime services, product code, deployment behavior, or Codex environment mutation.
- Restricted data remains forbidden: secrets, tokens, private keys, `.env` values, raw logs, raw chat, raw VPN configs, production data, credentials, and shell history.

## Required checks

Run from the plugin root or any working directory:

```bash
python3 /srv/bears/plugins/bears/scripts/capability_layout.py validate-inventory --json
python3 /srv/bears/plugins/bears/scripts/capability_layout.py validate-hot-path --json
python3 /srv/bears/plugins/bears/scripts/capability_layout.py status --json
```
