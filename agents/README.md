# Plugin Agent Profiles

`role-definitions/*.json` is the authoritative source for every active role. The fixed root-gateway renderer validates the capability catalog and produces this directory's TOML files from a closed safe subset; hand-authored TOML and raw configuration fragments are forbidden.

Each JSON definition owns one bounded behavior, capability set, authority kind, descriptive specialization, and one result fact per assignment. The generated profile is an exact projection, not an independent source.

`explorer` always owns bounded read-only fact extraction; an exact app-analyze assignment serializes that deliverable as one semantic result instead of one workspace-exploration result.

Every profile declares `Role identity: profile=<name>; level=<L1|L2|L3>; role_kind=<kind>; specialization=<description>` inside `developer_instructions`. Dispatch identity binds profile, level, and role kind. Role kind alone defines maximum authority and session lifecycle; level binds caller topology without granting authority. Specialization only describes subject focus and never grants authority, lifecycle rights, tools, skills, or MCP access. The packet instruction refs must include the exact installed profile `config_file`, and the child starts with `fork_turns=none`. If the transport exposes `agent_type` or another documented role selector, it must also match; selector absence alone is not rejection. `task_name` is non-authoritative. Missing or mismatched profile binding fails closed instead of falling back to `default` or parent execution.

Role kinds define lifecycle authority:

- `helper` returns one bounded read-only fact or evidence packet and never delegates or mutates.
- `mutation-worker` owns one bounded workspace change and its task-scoped local commit.
- `primary-critic` reviews one immutable repository change range and never mutates it.
- `workflow-orchestrator` coordinates persistent repository lanes through native collaboration and has no app-stage, route, journal, or L3 authority.
- `repo-orchestrator` owns one persistent repository app-stage lifecycle, route selection, journal writes, and bounded L3 dispatch.

MCP capability policy is rendered under the installed plugin namespace. The plugin owns each server transport; role files only enable or disable its servers and exact tools, avoiding invalid standalone transport-less MCP definitions. `graph-evidence-reader` keeps an exact six-tool evidence-query subset that excludes `handoff_validate`; `explorer` uses the same subset only with named documentation paths for app-analyze. Only the `DIRECT` primary or repo-L2 stage owner may call `handoff_validate`; graph record and compile tools are limited to manifest-authorized orchestration.

The explicit `./install` entrypoint registers the discovered profiles through `config_file` entries in `$CODEX_HOME/config.toml`. Removed names are not registered and have no compatibility aliases; prior receipt ownership is required before a managed registration can be retired. Run the installer after profile changes and start a new task so Codex loads the current registrations.

Open each DELEGATED repository lane from the L1 profile `workflow-orchestrator` with role kind `workflow-orchestrator` through native collaboration, one `repo-lane-dispatch.v1`, and `fork_turns=none`.

Continue each lane through native collaboration with the same persistent `domain-lane-orchestrator`, role kind `repo-orchestrator`, and `orchestrator_session_id`.

Keep every DELEGATED app stage, route choice, and process-record decision with that repo-L2.

Invoke every L3 only from role kind `repo-orchestrator` through `$subagents` with `dispatch-packet.v3`, `result-packet.v2`, and applicable `app-task-dispatch.v2`.

Treat complete lane, L3, result, and outgoing handoff packets as typed transient protocol inputs.

Record only represented completed L3 identity fields in native v3 records; embed the app-analyze completion atomically in its analysis event and never treat a packet body as graph evidence.

- Do not copy these profiles into the global agent directory.
- Deterministic role choice and dispatch live in `skills/subagents/SKILL.md`.
- A role name is derived from one deliverable; removed names have no aliases.
- Profile identity, authority kind, runtime controls, capability sets, and behavior sections are schema-validated from authoritative JSON.
- Agent TOML files use only the Codex custom-agent schema and supported `config.toml` keys; plugin role metadata belongs in `developer_instructions` or plugin-owned documentation, not in unsupported top-level fields.
- Role TOML files own triggers, permissions, decisions, completion conditions, result fields, and one declarative example.
- Skills own repeatable methods, templates, scripts, references, and packet schemas.
