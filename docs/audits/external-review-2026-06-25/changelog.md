# Changelog Audit Artifact — 2026-06-25

## Purpose

This artifact records the changelog and release-note expectations required for external review of @Bears governed deliveries.

The changelog must be repo-visible and auditable. It must not exist only in a PR body, commit message, chat summary, or ignored runtime packet.

## Review rule

A governed delivery that changes behavior must have a repo-visible changelog or release-note entry before closeout.

Behavior-changing surfaces include:

- policy;
- workflow;
- role routing;
- hooks;
- schemas;
- validators;
- delivery gates;
- issue closeout;
- autostart;
- release gates;
- manifest capabilities.

## Required entry fields

Each changelog or release-note entry must include:

- date;
- issue reference;
- delivery id;
- affected surfaces;
- impact;
- validation proof reference;
- `bears_doctor` proof reference when closeout is claimed;
- exemption reason when no changelog is required.

## Current known gap

The repository has release-note gate mechanics, but external review still needs a single closeout summary that links:

```text
issue state -> changelog entry -> decision ledger -> validation proof -> bears_doctor proof
```

If that chain is not present, the delivery remains non-reviewable even when code changes exist.

## Failure conditions

External review fails when:

- behavior changed and no changelog/release-note entry exists;
- changelog entry does not name the delivery id;
- changelog entry does not name the issue reference;
- changelog entry does not name affected surfaces;
- changelog entry claims validation without exact proof;
- changelog entry is stale relative to the latest delivery commit;
- changelog entry exists only in runtime or chat.

## Safety boundary

Changelog entries must be concise metadata. They must not include raw logs, raw chat, secrets, credentials, environment values, VPN configs, or production data.
