# Bears doctor closeout validator

`bears_doctor.py` is the single closeout validator for the machine-first `@Bears` plugin workflow.

## Commands

```bash
python3 scripts/bears_doctor.py validate
python3 scripts/bears_doctor.py validate-closeout --from-git <range> --json
python3 scripts/bears_doctor.py validate-node --workflow-tree <path> --node-id <id> --json
python3 scripts/bears_doctor.py emit-summary --from-git <range> --json
```

## Closeout result

The command emits `bears-doctor-result.v1` JSON with changed files, checks, failed checks, warnings, blockers, required next actions, sanitized summary, and `closeout_summary`.

`closeout_summary` is the detailed final-report source. It records delivery id, final SHA, issue refs, scope, affected range, expected evidence paths, changelog linkage, known blockers, validation result, doctor result, debt status, and cleanup status. User replies may stay compact after this packet is written.

The first canonical delivery id is `bears-governance-kernel-v1`. `bears_doctor` requires it in the commit closeout metadata and mirrors it into the changelog linkage object.

## Required checks

The first kernel requires workflow tree validation, canonical plugin worktree proof, artifact registry validation, decision ledger validation, release notes validation, authority map validation, route/audit role checks, test-selection validation, commit closeout metadata, exact local commit proof, workspace hygiene, tracked-runtime-file guard, and unresolved blocker guard.

Current integrated components:

- #386 workspace hygiene
- #384 release notes gate
- #385 authority map
- #395 issue autostart control plane
- #391 commit-bound closeout metadata, delivery id, and detailed final-report summary

## Safety rules

The result must not include raw logs, secrets, credentials, env values, raw chat, raw VPN config, or production data. Any forbidden marker makes validation fail.

## Canonical worktree guard

`canonical_plugin_worktree` blocks closeout when the script is executed from a hidden temporary checkout, when `git rev-parse --show-toplevel` does not resolve to `/srv/bears/plugins/bears`, or when `core.worktree` redirects the canonical checkout elsewhere. This catches stale submodule/worktree wiring before the final report.
