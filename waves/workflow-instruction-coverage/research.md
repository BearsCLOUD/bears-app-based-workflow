# Wave Research: workflow-instruction-coverage

## Wave ID

`workflow-instruction-coverage`

## Scope

- Cover the plugin workflow instructions so a future agent can follow constitution, research, plan, graph modeling, dev handoff, and analysis without relying on host-specific docs.

## Constitution mapping

| Constitution ref | Research explanation | Source refs | Decision state |
| --- | --- | --- | --- |
| `cap-sequential-workflow` | The workflow must be linear. Research confirms graph modeling happens after approved plan microtasks and models dev. | `SPEC.md#workflow`, `docs/workflow-stage-gates.md#rule-summary` | closed |
| `cap-constitution-truth` | Functional drift is resolved against constitution first; this keeps research, plan, and graph aligned. | `docs/workflow-stage-gates.md#drift-routing` | closed |
| `cap-research-explains-truth` | Every wave must show which constitution ids it explains and what sources support each explanation. | `docs/artifact-contracts.md#waveswave-idresearchmd` | closed |
| `cap-plan-microtasks` | Planning turns research explanations into ordered microtasks with constitution and research refs. | `docs/functional-graph-ledger-contract.md#ledger-microtask-requirements` | closed |
| `cap-graph-dev-model` | The graph is built from approved microtasks and must carry constitution, research, and plan lineage. | `docs/functional-graph-ledger-contract.md#graph-node-requirements` | closed |
| `cap-lineage-analysis` | Analysis checks each graph node and reports the exact missing constitution, research, plan, graph, or dev link. | `docs/artifact-contracts.md#waveswave-idanalysismd` | closed |
| `cap-self-contained-plugin` | Plugin docs are portable; host policies are optional live constraints and not plugin functional truth. | `README.md#independence-and-script-ownership` | closed |

## Known behavior

- Existing plugin skills already cover the same named stages, but prior text included obsolete graph-input and non-sequential wording.
- The new target behavior is sequential and lineage-first.

## Sources

- `SPEC.md`: canonical workflow order and stage contracts.
- `docs/workflow-stage-gates.md`: stage reads, writes, forbidden writes, exits, and drift routes.
- `docs/functional-graph-ledger-contract.md`: lineage fields and ledger statuses.
- `docs/artifact-contracts.md`: required artifact sections.
- `templates/`: copy-ready artifact shapes.

## Decisions

- `decision-sequential-order`: Use `constitution -> research -> plan -> graph` as the required modeling order.
- `decision-graph-after-plan`: Build graph nodes only from approved plan microtasks.
- `decision-plugin-independent`: Do not depend on host-specific instruction files or runtime services.

## Unknowns

- None for this self-test wave.

## Clarifications

- `app-specify` remains a helper for unresolved research questions and is not a main stage gate.

## Plan inputs

- Update public workflow docs.
- Update stage skills.
- Create artifact contracts and templates.
- Create self-test graph and ledger with complete lineage.
- Update manifests to remove non-sequential positioning.

## Drift notes

- Any functional mismatch found later must route to `docs/app-constitution.md` first.
- Host-policy mismatch must be reported separately and must not rewrite functional truth.

## Next skill

- `app-plan`
