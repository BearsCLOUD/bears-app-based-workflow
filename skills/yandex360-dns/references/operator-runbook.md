# Yandex 360 DNS Infisical operator runbook

## Purpose

Move `bears.ru` DNS operations to the plugin-owned `yandex360-dns` skill with secrets from Infisical only.

- Owning skill: `/srv/bears/plugins/bears/skills/yandex360-dns`.
- DNS helper: plugin-local scripts under the owning skill.
- Infisical: secret manager used to inject keys at command runtime.
- OAuth token: Yandex access token used by the API client.
- TTL: DNS cache lifetime for one record.

## Secret path and key-name policy

Use this Infisical target only:

- Environment: `prod`.
- Path: `/global/dns/yandex360/bears-ru`.

Required runtime key names:

```text
YANDEX360_DNS_CLIENT_ID
YANDEX360_DNS_CLIENT_SECRET
YANDEX360_DNS_DOMAIN
YANDEX360_DNS_ORG_ID
YANDEX360_DNS_OAUTH_TOKEN
YANDEX360_DNS_API_BASE
YANDEX360_DNS_SCOPE
```

Do not write secret values in docs, chat, Git, Codex config, shell history, command arguments, logs, local env files, or temp files.

## Operator checklist

Run these commands from an operator shell. Do not paste command output that contains account data or secret material into chat or docs.

1. Log in to Infisical CLI and verify the session.

   ```bash
   infisical login
   infisical whoami >/dev/null
   ```

2. Set `INFISICAL_PROJECT_ID` without printing it.

   ```bash
   read -r -s -p "INFISICAL_PROJECT_ID: " INFISICAL_PROJECT_ID; printf '\n'
   export INFISICAL_PROJECT_ID
   test -n "${INFISICAL_PROJECT_ID:?INFISICAL_PROJECT_ID must be set in this shell}"
   ```

3. Run the setup helper dry-run. It prints only key names, target path, and operator action.

   ```bash
   python3 /srv/bears/plugins/bears/skills/yandex360-dns/scripts/infisical_yandex360_setup.py --dry-run
   ```

4. Input secret values interactively in Infisical UI or an operator-approved prompt. Do not pass values in command arguments. The helper does not write temp secret files and does not upload secrets.

5. Run presence-only `env-check` under `infisical run`.

   ```bash
   infisical run --env prod --projectId "$INFISICAL_PROJECT_ID" --path /global/dns/yandex360/bears-ru --domain "${INFISICAL_API_URL:-${INFISICAL_HOST_URL:-https://app.infisical.com}/api}" --silent -- \
     env PYTHONDONTWRITEBYTECODE=1 python3 /srv/bears/plugins/bears/skills/yandex360-dns/scripts/yandex360_dns.py env-check
   ```

6. Run the local cutover validator.

   ```bash
   python3 /srv/bears/plugins/bears/skills/yandex360-dns/scripts/validate_yandex360_dns_cutover.py
   ```

7. List DNS records only after the operator gives an explicit read scope such as: `read-only list bears.ru records through Yandex 360 now`.

   ```bash
   infisical run --env prod --projectId "$INFISICAL_PROJECT_ID" --path /global/dns/yandex360/bears-ru --domain "${INFISICAL_API_URL:-${INFISICAL_HOST_URL:-https://app.infisical.com}/api}" --silent -- \
     env PYTHONDONTWRITEBYTECODE=1 python3 /srv/bears/plugins/bears/skills/yandex360-dns/scripts/yandex360_dns.py list
   ```

## DNS write policy

DNS create, delete, and replace are production changes. This local helper does not apply them.

- Use `create` and `delete` commands only to produce dry-run review packets.
- Save or quote only non-secret dry-run evidence: record type, record name, target domain, TTL, and intended action.
- A live DNS change requires dry-run evidence, explicit operator confirmation for the exact record payload, and no raw secret output.
- There is no local apply flag in this helper.
- Do not print raw secret values before, during, or after any command.
- Route any approved production DNS change to a separately approved production path outside this helper.

## Legacy safety

`/srv/bears/.env` and other local env files are refused for this workflow.

- Do not read `/srv/bears/.env`.
- Do not use `/srv/bears/.env` as proof that DNS keys exist.
- Do not copy values from any local env file.
- If a task asks to use `/srv/bears/.env` or another local env file, stop that step and route the operator back to Infisical runtime injection.

## Handoff to the network lane

`/srv/bears/dev/infrastructure/network` owns network documentation status only.

- Keep the global/local split there.
- Keep DNS requirement status there.
- Keep DNS implementation, scripts, write policy, and operator flow in this plugin-owned skill.
- Network lane docs must point here instead of duplicating secret handling details.

## Concrete failure handling

- Missing Infisical login: stop DNS setup, run `infisical login`, then `infisical whoami >/dev/null`; do not paste identity output.
- Missing `INFISICAL_PROJECT_ID`: stop DNS setup, set it with the hidden `read -r -s` command above, then rerun the failed command.
- Missing required keys: run the helper dry-run, then enter values directly in Infisical. If `YANDEX360_DNS_ORG_ID` is unknown, get it from Yandex 360 admin UI or a separately approved `orgs` read after token injection.
- Live write requested without approval: refuse local apply, produce a dry-run packet, and require explicit confirmation for the exact record payload before any separate production path is used.
