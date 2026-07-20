---
name: app-functional-graph
description: Maintain source-linked workflow entities, observations, and closed-type relations through MCP. Use after app-specify.
---

# App Functional Graph

## Purpose

Turn the specified behavior into a durable, source-linked graph: entities for the
things the system has, observations for what is true about them, relations for how
they constrain each other. The graph is the shared model that planning, dev, and
analysis read from.

Done means the graph reflects the current spec, every record carries a local source
ref, obsolete records are retired rather than dropped, diagnostics show no new
inconsistency, and `waves/<wave_id>/functional-graph.md` describes the resulting
model and what changed.

## How to think about this phase

- Model what the spec commits to, not what the code happens to look like today.
  A record that cannot be traced to a local source ref does not belong in the graph.
- Prefer stable refs that survive rewrites. Renaming a concept is a retire plus a
  replacement, not an edit of meaning under a stale name.
- Relations are a closed set of eight: `depends_on`, `constrains`, `defines`,
  `decomposes_to`, `implemented_by`, `evidenced_by`, `replaces`, `remediates`.
  If a link does not fit one of them, the model is wrong, not the vocabulary.
- Records are retired, never deleted. Retire with a `replacement_ref` when a
  successor exists. Upserting a retired record is rejected, so revive by
  introducing a successor instead.
- Keep one logical change in one `graph_apply` batch: a batch commits or rolls
  back atomically, and splitting it can leave the graph half-migrated.
- A good artifact lets a reader reconstruct the model without querying: the
  entities that matter, the relations that carry the constraints, what was
  retired and why.

## Tools and artifact

- Reads: `project_status`, `graph_read`, `graph_search`, `graph_diagnostics`.
- Records: `graph_apply`, then `phase_record`.
- Writes exactly one artifact: `waves/<wave_id>/functional-graph.md`.

Mutations are performed only by the wave owner and carry `request_id`,
`expected_revision`, and `expected_logical_digest` read fresh from `project_status`
on the reader server. Subagents never touch the maintainer server. There is no
JSON graph fallback; if the workflow servers are unavailable, the phase does not
proceed.

## Deferred to the orchestrator

Phase ordering, entry and exit gates, retries after a CAS conflict, and the
decision to advance to app-plan belong to the orchestrator, not to this skill.
