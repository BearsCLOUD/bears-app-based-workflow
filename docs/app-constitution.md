# App Constitution

## Functional summary

- App target: `bears-app-based-workflow`.
- Source-of-truth rule: this file owns plugin functional workflow intent.
- Required order: `app-constitution -> app-research -> app-plan -> app-functional-graph -> app-dev -> app-analyze`.

## Core capabilities

| ID | Capability | Owner | Evidence need | State |
| --- | --- | --- | --- | --- |
| `cap-sequential-workflow` | Keep app workflow strictly sequential from constitution to graph-modeled dev. | Plugin workflow | `SPEC.md#workflow` | accepted |
| `cap-constitution-truth` | Treat constitution as functional source of truth. | `app-constitution` | `skills/app-constitution/SKILL.md` | accepted |
| `cap-research-explains-truth` | Require research waves to explain constitution ids through sources and decisions. | `app-research` | `skills/app-research/SKILL.md` | accepted |
| `cap-plan-microtasks` | Require plan to create ordered microtasks from research and constitution refs. | `app-plan` | `skills/app-plan/SKILL.md` | accepted |
| `cap-graph-dev-model` | Build functional graph after planning as the dev-stage model. | `app-functional-graph` | `skills/app-functional-graph/SKILL.md` | accepted |
| `cap-lineage-analysis` | Analyze exact broken lineage links across constitution, research, plan, graph, and dev. | `app-analyze` | `skills/app-analyze/SKILL.md` | accepted |
| `cap-self-contained-plugin` | Keep plugin artifacts independent from host workspace instruction files and runtime services. | Plugin docs | `README.md#independence-and-script-ownership` | accepted |

## Actors and runtime surfaces

- Codex agent uses plugin skills to create and inspect workflow artifacts.
- Role-matched subagent may receive one bounded sequential dispatch packet.
- External automation may validate or test outside the plugin contract.

## Constraints and evidence

- `constraint-no-env-dependency`: plugin artifacts must not depend on a specific host workspace instruction file, MCP server, hook, or runtime.
- `constraint-no-manual-scripts`: plugin skills must not instruct agents to run validation, test, audit, route, cache, cachebuster, quick-validate, or plugin-validate scripts manually.
- `constraint-sequential-only`: planning and development handoffs are sequential by default.

## Functional gaps

| ID | Gap | Impact | Evidence | Route |
| --- | --- | --- | --- | --- |
| `gap-none-current` | No current functional gap for the self-test wave. | None | `docs/backtests/plugin-self-test.md` | `app-analyze` |

## Open decisions

| ID | Decision | Blocks | Owner |
| --- | --- | --- | --- |
| `decision-none-current` | No open decision for the self-test wave. | Nothing | Plugin workflow |

## Host policy notes

- Host policy may constrain a live session, but it is not plugin functional truth.

## Next skill

- `app-research`
