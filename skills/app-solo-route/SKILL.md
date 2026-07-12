---
name: app-solo-route
description: Sequentially route one DIRECT primary through Bears app research, specification, functional graph, planning, and analysis. Use when one agent should resume the earliest incomplete app stage and continue to app-dev, pass, blocked, unchanged waiting, or a required user decision without delegation.
---

# App Solo Route

## Boundary

Run only when the workstream is already classified `DIRECT`. The same primary performs discovery, loads each selected `$app-*` stage skill, creates that stage's artifacts and canonical handoff, and selects the next stage. Do not initialize a selector or call delegation tools. `app-constitution` and `app-dev` are external boundaries: return a handoff to them but do not execute them.

Start immediately. Keep one route state containing the current canonical handoff, its semantic fingerprint, and the answer or evidence refs added since it was produced.

## Canonical routes

Validate every supplied or stage-produced `app-stage-handoff.v1` against the common and status-specific fields defined by `$app-functional-graph`. The status and `target_stage` must be this exact pair:

<!-- route-map:start -->
```json
{
  "constitution-ready": "app-research",
  "needs-research": "app-research",
  "research-ready": "app-specify",
  "needs-spec": "app-specify",
  "spec-ready": "app-functional-graph",
  "needs-graph": "app-functional-graph",
  "graph-ready": "app-plan",
  "waiting": "app-plan",
  "needs-plan": "app-plan",
  "no-work": "app-analyze",
  "implemented": "app-analyze",
  "plan-ready": "app-dev",
  "ready": "app-dev",
  "pass": "none",
  "blocked": "none"
}
```
<!-- route-map:end -->

Reject an unknown status, missing required field, or mismatched status/target pair before executing another stage. Report the exact invalid pair or field; do not repair it by guessing.

## Resume

1. If a valid canonical handoff exists, route only by its validated `target_stage`.
2. Otherwise inspect the stable artifact refs in this order and select the earliest incomplete stage:
   - missing constitution: stop with an `app-constitution` transition;
   - incomplete or missing wave research: `$app-research`;
   - incomplete or missing decision-complete specification: `$app-specify`;
   - incomplete, missing, or stale functional graph coverage: `$app-functional-graph`;
   - incomplete, missing, or stale plan or executable ledger coverage: `$app-plan`;
   - complete planning with no executable ready task, or available implemented-state evidence requiring convergence assessment: `$app-analyze`.
3. If complete canonical tasks are already `ready`, return a repo-scoped `plan-ready` or `ready` handoff to `app-dev` without executing development.

Never infer completion only from a file's presence. Use its stage status, required refs, coverage, and current evidence.

## Sequential loop

For an internal target, load the named stage skill, execute it as the same primary, validate its canonical output, then route again. Forward transitions and feedback transitions use the same table; do not skip an earlier target selected by feedback.

Stop and return the current canonical handoff when:

- its target is `app-dev`;
- its status is `pass` or `blocked`;
- `waiting` is semantically unchanged and no new dependency evidence exists;
- any produced handoff is semantically identical to the last routed handoff and no new user answer or evidence ref exists;
- the current stage requires a user answer under the decision gate below.

The semantic fingerprint covers the complete canonical handoff after stable key ordering. Never execute the same target again from an unchanged fingerprint.

## User decision gate

Ask the user only when the current stage exposes an architectural fork: at least two materially different architecture paths exist and no artifact, accepted decision, constraint, or user answer selects one. This gate overrides broader question loops in a loaded stage skill. Ask one concise question that names the paths and their main tradeoff, then pause the route. After the answer, add its stable decision ref, resume the same stage, and continue the full route.

Do not ask merely because evidence is incomplete, a preference is cosmetic, or one architecture is already required by recorded constraints. In those cases continue from evidence or return the stage's canonical handoff without inventing a decision.

## Result

Return the last validated `app-stage-handoff.v1` when one exists; otherwise return the `app-constitution` boundary transition. Also return the last executed internal stage and one stop reason: `app-constitution-boundary`, `app-dev-boundary`, `pass`, `blocked`, `unchanged-waiting`, `unchanged-handoff`, `user-architecture-decision`, or `invalid-handoff`.
