# Operator Telegram Auth Interface

## Scope

This reference describes local operator interfaces for creating a Telegram user session through Infisical-injected API credentials.

Read `telegram-infisical-kubernetes-map.md` first for concrete Infisical paths, Kubernetes Secret names, service names, session paths, and safe probe commands.

## Hard rules

- Operator auth commands must not print raw Infisical values, Telegram codes, 2FA passwords, tokens, chat IDs, QR login URLs, or session payloads.
- Agents must not log in to a personal Telegram account unless the operator explicitly approves the login action in the current task.
- Do not store Telegram 2FA passwords, login codes, QR login tokens, or session files in Infisical through this interface.
- Do not host Telegram QR login through a public route unless the operator explicitly approves a short-lived token-gated web flow. Never expose the raw `tg://login` URL.
- Prefer local terminal QR. Use web QR only when the operator cannot scan terminal output.
- `tg.env` may contain `TG_LOGIN` for local operator convenience. `TG_PASS`, `TELEGRAM_PASSWORD`, and `TWO_FA_PASSWORD` are ignored and never passed to Telegram.
- Tests must use mock JSON and local path fixtures only.

## Kubernetes Secret QR command

Use this path when the Kubernetes `ExternalSecret` has already materialized `bears-platform-telegram-tdlib-runtime`. It does not need local `INFISICAL_PROJECT_ID`; Kubernetes resolves Infisical through `ClusterSecretStore infisical-bears`.

```bash
cd /srv/bears
python3 plugins/bears/skills/bears-telegram-workflow/scripts/operator_telethon_kube_auth.py preflight-kube
python3 plugins/bears/skills/bears-telegram-workflow/scripts/operator_telethon_kube_auth.py run-qr-kube
```

The command reads `api-id` and `api-hash` from Kubernetes Secret `bears-platform-telegram-tdlib-runtime` in namespace `bears-platform-telegram-dev`. It must not print secret values. It also writes the short-lived QR image to `/srv/bears/.secrets/telegram-sessions/operator-telethon-kube-qr.png` with mode `0600`.

If host networking cannot reach Telegram MTProto directly, set `TG_PROXY_URL` before `run-qr-kube`. Supported schemes are `socks5://host:port`, `socks5h://host:port`, and `http://host:port`. The proxy URL must not be printed in logs.

## Kubernetes Secret web QR command

Use this when the operator cannot scan the terminal QR. The temporary web page is token-gated, serves `/qr.png`, auto-refreshes the Telegram QR before expiry, and must not expose the raw `tg://login` URL.

```bash
cd /srv/bears
python3 plugins/bears/skills/bears-telegram-workflow/scripts/operator_telethon_kube_web_auth.py run-web-kube
```

After completion or failure, stop the web process or tunnel and delete `/srv/bears/.secrets/telegram-sessions/operator-telethon-kube-qr.png`.

## QR operator command

```bash
cd /srv/bears
python3 plugins/bears/skills/bears-telegram-workflow/scripts/operator_telethon_auth.py doctor
python3 plugins/bears/skills/bears-telegram-workflow/scripts/operator_telethon_auth.py preflight
python3 plugins/bears/skills/bears-telegram-workflow/scripts/operator_telethon_auth.py run-qr
```

The QR flow reads `api-id` and `api-hash` from `/kubernetes/bears-platform-telegram/tdlib` in Infisical. Run `preflight` first. If Infisical needs an explicit project id, set `INFISICAL_PROJECT_ID` in the shell or in `tg.env` before running `run-qr`.

## Optional tg.env

```bash
INFISICAL_PROJECT_ID=<project-id>
TG_LOGIN=+10000000000
```

`TG_PASS` is ignored if present. Two-factor password must be typed only into the hidden terminal prompt after QR scan when Telegram requires it.

## TDLib/tglib fallback command

```bash
cd /srv/bears
python3 plugins/bears/skills/bears-telegram-workflow/scripts/operator_tglib_auth.py doctor
python3 plugins/bears/skills/bears-telegram-workflow/scripts/operator_tglib_auth.py run
```

Use the Telethon QR command first. Keep the TDLib/tglib path as a fallback for phone-code login.
