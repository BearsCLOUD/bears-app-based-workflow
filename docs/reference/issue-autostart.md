# Issue Autostart

Issue autostart discovers, enqueues, leases, runs, watches, pauses, resumes, drains, and cancels safe GitHub issue automation work.

The canonical validator is:

```bash
python3 scripts/issue_autostart.py validate
```

Autostart may enqueue only `safe_auto` issue work and must create a lease before Codex Exec work starts.
