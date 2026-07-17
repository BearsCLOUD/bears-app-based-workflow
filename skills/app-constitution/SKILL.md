---
name: app-constitution
description: Register a Git project and establish one app wave's purpose, constraints, authority, and ownership. Use first in the seven-phase workflow.
---

# App Constitution

## Preconditions

- Keep the stage with the `DIRECT` primary or the persistent `repo-orchestrator`.
- Require an absolute non-symlink Git root for first registration.
- Keep `project_ref`, `wave_id`, `owner_session_ref`, revision, and logical digest in every stage handoff.
- Leave the phase `pending` when either workflow MCP server is unavailable.
- Never use a JSON workflow-state fallback.

## Method

1. Call `project_list` and reuse the registered `project_ref` for the exact Git root.
2. Call `project_register` through `app-workflow-maintainer` when the project is not registered.
3. Call `project_status` and retain its current revision and logical digest.
4. Call `wave_initialize` with one `DIRECT` or `DELEGATED` mode and the stable owner-session ref.
5. Write `waves/<wave_id>/constitution.md` with purpose, scope, constraints, authority, and unresolved decisions.
6. Call `phase_record` once with exact source and artifact refs, current CAS fields, and outcome `completed` or `blocked`.

## Completion

- Return the stable project and wave identity, new revision and digest, Markdown artifact ref, process-record ref, and next phase.
- Never register a symlink, transfer the wave owner, emit `audited`, push, merge, or deploy.
