# Process-mining feedback

This surface closes #446.

## Data rule
The miner reads bounded JSON or JSONL runtime events and normalizes them into compact trace events. It rejects forbidden raw prompt, raw chat, raw log, secret, credential, environment, and production markers.

## Commands
- `scripts/process_mining.py validate` validates the policy and schemas.
- `scripts/process_mining.py ingest --paths <glob> --json` creates bounded trace events.
- `scripts/process_mining.py compare --model <path> --events <path> --json` emits non-fitting traces, validator gaps, and context-budget candidates.
- `scripts/workflow_improvement_candidates.py generate --report <path> --json` creates deduped improvement candidates.
- `scripts/workflow_improvement_candidates.py create-issues --candidates <path> --dry-run --json` reports issue creation without writing.
- `scripts/process_mining.py doctor --json` reports health for closeout.
