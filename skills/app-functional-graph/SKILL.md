---
name: app-functional-graph
description: Maintain source-linked workflow entities, observations, and closed-type relations through MCP. Use after app-specify.
---

# App Functional Graph

## Preconditions

- Keep graph writes with the wave owner.
- Require `project_ref`, `wave_id`, `owner_session_ref`, revision, and logical digest.
- Leave the phase `pending` when either workflow MCP server is unavailable.
- Never write `app-functional-map.v5.json` or another graph fallback.

## Method

1. Call `project_status`, `graph_read`, `graph_search`, and `graph_diagnostics` at the current revision.
2. Map specified behavior into stable entities, observations, and relations with mandatory local source refs.
3. Use only `depends_on`, `constrains`, `defines`, `decomposes_to`, `implemented_by`, `evidenced_by`, `replaces`, or `remediates`.
4. Retire obsolete objects with `replacement_ref` when applicable; never request physical deletion.
5. Submit every related change in one `graph_apply` batch with current CAS and owner fields.
6. Re-read diagnostics, write `waves/<wave_id>/functional-graph.md`, and call `phase_record` once.

## Completion

- Return changed stable refs, diagnostics, new revision and digest, Markdown artifact ref, process-record ref, and next phase.
- Never split one logical batch, mutate plan tasks, emit `audited`, push, merge, or deploy.
