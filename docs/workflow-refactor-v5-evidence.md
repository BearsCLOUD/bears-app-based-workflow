# Workflow Refactor v5 Evidence

This packet maps the full workflow architecture refactor to current repository sources. It records correspondence inputs and does not itself assert a terminal semantic result.

## EVIDENCE-CONTRACTS

| Source | Represented meaning |
| --- | --- |
| `contracts/app-workflow-definition.v3.json` | Stage order, ownership modes, status routes, finding routes, and terminal semantics |
| `contracts/delegation-packets.v2.json` | Native L1 lane packet plus L3 dispatch, result, and app-task packet boundaries |
| `contracts/app-functional-map.v4.schema.json` | Semantic entities, relations, seven-dimension mapping, and evidence refs |
| `contracts/app-task-ledger.v3.schema.json` | Repository task ownership, dependency order, and implementation refs |
| `contracts/app-process-event.v3.schema.json` | Stage-owner journal records, actor scope, causality, and analysis payload |
| `contracts/app-stage-handoff.v4.schema.json` | Typed transient stage handoff and exact-snapshot fields |
| `contracts/app-semantic-analysis-result.v1.schema.json` | Analysis basis, coverage, findings, completeness, and canonical route |
| `contracts/app-traceability-index.v4.schema.json`; `contracts/app-process-index.v4.schema.json` | Build-bound semantic and process index shapes |

## EVIDENCE-RUNTIME

| Source | Represented meaning |
| --- | --- |
| `scripts/app_graph_store.py` | Manifest, pointer, receipt, source, and journal storage boundary |
| `scripts/app_graph_process.py` | Native process-record admission and lifecycle checks |
| `scripts/app_graph_compiler.py` | Deterministic source and journal reconciliation into build-bound indexes |
| `scripts/app_graph_query.py` | Bounded graph reads, opaque cursors, impact, dependency, plan, and workflow-state views |
| `scripts/app_graph_mcp.py` | Read-only graph tools and manifest-gated maintainer tools |
| `scripts/README.md` | Runtime ownership and protocol boundary guide |

Lane, L3, result, and handoff packets remain typed transient protocol inputs. Only the L3 identity fields represented by an immutable v3 event `delegation_record` are durable graph evidence; the full packet bodies are not implied.

## EVIDENCE-STAGES

| Stage source | Represented meaning |
| --- | --- |
| `skills/app-constitution/SKILL.md`; `skills/app-research/SKILL.md`; `skills/app-specify/SKILL.md` | Constitution, research, and specification goals plus canonical handoffs |
| `skills/app-functional-graph/SKILL.md`; `skills/app-plan/SKILL.md` | Typed semantic mapping and graph-linked task planning |
| `skills/app-dev/SKILL.md`; `skills/app-analyze/SKILL.md` | Repository work orchestration and exact-snapshot logical correspondence analysis |
| `skills/app-context-index/SKILL.md`; `skills/app-graph-compile/SKILL.md`; `skills/app-solo-route/SKILL.md` | Context reconciliation, deterministic compilation, and sequential DIRECT routing |
| `skills/subagents/SKILL.md` | L3-only role selection and assignment-bounded dispatch |

## EVIDENCE-ROLES

| Source | Represented meaning |
| --- | --- |
| `role-definitions/workflow-orchestrator.json` | L1 native repository-lane coordination without stage or L3 authority |
| `role-definitions/domain-lane-orchestrator.json` | Persistent repo-L2 ownership of every DELEGATED app stage |
| `role-definitions/capability-catalog.v1.json` | Closed skills, MCP tools, native tools, and request-user-input capability sets |
| `role-definitions/*.json`; `agents/*.toml` | Authoritative role definitions and rendered installed profiles |
| `agents/README.md` | `role_kind` authority, descriptive specialization, profile identity, and lane lifecycle |
| `skills/subagents/SKILL.md`; `contracts/delegation-packets.v2.json`; `contracts/app-process-event.v3.schema.json` | L3 selection, exact profile binding, packet identity, session lifecycle, and represented `delegation_record` fields |

L1 opens or continues a persistent repo-L2 through native collaboration with `repo-lane-dispatch.v1`. Only repo-L2 invokes L3, and it does so through `$subagents` with `dispatch-packet.v3`, `result-packet.v2`, and applicable `app-task-dispatch.v2`. The immutable v3 event stores only the represented delegation identity, not the transient packet bodies.

## EVIDENCE-DOCS-GRAPH

| Source | Represented meaning |
| --- | --- |
| `docs/app-constitution.md`; `README.md`; `AGENTS.md` | Human workflow model and repository routing boundary |
| `waves/workflow-refactor-v5/research.md`; `waves/workflow-refactor-v5/spec.md`; `waves/workflow-refactor-v5/plan.md`; `waves/workflow-refactor-v5/analysis.md` | Wave intent, decisions, requirements, dependency order, and pre-binding analysis notes |
| `docs/app-functional-map.v4.json` | Decision, requirement, functionality, dimension, relation, and evidence mappings |
| `docs/app-task-ledger.v3.json`; `docs/app-artifact-catalog.v2.json` | Canonical tasks and exact artifact refs |
| `docs/app-graph-source-manifest.v1.json` | Opted-in structured-source and journal compilation boundary |
| `docs/plugin-effectiveness-metrics-and-agent-audit-methodology.md` | Read-only effectiveness observation methodology |

The structured app-analyze result must reconcile these sources on one exact build before a terminal status is selected.

## EVIDENCE-DELIVERY

| Source or commit | Represented meaning |
| --- | --- |
| `.codex-plugin/plugin.json`; `.agents/plugins/marketplace.json`; `install` | Plugin identity, discovery metadata, and explicit installation entrypoint |
| `.github/runner/README.md`; `.github/workflows/plugin-marketplace-cd.yml` | Machine-owned publication boundary and operator guide |
| `CHANGELOG.md`; `waves/index.md` | Release history and wave navigation |
| `8b817cab02280b173f09039cfdd58006768a71ea` | Earlier documentation semantics slice |
| `b94dcdf899653e965413a0cc8c3b1830fd7641e3` | Earlier role authority and capability slice |
| `9bcc11d4ac4d80dde30d4eeb7d7c193cad28f781` | Earlier stage ownership and semantic-analysis slice |

Bind this packet through an exact source ref in the final structured analysis input set. Keep delivery metadata and transient protocol traffic non-authoritative unless an opted-in structured source or native process record represents them.
