# Workspace hygiene

`workspace_hygiene.py` classifies ignored and generated local artifacts and emits safe cleanup plans.

## Commands

```bash
python3 scripts/workspace_hygiene.py validate
python3 scripts/workspace_hygiene.py scan --json
python3 scripts/workspace_hygiene.py plan-cleanup --json
python3 scripts/workspace_hygiene.py cleanup --apply --allow-path <path>
python3 scripts/workspace_hygiene.py check-stale --json
```

## Safety rules

- Cleanup is dry-run unless `--apply` is passed.
- `cleanup --apply` needs an exact `--allow-path`.
- Cleanup refuses tracked durable files.
- Cleanup refuses secrets, env files, credentials, raw logs, raw chat, raw VPN config, and production data.
- Runtime proof is classified separately from durable tracked artifacts.

## Closeout routing

`bears_doctor.py` calls the hygiene validator after #386. Stale files become warnings unless the file is tracked, unsafe, or treated as current proof.
