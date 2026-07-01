# Commit closeout

`commit-closeout` is the #391 contract for short `/goal` prompts and detailed machine closeout.

## Required commit metadata

Every governance closeout commit records these body lines:

- `Issue: #391` or the owning issue list.
- `Delivery-Id: bears-governance-kernel-v1`.
- `Scope: machine-first-execution-kernel`.
- `Affected-Range: HEAD^..HEAD` for the single incremental commit, or a concrete range when closing a chain.
- `Evidence: runtime/local-commit-validation/<commit_sha>.json`.
- `Evidence: runtime/plugin-cache-sync/plugin-cache-sync-state.v1.json`.
- `Changelog: release-note-gate:#384 delivery_id:bears-governance-kernel-v1` until the #384 release-note gate owns the final decision.
- `Blockers: none` or a short blocker id.

`<commit_sha>` stays a template in the commit. The exact SHA is written after commit by local validation and consumed by plugin cache sync.

## Runtime authority

`runtime/local-commit-validation/<sha>.json` is the exact-SHA validation proof. `runtime/plugin-cache-sync/plugin-cache-sync-state.v1.json` is the pushed-plugin closeout proof and must record `delivery_complete=true` plus effective hooks proof for the same SHA.

The canonical first delivery id is `bears-governance-kernel-v1`. It is required in commit metadata, `closeout_summary.delivery_id`, and `closeout_summary.changelog.delivery_id`.

## Commands

```bash
python3 scripts/commit_closeout.py validate
python3 scripts/commit_closeout.py check-message --commit HEAD --json
python3 scripts/commit_closeout.py validate-runtime --commit <sha> --json
python3 scripts/plugin_cache_sync.py sync-once --commit-sha <sha>
```

Final user replies may stay compact when exact LCV and plugin cache sync proof paths are cited.
