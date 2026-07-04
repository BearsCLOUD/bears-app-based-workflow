---
name: bears-agents
description: "Use for @Bears role lifecycle work: create/update role TOML, close ROLE_COVERAGE_BLOCKER gaps, sync role registration, and handle stale, missing, or extra role drift."
---

# Bears Agents

Use this skill for `@Bears` role lifecycle changes under `/srv/bears/plugins/bears/agents` and the role catalog.

This skill defines role authority. It does not run delegated work. Use `subagents` for runtime delegation after a route gate selects a role.

## Scope

Use this skill for:

- creating or updating role TOML profiles;
- adding exact role catalog mappings;
- fixing `ROLE_COVERAGE_BLOCKER` gaps;
- syncing role registration policy;
- handling stale, missing, duplicate, or extra role drift;
- keeping role aliases, write roots, trust boundaries, and validation ownership exact.

## Boundaries

Do not use this skill to select, start, constrain, review, or close runtime subagents. That belongs to `subagents`.

Do not store product facts, target board facts, repo-local implementation details, deploy facts, secret exceptions, or target docs content in role profiles. Put target facts in the target `AGENTS.md`, target docs, or target `.codex/`.

## Role lifecycle rules

- Role profiles define specialist scope, allowed evidence, forbidden actions, handoff shape, and validation focus after route selection.
- Role profiles do not choose the role by themselves. The route/audit gate selects the role.
- Role profiles must not invent product ownership, Git/CD policy, deployment paths, or secret exceptions.
- If a role profile is broader than the route gate, fix the role profile or catalog mapping before implementation.
- `ROLE_COVERAGE_BLOCKER` remediation must produce one exact primary role or one exact helper role for the requested write granularity.

## Validation ownership

Route/audit is ownership discovery only. Automatic CI and local-commit validation own blocking check results for role lifecycle changes.

## Closeout

Report:

- changed role files and catalog paths;
- exact route/audit result for the new or changed target;
- whether role coverage now returns one primary role;
- validation source;
- any carried unrelated dirty paths.
