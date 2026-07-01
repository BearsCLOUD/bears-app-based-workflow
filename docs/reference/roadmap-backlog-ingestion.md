# Roadmap backlog ingestion

`roadmap_backlog_ingest.py` converts open GitHub issues into bounded roadmap evidence.

Commands:

```bash
python3 scripts/roadmap_backlog_ingest.py validate
python3 scripts/roadmap_backlog_ingest.py scan --repo BearsCLOUD/bears-codex-workflow-plugin --json
python3 scripts/roadmap_backlog_ingest.py propose --repo BearsCLOUD/bears-codex-workflow-plugin --json
python3 scripts/roadmap_backlog_ingest.py apply --packet <path>
python3 scripts/roadmap_backlog_ingest.py fillability --json
```

Rules:

- `scan`, `propose`, and `fillability` are read-only.
- `apply` mutates `assets/catalog/workflow-roadmap.v1.json` only from a schema-valid packet.
- Proposed nodes preserve issue number, labels, risk class, source URL, required files, acceptance criteria, owner role, and autostart policy.
- Duplicate issue-node mappings and duplicate output paths are blockers.
- Default generated backlog nodes are `manual_review` unless source labels explicitly allow safe autostart.
- Python helpers read the active roadmap path at call time, so tests can inject a temporary roadmap file.
