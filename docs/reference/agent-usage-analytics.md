# Agent usage analytics

This surface closes #419.

## Data rule
Store only compact counters: role id, executor id, delivery id, commit sha, token estimates, context surface ids, status, and evidence paths. Do not store raw prompts, raw chat, raw logs, secrets, credentials, environment values, private chats, or production data.

## Commands
- `scripts/agent_usage.py record --event <path>` validates and appends one compact event.
- `scripts/agent_usage.py summarize --delivery-id <id> --json` reports delivery totals by executor, role, and context surface.
- `scripts/commit_usage_ledger.py build --commit <sha> --json` builds a per-commit ledger.
- `scripts/commit_usage_ledger.py diff --base <sha> --head <sha> --json` flags token regressions.
- `scripts/commit_usage_ledger.py doctor --json` validates the policy surface.

## Closeout
`bears_doctor` must include the commit usage ledger gate. Blocking output is limited to status, summary, and evidence path names.
