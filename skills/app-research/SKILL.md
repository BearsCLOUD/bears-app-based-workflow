---
name: app-research
description: Create and synchronize app research waves from intent, sources, and explicit unknowns.
---

# App Research

## Ownership

- Keep the `DIRECT` primary as the stage owner for target access, artifact changes, protocol decisions, journal events, and the outgoing handoff.
- Keep one persistent repo-L2 with role `domain-lane-orchestrator` as the stage owner for `DELEGATED` work.
- Require the repo-L2 to invoke every L3 assignment through `$subagents` and consume only its bounded result packet.
- Never let an L3 write the journal, select a transition, or emit the stage handoff.

## Input

- Accept only `app-stage-handoff.v4` status `constitution-ready` or `needs-research` for the same repo boundary.
- Require a current `$app-context-index` result whose build and source snapshot match the handoff.
- Read routes only from `contracts/app-workflow-definition.v3.json`.
- Carry the constitution, source, constraint, question, decision, requirement, finding, and evidence refs without copying their bodies into the handoff.
- Follow every opaque cursor until no cursor remains before treating a paged source set as complete.

## Artifacts

Update `waves/index.md` with active wave refs and update `waves/<wave-id>/research.md` for each affected wave.

Record the wave scope, known behavior, unknowns, sources, decisions, follow-up questions, synchronization notes, and next stage.

Create a wave only for a distinct user value, dependency set, or repo lane.

Update an existing wave when new evidence changes its scope, decisions, unknowns, or sources.

Propagate one shared decision to every affected wave through stable refs.

Keep unresolved product choices as explicit questions and keep graph or task observations as downstream hints.

## Completion

1. Require the `DIRECT` primary to perform the bounded reads and writes itself.
2. Require the repo-L2 in `DELEGATED` mode to decompose each bounded read or write and dispatch each L3 through `$subagents`.
3. Reconcile changed sources through `$app-context-index` before selecting a transition.
4. Select `research-ready` with target `app-specify` from workflow v3.
5. Put constitution, research, question, and source refs in `stage_payload`.
6. Validate the candidate `app-stage-handoff.v4`, record only the actual native v3 stage event, and reconcile the resulting journal.
7. Emit the build-bound handoff without bypassing `app-specify`.
