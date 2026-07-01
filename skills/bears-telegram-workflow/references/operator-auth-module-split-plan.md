# Operator Auth Module Split Plan

## Scope

This plan limits growth of Telegram operator auth helpers. It is required because `operator_telethon_kube_web_auth.py` exceeds the 400-line Python maintenance threshold.

## Current long files

| File | Current boundary | Split target |
| --- | --- | --- |
| `scripts/operator_telethon_kube_web_auth.py` | Web server, QR state, Telethon web login orchestration, CLI parent/child wiring | Split into web server adapter, QR login application flow, and CLI entrypoint |
| `scripts/operator_telethon_kube_auth.py` | Kubernetes Secret access, proxy parsing, QR login, CLI parent/child wiring | Keep under review; split only if it crosses 400 lines |

## Target modules

```text
scripts/operator_auth_common.py
scripts/operator_auth_kube.py
scripts/operator_auth_qr.py
scripts/operator_auth_web.py
scripts/operator_telethon_kube_auth.py
scripts/operator_telethon_kube_web_auth.py
```

Rules:

- `operator_auth_common.py`: session paths, file modes, redaction helpers, dependency constants.
- `operator_auth_kube.py`: Kubernetes Secret key presence and value loading.
- `operator_auth_qr.py`: Telethon QR login flow and 2FA handling.
- `operator_auth_web.py`: token-gated HTTP server and QR PNG rendering.
- CLI files stay thin and only parse args, run preflight, and call application functions.
- Tests must stay behavior-based and must not use real secret values.

## Validation after split

```bash
cd /srv/bears/plugins/bears
python3 -m py_compile \
  skills/bears-telegram-workflow/scripts/operator_telethon_auth.py \
  skills/bears-telegram-workflow/scripts/operator_telethon_kube_auth.py \
  skills/bears-telegram-workflow/scripts/operator_telethon_kube_web_auth.py \
  skills/bears-telegram-workflow/scripts/operator_tglib_auth.py
python3 -m pytest -q \
  skills/bears-telegram-workflow/tests/test_operator_telethon_auth.py \
  skills/bears-telegram-workflow/tests/test_operator_telethon_kube_auth.py \
  skills/bears-telegram-workflow/tests/test_operator_telethon_kube_web_auth.py \
  skills/bears-telegram-workflow/tests/test_operator_tglib_auth.py
```
