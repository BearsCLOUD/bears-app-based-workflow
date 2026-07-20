---
name: app-analyze
description: Phase 7. Cross-check workflow semantics against the exact SQLite-backed snapshot and attest the wave audited. Entry point for the analyze phase.
---

# App Analyze

## Purpose

Phase 7 is the semantic audit of a wave. Earlier phases each assert something:
the constitution asserts constraints, research asserts context, the spec asserts
intent, the functional graph asserts structure, the plan asserts decomposition,
and dev asserts that the work landed. Analyze is the only phase that asks
whether all of those assertions still agree with each other and with the files
on disk. Structural validation is cheap and already automated; the value added
here is judgment about meaning.

## Done

The phase is done when one of two things is true:

- Findings exist, they are recorded, and the earliest affected phase is
  reopened. A wave with open findings is not audited and must not be attested.
- The analysis is clean, `workflow_validate` passes, and `workflow_mark_audited`
  succeeded at that exact revision and digest.

A clean analysis is rejected while findings are still open or tasks are
incomplete, so a rejection is information about the wave, not a transient error.

`workflow_mark_audited` revalidates at the same revision inside its own
transaction, so the attestation is atomic with the check that justified it. It
is also only as current as that revision: any later mutation stales it, and the
wave must be validated and attested again.

## How to think about the cross-check

Read the snapshot first, then look for disagreement rather than for confirmation.
Useful seams:

- Documentation against graph: does every claim in the spec have an entity or
  observation behind it, and does every entity trace back to a stated intent?
- Graph against plan: do the dependencies in the plan match the relations in the
  graph, and does the topological order actually respect them?
- Plan against dev: do completed tasks correspond to real changes in real files,
  and do provenance rows point at those files?
- Records against each other: reviews, corrections, and process records should
  narrate a history that the current state is consistent with.

Prefer a small number of stable, reproducible findings over a long list of
impressions. A finding should name the earliest phase whose output would have to
change to fix it, because that is the phase that gets reopened along with
everything after it. Do not weaken a finding to keep a wave clean, and do not
manufacture one to look thorough.

Keep the analysis with the wave owner. An `app-analyst` subagent may be used for
a bounded semantic slice, but it reads only and never records.

## Tools

Reads: `workflow_state`, `graph_read`, `graph_diagnostics`, `topological_plan`,
`workflow_validate`, all at the current revision.

Records: `phase_record` for the analysis attempt, `analysis_record` for the
findings (or an empty finding set for `ready`), and `workflow_mark_audited` for
the attestation.

Never validate or reconstruct JSON workflow state. If either workflow MCP server
is unavailable, the phase stays `pending`.

## Artifact

Write `waves/<wave_id>/analysis.md`.

## Read-only CLI

```bash
python3 <plugin-root>/skills/app-analyze/scripts/validate_workflow.py \
  --project-ref <project_ref> --wave-id <wave_id>
```

Emits `ok`, `snapshot_digest`, and `findings`.

## Sequencing

The orchestrator decides when this phase runs, in what order calls are made,
whether an attempt is retried, and what happens after a reopen. This skill does
not encode that control flow.
