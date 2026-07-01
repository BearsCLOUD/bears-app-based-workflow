# External Review Audit Package — 2026-06-25

## Purpose

This package makes issue state, changelog/release records, and decision records visible from the repository for external review.

It is not runtime evidence and it is not a final closeout proof. It is a repo-visible audit surface that external reviewers can inspect without relying on chat context, agent memory, or ignored `runtime/` files.

## Included artifacts

- `issue-state.md` — current issue-state review requirements and known blocking gaps.
- `changelog.md` — repo-visible change/release-note audit requirements for governed deliveries.
- `decisions.md` — decision ledger requirements and current decisions for this external-review package.
- `audit-index.v1.json` — machine-readable index for the package.

## Required external review chain

Every governed delivery must expose an auditable chain:

```text
GitHub issue state
  -> delivery manifest
  -> decision ledger
  -> changelog or release note
  -> validation proof
  -> bears_doctor closeout summary
```

A delivery claim is not reviewable when any link in that chain is absent, stale, or stored only in ignored runtime files.

## Current review status

Status: `external_review_blocked`

Reason: issue-state, changelog, and decision records are not yet enforced as first-class closeout surfaces across the delivery workflow.

Known related open issues:

- #404 — solved issue closure after `codex exec` delivery.
- #411 — old open backlog reconciliation.
- #423 — roadmap backlog ingestion and fillability reconciliation.
- #425 — issue state, changelog, and decisions as first-class audit surfaces.

## Safety boundary

This package must not contain raw logs, raw chat, secrets, credentials, environment values, VPN configs, production data, or unredacted runtime payloads.

All evidence here is metadata-only and intended for external audit.
