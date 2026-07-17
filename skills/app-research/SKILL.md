---
name: app-research
description: Reconcile primary evidence for one registered app workflow wave. Use after app-constitution when facts or constraints remain unresolved.
---

# App Research

## Preconditions

- Keep the stage with the wave owner.
- Require `project_ref`, `wave_id`, `owner_session_ref`, revision, and logical digest.
- Leave the phase `pending` when `app-workflow` or `app-workflow-maintainer` is unavailable.
- Never reconstruct workflow state from JSON artifacts.

## Method

1. Call `project_status` and reject a stale revision or logical digest.
2. Call `workflow_state`, `graph_search`, and `graph_open` for the exact current evidence boundary.
3. Read primary sources and separate observed facts, inferences, conflicts, and open questions.
4. Write one current `waves/<wave_id>/research.md` artifact with local source refs.
5. Call `phase_record` once with the current CAS fields and outcome `completed`, `skipped-current`, or `blocked`.
6. Use `skipped-current` only when the recorded input digest still matches the exact source set.

## Completion

- Return the new revision and logical digest, evidence refs, artifact ref, process-record ref, unresolved questions, and next phase.
- Never decide product behavior, mutate the graph, emit `audited`, push, merge, or deploy.
