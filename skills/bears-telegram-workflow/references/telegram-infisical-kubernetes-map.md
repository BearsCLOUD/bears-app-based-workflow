# Telegram Infisical and Kubernetes Map

## Scope

This reference tells Bears agents where Telegram credentials, Kubernetes objects, and operator auth helpers live. It is a location map, not a permission grant.

## Hard safety rules

- Do not print Infisical values, Kubernetes Secret values, bot tokens, callback keys, Telegram login codes, 2FA passwords, raw `tg://login` URLs, session bytes, or private chat data.
- Prefer presence checks over value reads. Read Secret values only inside the operator auth helper process that needs them.
- Do not store Telegram 2FA passwords, login codes, QR login URLs, or user session files in Git or Infisical.
- Web QR is allowed only after explicit operator approval, must be token-gated, short-lived, and must not expose the raw Telegram login URL.
- After QR auth, stop any public tunnel, delete QR images, and keep the session file mode at `0600`.

## Infisical source paths

Kubernetes resolves Infisical through `ClusterSecretStore infisical-bears`; agents normally should not call Infisical directly when the Kubernetes Secret already exists.

| Purpose | Infisical remote key | Kubernetes Secret | Secret key |
| --- | --- | --- | --- |
| TDLib API id | `/kubernetes/bears-platform-telegram/tdlib/api-id` | `bears-platform-telegram-tdlib-runtime` | `api-id` |
| TDLib API hash | `/kubernetes/bears-platform-telegram/tdlib/api-hash` | `bears-platform-telegram-tdlib-runtime` | `api-hash` |
| TDLib encryption key | `/kubernetes/bears-platform-telegram/tdlib/encryption-key` | `bears-platform-telegram-tdlib-runtime` | `encryption-key` |
| Bot API server API id | `/kubernetes/bears-platform-telegram/bot-api/api-id` | `bears-platform-telegram-bot-api-runtime` | `api-id` |
| Bot API server API hash | `/kubernetes/bears-platform-telegram/bot-api/api-hash` | `bears-platform-telegram-bot-api-runtime` | `api-hash` |
| Aiogram default bot token | `/kubernetes/bears-platform-telegram/aiogram/bots/bears-platform-telegram-dev-default/token` | `bears-platform-telegram-aiogram-workers-runtime` | `TELEGRAM_BOT_TOKEN__BEARS_PLATFORM_TELEGRAM_DEV_DEFAULT` |
| Aiogram callback signing | `/kubernetes/bears-platform-telegram/aiogram/callback-signing-key` | `bears-platform-telegram-aiogram-workers-runtime` | `CALLBACK_SIGNING_KEY` |

Authoritative desired-state file:

```text
/srv/bears/kubernetes/manifests/bears-platform-telegram/base/externalsecrets.yaml
```

Local Infisical CLI fallback:

```bash
cd /srv/bears
infisical export --silent --env=dev --path=/kubernetes/bears-platform-telegram/tdlib --format=json
```

If the CLI says a project id is required, set `INFISICAL_PROJECT_ID` in the shell or in `/srv/bears/tg.env`. Do not put secret values into command history.

## Kubernetes runtime locations

Default nonprod namespace:

```text
bears-platform-telegram-dev
```

Runtime Secrets:

```text
bears-platform-telegram-tdlib-runtime
bears-platform-telegram-bot-api-runtime
bears-platform-telegram-aiogram-workers-runtime
```

Runtime Services:

```text
bears-platform-telegram-bot-api
bears-platform-telegram-tdlib-headless
```

Desired-state files:

```text
/srv/bears/kubernetes/manifests/bears-platform-telegram/base/services.yaml
/srv/bears/kubernetes/manifests/bears-platform-telegram/base/tdlib-statefulset.yaml
/srv/bears/kubernetes/manifests/bears-platform-telegram/base/telegram-bot-api-deployment.yaml
/srv/bears/kubernetes/manifests/bears-platform-telegram/base/aiogram-workers-deployment.yaml
```

Local k3d access observed on this host:

```bash
docker exec k3d-bears-platform-telegram-nonprod-server-0 kubectl get ns
```

Safe Secret key presence probe:

```bash
docker exec k3d-bears-platform-telegram-nonprod-server-0 \
  kubectl -n bears-platform-telegram-dev get secret bears-platform-telegram-tdlib-runtime \
  -o 'go-template={{range $k,$v := .data}}{{println $k}}{{end}}'
```

This probe prints key names only, not values.

## Telegram auth surfaces

Bot API server is for bot tokens only. It cannot authorize a personal Telegram user account.

Personal user-account auth uses MTProto through Telethon or TDLib/tglib with `api_id` and `api_hash`.

Operator helper scripts:

```text
/srv/bears/plugins/bears/skills/bears-telegram-workflow/scripts/operator_telethon_kube_auth.py
/srv/bears/plugins/bears/skills/bears-telegram-workflow/scripts/operator_telethon_kube_web_auth.py
/srv/bears/plugins/bears/skills/bears-telegram-workflow/scripts/operator_telethon_auth.py
/srv/bears/plugins/bears/skills/bears-telegram-workflow/scripts/operator_tglib_auth.py
```

Private session directory:

```text
/srv/bears/.secrets/telegram-sessions
```

Current operator session path:

```text
/srv/bears/.secrets/telegram-sessions/operator-telethon-kube.session
```

Required session file mode:

```text
0600
```

## Preferred operator auth order

1. Kubernetes-backed Telethon QR: use when `bears-platform-telegram-tdlib-runtime` exists.
2. Kubernetes-backed web QR: use only when terminal QR is not usable and the operator explicitly approves web exposure.
3. Infisical-backed Telethon QR: use when Kubernetes access is absent but Infisical CLI is configured.
4. TDLib/tglib phone-code fallback: use only when QR flow is not viable.

## Validation commands

```bash
cd /srv/bears
python3 plugins/bears/skills/bears-telegram-workflow/scripts/operator_telethon_kube_auth.py preflight-kube
python3 plugins/bears/skills/bears-telegram-workflow/scripts/operator_telethon_auth.py doctor
```

With the local k3d wrapper:

```bash
cd /srv/bears
mkdir -p /tmp/bears-kubectl-wrapper
cat > /tmp/bears-kubectl-wrapper/kubectl <<'SH'
#!/bin/sh
exec docker exec k3d-bears-platform-telegram-nonprod-server-0 kubectl "$@"
SH
chmod 700 /tmp/bears-kubectl-wrapper/kubectl
PATH=/tmp/bears-kubectl-wrapper:/srv/bears/.tmp/bpl-telegram-tools:$PATH \
  python3 plugins/bears/skills/bears-telegram-workflow/scripts/operator_telethon_kube_auth.py preflight-kube
```
