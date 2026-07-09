# App Constitution

## Functional summary

- App target: `bears-app-based-workflow`.
- Source-of-truth rule: this file owns plugin functional workflow intent.
- Required order: `app-constitution -> app-research -> app-plan -> app-functional-graph -> app-dev -> app-analyze`.
- Support skills are helpers inside the ordered flow, not extra main gates.

## Core capabilities

| ID | Capability | Owner | Evidence need | State |
| --- | --- | --- | --- | --- |
| `cap-sequential-workflow` | Keep the app workflow strictly sequential from constitution truth through graph-modeled development and analysis. | Plugin workflow | `SPEC.md#core-workflow` | accepted |
| `cap-constitution-truth` | Treat constitution as functional source of truth for capabilities, gaps, decisions, constraints, and drift. | `app-constitution` | `skills/app-constitution/SKILL.md` | accepted |
| `cap-research-explains-truth` | Require research waves to explain constitution ids through sources, decisions, unknowns, and wave scope. | `app-research` | `skills/app-research/SKILL.md` | accepted |
| `cap-plan-microtasks` | Require plan to create ordered microtasks from research and constitution refs before graph modeling. | `app-plan` | `skills/app-plan/SKILL.md` | accepted |
| `cap-graph-dev-model` | Build the functional graph after planning as the model for future `app-dev` work. | `app-functional-graph` | `skills/app-functional-graph/SKILL.md` | accepted |
| `cap-lineage-analysis` | Analyze exact broken links across constitution, research, plan, graph, ledger, dev, and closeout. | `app-analyze` | `skills/app-analyze/SKILL.md` | accepted |
| `cap-file-reuse-audit` | Let `app-analyze` audit every plugin file for usefulness, consistency, brevity, unambiguity, coverage, portability, degradation resistance, continuous-development readiness, and no-test-tooling risk. | `app-analyze` | `waves/workflow-instruction-coverage/analysis.md#file-reuse-audit` | accepted |
| `cap-packet-contracts` | Keep versioned handoff packets aligned so downstream skills never require fields missing from upstream packets. | Plugin contracts | `docs/handoff-packet-contracts.md` | accepted |
| `cap-self-contained-roles` | Provide self-contained role names for handoff packets without an external role inventory. | `subagents-roles` | `docs/role-catalog.md` | accepted |
| `cap-self-contained-plugin` | Keep plugin artifacts independent from host workspace instruction files, runtime services, hooks, MCP servers, role inventories, and validation scripts. | Plugin docs | `README.md#independence-and-script-ownership` | accepted |
| `cap-no-test-tooling-loop` | Prevent agents from creating validation software, test harnesses, or workflow-testing scripts just to prove the workflow. | Plugin workflow | `README.md#independence-and-script-ownership` | accepted |

## Actors and runtime surfaces

- Codex agent uses plugin skills to create and inspect workflow artifacts.
- Role-matched subagent may receive one bounded sequential dispatch packet when subagents are available.
- Parent agent may execute the same packet locally when subagents are unavailable.
- External automation may create validation or test evidence outside this plugin contract.

## Constraints and evidence

- `constraint-no-env-dependency`: plugin artifacts must not depend on a specific host workspace instruction file, MCP server, hook, role inventory, or runtime.
- `constraint-no-manual-scripts`: plugin skills must not instruct agents to run validation, test, audit, route, cache, cachebuster, quick-validate, or plugin-validate scripts manually.
- `constraint-no-workflow-test-tooling`: plugin skills must not create scripts, validators, harnesses, or extra software just to test the workflow.
- `constraint-sequential-only`: planning and development handoffs are sequential by default.
- `constraint-complete-lineage`: every graph node used by `app-dev` must carry constitution, research, and plan refs.

## Functional gaps

| ID | Gap | Impact | Evidence | Route |
| --- | --- | --- | --- | --- |
| `gap-none-current` | No current functional gap for the self-test wave. | None | `docs/backtests/plugin-self-test.md` | `app-analyze` |

## Open decisions

| ID | Decision | Blocks | Owner |
| --- | --- | --- | --- |
| `decision-none-current` | No open decision for the self-test wave. | Nothing | Plugin workflow |

## Execution constraints

- Live session instructions may constrain a run, but they are not plugin functional truth.
- When execution constraints drift from plugin behavior, record the constraint separately and preserve constitution truth unless the user changes functional intent.

## Next skill

- `app-research`
