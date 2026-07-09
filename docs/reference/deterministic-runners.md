# Deterministic Runners

Deterministic runners execute repeatable procedures from strict JSON packets. Agents prepare or review packets; runners execute bounded commands and write evidence under `runtime/`.

## Authority

- `assets/catalog/deterministic-runners.v1.json` lists runner ids, scripts, schemas, and evidence paths.
- `assets/schemas/git-workflow-runner-packet.v1.schema.json` gates git workflow checks.
- `assets/schemas/validation-runner-packet.v1.schema.json` gates validation job execution.
- `assets/schemas/cache-sync-runner-packet.v1.schema.json` gates plugin cache sync verification.
- `assets/schemas/evidence-compaction-packet.v1.schema.json` gates bounded evidence summaries.

## Runner commands

- `python3 scripts/git_workflow_runner.py validate`
- `python3 scripts/git_workflow_runner.py run --packet <packet.json>`
- `python3 scripts/validation_job_runner.py validate`
- `python3 scripts/validation_job_runner.py run --packet <packet.json>`
- `python3 scripts/cache_sync_runner.py validate`
- `python3 scripts/cache_sync_runner.py run --packet <packet.json>`
- `python3 scripts/evidence_compactor.py validate`
- `python3 scripts/evidence_compactor.py run --packet <packet.json>`

## Boundaries

Runners fail closed on unsupported packet fields. Runner packets and evidence must not include secrets, credentials, environment values, private chats, unrestricted diagnostics, VPN config, or production data.

`git_workflow_runner.py` checks branch, start SHA, staged-file ownership, and force-push prohibition.

`validation_job_runner.py` delegates to the async validation worker and accepts only allowlisted validator ids.

`cache_sync_runner.py` requires exact commit validation pass before cache verification.

`evidence_compactor.py` reads bounded state packets only and emits compact parent-agent evidence.
