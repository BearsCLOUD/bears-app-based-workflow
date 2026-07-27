---
name: app-constitution
description: Establish one app wave's purpose, scope, constraints, and authority, register its Git project, and update the project constitution index. Phase 1 of the seven-phase workflow.
---

# App Constitution

## Purpose

Give a wave a stable identity and a written charter: why this work exists,
what it may and may not touch, which constraints are non-negotiable, and who
decides. Verify the project constitution index and accumulate one anchored line
per wave, derived from the wave document.

## Done means

- The Git project is registered and has a stable `project_ref`.
- The wave exists with a `wave_id`, a mode (`DIRECT` or `DELEGATED`), and a
  stable `owner_session_ref`.
- The project constitution index contains one line for this wave enclosed by
  matching `<!-- bind:REF -->` and `<!-- /bind:REF -->` anchors and derived from
  the wave document.

## How to think about this phase

- Verify and update the project constitution index; do not author a per-wave
  constitution document from scratch.
- Derive the wave's anchored line from the wave document.
- Leave sequencing to the orchestrator.
- Charter, not plan. Say what the wave is for and what bounds it; leave design,
  evidence, and tasks to later phases.
- Constraints are the valuable part. A constraint that cannot be violated
  without failing the wave belongs here; a preference does not.
- Name the unresolved decisions explicitly instead of guessing. An open
  question written down is what app-research is for.
- Scope is defined by its edges. State the non-scope as concretely as the scope.
- One registration per exact Git root: reuse an existing `project_ref` for a
  root that is already registered, and never register a symlink.

## Tools and artifact

- Reads: `project_list`, `project_status`.
- Records: `project_register` (only when the root is unregistered),
  `wave_initialize`, `phase_record`.
- Verifies or updates exactly one artifact: the project constitution index.

Workflow state lives only in the MCP servers; never reconstruct it from JSON
artifacts.

## Left to the orchestrator

Phase sequencing, gate decisions, retries, and outcome selection
(`completed`, `blocked`, or `pending` when a workflow MCP server is
unavailable) belong to the wave owner. Only the wave owner
performs mutations, and every mutation carries `request_id`,
`expected_revision`, and `expected_logical_digest` read fresh from
`project_status`. Subagents never call the maintainer server.

Never transfer wave ownership, emit `audited`, push, merge, or deploy.
