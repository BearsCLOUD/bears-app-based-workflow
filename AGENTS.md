# Bears App-Based Workflow Router

This file narrows the root instruction-ownership and autoCI rules for this plugin checkout. Shared execution and delegation rules remain in root `AGENTS.md` and contracts because other subtrees reuse them.

- This repo owns plugin procedures in `skills/`, unique role behavior in `agents/`, plugin metadata, and the explicit `./install` entrypoint.
- `app-dev` owns fixed L1-to-L2 orchestration and L2 decomposition. `skills/subagents` owns the role-selection and dispatch procedure for each concrete L3 assignment. Other `app-*` skills own only stage goals, payloads, outputs, and transitions.
- Keep plugin instructions and documentation in English. Do not move workspace rules or shared invariants into this repo.
- Do not add tests, validators, audits, cache checks, or manual verification commands. External autoCI owns them.
- Do not add `subagents-roles` or a parent execution fallback.
