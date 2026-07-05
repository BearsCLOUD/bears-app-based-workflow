# Agent Registration Sync

## Scope

agent TOML files in `agents/` is the canonical Bears governance source for role profiles. Codex custom-agent discovery is not claimed from the plugin root.

Codex custom-agent registration is materialized only by `scripts/agent_registration_sync.py` into one target:

- user target: `~/.codex/agents`
- repo target: `.codex/agents` under the selected repo root

`agents/openai.yaml` is plugin or skill UX metadata only. It is not custom-agent TOML registration.

No SessionStart hook is enabled by this policy. Hook registration requires a separate policy review.

## Commands

Read-only drift check:

```bash
python3 scripts/agent_registration_sync.py check --target user --json
python3 scripts/agent_registration_sync.py check --target repo --json
```

Sequential role audit:

```bash
python3 scripts/agent_registration_sync.py audit-roles --json
```

Explicit sync:

```bash
python3 scripts/agent_registration_sync.py sync --target user
python3 scripts/agent_registration_sync.py sync --target repo
```

Validator ownership:

- Local commit validation owns `python3 scripts/agent_registration_sync.py validate`; manual execution requires operator approval.

## Drift contract

The check packet reports:

- `missing`: canonical agent has no managed target TOML.
- `stale`: managed target TOML differs from canonical source.
- `extra`: managed target TOML is outside the canonical destination set, including removed-source files and rogue managed files that point to an existing canonical source.
- `local_edits`: target TOML exists but is not managed by this script.
- `schema_errors`: canonical source TOML is not valid for Bears custom-agent registration.

`sync` writes only managed target files. It does not overwrite unmanaged local files and does not delete stale managed files.

## Validation

`validate` checks canonical TOML schema, role classification, developer-instruction role overrides, and platform role alignment.

Every canonical `agents/*.toml` file must declare these top-level keys:

- `role_kind`
- `execution_class`
- `primary_eligible`

Every canonical `agents/*.toml` `developer_instructions` block must include:

- exact role marker: `Operate as \`<agent-name>\``
- exact role override line: `- Role override: <description>` from the same TOML `description`

Role-backed TOMLs must match the same fields from `assets/catalog/platform-role-catalog.v1.json` `roles[]`. Profile-backed TOMLs must match `agent_profile_mappings[]`; `domain_orchestrator_profile` maps to `role_kind=orchestrator` and `primary_eligible=false`, and `workflow_helper_profile` maps to `role_kind=helper` and `primary_eligible=true`.

Every role declared or referenced by `assets/catalog/platform-role-catalog.v1.json` must have a matching canonical `agents/<role>.toml` file. This prevents the role gate from selecting a role that Codex custom-agent registration cannot materialize.

After `sync`, an already-open Codex session may need a new thread or app reload before newly materialized custom-agent profiles appear in the multi-agent runtime.

Local commit validation owns validation after agent registration policy changes:

- `python3 scripts/agent_registration_sync.py validate`; manual execution requires operator approval.
- `python3 scripts/agent_registration_sync.py audit-roles --json`; manual execution is static audit evidence only and does not execute repo validator suites.
- `python3 scripts/subagents_roles.py validate`; manual execution requires operator approval.
- `python3 -m unittest tests/test_agent_registration_sync.py tests/test_subagents_roles.py`; manual execution requires operator approval.
