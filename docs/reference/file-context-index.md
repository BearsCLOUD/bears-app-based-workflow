# File context index

The file-context index is a bounded JSON memory layer for goal orchestration. It is not LLM memory and not markdown notes.

## Canonical files

- Policy: `assets/catalog/file-context-policy.v1.json`.
- Index: `assets/file-context/index.v1.json`.
- Record schema: `assets/schemas/file-context.v1.schema.json`.
- Index schema: `assets/schemas/file-context-index.v1.schema.json`.
- Refresh result schema: `assets/schemas/file-context-refresh.v1.schema.json`.

## Rules

- Select context with `python3 scripts/file_context_index.py select --path <path> --role <role_id> --json` before reading a governed file.
- Active records must match the current `source_hash`.
- Stale records block write-scoped execution and must be refreshed or moved to manual review.
- Python records extract functions, classes, and imports through AST parsing.
- JSON records expose schema, commands, owner role, and authority topic when available.
- Deleted-file records are removed with `python3 scripts/file_context_refresh.py gc --json`.

## Validation

```bash
python3 scripts/file_context_index.py validate
python3 scripts/file_context_index.py stale --json
python3 scripts/file_context_index.py doctor --json
python3 -m unittest tests/test_file_context_index.py
```

## Module split note

`file_context_index.py` currently owns selector, stale, doctor, and refresh helpers in one script to keep issue #429 atomic. If future changes add another command family, split pure extraction and index mutation into `scripts/file_context_core.py`, then keep `scripts/file_context_index.py` as the CLI wrapper. Current validation evidence: `python3 -m unittest tests/test_file_context_index.py`.
