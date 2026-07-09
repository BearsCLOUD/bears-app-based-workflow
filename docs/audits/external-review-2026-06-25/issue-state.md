# Issue-State Audit Artifact — 2026-06-25

## Purpose

This artifact records the issue-state expectations required for external review of @Bears governed deliveries.

The source of truth for issue status is GitHub issue state plus repo-visible delivery artifacts. Agent claims, chat summaries, and ignored runtime files are not sufficient.

## Review rule

A governed delivery is not externally reviewable unless each covered issue is represented in a repo-visible artifact with:

- issue number;
- repository;
- GitHub state;
- delivery id;
- closeout classification;
- proof commit or proof path;
- action taken or action blocked;
- reason.

## Required closeout classifications

Allowed classifications:

```text
closed
partial
superseded
out_of_scope
blocked
manual_review
```

Rules:

- `closed` requires exact validation proof and a closeout comment.
- `superseded` requires exact proof of the replacement delivery or issue.
- `partial`, `blocked`, `manual_review`, and `out_of_scope` must remain open unless explicitly reclassified later.
- Solved-but-open issues must be blocking closeout debt.

## Current known blockers

- #404 is open and defines the missing solved-issue closeout contract.
- #411 is open and requires old backlog reconciliation after #404.
- #423 is open and requires backlog ingestion/fillability for roadmap-first execution.
- #425 is open and requires issue state, changelog, and decisions to become first-class audit surfaces.

## Minimum required commands

The repository should expose commands equivalent to:

```text
python3 scripts/issue_state_reconciler.py solved-open --delivery-id <id> --json
python3 scripts/issue_closeout.py close-covered --delivery-id <id> --dry-run
python3 scripts/bears_doctor.py validate-closeout --from-git <range> --json
```

## External review failure condition

External review fails when a delivery says `done` but any of these conditions hold:

- a covered issue is absent from the delivery manifest;
- a solved covered issue remains open;
- a partial or blocked issue is auto-closed;
- closeout lacks exact validation proof;
- closeout lacks `bears_doctor` proof;
- issue classification exists only in chat or ignored runtime files.

## Safety boundary

Do not copy raw issue discussions, raw logs, raw chat, secrets, credentials, environment values, VPN configs, or production data into this artifact.
