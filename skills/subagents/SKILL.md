---
name: subagents
description: Prepare bounded subagent delegation packets for Bears app-dev orchestration. Use when Codex must split ready ledger work into L2 lanes, L3 worker tasks, critic tasks, and completion criteria.
---

# Subagents

## Purpose

Create delegation packets for L2 lane orchestrators and L3 workers or critics.

## Packet fields

- Role.
- Scope.
- Task ids.
- Allowed paths.
- Forbidden paths.
- Inputs to read.
- Expected edits or read-only output.
- Completion criteria.
- Closeout format.

## Rules

- Delegate only bounded work with a clear owner and output.
- Keep write scopes disjoint across parallel packets.
- Include exact task ids and graph refs for app-dev work.
- Do not ask a subagent to infer missing product decisions.
- Require subagents to list changed files or state `read-only`.
