---
name: app-constitution
description: Create or update the app-local constitution that starts a Bears app workflow run.
---

# App Constitution

## Ownership

- Keep the `DIRECT` primary as the stage owner for target access, artifact changes, protocol decisions, journal events, and the outgoing handoff.
- Keep one persistent repo-L2 with role `domain-lane-orchestrator` as the stage owner for `DELEGATED` work.
- Require the repo-L2 to invoke every L3 assignment through `$subagents` and consume only its bounded result packet.
- Never let an L3 write the journal, select a transition, or emit the stage handoff.

## Input

- Accept direct user entry with an app id, one repo boundary, a decision source, known actors, runtime surfaces, constraints, and unresolved decisions.
- Accept an existing constitution ref only when it belongs to the same app and repo boundary.
- Invoke `$app-context-index` at entry and bind all subsequent work to its current build and source snapshot.
- Resolve inter-stage schemas and routes only from `contracts/app-stage-handoff.v4.schema.json` and `contracts/app-workflow-definition.v3.json`.

## Artifact

Create or update `docs/app-constitution.md` with the app boundary, decision owner, actors, runtime surfaces, constraints, data ownership, secret boundaries, required evidence, and open decisions.

Link wave-owned detail instead of copying it into the constitution.

Keep workspace-wide policy outside the app constitution.

Do not create implementation tasks in this stage.

## Completion

1. Require the `DIRECT` primary to perform the bounded reads and writes itself.
2. Require the repo-L2 in `DELEGATED` mode to decompose each bounded read or write and dispatch each L3 through `$subagents`.
3. Reconcile changed sources through `$app-context-index` before selecting a transition.
4. Select `constitution-ready` with target `app-research` from workflow v3.
5. Keep `task_refs` empty and put the constitution ref, constraint refs, research unknowns, wave creation basis, and known wave refs in `stage_payload`.
6. Record only the actual native v3 run-start event with `handoff_payload_digest` over canonical `stage_payload`, reconcile the journal, and call `app-graph.handoff_validate` for the complete candidate.
7. Emit the build-bound handoff with exact artifact, decision, requirement, finding, and evidence refs.
