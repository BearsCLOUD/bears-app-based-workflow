# Sequential Codex Exec

Sequential Codex Exec splits issue work into finite role steps with bounded prompts, step outputs, failure classes, dirty-scope checks, resume packets, and abort packets.

The canonical validator is:

```bash
python3 scripts/sequential_codex_exec.py validate
```

The command adapter source is `assets/catalog/codex-exec-adapter.v1.json`.
