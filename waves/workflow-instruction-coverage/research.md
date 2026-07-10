# Wave Research: workflow-instruction-coverage

## Wave ID

`workflow-instruction-coverage`

## Scope

- Cover the plugin workflow instructions so a future agent can produce a precise constitution with every required source and follow research, planning, graph modeling, development, and analysis without host-specific dependencies or workflow-testing software.

## Constitution mapping

| Constitution ref | Research explanation | Source refs | Decision state |
| --- | --- | --- | --- |
| `cap-sequential-workflow` | The workflow must be linear. Research confirms graph modeling happens after approved plan microtasks and models dev. | `SPEC.md#core-workflow`, `docs/workflow-stage-gates.md#rule-summary` | closed |
| `cap-constitution-truth` | Functional drift is resolved against constitution first; this keeps research, plan, graph, dev, and analysis aligned. | `docs/workflow-stage-gates.md#drift-routing`, `SPEC.md#app-constitution` | closed |
| `cap-research-explains-truth` | Every wave must show which constitution ids it explains and what sources support each explanation before plan. | `docs/artifact-contracts.md#waveswave-idresearchmd`, `skills/app-research/SKILL.md#research-file-sections` | closed |
| `cap-plan-microtasks` | Planning turns research explanations into ordered microtasks with constitution refs, research refs, target paths, dependencies, roles, done, and proof. | `docs/functional-graph-ledger-contract.md#ledger-microtask-requirements`, `templates/waves/wave-id/plan.md#sequential-microtasks` | closed |
| `cap-graph-dev-model` | The graph is built from approved microtasks and every node carries constitution, research, plan, dependency, and evidence refs. | `docs/functional-graph-ledger-contract.md#graph-node-requirements`, `skills/app-functional-graph/SKILL.md#graph-node-requirements` | closed |
| `cap-lineage-analysis` | Analysis checks lineage, implementation convergence, and broken-link routing across the ordered flow. | `docs/artifact-contracts.md#waveswave-idanalysismd`, `skills/app-analyze/SKILL.md#rules` | closed |
| `cap-file-reuse-audit` | File-audit mode reviews every plugin file for a named consumer, agreement with workflow order, concise wording, single route, coverage, portability, degradation resistance, next-agent readiness, and no-test-tooling risk. | `skills/app-analyze/SKILL.md#file-audit-mode`, `waves/workflow-instruction-coverage/analysis.md#file-reuse-audit` | closed |
| `cap-packet-contracts` | Versioned packets keep support skills aligned and prevent downstream fields from drifting away from upstream outputs. | `docs/handoff-packet-contracts.md#handoff-packet-contracts`, `docs/artifact-contracts.md#packets` | closed |
| `cap-self-contained-roles` | Role mapping must use a plugin-local role catalog so the plugin stays portable and does not require external role inventory files. | `docs/role-catalog.md#rules`, `skills/subagents-roles/SKILL.md#rules` | closed |
| `cap-self-contained-plugin` | Plugin docs are portable; execution constraints are optional live-session limits and not plugin functional truth. | `README.md#independence-and-script-ownership`, `SPEC.md#script-ownership` | closed |
| `cap-no-test-tooling-loop` | The plugin must not cause recursive workflow testing by asking agents to create validators, harnesses, scripts, cache tools, or plugin-specific validation software just to prove the workflow. | `README.md#independence-and-script-ownership`, `skills/app-analyze/SKILL.md#rules`, `docs/handoff-packet-contracts.md#dispatch-packetv1` | closed |
| `cap-constitution-precision` | Constitution records have type-specific fields, exact sources, and independently changeable scope. Empty sections, placeholders, size padding, and size truncation are forbidden. | `docs/app-user-evidence.md#user-msg-0001`, `docs/artifact-contracts.md#docsapp-constitutionmd` | closed |
| `cap-user-message-evidence` | A session message used as a constitution source is stored as a stable, safe evidence entry with an unchanged minimal continuous excerpt. | `docs/app-user-evidence.md#user-msg-0002`, `docs/artifact-contracts.md#docsapp-user-evidencemd` | closed |

## Known behavior

- Existing plugin skills cover the same named stages, but stale traces previously mixed graph input with plan output and pointed to host-specific role or policy concepts.
- The target behavior is sequential, lineage-first, self-contained, and resistant to recursive test-tool creation.
- `app-analyze` now owns the broad plugin-file audit instead of creating a separate audit tool.
- The previous constitution used eight fixed sections, placeholder rows, and synthetic no-gap and no-decision records; the precise shape keeps only populated record sections.
- Both cited user-message excerpts are active, contain no sensitive text, and support the two new capability records without paraphrasing.

## Sources

