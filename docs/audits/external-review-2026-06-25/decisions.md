# Decision Audit Artifact — 2026-06-25

## Purpose

This artifact records the decision-ledger expectations required for external review of @Bears governed deliveries.

A decision is not auditable when it exists only in chat, agent memory, a commit message, or an ignored runtime packet.

## Review rule

Any governed delivery that changes policy, workflow, role routing, hooks, schemas, validators, delivery gates, issue closeout, autostart, release gates, or manifest capabilities must include a repo-visible decision record.

## Required decision fields

Each decision record must include:

- decision id;
- date;
- owner issue;
- delivery id;
- affected paths or surfaces;
- decision;
- rationale;
- alternatives considered;
- validation impact;
- rollback or remediation path;
- safety boundary;
- status.

## Current package decisions

### D-2026-06-25-EXT-001 — External review requires repo-visible artifacts

Decision: external reviewers must be able to inspect issue state, changelog/release notes, and decision records from committed repository artifacts.

Rationale: ignored runtime files and chat context are not durable external review surfaces.

Status: accepted.

### D-2026-06-25-EXT-002 — Runtime evidence is not enough for final review

Decision: runtime evidence may support validation, but it must be summarized by repo-visible audit artifacts before a delivery can be treated as externally reviewable.

Rationale: `runtime/` is ignored and may not be available to external reviewers.

Status: accepted.

### D-2026-06-25-EXT-003 — Raw logs remain forbidden

Decision: external review artifacts must remain metadata-only and must not include raw logs, raw chat, secrets, credentials, environment values, VPN configs, or production data.

Rationale: external audit must not create a data-exposure path.

Status: accepted.

## Failure conditions

External review fails when:

- a governance or workflow behavior change has no decision record;
- the decision record does not name the owner issue;
- the decision record does not name affected surfaces;
- the decision record does not include validation impact;
- the decision record lacks rollback or remediation path;
- the decision record exists only in chat or ignored runtime files.
