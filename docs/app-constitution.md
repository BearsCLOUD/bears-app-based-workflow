# App Constitution

- App: `bears-app-based-workflow`

## Capabilities

### cap-sequential-workflow

- Condition: A main stage before `app-analyze` passes its exit gate.
- Actor/System: Workflow runner.
- Observable result: The runner follows the next edge in `SPEC.md#core-workflow` without skipping a main stage.
- Source: `SPEC.md#core-workflow`.

### cap-constitution-truth

- Condition: App functionality is added, changed, removed, or found inconsistent downstream.
- Actor/System: `app-constitution`.
- Observable result: Each downstream constitution ID and source link resolves to the current record.
- Source: `docs/workflow-stage-gates.md#drift-routing`.

### cap-research-explains-truth

- Condition: A constitution record needs explanation or verification.
- Actor/System: `app-research`.
- Observable result: The wave research maps the constitution ID to exact sources, its decision or unknown state, and its eligibility for planning.
- Source: `SPEC.md#app-research`.

### cap-plan-microtasks

- Condition: Research confirms a source-backed `cap-*` or `gap-*` as a plan input.
- Actor/System: `app-plan`.
- Observable result: The plan row and ledger task satisfy `docs/functional-graph-ledger-contract.md#ledger-microtask-requirements`.
- Source: `docs/functional-graph-ledger-contract.md#ledger-microtask-requirements`.

### cap-graph-dev-model

- Condition: Plan microtasks are approved and recorded in the ledger.
- Actor/System: `app-functional-graph`.
- Observable result: Each modeled node satisfies `docs/functional-graph-ledger-contract.md#graph-node-requirements` and links back to its ledger task.
- Source: `docs/functional-graph-ledger-contract.md#graph-node-requirements`.

### cap-lineage-analysis

- Condition: A workflow wave reaches analysis.
- Actor/System: `app-analyze`.
- Observable result: The analysis records `pass` or names the earliest broken workflow link and its reroute stage.
- Source: `SPEC.md#app-analyze`.

### cap-file-reuse-audit

- Condition: `app-analyze` runs in plugin file-audit mode.
- Actor/System: `app-analyze`.
- Observable result: The analysis has one row per plugin file with a named consumer and all nine file-audit results.
- Source: `skills/app-analyze/SKILL.md#file-audit-mode`.

### cap-packet-contracts

- Condition: A support skill emits or consumes a workflow handoff packet.
- Actor/System: `app-research`, `app-specify`, `subagents-roles`, `subagents`, `instruction-hardening`, and `app-analyze`.
- Observable result: The packet uses the exact fields and version named in `docs/handoff-packet-contracts.md`.
- Source: `docs/handoff-packet-contracts.md#handoff-packet-contracts`.

### cap-self-contained-roles

- Condition: A graph-backed task needs an owner, critic, or helper role.
- Actor/System: `subagents-roles`.
- Observable result: The returned role name exists in `docs/role-catalog.md`, or the packet records the missing role requirement.
- Source: `docs/role-catalog.md#rules`.

### cap-self-contained-plugin

- Condition: The plugin receives valid app inputs in a host workspace other than this checkout.
- Actor/System: Plugin workflow.
- Observable result: It produces the same artifact sequence using only plugin-owned skills, contracts, templates, and packets.
- Source: `README.md#independence-and-script-ownership`.

### cap-no-test-tooling-loop

- Condition: An agent must inspect or prove workflow behavior.
- Actor/System: Plugin skills.
- Observable result: The agent returns inspection evidence without creating or requiring a plugin-owned verification tool.
- Source: `SPEC.md#script-ownership`.

### cap-constitution-precision

- Condition: `app-constitution` creates or updates the constitution.
- Actor/System: `app-constitution`.
- Observable result: The output contains exactly the independently changeable, contract-valid records supported by current inputs; line count neither adds nor removes content.
- Source: `docs/app-user-evidence.md#user-msg-0001`; `docs/artifact-contracts.md#docsapp-constitutionmd`.

### cap-user-message-evidence

- Condition: A session message is the exact source for a constitution record.
- Actor/System: `app-constitution`.
- Observable result: The source resolves to a contract-valid `user-msg-*` entry whose quote is the shortest unchanged safe continuous excerpt that preserves the condition and result.
- Source: `docs/app-user-evidence.md#user-msg-0002`; `docs/artifact-contracts.md#docsapp-user-evidencemd`.

## Constraints

### constraint-no-env-dependency

- Rule: The plugin must run without a file or service supplied only by its host workspace.
- Source: `README.md#independence-and-script-ownership`.

### constraint-no-manual-scripts

- Rule: Plugin skills must not require manual execution of scripts owned by external automation.
- Source: `SPEC.md#script-ownership`.

### constraint-no-workflow-test-tooling

- Rule: No software may be added solely to prove this workflow.
- Source: `SPEC.md#script-ownership`.

### constraint-sequential-only

- Rule: One main stage must finish its artifact before the next main stage begins.
- Source: `docs/workflow-stage-gates.md#rule-summary`.

### constraint-complete-lineage

- Rule: `app-dev` may consume only graph nodes that satisfy the complete-lineage gate.
- Source: `docs/functional-graph-ledger-contract.md#graph-node-requirements`.
