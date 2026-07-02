# Async Validation

Async validation records post-commit validation jobs under `runtime/validation-jobs/<commit_sha>/` and state under `runtime/validation-state/<commit_sha>/validation-state.v1.json`.

The canonical validator is:

```bash
python3 scripts/validation_worker.py validate
```

Worker output is metadata-only. It must not include secrets, raw logs, private chats, raw VPN configs, or production data.
