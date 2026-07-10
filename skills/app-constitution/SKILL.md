---
name: app-constitution
description: Create or update the first-stage app constitution with exact capability, constraint, gap, decision, and inference records plus required source links. Use when Codex must capture app rules or cited user-message evidence for app research.
---

# App Constitution

## Purpose

Maintain `docs/app-constitution.md` as a compact index of app rules that `app-research` must explain or verify. Use `docs/artifact-contracts.md` as the authority for record fields and artifact format.

## Procedure

1. Read `docs/artifact-contracts.md` and the current app sources.
2. Record the exact app ID or path.
3. Convert each supported statement into one independently changeable record.
4. Link an existing exact rule instead of copying it from `SPEC.md`, research, a plan, or code.
5. Add a section only when it contains at least one record.
6. Send every added or changed record to `app-research` in the closeout.

A constitution file requires at least one exact record in addition to the title and app target. If no record meets the artifact contract, do not create or retain the file; ask one concrete question that would supply the missing field.

## Record procedure

Copy the exact field labels and order for these record types from `docs/artifact-contracts.md`; do not redefine the shape in this skill.

- Use `cap-*` for one observable app behavior.
- Use `constraint-*` for one mandatory app restriction.
- Use `gap-*` when required and observed behavior differ.
- Use `decision-*` when one authority must answer one blocking question.
- Use `inference-*` only for an unverified conclusion derived from cited facts. Send it to `app-research`; do not pass it to `app-plan` or `app-functional-graph`.

## User-message evidence

When a constitution source is a user message, apply the exact format and lifecycle in `docs/artifact-contracts.md`.

1. Select the shortest continuous excerpt that preserves the condition and result.
2. Reject excerpts containing secrets, credentials, or production data; ask for one sanitized statement instead.
3. Create or update `docs/app-user-evidence.md` only when the constitution will cite the entry.
4. Put the exact `docs/app-user-evidence.md#user-msg-*` anchor in the constitution; never use `user said`, `session`, or a paraphrase as the source.

## Precision rules

- Keep the title and exact app target. Omit empty sections and all tables.
- Do not use placeholder records or `None`, `N/A`, or `TBD`.
- Do not add, remove, or shorten text to meet a line count.
- Do not store session execution constraints or `Next skill` in the constitution. Return non-sensitive descriptions of session constraints in the closeout; the next stage is always `app-research`.
- Do not create research waves, plan microtasks, graph nodes, development packets, or test tooling here.
- Do not ask agents to run validation, test, audit, route, cache, cachebuster, quick-validate, or plugin-validate scripts manually.
