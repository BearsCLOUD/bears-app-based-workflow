---
name: app-constitution
description: Establish one app wave's purpose, scope, constraints, and authority, and register the Git project that holds it. Phase 1 of the seven-phase workflow.
---

# App Constitution

## Purpose

Give a wave a stable identity and a written charter: why this work exists,
what it may and may not touch, which constraints are non-negotiable, and who
decides. Everything later in the workflow is judged against this artifact.

## Done means

- The Git project is registered and has a stable `project_ref`.
- The wave exists with a `wave_id`, a mode (`DIRECT` or `DELEGATED`), and a
  stable `owner_session_ref`.
- `waves/<wave_id>/constitution.md` states purpose, scope and non-scope,
  constraints, decision authority, and the decisions still unresolved.

## How to think about this phase

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
- Writes exactly one artifact: `waves/<wave_id>/constitution.md`.

Workflow state lives only in the MCP servers; never reconstruct it from JSON
artifacts.

## Left to the orchestrator

Phase ordering, gate decisions, retries, and outcome selection
(`completed`, `blocked`, or `pending` when a workflow MCP server is
unavailable) belong to the wave owner. Only the wave owner
performs mutations, and every mutation carries `request_id`,
`expected_revision`, and `expected_logical_digest` read fresh from
`project_status`. Subagents never call the maintainer server.

Never transfer wave ownership, emit `audited`, push, merge, or deploy.
