# Workflow Refactor v5 Source Map

This packet maps the full workflow architecture refactor to current repository sources. It is an implementation source map, not independent evidence and not a terminal semantic result.

## EVIDENCE-CONTRACTS

| Source | Represented meaning |
| --- | --- |
| `contracts/app-workflow-definition.v3.json` | Stage order, ownership modes, edge registry, process transitions, finding routes, and terminal semantics |
| `contracts/delegation-packets.v2.json` | Native L1 lane packet plus L3 dispatch, result, and app-task packet boundaries |
| `contracts/app-functional-map.v4.schema.json` | Semantic entities, relations, seven-dimension mapping, and evidence refs |
| `contracts/app-task-ledger.v3.schema.json` | Repository task ownership, dependency order, implementation refs, path-free retirement provenance, and linked remediation basis |
| `contracts/app-process-event.v3.schema.json` | Exact transitions, task-spec bindings, completed delegation provenance, causality, payload digest, result provenance, review, and analysis payload |
| `contracts/app-stage-handoff.v4.schema.json` | Typed transient stage handoff, exact-snapshot fields, and remediation task refs |
| `contracts/app-semantic-analysis-result.v1.schema.json` | Analysis basis, categorized input-set digests, coverage, findings, completeness, and canonical route |
| `contracts/app-traceability-index.v4.schema.json`; `contracts/app-process-index.v4.schema.json` | Build-bound semantic and process index shapes |

## EVIDENCE-RUNTIME

| Source | Represented meaning |
| --- | --- |
| `scripts/app_graph_store.py` | Manifest, source, journal, Git-object provenance, immutable build-bundle publication, and atomic current-pointer boundary |
| `scripts/app_graph_process.py` | Native record admission, exact task specifications, completed delegation results, dependency completion, exact review ranges, linked-run lineage, and causal boundaries |
| `scripts/app_graph_compiler.py` | Deterministic ledger and journal parity, generic registry cycle checks, and reconciliation into immutable build-bound indexes |
| `scripts/app_graph_handoff.py` | Read-only current-boundary proof, derived handoff identity, payload-digest validation, and exact implemented or audited payload reconstruction |
| `scripts/app_graph_query.py` | Bounded graph reads, opaque cursors, deduplicated impact, dependency, remediates lineage, plan, and workflow-state views |
| `scripts/app_graph_mcp.py` | Seven read-only graph tools, including `handoff_validate`, and manifest-gated maintainer tools |
| `scripts/README.md` | Runtime ownership and protocol boundary guide |

Lane, L3, result, and handoff packets remain typed transient protocol inputs. Completed v3 delegation provenance becomes durable only after it binds one result ref, digest, status, profile, model, checklist, and authority identity; app-analyze stores its analyst completion atomically in the single analysis event, and packet bodies remain transient.

## EVIDENCE-STAGES

| Stage source | Represented meaning |
| --- | --- |
| `skills/app-constitution/SKILL.md`; `skills/app-research/SKILL.md`; `skills/app-specify/SKILL.md` | Constitution, research, and specification goals plus canonical handoffs |
| `skills/app-functional-graph/SKILL.md`; `skills/app-plan/SKILL.md` | Typed semantic mapping, ordinary task-scope establishment, and correction-task provenance |
| `skills/app-dev/SKILL.md`; `skills/app-analyze/SKILL.md` | Repository work orchestration, linked correction runs, and exact-snapshot logical correspondence analysis |
| `skills/app-context-index/SKILL.md`; `skills/app-graph-compile/SKILL.md`; `skills/app-solo-route/SKILL.md` | Context reconciliation, deterministic compilation, and sequential DIRECT routing |
| `skills/subagents/SKILL.md` | L3-only role selection and assignment-bounded dispatch |

## EVIDENCE-ROLES

| Source | Represented meaning |
| --- | --- |
| `role-definitions/workflow-orchestrator.json` | L1 `workflow-orchestrator` native repository-lane coordination without stage or L3 authority |
| `role-definitions/domain-lane-orchestrator.json` | Persistent `repo-orchestrator` repo-L2 ownership of every DELEGATED app stage |
| `role-definitions/capability-catalog.v1.json` | Closed skills, MCP tools, native tools, and request-user-input capability sets |
| `role-definitions/*.json`; `agents/*.toml` | Authoritative role definitions and rendered installed profiles |
| `agents/README.md` | `role_kind` authority, descriptive specialization, profile identity, and lane lifecycle |
| `skills/subagents/SKILL.md`; `contracts/delegation-packets.v2.json`; `contracts/app-process-event.v3.schema.json` | L3 selection, exact profile binding, packet identity, session lifecycle, represented delegation fields, and the atomic app-analyze completion |

L1 opens or continues a persistent repo-L2 through native collaboration with `repo-lane-dispatch.v1`. Only repo-L2 invokes L3, and it does so through `$subagents` with `dispatch-packet.v3`, `result-packet.v2`, and applicable `app-task-dispatch.v2`. The immutable v3 event stores stable ownership and completed-result provenance, not transient packet bodies.

## EVIDENCE-DOCS-GRAPH

| Source | Represented meaning |
| --- | --- |
| `docs/app-constitution.md`; `README.md`; `AGENTS.md` | Human workflow model and repository routing boundary |
| `waves/workflow-refactor-v5/research.md`; `waves/workflow-refactor-v5/spec.md`; `waves/workflow-refactor-v5/plan.md`; `waves/workflow-refactor-v5/analysis.md` | Wave intent, decisions, requirements, dependency order, and pre-binding analysis notes |
| `docs/app-functional-map.v4.json` | Decision, requirement, functionality, dimension, relation, and evidence mappings |
| `docs/app-task-ledger.v3.json`; `docs/app-artifact-catalog.v2.json` | Canonical tasks and exact artifact refs |
| `docs/app-graph-source-manifest.v1.json` | Opted-in structured-source and journal compilation boundary |
| `docs/plugin-effectiveness-metrics-and-agent-audit-methodology.md` | Read-only effectiveness observation methodology |
| `docs/workflow-refactor-v5-assessment.md` | Independent frozen assessment, metric verdict, findings, and six evidence sections |

The structured app-analyze result must reconcile these sources, graph edges, task-result provenance, remediation ledger tasks, independent evidence, and either the implemented run's final clean review or the canonical no-work basis on one exact build.

## EVIDENCE-DELIVERY

| Source | Represented meaning |
| --- | --- |
| `.codex-plugin/plugin.json`; `.agents/plugins/marketplace.json`; `install` | Plugin identity, discovery metadata, and explicit installation entrypoint |
| `.github/runner/README.md`; `.github/workflows/plugin-marketplace-cd.yml` | Machine-owned publication boundary and operator guide |
| `CHANGELOG.md`; `waves/index.md` | Release history and wave navigation |
| `docs/app-artifact-catalog.v2.json`; `docs/app-task-ledger.v3.json` | Exact refactor artifact coverage and bounded task ownership |
| `docs/app-functional-map.v4.json`; `docs/app-graph-source-manifest.v1.json` | Semantic dependency model and opted-in source boundary |

Bind this source map through the exact source-set digest in the final structured analysis input. Keep delivery metadata and transient protocol traffic non-authoritative unless an opted-in structured source or native process record represents them.
