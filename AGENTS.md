# Bears App-Based Workflow Router

Short router for this plugin checkout. Shared execution, delegation, and verification rules stay in `/srv/bears/contracts/developer_instructions_contract.md` and the injected root instruction chain.

- This repo owns plugin procedures in `skills/`, unique role behavior in `agents/`, plugin metadata, and the explicit `./install` entrypoint.
- The active caller instruction chain classifies each coherent workstream as `DIRECT` or `DELEGATED` before this plugin is invoked. `DIRECT` work remains with the primary and never enters `skills/subagents`.
- For `DELEGATED` work, `app-dev` owns fixed L1-to-L2 orchestration and L2 decomposition. `skills/subagents` owns persistent selector reuse, L3 role selection, and bounded L3 dispatch.
- Other `app-*` skills own only stage goals, payloads, outputs, and transitions.
- Keep plugin instructions and documentation in English. Do not move workspace rules or shared invariants into this repo.
- Do not add validators, tests, audits, cache checks, manual verification commands, or parent execution fallback.