- `README.md`: user-facing workflow, artifact list, skill list, independence, and script ownership.
- `SPEC.md`: canonical workflow order, stage contracts, support contracts, and change-management rule.
- `docs/workflow-stage-gates.md`: required reads, writes, forbidden writes, exits, and drift routes.
- `docs/functional-graph-ledger-contract.md`: graph node fields, function fields, ledger fields, statuses, and backlinks.
- `docs/artifact-contracts.md`: required sections for constitution, waves, analysis, and packets.
- `docs/app-user-evidence.md`: unchanged user-message excerpts cited by the constitution precision capabilities.
- `docs/handoff-packet-contracts.md`: versioned packet fields for research, clarification, roles, dispatch, hardening, and analysis.
- `docs/role-catalog.md`: self-contained role names and role-gap rules.
- `templates/`: copy-ready constitution, wave, ledger, and graph shapes.
- Skill instructions: `skills/app-analyze/SKILL.md`, `skills/app-constitution/SKILL.md`, `skills/app-dev/SKILL.md`, `skills/app-functional-graph/SKILL.md`, `skills/app-plan/SKILL.md`, `skills/app-research/SKILL.md`, `skills/app-specify/SKILL.md`, `skills/instruction-hardening/SKILL.md`, `skills/subagents-roles/SKILL.md`, `skills/subagents/SKILL.md`.

## Decisions

- `decision-sequential-order`: Use `constitution -> research -> plan -> graph -> dev -> analyze` as the required main order.
- `decision-graph-after-plan`: Build graph nodes only from approved plan microtasks.
- `decision-plugin-independent`: Do not depend on host-specific instruction files, role inventories, runtime services, hooks, MCP servers, or validation scripts.
- `decision-packet-contracts`: Add versioned packet contracts so support skill outputs and inputs stay aligned.
- `decision-role-catalog`: Replace external role inventory dependence with plugin-local role names.
- `decision-file-audit-owned-by-analyze`: Put broad file-quality audit in `app-analyze`, not in new testing or audit software.
- `decision-no-workflow-test-tooling`: Use targeted reads, grep, JSON parsing, and existing generated evidence only; do not create plugin-local test tools to prove this workflow.
- `decision-remove-stale-role-trace`: Remove obsolete legacy role-skill artifacts and references because they duplicate role mapping and imply external Bears role dependence.
- `decision-exact-packet-fields`: Support skills must use the exact versioned field names from `docs/handoff-packet-contracts.md`.
- `decision-graph-dev-exit`: Complete graph lineage with ledger backlinks routes to `app-dev`; incomplete lineage routes upstream.
- `decision-exact-graph-evidence`: Graph evidence refs must name concrete files or anchors, not directories or wildcard paths.
- `decision-constitution-record-shape`: Use only the record fields owned by `docs/artifact-contracts.md`; omit unpopulated constitution sections and size-based filler.
- `decision-user-evidence-excerpt`: Store the shortest unchanged continuous excerpt that preserves the user's condition and result; append corrections instead of editing committed quotes.
- `decision-inference-boundary`: Research may inspect `inference-*`, but plan, ledger, and graph accept only research-confirmed `cap-*` and `gap-*` IDs.

## Unknowns

- This wave has no unresolved research question.

## Clarifications

- `app-specify` remains a helper for unresolved research questions and is not a main stage gate.
- Execution constraints may appear in a live session, but they constrain execution only and do not replace constitution truth.

## Plan inputs

- Update public workflow docs and stage gates for the strict order and drift routing.
- Update artifact contracts and templates so constitution, research, plan, graph, ledger, packets, and analysis share the same fields.
- Update stage skills so research cannot jump to graph or dev, plan cannot create graph nodes, graph consumes approved microtasks, dev consumes only complete lineage, and analyze reports exact broken links.
- Add packet contracts, exact support-skill packet fields, and a self-contained role catalog.
- Remove obsolete external role-inventory traces.
- Extend `app-analyze` to perform broad file reuse-quality audits without creating testing software.
- Create self-test graph and ledger with complete lineage and concrete evidence refs for all constitution capabilities.
- Update manifests to present the plugin as self-contained and sequential.
- Replace the fixed constitution shape with populated record sections and exact source fields, and add optional user-message evidence only when cited.

## Drift notes

- Functional mismatch routes to `docs/app-constitution.md` first.
- Research mismatch updates or reroutes this wave against constitution refs.
- Plan mismatch maps back to this research explanation and a constitution id.
- Graph mismatch maps back to a plan microtask, this wave, and a constitution id.
- Execution-constraint mismatch is reported separately and must not rewrite functional truth.
- An unverified constitution inference stays in research and cannot be repaired by copying it into a plan or graph.

## Next skill

- `app-plan`
