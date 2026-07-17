---
name: app-analyze
description: Compare workflow semantics, validate the exact SQLite-backed snapshot, and atomically attest audited. Use after app-dev.
---

# App Analyze

## Preconditions

- Keep the stage and final audit write with the wave owner.
- Require `project_ref`, `wave_id`, `owner_session_ref`, revision, and logical digest.
- Leave the phase `pending` when either workflow MCP server is unavailable.
- Never validate or reconstruct JSON workflow state.

## Method

1. Call `workflow_state`, `graph_read`, `graph_diagnostics`, `topological_plan`, and `workflow_validate` at the current revision.
2. Compare documentation, graph edges, provenance, tasks, dependencies, reviews, corrections, process records, and exact files for logical correspondence.
3. Use an optional read-only `app-analyst` only for a bounded semantic slice.
4. Write `waves/<wave_id>/analysis.md` and call `phase_record` once for the current analysis attempt.
5. Call `analysis_record` with stable findings and the earliest required phase, or an empty finding set for `ready`.
6. When findings exist, stop at the reopened phase and do not attest audit.
7. When clean, call `workflow_validate` again, then call `workflow_mark_audited` with that exact revision and digest.

## CLI

```bash
python3 <plugin-root>/skills/app-analyze/scripts/validate_workflow.py \
  --project-ref <project_ref> --wave-id <wave_id>
```

The read-only CLI emits `ok`, `snapshot_digest`, and `findings`.

## Completion

- Emit `audited` only from the atomic MCP attestation and exact clean snapshot.
- Treat every later mutation as a stale audit requiring validation and attestation again.
