---
name: bears-project-specify
description: "Create or update Bears project specifications and functional documentation from operator intent, constitution rules, repo evidence, and acceptance criteria. Use as the Bears-native analogue to Spec Kit specify for feature descriptions, repo/project docs, user/operator behavior docs, and implementation-ready requirements."
---

# Bears Project Specify

Use this skill to turn operator intent into concrete project documentation and implementation-ready requirements.

A specification is the source document that states what the feature or workstream must do, for whom, where it lives, how success is proven, and what is out of scope.

## Boundary

Allowed:

- Read nearest `AGENTS.md`, constitution, README, SPEC, requirements, current docs, route/audit output, and relevant GitHub Issues/Project metadata.
- Create or update `spec.md`, feature docs, operator docs, user docs, or README sections in the owning repo path.
- Produce acceptance criteria and validation expectations for planning.

Forbidden:

- Implementation code edits unless a later execution skill explicitly owns them.
- Runtime, deploy, Kubernetes, provider, repo-setting, secret, `.env`, production-data, raw-log, or raw-chat mutation.
- Root `/srv/bears/specs`, `.specify`, root `plans.md`, root `roadmap.md`, or `/srv/bears/docs/plans.md` recreation.

## Artifact placement

Use the narrowest owner path:

- Existing Spec Kit feature directory when one already exists and is in the owning repo.
- `docs/features/<slug>/spec.md` for repo-local feature work.
- `SPEC.md` only when it already owns the repo-level product contract.
- README updates only for entrypoint summaries and links, not full specs.

## Workflow

1. Read `/srv/bears/AGENTS.md`, nearest project `AGENTS.md`, and the target constitution. If no constitution exists, run `$bears-project-constitution` or record an explicit constitution gap.
2. Run route/audit for the exact target path.
3. Extract operator intent into concrete scope, actors, workflows, inputs, outputs, data boundaries, errors, recovery behavior, and validation proof.
4. Inspect only files needed to avoid contradicting current implementation and docs.
5. Write or update the specification with these sections:
   - Problem and outcome;
   - Scope and non-goals;
   - Actors and triggered workflows;
   - Functional requirements with stable ids;
   - Documentation requirements;
   - Data, secret, runtime, deploy, and GitHub metadata boundaries;
   - Acceptance criteria;
   - Validation plan;
   - Dependencies and open questions.
6. Update user/operator/developer docs only when the spec changes visible behavior or workflow use.
7. Emit a `bears-project.specification-packet` and hand it to `$bears-project-plan`.

## Specification packet

```json
{
  "schema": "bears-project.specification-packet",
  "version": "1",
  "status": "draft|review|ready|blocked",
  "target": "<exact path or repo>",
  "constitution": "<path or gap>",
  "spec": "<path>",
  "docs_changed": ["<paths>"],
  "requirements": ["<stable ids>"],
  "acceptance_criteria": ["<ids or summaries>"],
  "validation_expectation": ["<commands or metadata checks>"],
  "planning_input": "ready|needs-operator-review|blocked",
  "recommendation": "<next action>"
}
```

Use `blocked` only for missing owner, missing route coverage, missing required constitution decision, access failure, or explicit operator stop.
