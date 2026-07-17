---
name: app-specify
description: Turn approved intent and evidence into decision-complete app behavior and acceptance criteria. Use after app-research.
---

# App Specify

## Preconditions

- Keep the stage with the wave owner.
- Require `project_ref`, `wave_id`, `owner_session_ref`, revision, and logical digest.
- Leave the phase `pending` when either workflow MCP server is unavailable.
- Never use a JSON workflow-state fallback.

## Method

1. Call `project_status` and `workflow_state` at the supplied revision.
2. Call `graph_search` and `impact_analysis` for existing constraints and affected behavior.
3. Resolve actors, states, inputs, outputs, failures, compatibility, and acceptance criteria without choosing implementation details.
4. Write one current `waves/<wave_id>/spec.md` artifact with local source refs and explicit unresolved decisions.
5. Call `phase_record` once with current CAS fields and outcome `completed`, `skipped-current`, or `blocked`.

## Completion

- Return the new revision and logical digest, requirement refs, artifact ref, process-record ref, and next phase.
- Never mutate graph entities, create plan tasks, emit `audited`, push, merge, or deploy.
