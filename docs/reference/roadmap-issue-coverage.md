# Roadmap issue coverage and priority freshness gate

## Purpose

`scripts/roadmap_issue_coverage.py` adds a local-only gate for issue freshness. It checks metadata-only issue rows against these source-of-truth catalogs:

- `assets/catalog/workflow-roadmap.v1.json`
- `assets/catalog/issue-execution-priority.v1.json`

The gate does not read or persist raw issue bodies, raw logs, prompts, secrets, or production data.

## Commands

```text
python3 scripts/roadmap_issue_coverage.py validate --json
python3 scripts/roadmap_issue_coverage.py check-roadmap --json
python3 scripts/roadmap_issue_coverage.py check-priority --json
python3 scripts/roadmap_issue_coverage.py doctor --json
```

`validate` checks schemas, catalogs, command entries, source paths, and local fixtures. `check-roadmap` reports open issues without workflow-roadmap nodes. `check-priority` reports open priority issues missing from priority waves. `doctor` runs both checks.

## Metadata input

Use `--issues-json <path>` for local fixture input. The accepted row fields are:

```json
{
  "number": 515,
  "issue_ref": "#515",
  "title": "P0: Add workflow roadmap and issue-priority freshness gate",
  "state": "OPEN",
  "url": "https://github.com/BearsCLOUD/bears_plugin/issues/515",
  "labels": ["bears:auto-start", "scope:bears-plugin"],
  "updated_at": "2026-06-27T00:00:00Z",
  "priority": "P0"
}
```

Do not include `body`, `raw_body`, `raw_log`, `prompt`, `secret`, `token`, `credential`, or `private_key` fields.

## Default status

The default catalogs intentionally record the issue #515 freshness snapshot for newer P0 Knowledge Orchestrator issues. Until `workflow-roadmap.v1.json` and `issue-execution-priority.v1.json` are refreshed, `doctor --json` reports `fail` with `missing_roadmap_issues` and `missing_priority_issues`.

## Closeout integration still needed

This slice does not edit `workflow_roadmap.py`, `issue_autostart.py`, `bears_doctor.py`, or existing autostart catalogs. Wire this gate into those entrypoints in a later scoped change before using it as blocking closeout evidence.
