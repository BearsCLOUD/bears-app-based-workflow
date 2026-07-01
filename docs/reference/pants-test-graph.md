# Pants Test Graph Pilot

The pilot maps changed files to a small Pants-shaped test graph.
It does not replace `scripts/test_selection.py`; it checks a bounded subset and compares results against that authority.

## Authority

- `assets/catalog/pants-test-graph.v1.json` owns the pilot routes.
- `assets/schemas/pants-test-graph.v1.schema.json` validates the catalog.
- `scripts/pants_test_graph.py` is the deterministic adapter.
- `scripts/test_selection.py` stays the comparison baseline.

## Command surface

```text
python3 scripts/pants_test_graph.py validate
python3 scripts/pants_test_graph.py impacted --from-git <range> --json
```

## Route model

- `scripts/*.py` routes to `tests/test_pants_test_graph.py`.
- `tests/test_*.py` routes to `tests/test_pants_test_graph.py`.
- `assets/catalog/*.json` routes to `tests/test_pants_test_graph.py`.
- `assets/schemas/*.json` routes to `tests/test_pants_test_graph.py`.
- `BUILD`, `pants.toml`, this doc, and the pilot catalog/schema route to `tests/test_pants_test_graph.py`.
- `docs/audits/external-review-2026-06-25/*` and the external-review audit artifacts route to the external-review gate tests.

## Exit rules

- `validate` prints stable JSON and fails when the catalog or references drift.
- `impacted` prints stable JSON for the git range.
- Unknown paths fail the pilot instead of pretending full coverage.
