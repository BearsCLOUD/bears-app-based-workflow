---
name: secret-factory
description: Governed Bears workflow for locally generating allowed secret values and writing them to Infisical without reading, printing, storing, logging, committing, or exposing the value to the agent.
---

# Secret Factory

Required: activate this skill when an agent must create a Bears-approved generated value and place it in Infisical through the plugin-owned write-only path.

## Required workflow

1. Read `the @Bears plugin checkout/AGENTS.md`, `assets/catalog/secret-factory.v1.json`, and `docs/reference/secret-factory.md`.
2. Run the role route for the concrete Secret Factory target:
   `python3 the @Bears plugin checkout/scripts/subagents_roles.py route the @Bears plugin checkout/assets/catalog/secret-factory.v1.json`
3. Accept only a request JSON file with keys `secret_name`, `kind`, and optional `secret_path`, `bytes`, or `length`.
4. Reject any request file containing `secret_value`, `token`, `credential`, or `private_key` fields.
5. Treat `assets/catalog/secret-factory.v1.json:request_schema` as the parser contract and fail closed on schema/runtime drift.
6. Treat `infisical_network_policy` as the write boundary: HTTPS only, pinned Infisical host only, and no redirect-host value transport.
7. For local generated values, run:
   `python3 the @Bears plugin checkout/scripts/secret_factory.py create <request.json>`
8. For preflight without generation or write, run:
   `python3 the @Bears plugin checkout/scripts/secret_factory.py create <request.json> --dry-run`
9. For provider-owned values, return the handoff packet from:
   `python3 the @Bears plugin checkout/scripts/secret_factory.py plan <request.json>`
10. For cataloged provider-owned Infisical refs, return names-only readiness from:
   `python3 the @Bears plugin checkout/scripts/secret_factory.py handoff-readiness`
11. For refs with `existence_status=documented_unconfirmed`, require operator-confirmed exact ref metadata or safe metadata-only `list_folders` then `list_secret_names` before the blocked task IDs in the catalog.
12. For refs with `existence_status=operator_confirmed_live_ref`, read the exact `provider_api_routing` entry from `assets/catalog/secret-factory.v1.json`; resolve the token only at task time and never print it.

## Allowed local kinds

- `random_base64url`
- `random_hex`
- `random_password`

## Forbidden actions

- Do not ask the user to paste a secret value.
- Do not read Infisical values.
- Do not print generated values.
- Do not store generated values in files.
- Do not pass generated values through command-line arguments.
- Do not log generated values.
- Do not commit generated values.
- Do not create provider-issued API keys, OAuth client secrets, SSH keys, TLS keys, payment credentials, or wallet keys.
- Do not claim live Infisical existence for names-only handoff refs; Secret Factory does not call Infisical read or list endpoints.
- Do not treat a `documented_unconfirmed` ref as live-confirmed.
- Do not invent replacement paths for documented-unconfirmed refs.
- Do not replace the Bears GitLab API route; set scheme `https`, host `bears.gitlab.yandexcloud.net`, and path prefix `/api/v4` for the `gitlab` route. Never set host `gitlab.com`.
- Forbidden: call `list_secrets` for documented-unconfirmed ref confirmation unless the MCP surface has a names-only or exclude-values mode.
- Do not bypass required static safety evidence when Secret Factory work touches manifest text, inventory output, live-tool wording, raw endpoint literals, or secret-discovery paths.
- Enforce `validate_overlay_static_safety_pr_gate` for `raw_endpoint_literal` and `raw_ip_or_cidr_literal` counts across `secret_factory_governance` and `infrastructure_network_governance` planes.
- Automatic evidence owns `python3 scripts/validate_overlay.py --json scan-static-safety --path <repo-relative-file>` for changed files that can carry static endpoint, URI, IP, CIDR, inventory, or live-tool wording; manual execution requires operator approval.

## Validation

- Automatic evidence owns `python3 scripts/subagents_roles.py validate`; manual execution requires operator approval.
- Automatic evidence owns `python3 scripts/secret_factory.py validate`; manual execution requires operator approval.
- Agents may run `python3 scripts/subagents_roles.py route the @Bears plugin checkout/assets/catalog/secret-factory.v1.json`.
- Agents may run `python3 scripts/subagents_roles.py audit the @Bears plugin checkout/assets/catalog/secret-factory.v1.json`.
- Automatic evidence owns `python3 -m unittest tests/test_secret_factory.py tests/test_subagents_roles.py`; manual execution requires operator approval.
- Automatic evidence owns `python3 scripts/validate_overlay.py --json validate --strict-overlay-skills`; manual execution requires operator approval.
