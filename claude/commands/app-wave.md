---
name: app-wave
description: Start a new app wave or resume an interrupted one by reading live workflow state from the read-only MCP server.
argument-hint: "[wave-id] [goal]"
allowed-tools: mcp__app-workflow__project_list, mcp__app-workflow__project_status, mcp__app-workflow__workflow_state, mcp__app-workflow__workflow_validate, Bash, Read, Glob, Skill
---

# App Wave

Arguments: `$ARGUMENTS` (optional wave id, then an optional one-line goal).

You are the wave owner: the `DIRECT` primary session. Never assume a phase is done,
never re-run a completed phase, and never guess identity fields. Every routing
decision below comes from a tool result you just read.

## Preconditions

- Stop and report when `app-workflow` is unavailable; never fall back to JSON state.
- Never call `app-workflow-maintainer` from this command. Routing only; the phase
  skill performs its own mutations.
- Carry `project_ref`, `wave_id`, `owner_session_ref`, `revision`, and
  `logical_digest` into the phase skill you hand off to.

## Method

### 1. Resolve the project

1. Run `git rev-parse --show-toplevel` to get the absolute Git root.
2. Call `project_list` and match a project whose `root_path` equals that root
   exactly. Reuse its `project_ref`.
3. When no entry matches, there is no registered project: skip to step 4 with no
   `project_ref` and route to `app-constitution`, which owns `project_register`.
4. When a match exists but reports `available: false`, stop and report the
   unreadable project database instead of registering a second time.
5. Call `project_status {project_ref}` and keep `revision` and `logical_digest`
   as the current CAS values for the handoff.

### 2. Resolve the wave

The reader server has no wave-listing tool, so discover candidates from the
project tree and confirm each one against the database.

1. When `$ARGUMENTS` names a wave id, use it.
2. Otherwise list `waves/*/` under the Git root and treat each directory name as
   a candidate wave id.
3. Call `workflow_state {project_ref, wave_id}` per candidate. A `WAVE_NOT_FOUND`
   result means the directory has no database record; report it rather than
   silently creating a parallel wave.
4. With several live waves and no wave id in `$ARGUMENTS`, list them with their
   `wave.current_phase` and `workflow_status` and ask which to resume.
5. With no candidate at all, this is a new wave. Propose a wave id, confirm it
   with the user, and route to `app-constitution`, which owns `wave_initialize`.

### 3. Read the state

From the `workflow_state` result, read exactly these fields:

- `wave.current_phase` - the phase to run next. This is the resume signal.
- `wave.status` and top-level `workflow_status` - `workflow_status` is `audited`
  only when the latest attestation still matches the current revision, logical
  digest, and snapshot digest.
- `phases[]` - seven rows ordered by `ordinal`, each with `status`,
  `process_record_ref`, and `reopened_by`. Phase status is only `pending`,
  `completed`, or `blocked`: `phase_record` maps the `skipped-current` outcome
  onto status `completed`, so read `process_records[].outcome` when you need to
  tell a skipped phase from a worked one. A non-null `reopened_by` means a
  correction reopened that phase.
- `revision` and `logical_digest` - fresher than the `project_status` pair when
  anything changed in between; prefer these.
- `tasks[]`, `reviews[]`, `findings[]`, `corrections[]`, `analyses[]` - outstanding
  work inside the current phase.
- `total` versus `count` - when they differ the response was paged; follow
  `next_cursor` until the ledger is complete before judging outstanding work.

### 4. Route

Phase order is `app-constitution`, `app-research`, `app-specify`,
`app-functional-graph`, `app-plan`, `app-dev`, `app-analyze`. `phase_record`
validates the phase name and the single-active-record rule but does not check
that earlier phases completed, so the ordering discipline is yours.

1. Route to the skill named by `wave.current_phase`.
2. Before handing off, verify every phase with a lower `ordinal` has status
   `completed`. If an earlier phase is `pending` or `blocked`, route to that
   earlier phase instead and say why.
3. Never route to a phase whose row is already `completed` unless the user asks
   for a rerun. A rerun supersedes the prior record rather than adding a second
   active one, and it needs a fresh `record_ref`: reusing one fails with
   `RECORD_REF_EXISTS`.
4. When `wave.current_phase` is `app-dev`, report open `tasks[]`, unresolved
   `reviews[]`, and open `corrections[]` before continuing, and resume the task
   ledger instead of restarting it.
5. When `wave.current_phase` is `app-analyze`, call
   `workflow_validate {project_ref, wave_id}` first and hand its findings to the
   skill. `ok: false` with a single `ANALYSIS_NOT_READY` finding is the expected
   result for a wave that has not recorded its analysis yet - not a failure.
6. When all seven phases are `completed` and `workflow_status` is `audited`, the
   wave is finished. Report it and do not reopen a phase.

### 5. Hand off

Invoke the phase skill with the resolved `project_ref`, `wave_id`,
`owner_session_ref`, `revision`, and `logical_digest`, plus the goal from
`$ARGUMENTS` on a new wave. Delegate bounded implementation, review, and analysis
work per the `subagents` skill; the wave owner keeps every maintainer call.

## Completion

Report the project ref, wave id, the phase you routed to, the phase statuses you
read, and any outstanding tasks, reviews, findings, or corrections. State plainly
whether this was a new wave or a resume.
