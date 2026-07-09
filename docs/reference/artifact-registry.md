# Artifact Registry

The artifact registry records why new plugin files exist before they become tracked files.

## Authority

- `assets/catalog/artifact-registry.v1.json` is the registry.
- `assets/schemas/artifact-registry.v1.schema.json` defines registry records.
- `scripts/artifact_registry.py` validates, registers, checks, and reports records.

## Required tracked fields

Each tracked artifact record declares path, artifact type, lifecycle, owner issue or scope, owner role, allowed writers, validation runner references, changelog requirement, decision reference requirement, and source-of-truth status.

Runtime files declare `git_tracked=false` with lifecycle `runtime_ignored`, `tmp`, `cache`, or `local_proof` and must not be committed.

## Commands

- `python3 scripts/artifact_registry.py validate`
- `python3 scripts/artifact_registry.py register --path <path> --type <type> --issue <owner> --owner-role <role>`
- `python3 scripts/artifact_registry.py register-from-plan --plan <plan.json>`
- `python3 scripts/artifact_registry.py check-path --path <path>`
- `python3 scripts/artifact_registry.py check-added-files --from-git <range>`
- `python3 scripts/artifact_registry.py check-added-files --staged`
- `python3 scripts/artifact_registry.py emit-report --json`

## Commit gate

The shared `@bears` pre-commit runner calls `check-added-files --staged`. Newly added tracked files without registry records fail closed. Existing files before issue #382 are covered by the phased baseline exception.
