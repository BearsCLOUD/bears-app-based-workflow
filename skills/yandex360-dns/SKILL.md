---
name: "yandex360-dns"
description: "Read-only and dry-run helper for bears.ru DNS records through the Yandex 360 for Business API. Use when listing records, checking runtime key presence, generating an OAuth authorize URL, or preparing DNS change review packets without exposing secrets."
metadata:
  short-description: "Read-only Yandex 360 DNS helper"
---

# Yandex 360 DNS

Use this plugin-local skill for `bears.ru` DNS inspection and dry-run change packets when records are managed through Yandex 360 for Business.

## Safety rules

- Never print OAuth tokens, client secrets, `.env` values, raw secrets, browser callback fragments, or Infisical secret values.
- Local env file loading is disabled. Do not use `--env`, `.env`, temp env files, or migration env files.
- Local credential persistence is disabled. There is no `save-token` or `exchange-code` command.
- Live DNS mutation apply is disabled. `create` and `delete` produce dry-run packets only; there is no `--yes` apply flag.
- Use Infisical or another operator-approved secret manager for storage. The helper may give key names and target path only.
- `OAuth token`: access token sent in the `Authorization: OAuth ...` header.
- `TTL`: DNS cache lifetime for one record.

## Files and runtime environment

- Canonical skill path: `/srv/bears/plugins/bears/skills/yandex360-dns`.
- DNS helper: `/srv/bears/plugins/bears/skills/yandex360-dns/scripts/yandex360_dns.py`.
- Infisical setup helper: `/srv/bears/plugins/bears/skills/yandex360-dns/scripts/infisical_yandex360_setup.py`.
- Presence-only cutover validator: `/srv/bears/plugins/bears/skills/yandex360-dns/scripts/validate_yandex360_dns_cutover.py`.
- API reference: `/srv/bears/plugins/bears/skills/yandex360-dns/references/api.md`.
- Operator runbook: `/srv/bears/plugins/bears/skills/yandex360-dns/references/operator-runbook.md`.
- Canonical secret store: Infisical, injected at runtime through `/srv/bears/control-plane/infisical/infisical_mcp_stdio.sh` or an approved shell environment.
- Recommended Infisical path: `/global/dns/yandex360/bears-ru`, environment `prod`.
- Infisical folder names allow alphanumeric characters, dashes, and underscores; use `bears-ru`, not `bears.ru`, as the folder segment.
- Default commands read only runtime environment variables injected by Infisical or an operator-prepared shell.

Required runtime keys:

```dotenv
YANDEX360_DNS_CLIENT_ID=...
YANDEX360_DNS_CLIENT_SECRET=...
YANDEX360_DNS_DOMAIN=bears.ru
YANDEX360_DNS_ORG_ID=...
YANDEX360_DNS_OAUTH_TOKEN=...
YANDEX360_DNS_API_BASE=https://api360.yandex.net
YANDEX360_DNS_SCOPE=directory:read_organization directory:manage_dns
```

`YANDEX360_DNS_ORG_ID` and `YANDEX360_DNS_OAUTH_TOKEN` may be absent until the operator stores the values in Infisical.

## Workflow

1. Load `references/api.md` only when endpoint fields, auth flow, or troubleshooting details are needed.
2. Check key presence only, not values:
   ```bash
   python3 /srv/bears/plugins/bears/skills/yandex360-dns/scripts/yandex360_dns.py env-check
   ```
3. Validate local guardrails without reading or printing secret values:
   ```bash
   python3 /srv/bears/plugins/bears/skills/yandex360-dns/scripts/validate_yandex360_dns_cutover.py
   ```
4. Verify Infisical runtime injection only from an operator-prepared shell where Infisical auth env is already injected:
   ```bash
   infisical run --env prod --projectId "$INFISICAL_PROJECT_ID" --path /global/dns/yandex360/bears-ru --domain "${INFISICAL_API_URL:-${INFISICAL_HOST_URL:-https://app.infisical.com}/api}" --silent -- \
     env PYTHONDONTWRITEBYTECODE=1 python3 /srv/bears/plugins/bears/skills/yandex360-dns/scripts/yandex360_dns.py env-check
   ```
   This prints presence only. Do not paste environment values into chat or docs.
5. If no token exists, generate an authorization URL:
   ```bash
   python3 /srv/bears/plugins/bears/skills/yandex360-dns/scripts/yandex360_dns.py auth-url --response-type token
   ```
   The operator stores the token directly in Infisical path `/global/dns/yandex360/bears-ru`. Do not paste the token into chat.
6. To prepare secret setup instructions without writing files:
   ```bash
   python3 /srv/bears/plugins/bears/skills/yandex360-dns/scripts/infisical_yandex360_setup.py --dry-run
   ```
   The helper prints key names, target path, and operator action only.
7. If no organization id exists, list organizations after runtime token injection:
   ```bash
   python3 /srv/bears/plugins/bears/skills/yandex360-dns/scripts/yandex360_dns.py orgs
   ```
   Store the selected id directly in Infisical. Do not commit it to Git or Codex config.
8. List records before any planned change:
   ```bash
   python3 /srv/bears/plugins/bears/skills/yandex360-dns/scripts/yandex360_dns.py list
   ```
9. Prepare a create review packet. This never applies the change:
   ```bash
   python3 /srv/bears/plugins/bears/skills/yandex360-dns/scripts/yandex360_dns.py create --type TXT --name test --text value --ttl 21600 --dry-run
   ```
10. Prepare a delete review packet. This never applies the change:
   ```bash
   python3 /srv/bears/plugins/bears/skills/yandex360-dns/scripts/yandex360_dns.py delete --record-id 123 --dry-run
   ```

## Record payload hints

Use `--field key=value` or `--data-json '{...}'` when a record type needs fields not covered by shortcut flags.

Common fields:

- A/AAAA: `--address`.
- TXT: `--text`.
- CNAME/NS: `--target`.
- MX: `--exchange` and `--preference`.
- SRV: `--priority`, `--weight`, `--port`, and `--target`.
- CAA: `--flag`, `--tag`, and `--value`.

If `orgs` returns `403`, check that the token scope includes `directory:read_organization`. If `list` returns `403`, check `directory:manage_dns` and the account rights in the Yandex 360 organization.
