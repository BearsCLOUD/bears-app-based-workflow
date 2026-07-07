# Bears goals and principles

## Scope

`assets/catalog/bears-goals.v1.json` is the active goals catalog.
`assets/catalog/bears-principles.v1.json` is the active workflow principle catalog.
`assets/schemas/principle-decision.v1.schema.json` defines the decision packet required for material workflow decisions.

## Goal record

A goal contains `goal_id`, `horizon`, `status`, `priority`, `owner_surface`, `success_metric`, `linked_issues`, and `blocked_by`.
Only `active` goals can satisfy a decision packet.

## Principle record

A principle contains `principle_id`, `status`, `severity`, `rule`, `validator`, `decision_required_when`, and `exceptions`.
Required active principles are:

- `machine_contracts_over_prose`
- `cheap_research_by_default`
- `no_parent_context_for_shards`
- `no_silent_role_omission`
- `codex_exec_requires_gate`
- `deterministic_runner_before_llm`
- `main_only_closeout_authority`
- `exact_proof_before_issue_close`
- `no_unbounded_autostart`
- `roadmap_leaf_before_execution`

## Decision packet rule

Every material workflow decision must declare `schema: bears-principle-decision.v1` and must name at least one active principle and one active goal.
Missing principle references block material workflow changes.
Principle exceptions must include `reason_code`, `rationale`, and `evidence_paths`.

## Commands

```bash
scripts/bears_goals.py validate
scripts/bears_goals.py status --json
scripts/bears_principles.py validate
scripts/bears_principles.py decision-check --packet <path>
scripts/bears_principles.py doctor --json
```

## Doctor output

`bears_doctor` includes the `bears_goals_principles` check.
The report returns active goal count, active principle count, and missing required active principles.
